import json
import datetime
from pathlib import Path

def get_output_paths(clj_file: Path, input_path: Path, is_dir: bool, project_out_dir: Path) -> tuple[Path, Path, Path]:
    try:
        rel_path = clj_file.relative_to(input_path if is_dir else input_path.parent)
    except ValueError:
        rel_path = Path(clj_file.name)

    out_base = project_out_dir / rel_path.parent
    out_json_path = out_base / (clj_file.name + "_result.json")
    out_md_path = out_base / (clj_file.name + "_trace.md")
    return out_json_path, out_md_path, rel_path

def write_result_and_trace(clj_file: Path, input_path: Path, is_dir: bool, project_out_dir: Path, artifact, trace: dict) -> tuple[Path, Path]:
    out_json_path, out_md_path, rel_path = get_output_paths(clj_file, input_path, is_dir, project_out_dir)
    out_json_path.parent.mkdir(parents=True, exist_ok=True)


    out_json_path.write_text(
        artifact.model_dump_json(indent=2),
        encoding="utf-8",
    )

    md_content = f"# Trace for {clj_file.name}\n\n"
    
    md_content += "## Detection Agent\n\n"
    md_content += f"### System Prompt\n```text\n{trace['detection']['system_prompt']}\n```\n\n"
    md_content += f"### User Prompt\n```text\n{trace['detection']['user_prompt']}\n```\n\n"
    md_content += f"### Raw Response\n```json\n{trace['detection']['raw_response']}\n```\n\n"

    md_content += "---\n\n## Critic Agent\n\n"
    md_content += f"### System Prompt\n```text\n{trace['critic']['system_prompt']}\n```\n\n"
    md_content += f"### User Prompt\n```text\n{trace['critic']['user_prompt']}\n```\n\n"
    if trace['critic'].get('tool_transcript'):
        md_content += f"### Tool-Calling Transcript (agentic mode)\n```text\n{trace['critic']['tool_transcript']}\n```\n\n"
    md_content += f"### Raw Response\n```json\n{trace['critic']['raw_response']}\n```\n\n"

    out_md_path.write_text(md_content, encoding="utf-8")
    
    return out_json_path, rel_path

def write_summary_json(project_name: str, project_out_dir: Path, total_time_ms: float,
                       total_prompt_tokens: int, total_completion_tokens: int,
                       processed_files: list[str], all_smells: list[dict],
                       total_cache_read_tokens: int = 0, total_cache_write_tokens: int = 0,
                       total_cost: float | None = None) -> Path:
    smell_counts = {}
    file_smell_counts = {}
    for s in all_smells:
        sid = s["smell_id"]
        fname = s["file"]
        smell_counts[sid] = smell_counts.get(sid, 0) + 1
        
        if fname not in file_smell_counts:
            file_smell_counts[fname] = {}
        file_smell_counts[fname][sid] = file_smell_counts[fname].get(sid, 0) + 1
        
    total_tokens = total_prompt_tokens + total_completion_tokens
    
    summary_data = {
        "project": project_name,
        "total_time_ms": total_time_ms,
        "tokens": {
            "prompt": total_prompt_tokens,
            "completion": total_completion_tokens,
            "total": total_tokens,
            # D17: sum of AgentLLMMetrics.cache_read_tokens/cache_write_tokens
            # across detection+critic, every file. 0/0 for any run that
            # didn't go through provider(s) this project reads cache usage
            # from — not proof caching didn't happen, just unmeasured here.
            "cache_read": total_cache_read_tokens,
            "cache_write": total_cache_write_tokens,
        },
        # D23: OpenRouter's own reported `usage.cost`, summed across every
        # call that reported one. `null` — not 0 — when no call in this run
        # reported a cost (e.g. no OpenRouter calls were made), so an
        # unmeasured run isn't shown as a free one.
        "cost": total_cost,
        "processed_files": sorted(processed_files),
        "smell_summary": smell_counts,
        "smells_by_file": file_smell_counts,
        "smells": all_smells
    }
    
    timestamp_str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    summary_data["timestamp"] = timestamp_str
    
    summary_path = project_out_dir / f"summary_{timestamp_str}.json"
    summary_path.write_text(json.dumps(summary_data, indent=2), encoding="utf-8")
    
    return summary_path
