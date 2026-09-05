"""Independent operation audits; no cross-task reasoning or candidate sharing."""
from __future__ import annotations

from pathlib import Path
from typing import Any

from .artifacts import add_usage, cost_summary, create_run_directory, write_json
from .evidence import build_evidence_manifest
from .preparation import check_map_inputs
from .preparation_validation import operation_groups, review_summary, validate_requirements
from .report import parse_json, unchecked_result, validate_task_result
from .runner import ChatClient, RunConfig, run_task
from .source_materials import block_index, load_object, referenced_blocks, validate_bundle
from .workspace import InspectionWorkspace


def relevant_items(items: list[dict[str, Any]], requirements: list[dict[str, Any]], *,
                   global_by_default: bool = False) -> list[dict[str, Any]]:
    ids = {r["id"] for r in requirements}
    blocks = {ref["block_id"] for r in requirements for field in ("source_refs", "definitions") for ref in r.get(field, [])}
    return [item for item in items if
            (bool(ids.intersection(item["requirement_ids"])) if item.get("requirement_ids") else
             global_by_default or not item.get("source_refs") or any(ref["block_id"] in blocks for ref in item["source_refs"]))]


def task_input(group: dict[str, Any], bundle: dict[str, Any], requirements: dict[str, Any],
               mappings: list[dict[str, Any]]) -> dict[str, Any]:
    ids = {r["id"] for r in group["requirements"]}
    assumptions = relevant_items(requirements["assumptions"], group["requirements"], global_by_default=True)
    accepted_assumptions = [a for a in assumptions if a["review_status"] == "accepted"]
    # Include all mapped sides of each task requirement, while retaining operation
    # labels. The current task must still inspect its own code and dependencies.
    selected = [{k: v for k, v in m.items() if k not in {"evidence_run", "task_id"}}
                for m in mappings if m["requirement_id"] in ids]
    locations, seen = [], {}
    for mapping in selected:
        for field in ("locations", "contract_refs"):
            links = []
            for location in mapping[field]:
                key = (location["path"], location["start_line"], location["end_line"])
                if key not in seen:
                    seen[key] = f"L{len(locations) + 1}"
                    locations.append({"id": seen[key], **{k: location[k] for k in ("path", "symbol", "start_line", "end_line")}})
                links.append({"location_id": seen[key], **{k: location[k] for k in ("symbol", "responsibility", "basis")}})
            mapping[field] = links
    return {**group, "source_blocks": referenced_blocks(group["requirements"] + accepted_assumptions, bundle),
            "material_index": block_index(bundle), "assumptions": accepted_assumptions,
            "code_map": selected, "starting_locations": locations,
            "unresolved": relevant_items(requirements["unresolved"], group["requirements"]),
            "unaccepted_assumptions": [a for a in assumptions if a["review_status"] != "accepted"],
            "material_unresolved": bundle.get("unresolved", [])}


def audit(requirements: dict[str, Any], bundle: dict[str, Any], code_map_path: Path,
          target_root: Path, client: ChatClient | None, config: RunConfig, model: dict[str, Any]) -> Path:
    validate_bundle(bundle)
    validate_requirements(requirements, bundle)
    code_map = check_map_inputs(code_map_path, requirements, bundle, target_root)
    accepted = [r for r in requirements["requirements"] if r["review_status"] == "accepted"]
    groups = operation_groups(accepted)
    root = create_run_directory(config.run_root, "audit")
    review = review_summary(requirements, bundle)
    write_json(root / "input.json", {"stage": "audit", "target_root": str(target_root.resolve()),
        "tasks": [{"task_id": g["task_id"], "operation": g["operation"],
                   "requirement_ids": [r["id"] for r in g["requirements"]]} for g in groups], "review": review})
    prompt = "\n\n".join((config.spec_root / path).read_text(encoding="utf-8") for path in
                         ("audit/AUDIT.md", "common/CANDIDATE_CRITERIA.md", "common/TASK_RESULT.md"))
    child = RunConfig(root, config.spec_root, config.dry_run, config.max_turns, config.max_tool_calls)
    entries = []
    usage: dict[str, int] = {}
    for group in groups:
        ids = {r["id"] for r in group["requirements"]}
        payload = task_input(group, bundle, requirements, code_map["mappings"])
        workspace = InspectionWorkspace(target_root, bundle)
        def parse_result(raw: str, run: Path) -> dict[str, Any]:
            data = parse_json(raw)
            validate_task_result(data, group, bundle, target_root=target_root, evidence=build_evidence_manifest(run))
            return data
        run, result, summary = run_task(client, child, stage="audit", task_id=group["task_id"],
            system=prompt, payload=payload, workspace=workspace, model=model, parse_result=parse_result)
        add_usage(usage, summary["usage"])
        entry = {**summary, "operation": group["operation"], "run": run.name,
                 "requirement_ids": [r["id"] for r in group["requirements"]],
                 "location_results": [{k: m[k] for k in ("requirement_id", "operation", "status", "unresolved_dependencies")}
                                      for m in code_map["mappings"] if m["requirement_id"] in ids]}
        if not config.dry_run:
            if result is None:
                result = unchecked_result(group, f"Audit task {summary['status']}: {summary['errors']}")
            write_json(run / "result.json", result)
            entry.update({"candidate_count": len(result["candidates"]),
                          "requirement_results": result["requirement_results"], "unresolved": result["unresolved"]})
        entries.append(entry)
    costs = {"audit": cost_summary(usage, model),
             "locate-code": load_object(code_map_path.parent / "summary.json")["cost"]}
    extraction_run = requirements.get("preparation_run")
    if extraction_run and (Path(extraction_run) / "summary.json").is_file():
        costs["extract-requirements"] = load_object(Path(extraction_run) / "summary.json")["cost"]
    missing_stages = sorted({"extract-requirements", "locate-code", "audit"} - costs.keys())
    total: dict[str, int] = {}
    for cost in costs.values():
        add_usage(total, cost["usage"])
    amounts = [c.get("estimated_cost") for c in costs.values()]
    assigned = {r["id"] for g in groups for r in g["requirements"]}
    write_json(root / "summary.json", {"stage": "audit", "tasks": entries, "review": review, "usage": usage,
        "unassigned_requirement_ids": [r["id"] for r in requirements["requirements"] if r["id"] not in assigned],
        "cost": costs["audit"], "pipeline_cost": {"stages": costs, "usage": total, "missing_stages": missing_stages,
            "estimated_cost": sum(amounts) if not missing_stages and all(a is not None for a in amounts) else None},
        "status": "dry_run" if config.dry_run else "needs_review" if not accepted else
                  "partial" if any(e["status"] != "completed" for e in entries) else "completed"})
    return root
