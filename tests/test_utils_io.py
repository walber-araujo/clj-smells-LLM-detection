import json
from pathlib import Path

from src.artifact.schema import AgentLLMMetrics, AgentRetrievalMetrics, AgentsMetrics, RunArtifact
from src.utils.io import get_output_paths, write_result_and_trace, write_summary_json


def _metrics(**overrides):
    base = dict(model="m", prompt_tokens=1, completion_tokens=1, total_tokens=2, latency_ms=1.0)
    base.update(overrides)
    return AgentLLMMetrics(**base)


def _artifact(file="x.clj"):
    return RunArtifact(
        file=file,
        agents=AgentsMetrics(
            detection=_metrics(), retrieval=AgentRetrievalMetrics(vector_db="mock", calls=1, latency_ms=1.0),
            critic=_metrics(),
        ),
        total_latency_ms=10.0, retries=0, candidate_smells=[], verdicts=[],
    )


def test_get_output_paths_single_file_mode(tmp_path):
    input_path = tmp_path / "src" / "core.clj"
    project_out_dir = tmp_path / "out" / "src"

    out_json, out_md, rel = get_output_paths(input_path, input_path, is_dir=False, project_out_dir=project_out_dir)

    assert rel == Path("core.clj")
    assert out_json == project_out_dir / "core.clj_result.json"
    assert out_md == project_out_dir / "core.clj_trace.md"


def test_get_output_paths_dir_mode_preserves_relative_subdirs(tmp_path):
    input_dir = tmp_path / "project"
    clj_file = input_dir / "sub" / "core.clj"
    project_out_dir = tmp_path / "out" / "project"

    out_json, out_md, rel = get_output_paths(clj_file, input_dir, is_dir=True, project_out_dir=project_out_dir)

    assert rel == Path("sub/core.clj")
    assert out_json == project_out_dir / "sub" / "core.clj_result.json"


def test_get_output_paths_falls_back_to_bare_name_when_not_relative(tmp_path):
    clj_file = tmp_path / "elsewhere" / "core.clj"
    input_dir = tmp_path / "project"
    project_out_dir = tmp_path / "out"

    out_json, _, rel = get_output_paths(clj_file, input_dir, is_dir=True, project_out_dir=project_out_dir)

    assert rel == Path("core.clj")
    assert out_json == project_out_dir / "core.clj_result.json"


def test_write_result_and_trace_creates_json_and_markdown(tmp_path):
    clj_file = tmp_path / "core.clj"
    clj_file.write_text("(defn f [] 1)", encoding="utf-8")
    project_out_dir = tmp_path / "out"
    artifact = _artifact()
    trace = {
        "detection": {"system_prompt": "sys-d", "user_prompt": "user-d", "raw_response": "{}"},
        "critic": {"system_prompt": "sys-c", "user_prompt": "user-c", "raw_response": "{}"},
    }

    out_json_path, rel_path = write_result_and_trace(
        clj_file=clj_file, input_path=clj_file, is_dir=False, project_out_dir=project_out_dir,
        artifact=artifact, trace=trace,
    )

    assert out_json_path.exists()
    saved = json.loads(out_json_path.read_text(encoding="utf-8"))
    assert saved["file"] == "x.clj"

    md_path = project_out_dir / "core.clj_trace.md"
    md_text = md_path.read_text(encoding="utf-8")
    assert "sys-d" in md_text
    assert "sys-c" in md_text
    assert "Tool-Calling Transcript" not in md_text  # no tool_transcript key in trace


def test_write_result_and_trace_includes_tool_transcript_when_present(tmp_path):
    clj_file = tmp_path / "core.clj"
    project_out_dir = tmp_path / "out"
    trace = {
        "detection": {"system_prompt": "s", "user_prompt": "u", "raw_response": "{}"},
        "critic": {"system_prompt": "s", "user_prompt": "u", "raw_response": "{}", "tool_transcript": "AI called tool: x"},
    }
    write_result_and_trace(
        clj_file=clj_file, input_path=clj_file, is_dir=False, project_out_dir=project_out_dir,
        artifact=_artifact(), trace=trace,
    )
    md_text = (project_out_dir / "core.clj_trace.md").read_text(encoding="utf-8")
    assert "Tool-Calling Transcript (agentic mode)" in md_text
    assert "AI called tool: x" in md_text


def test_write_summary_json_aggregates_smell_counts_by_file(tmp_path):
    project_out_dir = tmp_path / "out"
    project_out_dir.mkdir(parents=True)
    all_smells = [
        {"smell_id": "a", "file": "f1.clj", "element_name": "x"},
        {"smell_id": "a", "file": "f1.clj", "element_name": "y"},
        {"smell_id": "b", "file": "f2.clj", "element_name": "z"},
    ]

    path = write_summary_json(
        project_name="proj", project_out_dir=project_out_dir, total_time_ms=100.0,
        total_prompt_tokens=10, total_completion_tokens=5,
        processed_files=["f2.clj", "f1.clj"], all_smells=all_smells,
    )

    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["smell_summary"] == {"a": 2, "b": 1}
    assert data["smells_by_file"] == {"f1.clj": {"a": 2}, "f2.clj": {"b": 1}}
    assert data["processed_files"] == ["f1.clj", "f2.clj"]  # sorted
    assert data["tokens"]["total"] == 15
    assert data["cost"] is None


def test_write_summary_json_carries_cache_and_cost_fields(tmp_path):
    project_out_dir = tmp_path / "out"
    project_out_dir.mkdir(parents=True)

    path = write_summary_json(
        project_name="proj", project_out_dir=project_out_dir, total_time_ms=1.0,
        total_prompt_tokens=1, total_completion_tokens=1,
        processed_files=[], all_smells=[],
        total_cache_read_tokens=42, total_cache_write_tokens=7, total_cost=0.5,
    )
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["tokens"]["cache_read"] == 42
    assert data["tokens"]["cache_write"] == 7
    assert data["cost"] == 0.5
