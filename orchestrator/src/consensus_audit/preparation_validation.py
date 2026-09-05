"""Structural/reference checks, deliberately not semantic approval."""
from __future__ import annotations

from typing import Any

from .source_materials import REVIEW_STATES, nonempty, require, validate_refs


def validate_requirements(data: dict[str, Any], bundle: dict[str, Any],
                          expected_blocks: list[str] | None = None) -> None:
    ids: set[str] = set()
    for array, text_field in (("requirements", "requirement"), ("assumptions", "assumption"), ("unresolved", "issue")):
        require(isinstance(data.get(array), list), f"{array} must be an array")
        for item in data[array]:
            require(isinstance(item, dict), f"{array} item must be an object")
            require(nonempty(item.get("id")) and item["id"] not in ids, "duplicate/invalid item ID")
            ids.add(item["id"])
            require(nonempty(item.get(text_field)), f"{array} item lacks {text_field}")
            require(item.get("review_status") in REVIEW_STATES, "invalid review_status")
            validate_refs(item.get("source_refs"), bundle, allow_empty=array == "unresolved")
            if array != "requirements":
                continue
            ops = item.get("operation")
            require(isinstance(ops, list) and bool(ops) and all(nonempty(op) for op in ops),
                    "operation must be a nonempty string array")
            require(len(ops) == len(set(ops)), "duplicate operation")
            require(item.get("category") in ("protocol_requirement", "extension_requirement", "caller_obligation"),
                    "invalid requirement category; environment assumptions belong in assumptions")
            require(nonempty(item.get("applies_when")), "requirement lacks applies_when")
            validate_refs(item.get("definitions"), bundle, allow_empty=True)
            require(item.get("origin") in ("explicit", "derived"), "origin must be explicit or derived")
            if item["origin"] == "derived":
                require(nonempty(item.get("derivation")), "derived requirement lacks derivation")
            # Scope configuration cannot masquerade as an extracted protocol rule.
            if item["category"] in {"protocol_requirement", "extension_requirement"}:
                blocks = {b["id"]: b for b in bundle["blocks"]}
                sources = {s["id"]: s for s in bundle["sources"]}
                require(any(sources[blocks[r["block_id"]]["source_id"]]["category"] in {"protocol", "extension"}
                            for r in item["source_refs"]), "protocol requirement needs original protocol/extension evidence")
    requirement_ids = {r["id"] for r in data["requirements"]}
    for item in data["assumptions"] + data["unresolved"]:
        if "requirement_ids" in item:
            links = item["requirement_ids"]
            require(isinstance(links, list) and all(isinstance(rid, str) and rid in requirement_ids for rid in links),
                    "assumption/unresolved item references an unknown requirement")
    records = data.get("block_results")
    require(isinstance(records, list), "block_results must be an array")
    expected = set(expected_blocks if expected_blocks is not None else [b["id"] for b in bundle["blocks"]])
    seen = set()
    referenced = set()
    requirements = {r["id"]: r for r in data["requirements"]}
    for record in records:
        require(isinstance(record, dict), "block_result must be an object")
        bid = record.get("block_id")
        require(isinstance(bid, str) and bid in expected and bid not in seen, "unexpected/duplicate block_result")
        seen.add(bid)
        rids = record.get("requirement_ids")
        require(isinstance(rids, list) and all(isinstance(r, str) and r in requirements for r in rids),
                "block_result has invalid requirement IDs")
        require(len(rids) == len(set(rids)), "duplicate requirement in block_result")
        for rid in rids:
            require(any(ref["block_id"] == bid for ref in requirements[rid]["source_refs"]),
                    "block_result requirement does not cite this block")
        referenced.update(rids)
        if not rids:
            require(nonempty(record.get("reason")), "empty block_result requires reason")
    require(seen == expected, f"missing block_results: {sorted(expected - seen)}")
    require(referenced == set(requirements), "requirements missing from block_results")


def force_pending(data: dict[str, Any]) -> None:
    for field in ("requirements", "assumptions", "unresolved"):
        if isinstance(data.get(field), list):
            for item in data[field]:
                if isinstance(item, dict):
                    item["review_status"] = "pending"


def review_summary(data: dict[str, Any], bundle: dict[str, Any]) -> dict[str, Any]:
    return {
        "requirements": {status: [r["id"] for r in data["requirements"] if r["review_status"] == status]
                         for status in sorted(REVIEW_STATES)},
        "assumptions": data["assumptions"], "unresolved": data["unresolved"],
        "material_unresolved": bundle.get("unresolved", []),
        "unreviewed_material_blocks": [b["id"] for b in bundle["blocks"] if b["review_status"] != "accepted"],
    }


def operation_groups(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """One group per operation; cross-operation requirements retain all links."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for requirement in requirements:
        for operation in requirement["operation"]:
            groups.setdefault(operation, []).append(requirement)
    return [{"task_id": f"operation-{index}", "operation": operation, "requirements": items}
            for index, (operation, items) in enumerate(groups.items(), 1)]


def validate_mappings(data: dict[str, Any], requirements: list[dict[str, Any]],
                      bundle: dict[str, Any], *, workspace: Any,
                      evidence: dict[str, Any]) -> None:
    from .report import validate_code_refs

    require(isinstance(data.get("mappings"), list), "mappings must be an array")
    expected = {r["id"] for r in requirements}
    seen = set()
    for mapping in data["mappings"]:
        require(isinstance(mapping, dict), "mapping must be an object")
        rid = mapping.get("requirement_id")
        require(isinstance(rid, str) and rid in expected and rid not in seen, "unexpected/duplicate requirement mapping")
        seen.add(rid)
        status = mapping.get("status")
        require(status in ("located", "partial", "unresolved", "not_applicable"), "invalid location status")
        refs = []
        for field in ("locations", "contract_refs"):
            require(isinstance(mapping.get(field), list), f"{field} must be an array")
            for loc in mapping[field]:
                require(isinstance(loc, dict), "location must be an object")
                for name in ("path", "symbol", "responsibility", "basis"):
                    require(nonempty(loc.get(name)), f"location lacks {name}")
                start, end = loc.get("start_line"), loc.get("end_line")
                require(type(start) is int and type(end) is int and 1 <= start <= end, "invalid code interval")
                refs.append({**loc, "claim": loc["responsibility"]})
        validate_code_refs(refs, target_root=workspace.root, evidence=evidence)
        deps = mapping.get("unresolved_dependencies")
        require(isinstance(deps, list) and all(nonempty(d) for d in deps), "invalid unresolved_dependencies")
        if status in {"partial", "unresolved"}:
            require(bool(deps), f"{status} must explain missing dependencies")
        if status == "located":
            require(bool(mapping["locations"]), "located requires executable code locations")
        if status == "not_applicable":
            require(nonempty(mapping.get("not_applicable_reason")), "not_applicable needs configuration/specification reason")
            validate_refs(mapping.get("not_applicable_refs"), bundle)
        else:
            validate_refs(mapping.get("not_applicable_refs", []), bundle, allow_empty=True)
    require(seen == expected, f"missing requirement mappings: {sorted(expected - seen)}")
