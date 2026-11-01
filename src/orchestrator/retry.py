import functools
import logging
import random
import re
import time
from typing import Callable, TypeVar

from ..artifact.validator import MalformedOutputError

logger = logging.getLogger(__name__)
T = TypeVar("T")


def _backoff_delay(attempt: int, base: float = 2.0, cap: float = 60.0) -> float:
    """
    Exponential backoff with full jitter.
    Formula: min(cap, base ** attempt) * random(0, 1)
    attempt=0 → up to 1s, attempt=1 → up to 2s, attempt=2 → up to 4s, ...
    """
    return random.uniform(0, min(cap, base ** attempt))


class MaxRetriesExceeded(Exception):
    """Raised when all retry attempts are exhausted."""
    pass


# Exceptions that warrant a retry (recoverable LLM failures)
RECOVERABLE = (MalformedOutputError, TimeoutError)


def with_retry(max_retries: int) -> Callable:
    """
    Decorator that retries a function up to max_retries times
    when a recoverable exception is raised.

    Additionally intercepts 429 RESOURCE_EXHAUSTED errors, sleeping and
    retrying without consuming the standard max_retries limit.
    """
    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last_error: Exception | None = None
            attempt = 0

            while attempt <= max_retries:
                try:
                    result = fn(*args, **kwargs)
                    # attempt == how many RECOVERABLE retries happened before
                    # this success (429/503 backoffs don't count, by design).
                    wrapper.retries_used = attempt
                    return result
                except Exception as exc:
                    exc_str = str(exc)
                    
                    # Intercept rate limit exceptions from any provider
                    if "429" in exc_str or "RESOURCE_EXHAUSTED" in exc_str or "Too Many Requests" in exc_str:
                        # Attempt to parse "retry in X.Xs"
                        match = re.search(r"retry in (\d+\.?\d*)s", exc_str, re.IGNORECASE)
                        sleep_time = float(match.group(1)) + 1 if match else 60

                        logger.warning(
                            "[Rate Limit] Hit 429 quota/limit. Sleeping for %.1f seconds...",
                            sleep_time
                        )
                        time.sleep(sleep_time)
                        last_error = exc
                        continue  # Do not increment attempt for rate limits

                    # Intercept transient 503 Service Unavailable from any provider
                    if "503" in exc_str or "UNAVAILABLE" in exc_str or "Service Unavailable" in exc_str:
                        logger.warning(
                            "[Transient Error] Hit 503 unavailable. Sleeping 30s before retrying..."
                        )
                        time.sleep(30)
                        last_error = exc
                        continue  # Do not increment attempt for transient errors

                        
                    if isinstance(exc, RECOVERABLE):
                        last_error = exc
                        if attempt >= max_retries:
                            # Exhausted — stop here so retries_used reports
                            # exactly max_retries, not max_retries + 1.
                            break
                        delay = _backoff_delay(attempt)
                        logger.warning(
                            "[retry %d/%d] %s: %s — backing off %.1fs",
                            attempt + 1,
                            max_retries,
                            type(exc).__name__,
                            str(exc)[:120],
                            delay,
                        )
                        time.sleep(delay)
                        attempt += 1
                    else:
                        # Propagate unknown exceptions immediately
                        raise
                        
            wrapper.retries_used = attempt
            raise MaxRetriesExceeded(
                f"Exhausted {max_retries} retries. "
                f"Last error ({type(last_error).__name__}): {last_error}"
            ) from last_error

        wrapper.retries_used = 0
        return wrapper
    return decorator
