"""JSON parsing, inspected-source references and operation task results."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .source_materials import nonempty, require, validate_refs


def parse_json(response: str) -> dict[str, Any]:
    """Accept a single object, optionally wrapped in prose or a JSON fence."""
    text = response.strip()
    try:
        value = json.loads(text)
    except ValueError:
        fences = re.findall(r"```(?:json)?\s*(.*?)\s*```", text, flags=re.I | re.S)
        if fences:
            require(len(fences) == 1, "response contains multiple JSON blocks")
            # Do not select a fenced object while silently ignoring another object.
            outside = re.sub(r"```(?:json)?\s*.*?\s*```", "", text, flags=re.I | re.S)
            require("{" not in outside, "response contains multiple JSON objects")
            value = json.loads(fences[0])
        else:
            start = text.find("{")
            require(start >= 0, "response is not a JSON object")
            value = json.loads(text[start:])
    require(isinstance(value, dict), "stage output must be a JSON object")
    return value


def validate_code_refs(refs: Any, *, target_root: Path, evidence: dict[str, Any]) -> None:
    require(isinstance(refs, list), "code references must be an array")
    ranges = {entry["path"]: entry["ranges"] for entry in evidence["files"]["read"]}
    root = target_root.resolve()
    for ref in refs:
        require(isinstance(ref, dict), "code reference must be an object")
        path = ref.get("path")
        require(nonempty(path), "code reference needs a path")
        relative = Path(path)
        require(not relative.is_absolute() and not {"..", ".git"}.intersection(relative.parts),
                f"invalid target-relative path: {path}")
        resolved = (root / relative).resolve()
        require(resolved.is_relative_to(root) and ".git" not in resolved.relative_to(root).parts
                and resolved.is_file(), f"code path missing or escapes target: {path}")
        start, end = ref.get("start_line"), ref.get("end_line")
        require(type(start) is int and type(end) is int and 1 <= start <= end, "invalid code interval")
        cursor = start
        for interval in sorted(ranges.get(path, []), key=lambda r: r["start"]):
            if interval["start"] > cursor:
                break
            cursor = max(cursor, interval["end"] + 1)
        require(cursor > end, f"code interval was not read in this task: {path}:{start}-{end}")


def string_list(value: Any, field: str, *, minimum: int = 0) -> None:
    require(isinstance(value, list) and len(value) >= minimum and all(nonempty(v) for v in value),
            f"{field} must be a string array with at least {minimum} entries")


def unchecked_result(task: dict[str, Any], reason: str) -> dict[str, Any]:
    return {"task_id": task["task_id"], "candidates": [],
            "requirement_results": [{"requirement_id": r["id"], "status": "not_checked", "candidate_ids": [],
                                     "note": reason} for r in task["requirements"]], "unresolved": [reason]}


def validate_task_result(data: dict[str, Any], task: dict[str, Any], bundle: dict[str, Any], *,
                         target_root: Path, evidence: dict[str, Any]) -> None:
    require(data.get("task_id") == task["task_id"], "wrong task_id in audit result")
    expected = {r["id"] for r in task["requirements"]}
    candidates = data.get("candidates")
    results = data.get("requirement_results")
    require(isinstance(candidates, list) and isinstance(results, list), "candidates and requirement_results must be arrays")
    candidate_refs: dict[str, set[str]] = {}
    for candidate in candidates:
        require(isinstance(candidate, dict), "candidate must be an object")
        cid = candidate.get("id")
        require(nonempty(cid) and cid not in candidate_refs, "duplicate/invalid candidate ID")
        ids = candidate.get("requirement_ids")
        string_list(ids, "requirement_ids", minimum=1)
        require(len(ids) == len(set(ids)) and set(ids) <= expected, "candidate references unknown/duplicate requirements")
        candidate_refs[cid] = set(ids)
        require(nonempty(candidate.get("summary")), "candidate needs a summary")
        refs = candidate.get("source_evidence")
        validate_code_refs(refs, target_root=target_root, evidence=evidence)
        require(bool(refs) and all(nonempty(r.get("claim")) for r in refs), "candidate needs inspected source claims")
        mechanism = candidate.get("mechanism")
        require(isinstance(mechanism, dict) and all(nonempty(mechanism.get(k))
                for k in ("violated_obligation", "decisive_relation")), "candidate needs an obligation and decisive mechanism")
        string_list(candidate.get("causal_chain"), "causal_chain", minimum=2)
        sketch = candidate.get("test_sketch")
        require(isinstance(sketch, dict) and all(nonempty(sketch.get(k))
                for k in ("precondition", "violation", "oracle")), "candidate needs P/V/O")
        string_list(sketch.get("actions"), "test_sketch.actions", minimum=1)
        string_list(candidate.get("uncertainties"), "uncertainties")
    seen = set()
    for result in results:
        require(isinstance(result, dict), "requirement result must be an object")
        rid = result.get("requirement_id")
        require(isinstance(rid, str) and rid in expected and rid not in seen, "unknown/duplicate requirement result")
        seen.add(rid)
        status = result.get("status")
        require(status in ("candidate_found", "no_candidate", "insufficient_evidence", "not_checked", "not_applicable"),
                "invalid requirement status")
        cids = result.get("candidate_ids")
        string_list(cids, "candidate_ids")
        require(len(cids) == len(set(cids)), "duplicate candidate_ids")
        linked = {cid for cid, rids in candidate_refs.items() if rid in rids}
        require(set(cids) == linked, "candidate/requirement links disagree")
        require(status == "not_checked" or bool(cids) == (status == "candidate_found"),
                "candidate_found must correspond to linked candidates")
        require(isinstance(result.get("note"), str), "requirement result needs a note")
        if status != "candidate_found":
            require(nonempty(result["note"]), f"{status} needs a reason or inspection note")
        if status == "not_applicable":
            validate_refs(result.get("source_refs"), bundle)
        if "source_evidence" in result:
            validate_code_refs(result["source_evidence"], target_root=target_root, evidence=evidence)
    unresolved = data.setdefault("unresolved", [])
    string_list(unresolved, "unresolved")
    # Omission is not success. Even if a candidate mentioned this requirement,
    # its missing processing record remains not_checked and is flagged below.
    for rid in sorted(expected - seen):
        note = "The model omitted this requirement's processing record; no completed check is inferred."
        results.append({"requirement_id": rid, "status": "not_checked",
                        "candidate_ids": [cid for cid, rids in candidate_refs.items() if rid in rids], "note": note})
        unresolved.append(f"{rid}: {note}")
