"""Independent extraction and location calls using the existing client/tools."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .artifacts import EventLog, create_run_directory, utc_now, write_json
from .deepseek import DeepSeekClient
from .evidence import build_evidence_manifest
from .materials import MaterialError
from .preparation_validation import (
    force_pending, operation_groups, review_summary, validate_mappings, validate_requirements,
)
from .runner import ChatClient, _add_usage
from .source_materials import (
    MaterialWorkspace, block_index, load_object, numbered_block, referenced_blocks,
    require, validate_bundle,
)
from .workspace import SourceWorkspace


@dataclass(frozen=True)
class PreparationConfig:
    run_root: Path
    spec_root: Path
    dry_run: bool = False
    max_turns: int = 12
    max_tool_calls: int = 40


def cost_summary(usage: dict[str, int], model: dict[str, Any]) -> dict[str, Any]:
    prices = model.get("prices_per_million") or {}
    required = ("input", "output")
    if not all(isinstance(prices.get(k), (int, float)) for k in required):
        return {"usage": usage, "estimated_cost": None, "reason": "No explicit pricing supplied."}
    if not all(k in usage for k in ("prompt_tokens", "completion_tokens")):
        return {"usage": usage, "estimated_cost": None, "reason": "Provider token breakdown unavailable."}
    cached = usage.get("prompt_cache_hit_tokens", 0)
    if cached and prices.get("cached_input") is None:
        return {"usage": usage, "estimated_cost": None, "reason": "Cached input price unavailable."}
    amount = ((usage["prompt_tokens"] - cached) * prices["input"]
              + cached * (prices.get("cached_input") or 0)
              + usage["completion_tokens"] * prices["output"]) / 1_000_000
    return {"usage": usage, "estimated_cost": amount, "prices_per_million": prices}


def run_json_stage(client: ChatClient | None, config: PreparationConfig, *, label: str,
                   system: str, payload: dict[str, Any], workspace: Any,
                   model: dict[str, Any], validate: Callable[[dict[str, Any], Path], None],
                   normalize: Callable[[dict[str, Any]], None] | None = None,
                   initial_tool: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any] | None, dict[str, Any]]:
    require(config.max_turns > 0 and config.max_tool_calls > 0, "budgets must be positive")
    run = create_run_directory(config.run_root, label)
    events = EventLog(run / "events.jsonl")
    write_json(run / "request.json", {"stage": label, "created_at": utc_now(), "dry_run": config.dry_run,
                                      "model": model, "max_turns": config.max_turns,
                                      "max_tool_calls": config.max_tool_calls})
    tools = workspace.tool_definitions()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    write_json(run / "input.json", {"messages": messages, "tools": tools})
    if initial_tool is not None:
        events.append("tool_result", turn=0, **initial_tool)
    if config.dry_run:
        events.append("dry_run_prepared")
        summary = {"status": "dry_run", "turns": 0, "tool_calls": 0, "usage": {},
                   "cost": cost_summary({}, model)}
        write_json(run / "summary.json", summary)
        return run, None, summary
    require(client is not None, "a chat client is required unless dry_run is enabled")
    usage: dict[str, int] = {}
    calls = 0
    recovery_used = False
    force_final = False
    data = None
    status = "budget_exhausted"
    errors: list[str] = []
    turn = 0
    try:
        for turn in range(1, config.max_turns + 1):
            final = force_final or turn == config.max_turns or calls >= config.max_tool_calls
            if final:
                notice = ("No further tools are available. Return the stage JSON object using inspected evidence. "
                          "Preserve every input block/requirement and record unknowns. Do not invent evidence.")
                messages.append({"role": "user", "content": notice})
                events.append("input_append", turn=turn, role="user", content=notice)
            events.append("llm_request", turn=turn, tools_enabled=not final,
                          response_format={"type": "json_object"} if final else None,
                          tool_choice="none" if final else None)
            response = client.create_chat_completion(messages, tools,
                response_format={"type": "json_object"} if final else None,
                tool_choice="none" if final else None)
            _add_usage(usage, response.usage)
            events.append("llm_response", turn=turn, content=response.content,
                          reasoning_content=response.reasoning_content, tool_calls=list(response.tool_calls),
                          finish_reason=response.finish_reason, response_id=response.response_id,
                          model=response.model, usage=response.usage)
            messages.append(response.assistant_message())
            if response.tool_calls:
                if final:
                    status, errors = "invalid_output", ["tool calls returned during final JSON turn"]
                    break
                for call in response.tool_calls:
                    function = call.get("function") or {}
                    name = str(function.get("name") or "")
                    arguments = function.get("arguments") or "{}"
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments)
                    if calls >= config.max_tool_calls:
                        result = json.dumps({"ok": False, "error": "tool budget exhausted; retain unresolved items"})
                    else:
                        result = workspace.execute_json(name, arguments)
                        calls += 1
                    events.append("tool_result", turn=turn, tool_call_id=call.get("id"),
                                  tool=name, arguments=arguments, result=result)
                    messages.append({"role": "tool", "tool_call_id": str(call.get("id") or ""), "content": result})
                continue
            (run / "response.md").write_text(response.content, encoding="utf-8")
            try:
                require(response.finish_reason != "length", "output truncated by max_tokens")
                require(bool(response.content.strip()), "empty model response")
                parsed = json.loads(response.content)
                require(isinstance(parsed, dict), "stage response must be a JSON object")
                if normalize:
                    normalize(parsed)
                validate(parsed, run)
            except (MaterialError, ValueError, TypeError) as exc:
                status = "empty_response" if not response.content.strip() else "invalid_output"
                errors = [str(exc)]
                if not recovery_used and turn < config.max_turns:
                    recovery_used, force_final = True, True
                    notice = ("Repair only the stage JSON structure/references using existing evidence; "
                              "do not invent missing support. Validation errors: " + str(exc))
                    messages.append({"role": "user", "content": notice})
                    events.append("input_append", turn=turn, role="user", content=notice)
                    continue
                break
            data, status, errors = parsed, "completed", []
            break
    except Exception as exc:
        status, errors = "failed", [f"{type(exc).__name__}: {exc}"]
        events.append("stage_failed", error=errors[0])
    summary = {"status": status, "turns": turn, "tool_calls": calls, "usage": usage,
               "errors": errors, "format_recovery_used": recovery_used, "cost": cost_summary(usage, model)}
    write_json(run / "summary.json", summary)
    return run, data, summary


def extract_requirements(bundle: dict[str, Any], client: ChatClient | None,
                         config: PreparationConfig, model: dict[str, Any]) -> Path:
    validate_bundle(bundle)
    root = create_run_directory(config.run_root, "extract-requirements")
    write_json(root / "materials.json", bundle)
    prompt = (config.spec_root / "preparation/EXTRACT_REQUIREMENTS.md").read_text(encoding="utf-8")
    child_config = PreparationConfig(root, config.spec_root, config.dry_run, config.max_turns, config.max_tool_calls)
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
        def validate(data: dict[str, Any], run: Path) -> None:
            validate_requirements(data, bundle, [block["id"]])
            for field in ("requirements", "assumptions", "unresolved"):
                for item in data[field]:
                    require(item["id"].startswith(prefix), f"generated IDs must start with {prefix}")
                    require(item["id"] not in all_ids, "item ID already exists in another block")
        run, data, summary = run_json_stage(client, child_config, label=f"block-{index}", system=prompt,
                                           payload=payload, workspace=workspace, model=model,
                                           validate=validate, normalize=force_pending)
        _add_usage(usage, summary["usage"])
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
    write_json(root / "summary.json", {"stage": "extraction", "dry_run": config.dry_run,
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
                client: ChatClient | None, config: PreparationConfig, model: dict[str, Any]) -> Path:
    validate_bundle(bundle)
    validate_requirements(requirements, bundle)
    accepted = [r for r in requirements["requirements"] if r["review_status"] == "accepted"]
    workspace = SourceWorkspace(target_root, allow_tests=False)
    root = create_run_directory(config.run_root, "locate-code")
    write_json(root / "input.json", {"requirements": requirements, "materials": bundle})
    overview_args = json.dumps({"path": ".", "max_depth": 2, "max_results": 500})
    overview = workspace.execute_json("list_files", overview_args)
    prompt = (config.spec_root / "preparation/LOCATE_CODE.md").read_text(encoding="utf-8")
    child_config = PreparationConfig(root, config.spec_root, config.dry_run, config.max_turns, config.max_tool_calls)
    usage: dict[str, int] = {}
    runs = []
    # A multi-operation requirement is located once with its first operation.
    # Audit grouping below still includes it under all of its operations.
    assigned: set[str] = set()
    mappings = []
    for group in operation_groups(accepted):
        items = [r for r in group["requirements"] if r["id"] not in assigned]
        if not items:
            continue
        assigned.update(r["id"] for r in items)
        payload = {"operation": group["operation"], "requirements": items,
                   "source_blocks": referenced_blocks(items, bundle), "repository_overview": json.loads(overview),
                   "material_unresolved": bundle.get("unresolved", [])}
        # No source file outside these already supplied blocks is available in
        # this stage; config/spec citations must refer to that actual input.
        def validate(data: dict[str, Any], run: Path) -> None:
            validate_mappings(data, items, bundle, workspace=workspace, evidence=build_evidence_manifest(run))
            available = {b["id"] for b in payload["source_blocks"]}
            require(all(ref["block_id"] in available for m in data["mappings"]
                        for ref in m.get("not_applicable_refs", [])), "not_applicable cites material not supplied to this task")
        run, data, summary = run_json_stage(client, child_config, label=f"operation-{len(runs)+1}",
            system=prompt, payload=payload, workspace=workspace, model=model, validate=validate,
            initial_tool={"tool": "list_files", "arguments": overview_args, "result": overview})
        _add_usage(usage, summary["usage"])
        runs.append({"operation": group["operation"], "run": run.name,
                     "requirement_ids": [r["id"] for r in items], **summary})
        if config.dry_run:
            continue
        evidence = build_evidence_manifest(run)
        write_json(run / "evidence-manifest.json", evidence)
        values = data["mappings"] if data else [unresolved_mapping(r["id"],
            f"Location stage {summary['status']}; inspect {run.name}/summary.json: {summary['errors']}") for r in items]
        mappings.extend({**value, "evidence_run": run.name} for value in values)
    if not config.dry_run:
        write_json(root / "code-map.json", {"schema_version": "code-map/v1", "target": target_identity(target_root),
            "mappings": mappings, "review": review_summary(requirements, bundle)})
    write_json(root / "summary.json", {"stage": "location", "dry_run": config.dry_run, "operations": runs,
        "usage": usage, "cost": cost_summary(usage, model), "review": review_summary(requirements, bundle),
        "status": "dry_run" if config.dry_run else ("needs_review" if not accepted else
                  "partial" if any(r["status"] != "completed" for r in runs) else "completed")})
    return root


def check_map_inputs(code_map_path: Path, requirements: dict[str, Any], bundle: dict[str, Any],
                     target_root: Path) -> dict[str, Any]:
    """Reuse actual saved inputs and read_file results instead of extra snapshots/hashes."""
    data = load_object(code_map_path)
    require(data.get("schema_version") == "code-map/v1", "invalid code-map version")
    require(data.get("target") == target_identity(target_root), "code-map target/path or Git version changed; locate again")
    previous = load_object(code_map_path.parent / "input.json")
    require(previous.get("requirements") == requirements and previous.get("materials") == bundle,
            "requirements/material input changed; locate again")
    accepted = [r for r in requirements["requirements"] if r["review_status"] == "accepted"]
    workspace = SourceWorkspace(target_root)
    require(isinstance(data.get("mappings"), list), "mappings must be an array")
    seen = set()
    checked = set()
    for mapping in data["mappings"]:
        require(isinstance(mapping, dict), "mapping must be an object")
        rid = mapping.get("requirement_id")
        require(isinstance(rid, str) and rid not in seen, "duplicate/invalid mapping ID")
        seen.add(rid)
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
        for line in (run / "events.jsonl").read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event_type") != "tool_result" or event.get("tool") != "read_file":
                continue
            envelope = json.loads(event["result"])
            if envelope.get("ok") is not True:
                continue
            old = envelope["result"]
            current = workspace.read_file(old["path"], old["start_line"], max(old["start_line"], old["end_line"]))
            require(current == old, f"previously read source changed: {old['path']}; locate again")
    require(seen == {r["id"] for r in accepted}, "code-map omits accepted requirements")
    return data
