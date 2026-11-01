import pytest

from src.artifact.validator import MalformedOutputError
from src.orchestrator.retry import MaxRetriesExceeded, with_retry


@pytest.fixture(autouse=True)
def no_real_sleep(monkeypatch):
    """Every retry path in with_retry sleeps — patch it out so the whole
    suite runs instantly and doesn't depend on real wall-clock time."""
    sleeps = []
    monkeypatch.setattr("src.orchestrator.retry.time.sleep", lambda s: sleeps.append(s))
    return sleeps


def test_succeeds_first_try_records_zero_retries():
    calls = []

    @with_retry(max_retries=3)
    def fn():
        calls.append(1)
        return "ok"

    assert fn() == "ok"
    assert fn.retries_used == 0
    assert len(calls) == 1


def test_retries_recoverable_error_then_succeeds(no_real_sleep):
    attempts = {"n": 0}

    @with_retry(max_retries=3)
    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise MalformedOutputError("bad json")
        return "ok"

    assert fn() == "ok"
    assert fn.retries_used == 2
    assert attempts["n"] == 3
    assert len(no_real_sleep) == 2  # one backoff sleep per failed attempt


def test_timeout_error_is_recoverable(no_real_sleep):
    attempts = {"n": 0}

    @with_retry(max_retries=2)
    def fn():
        attempts["n"] += 1
        if attempts["n"] < 2:
            raise TimeoutError("timed out")
        return "ok"

    assert fn() == "ok"
    assert fn.retries_used == 1


def test_exhausts_retries_raises_max_retries_exceeded(no_real_sleep):
    @with_retry(max_retries=2)
    def fn():
        raise MalformedOutputError("always bad")

    with pytest.raises(MaxRetriesExceeded) as excinfo:
        fn()
    assert fn.retries_used == 2  # 3 fn() calls total: 1 initial + 2 retries
    assert "Exhausted 2 retries" in str(excinfo.value)
    assert isinstance(excinfo.value.__cause__, MalformedOutputError)


def test_non_recoverable_exception_propagates_immediately(no_real_sleep):
    calls = {"n": 0}

    @with_retry(max_retries=3)
    def fn():
        calls["n"] += 1
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        fn()
    assert calls["n"] == 1  # no retry attempted
    assert len(no_real_sleep) == 0


def test_rate_limit_429_sleeps_and_does_not_consume_retry_budget(no_real_sleep):
    attempts = {"n": 0}

    @with_retry(max_retries=1)
    def fn():
        attempts["n"] += 1
        if attempts["n"] <= 2:
            raise RuntimeError("429 RESOURCE_EXHAUSTED: quota hit")
        return "ok"

    assert fn() == "ok"
    assert fn.retries_used == 0  # rate-limit backoffs don't count as retries
    assert attempts["n"] == 3
    assert no_real_sleep == [60, 60]  # no "retry in Xs" hint -> default 60s


def test_rate_limit_parses_retry_in_seconds_hint(no_real_sleep):
    attempts = {"n": 0}

    @with_retry(max_retries=1)
    def fn():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("429 Too Many Requests, please retry in 4.5s")
        return "ok"

    assert fn() == "ok"
    assert no_real_sleep == [5.5]  # parsed 4.5 + 1


def test_transient_503_sleeps_30s_and_does_not_consume_retry_budget(no_real_sleep):
    attempts = {"n": 0}

    @with_retry(max_retries=1)
    def fn():
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise RuntimeError("503 Service Unavailable")
        return "ok"

    assert fn() == "ok"
    assert fn.retries_used == 0
    assert no_real_sleep == [30]
