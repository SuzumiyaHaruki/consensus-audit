from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .artifacts import utc_now, write_json


class EvidenceError(ValueError):
    """Raised when a run's factual tool evidence cannot be reconstructed."""


def _load_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise EvidenceError(f"cannot read JSON object from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise EvidenceError(f"expected a JSON object in {path}")
    return data


def _load_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EvidenceError(f"cannot read event log {path}: {exc}") from exc
    for line_number, line in enumerate(lines, start=1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            raise EvidenceError(
                f"invalid JSON in {path} line {line_number}: {exc}"
            ) from exc
        if isinstance(event, dict):
            events.append(event)
    return events


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if not isinstance(value, str):
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _merge_ranges(ranges: list[tuple[int, int]]) -> list[dict[str, int]]:
    if not ranges:
        return []
    merged: list[list[int]] = []
    for start, end in sorted(ranges):
        if end < start:
            continue
        if not merged or start > merged[-1][1] + 1:
            merged.append([start, end])
        else:
            merged[-1][1] = max(merged[-1][1], end)
    return [{"start": start, "end": end} for start, end in merged]


def build_evidence_manifest(run_directory: Path) -> dict[str, Any]:
    run_directory = run_directory.resolve()
    request = _load_json(run_directory / "request.json")
    events = _load_events(run_directory / "events.jsonl")
    tool_events = [event for event in events if event.get("event_type") == "tool_result"]

    tool_counts: Counter[str] = Counter()
    successful = 0
    failed = 0
    read_ranges: dict[str, list[tuple[int, int]]] = defaultdict(list)
    read_calls: Counter[str] = Counter()
    search_lines: dict[str, set[int]] = defaultdict(set)
    search_calls_by_file: dict[str, set[tuple[int, str]]] = defaultdict(set)
    searches: list[dict[str, Any]] = []
    list_operations: list[dict[str, Any]] = []
    tests: list[dict[str, Any]] = []
    errors: list[dict[str, Any]] = []
    shared_evidence: dict[str, int] = {"new": 0, "reused": 0}
    shared_evidence_ids: list[str] = []

    match_pattern = re.compile(r"^(.*?):(\d+):(.*)$")
    for event in tool_events:
        turn = int(event.get("turn") or 0)
        tool = str(event.get("tool") or "")
        tool_counts[tool] += 1
        arguments = _json_object(event.get("arguments"))
        envelope = _json_object(event.get("result"))
        shared = envelope.get("shared_evidence")
        if isinstance(shared, dict):
            status = str(shared.get("status") or "")
            if status in shared_evidence:
                shared_evidence[status] += 1
            evidence_id = shared.get("id")
            if isinstance(evidence_id, str) and evidence_id not in shared_evidence_ids:
                shared_evidence_ids.append(evidence_id)
        ok = envelope.get("ok") is True
        if not ok:
            failed += 1
            errors.append(
                {
                    "turn": turn,
                    "tool": tool,
                    "arguments": arguments,
                    "error": str(envelope.get("error") or "unknown tool error"),
                }
            )
            continue

        successful += 1
        result = envelope.get("result")
        if not isinstance(result, dict):
            result = {}

        if tool == "read_file":
            path = str(result.get("path") or arguments.get("path") or "")
            start = result.get("start_line")
            end = result.get("end_line")
            if path and isinstance(start, int) and isinstance(end, int):
                read_ranges[path].append((start, end))
                read_calls[path] += 1
        elif tool == "search_code":
            pattern = str(arguments.get("pattern") or "")
            search_entry = {
                "turn": turn,
                "pattern": pattern,
                "path": str(arguments.get("path") or "."),
                "glob": str(arguments.get("glob") or "*.go"),
                "fixed_strings": bool(arguments.get("fixed_strings", False)),
                "engine": result.get("engine"),
                "matches_returned": result.get("match_count_returned", 0),
                "truncated": bool(result.get("truncated", False)),
            }
            searches.append(search_entry)
            matches = result.get("matches")
            if isinstance(matches, list):
                for raw_match in matches:
                    if not isinstance(raw_match, str):
                        continue
                    match = match_pattern.match(raw_match)
                    if not match:
                        continue
                    path, line_text = match.group(1), match.group(2)
                    search_lines[path].add(int(line_text))
                    search_calls_by_file[path].add((turn, pattern))
        elif tool == "list_files":
            files = result.get("files")
            list_operations.append(
                {
                    "turn": turn,
                    "path": str(arguments.get("path") or "."),
                    "max_depth": arguments.get("max_depth"),
                    "files_returned": len(files) if isinstance(files, list) else 0,
                    "truncated": bool(result.get("truncated", False)),
                }
            )
        elif tool == "run_go_test":
            tests.append(
                {
                    "turn": turn,
                    "package": str(arguments.get("package") or "./..."),
                    "test_regex": str(arguments.get("test_regex") or ""),
                    "timeout_seconds": arguments.get("timeout_seconds"),
                    "exit_code": result.get("exit_code"),
                }
            )

    files_read = [
        {
            "path": path,
            "read_calls": read_calls[path],
            "ranges": _merge_ranges(ranges),
        }
        for path, ranges in sorted(read_ranges.items())
    ]
    files_matched = [
        {
            "path": path,
            "search_calls": len(search_calls_by_file[path]),
            "matched_line_numbers": sorted(lines),
            "also_read": path in read_ranges,
        }
        for path, lines in sorted(search_lines.items())
    ]
    unique_source_lines_read = sum(
        item["end"] - item["start"] + 1
        for file_entry in files_read
        for item in file_entry["ranges"]
    )

    return {
        "schema_version": "evidence-manifest/v1",
        "generated_at": utc_now(),
        "source_event_log": "events.jsonl",
        "audit_mode": request.get("audit_mode"),
        "target_root": request.get("target_root"),
        "property_id": request.get("property_id"),
        "baseline_episode": request.get("baseline_episode"),
        "tool_calls": {
            "total": len(tool_events),
            "successful": successful,
            "failed": failed,
            "by_tool": dict(sorted(tool_counts.items())),
        },
        "shared_evidence": {
            "new": shared_evidence["new"],
            "reused": shared_evidence["reused"],
            "ids": shared_evidence_ids,
        },
        "files": {
            "read": files_read,
            "matched_by_search": files_matched,
            "search_only": sorted(path for path in search_lines if path not in read_ranges),
        },
        "source_cost": {
            "files_read": len(files_read),
            "unique_source_lines_read": unique_source_lines_read,
            "search_calls": len(searches),
        },
        "searches": searches,
        "list_operations": list_operations,
        "tests": tests,
        "tool_errors": errors,
    }


def write_evidence_manifest(run_directory: Path) -> Path:
    destination = run_directory.resolve() / "evidence-manifest.json"
    write_json(destination, build_evidence_manifest(run_directory))
    return destination
