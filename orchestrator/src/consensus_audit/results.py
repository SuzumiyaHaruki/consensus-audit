from __future__ import annotations

import csv
import io
import json
from pathlib import Path
from typing import Any


class ResultCollectionError(ValueError):
    """Raised when run artifacts cannot be collected into a result table."""


RESULT_FIELDS = [
    "run_directory",
    "target_id",
    "model",
    "arm",
    "run_id",
    "candidate_status",
    "format_valid",
    "provenance_valid",
    "mechanism_score",
    "evidence_score",
    "property_linkage_score",
    "P_score",
    "A_score",
    "V_score",
    "O_score",
    "uncertainty_discipline_score",
    "duplicate_group",
    "input_tokens",
    "output_tokens",
    "total_tokens",
    "cache_hit_tokens",
    "cache_miss_tokens",
    "turns",
    "tool_calls",
    "files_read",
    "source_lines_read",
    "duration_seconds",
    "notes",
]


def _load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResultCollectionError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ResultCollectionError(f"expected JSON object in {path}")
    return value


def _usage_value(usage: dict[str, Any], *names: str) -> int | str:
    for name in names:
        value = usage.get(name)
        if isinstance(value, int) and not isinstance(value, bool):
            return value
    return ""


def _source_cost(evidence: dict[str, Any]) -> dict[str, Any]:
    source_cost = evidence.get("source_cost")
    if isinstance(source_cost, dict):
        return source_cost
    files = evidence.get("files")
    read_entries = files.get("read") if isinstance(files, dict) else None
    if not isinstance(read_entries, list):
        return {}
    lines = 0
    for entry in read_entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("ranges"), list):
            continue
        for item in entry["ranges"]:
            if not isinstance(item, dict):
                continue
            start, end = item.get("start"), item.get("end")
            if isinstance(start, int) and isinstance(end, int) and end >= start:
                lines += end - start + 1
    return {
        "files_read": len(read_entries),
        "unique_source_lines_read": lines,
    }


def collect_result_rows(run_root: Path) -> list[dict[str, Any]]:
    root = run_root.resolve()
    if not root.is_dir():
        raise ResultCollectionError(f"run root is not a directory: {root}")
    rows: list[dict[str, Any]] = []
    for summary_path in sorted(root.rglob("summary.json")):
        run_directory = summary_path.parent
        request_path = run_directory / "request.json"
        evidence_path = run_directory / "evidence-manifest.json"
        if not request_path.is_file() or not evidence_path.is_file():
            continue
        summary = _load_object(summary_path)
        request = _load_object(request_path)
        evidence = _load_object(evidence_path)
        usage = summary.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        source_cost = _source_cost(evidence)
        model = request.get("model")
        if not isinstance(model, dict):
            model = {}
        audit_mode = str(request.get("audit_mode") or "")
        property_id = request.get("property_id")
        episode = request.get("baseline_episode")
        if audit_mode == "property-directed" or property_id is not None:
            arm = "guided"
        elif (
            audit_mode in {"matched-no-property", "unguided-baseline"}
            or episode is not None
        ):
            arm = "baseline"
        else:
            arm = audit_mode or "unknown"
        if property_id is not None:
            run_id = property_id
        elif isinstance(episode, int):
            run_id = f"baseline-{episode:02d}"
        else:
            run_id = ""
        target_root = Path(str(request.get("target_root") or ""))
        rows.append(
            {
                "run_directory": run_directory.relative_to(root).as_posix(),
                "target_id": target_root.name,
                "model": model.get("model", ""),
                "arm": arm,
                "run_id": run_id,
                "candidate_status": summary.get("candidate_status", ""),
                "format_valid": summary.get("candidate_format_valid", ""),
                "provenance_valid": summary.get("candidate_provenance_valid", ""),
                "mechanism_score": "",
                "evidence_score": "",
                "property_linkage_score": "",
                "P_score": "",
                "A_score": "",
                "V_score": "",
                "O_score": "",
                "uncertainty_discipline_score": "",
                "duplicate_group": "",
                "input_tokens": _usage_value(usage, "prompt_tokens", "input_tokens"),
                "output_tokens": _usage_value(
                    usage, "completion_tokens", "output_tokens"
                ),
                "total_tokens": _usage_value(usage, "total_tokens"),
                "cache_hit_tokens": _usage_value(
                    usage, "prompt_cache_hit_tokens", "cache_hit_tokens"
                ),
                "cache_miss_tokens": _usage_value(
                    usage, "prompt_cache_miss_tokens", "cache_miss_tokens"
                ),
                "turns": summary.get("turns", ""),
                "tool_calls": summary.get("tool_calls", ""),
                "files_read": source_cost.get("files_read", ""),
                "source_lines_read": source_cost.get(
                    "unique_source_lines_read", ""
                ),
                "duration_seconds": summary.get("duration_seconds", ""),
                "notes": "",
            }
        )
    return rows


def render_result_csv(rows: list[dict[str, Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=RESULT_FIELDS, lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue()


def write_result_csv(run_root: Path, output: Path | None = None) -> str:
    rendered = render_result_csv(collect_result_rows(run_root))
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
    return rendered
