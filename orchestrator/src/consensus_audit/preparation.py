"""Requirement extraction and operation-based source location."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .artifacts import add_usage, cost_summary, create_run_directory, write_json
from .deepseek import DeepSeekClient
from .evidence import build_evidence_manifest, tool_events
from .preparation_validation import force_pending, operation_groups, review_summary, validate_mappings, validate_requirements
from .report import parse_json
from .runner import ChatClient, RunConfig, run_task
from .source_materials import MaterialWorkspace, block_index, load_object, numbered_block, referenced_blocks, require, validate_bundle
from .workspace import SourceWorkspace, InspectionWorkspace


def extract_requirements(bundle: dict[str, Any], client: ChatClient | None,
                         config: RunConfig, model: dict[str, Any]) -> Path:
    validate_bundle(bundle)
    root = create_run_directory(config.run_root, "extract-requirements")
    write_json(root / "materials.json", bundle)
    prompt = (config.spec_root / "preparation/EXTRACT_REQUIREMENTS.md").read_text(encoding="utf-8")
    child_config = RunConfig(root, config.spec_root, config.dry_run, config.max_turns, config.max_tool_calls)
    combined: dict[str, Any] = {"requirements": [], "assumptions": [], "unresolved": [], "block_results": []}
    usage: dict[str, int] = {}
    runs = []
    workspace = MaterialWorkspace(bundle)
    configs = referenced_blocks([], bundle)
    all_ids: set[str] = set()
    for index, block in enumerate(bundle["blocks"], 1):
        prefix = f"B{index}-"
        payload = {"ID_PREFIX": prefix, "sources": bundle["sources"], "block_index": block_index(bundle),
                   "assigned_blocks": [numbered_block(block)], "scope_and_fault_model": configs,
                   "material_unresolved": bundle.get("unresolved", [])}
        def parse_result(raw: str, run: Path) -> dict[str, Any]:
            data = parse_json(raw)
            force_pending(data)
            validate_requirements(data, bundle, [block["id"]])
            for field in ("requirements", "assumptions", "unresolved"):
                for item in data[field]:
                    require(item["id"].startswith(prefix), f"generated IDs must start with {prefix}")
                    require(item["id"] not in all_ids, "item ID already exists in another block")
            return data
        run, data, summary = run_task(client, child_config, stage="extract-requirements", task_id=f"block-{index}", system=prompt,
                                           payload=payload, workspace=workspace, model=model,
                                           parse_result=parse_result)
        add_usage(usage, summary["usage"])
        runs.append({"block_id": block["id"], "run": run.name, **summary})
        if config.dry_run:
            continue
        if data is None:
            combined["block_results"].append({"block_id": block["id"], "requirement_ids": [],
                "reason": f"Processing failed ({summary['status']}); inspect {run.name}/summary.json.",
                "status": "failed"})
            combined["unresolved"].append({"id": f"SYSTEM-B{index}-FAILED", "issue": f"Block {block['id']} was not extracted: {summary['errors']}",
                "source_refs": [], "review_status": "pending"})
        else:
            for field in combined:
                combined[field].extend(data[field])
            all_ids.update(item["id"] for field in ("requirements", "assumptions", "unresolved") for item in data[field])
    if not config.dry_run:
        validate_requirements(combined, bundle)
        combined.update({"schema_version": "requirements/v1",
                         "generation": "model_api" if isinstance(client, DeepSeekClient) else "injected_client",
                         "preparation_run": str(root.resolve())})
        write_json(root / "requirements.json", combined)
    write_json(root / "summary.json", {"stage": "extract-requirements", "dry_run": config.dry_run,
        "blocks": runs, "usage": usage, "cost": cost_summary(usage, model),
        "review": review_summary(combined, bundle),
        "status": "dry_run" if config.dry_run else ("partial" if any(r["status"] != "completed" for r in runs) else "completed")})
    return root


def target_identity(root: Path) -> dict[str, Any]:
    """Use Git's existing identity, without reading config, remotes or credentials."""
    result: dict[str, Any] = {"root": str(root.resolve()), "git_commit": None}
    try:
        top = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-toplevel"],
                             capture_output=True, text=True, timeout=5)
        if top.returncode == 0 and Path(top.stdout.strip()).resolve() == root.resolve():
            head = subprocess.run(["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5)
            if head.returncode == 0:
                result["git_commit"] = head.stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        pass
    return result


def unresolved_mapping(rid: str, reason: str) -> dict[str, Any]:
    return {"requirement_id": rid, "status": "unresolved", "locations": [], "contract_refs": [],
            "unresolved_dependencies": [reason], "not_applicable_refs": [], "not_applicable_reason": ""}


def locate_code(requirements: dict[str, Any], bundle: dict[str, Any], target_root: Path,
                client: ChatClient | None, config: RunConfig, model: dict[str, Any]) -> Path:
    validate_bundle(bundle)
    validate_requirements(requirements, bundle)
    accepted = [r for r in requirements["requirements"] if r["review_status"] == "accepted"]
    workspace = InspectionWorkspace(target_root, bundle)
    root = create_run_directory(config.run_root, "locate-code")
    groups = operation_groups(accepted)
    write_json(root / "input.json", {"stage": "locate-code", "requirements": requirements, "materials": bundle,
        "tasks": [{"task_id": g["task_id"], "operation": g["operation"],
                   "requirement_ids": [r["id"] for r in g["requirements"]]} for g in groups]})
    overview_args = json.dumps({"path": ".", "max_depth": 2, "max_results": 500})
    overview = workspace.execute_json("list_files", overview_args)
    prompt = (config.spec_root / "preparation/LOCATE_CODE.md").read_text(encoding="utf-8")
    child = RunConfig(root, config.spec_root, config.dry_run, config.max_turns, config.max_tool_calls)
    usage: dict[str, int] = {}
    runs, mappings = [], []
    for group in groups:
        items = group["requirements"]
        payload = {**group, "source_blocks": referenced_blocks(items, bundle),
                   "material_index": block_index(bundle), "repository_overview": json.loads(overview),
                   "material_unresolved": bundle.get("unresolved", [])}
        def parse_result(raw: str, run: Path) -> dict[str, Any]:
            data = parse_json(raw)
            require(isinstance(data.get("mappings"), list), "mappings must be an array")
            returned = {m.get("requirement_id") for m in data["mappings"] if isinstance(m, dict) and isinstance(m.get("requirement_id"), str)}
            data["mappings"].extend(unresolved_mapping(r["id"], "Model omitted this requirement in this operation.")
                                    for r in items if r["id"] not in returned)
            validate_mappings(data, items, bundle, workspace=workspace, evidence=build_evidence_manifest(run))
            return data
        run, data, summary = run_task(client, child, stage="locate-code", task_id=group["task_id"],
            system=prompt, payload=payload, workspace=workspace, model=model, parse_result=parse_result,
            initial_tool={"tool": "list_files", "arguments": overview_args, "result": overview})
        add_usage(usage, summary["usage"])
        runs.append({"operation": group["operation"], "run": run.name,
                     "requirement_ids": [r["id"] for r in items], **summary})
        if config.dry_run:
            continue
        values = data["mappings"] if data is not None else [unresolved_mapping(r["id"],
            f"Location task {summary['status']}: {summary['errors']}") for r in items]
        mappings.extend({**value, "operation": group["operation"], "task_id": group["task_id"],
                         "evidence_run": run.name} for value in values)
    if not config.dry_run:
        write_json(root / "code-map.json", {"stage": "locate-code", "target": target_identity(target_root), "mappings": mappings})
    write_json(root / "summary.json", {"stage": "locate-code", "dry_run": config.dry_run, "tasks": runs,
        "usage": usage, "cost": cost_summary(usage, model), "review": review_summary(requirements, bundle),
        "mapping_results": [{k: m[k] for k in ("operation", "requirement_id", "status", "unresolved_dependencies")} for m in mappings],
        "status": "dry_run" if config.dry_run else "needs_review" if not accepted else
                  "partial" if any(r["status"] != "completed" for r in runs) else "completed"})
    return root


def check_map_inputs(code_map_path: Path, requirements: dict[str, Any], bundle: dict[str, Any],
                     target_root: Path) -> dict[str, Any]:
    """Compare actual saved inputs and source reads; no additional snapshots."""
    data = load_object(code_map_path)
    require(data.get("stage") == "locate-code", "expected a locate-code result")
    require(data.get("target") == target_identity(target_root), "code-map target/path or Git version changed; locate again")
    previous = load_object(code_map_path.parent / "input.json")
    require(previous.get("requirements") == requirements and previous.get("materials") == bundle,
            "requirements/material input changed; locate again")
    accepted = [r for r in requirements["requirements"] if r["review_status"] == "accepted"]
    groups = operation_groups(accepted)
    expected = {(g["operation"], r["id"]) for g in groups for r in g["requirements"]}
    workspace = SourceWorkspace(target_root)
    require(isinstance(data.get("mappings"), list), "mappings must be an array")
    seen, checked = set(), set()
    for mapping in data["mappings"]:
        require(isinstance(mapping, dict), "mapping must be an object")
        operation, rid = mapping.get("operation"), mapping.get("requirement_id")
        require(isinstance(operation, str) and isinstance(rid, str), "mapping needs operation and requirement_id")
        key = (operation, rid)
        require(key in expected and key not in seen, "unknown/duplicate operation mapping")
        seen.add(key)
        name = mapping.get("evidence_run")
        require(isinstance(name, str) and Path(name).name == name and name not in {".", ".."}, "invalid evidence_run")
        run = (code_map_path.parent / name).resolve()
        require(run.parent == code_map_path.parent.resolve(), "evidence run escapes code-map directory")
        evidence = build_evidence_manifest(run)
        items = [r for r in accepted if r["id"] == rid]
        validate_mappings({"mappings": [mapping]}, items, bundle, workspace=workspace, evidence=evidence)
        if name in checked:
            continue
        checked.add(name)
        for event in tool_events(run):
            if event["tool"] != "read_file":
                continue
            envelope = json.loads(event["result"])
            if envelope.get("ok") is not True:
                continue
            old = envelope["result"]
            current = workspace.read_file(old["path"], old["start_line"], max(old["start_line"], old["end_line"]))
            require(current == old, f"previously read source changed: {old['path']}; locate again")
    require(seen == expected, "code-map omits a requirement/operation pair")
    return data
