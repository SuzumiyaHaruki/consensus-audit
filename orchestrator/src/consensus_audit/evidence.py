"""Mechanical evidence reconstructed from this task's tool events."""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from .source_materials import load_object


def tool_events(run: Path) -> list[dict[str, Any]]:
    path = run / "events.jsonl"
    if not path.exists():
        return []
    return [event for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and (event := json.loads(line)).get("event_type") == "tool_result"]


def build_evidence_manifest(run: Path) -> dict[str, Any]:
    request = load_object(run / "request.json")
    reads: dict[str, list[tuple[int, int]]] = defaultdict(list)
    materials = set()
    errors = []
    counts: Counter[str] = Counter()
    for event in tool_events(run):
        name = event["tool"]
        counts[name] += 1
        envelope = json.loads(event["result"])
        if envelope.get("ok") is not True:
            errors.append({"tool": name, "error": envelope.get("error")})
            continue
        result = envelope["result"]
        if name == "read_file" and result["start_line"] <= result["end_line"]:
            reads[result["path"]].append((result["start_line"], result["end_line"]))
        elif name == "read_material":
            materials.add(result["id"])
    files = []
    for path, ranges in sorted(reads.items()):
        merged: list[dict[str, int]] = []
        for start, end in sorted(ranges):
            if merged and start <= merged[-1]["end"] + 1:
                merged[-1]["end"] = max(merged[-1]["end"], end)
            else:
                merged.append({"start": start, "end": end})
        files.append({"path": path, "ranges": merged})
    return {"stage": request["stage"], "task_id": request["task_id"],
            "files": {"read": files}, "material_blocks_read": sorted(materials),
            "tool_calls": dict(counts), "tool_errors": errors}
