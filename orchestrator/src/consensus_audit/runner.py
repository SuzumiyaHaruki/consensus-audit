"""The single bounded model/tool loop for every stage."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Protocol

from .artifacts import EventLog, add_usage, cost_summary, create_run_directory, utc_now, write_json
from .deepseek import ChatResponse
from .evidence import build_evidence_manifest
from .source_materials import MaterialError, require


class ChatClient(Protocol):
    def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatResponse: ...


@dataclass(frozen=True)
class RunConfig:
    run_root: Path
    spec_root: Path
    dry_run: bool = False
    max_turns: int = 12
    max_tool_calls: int = 40


def run_task(client: ChatClient | None, config: RunConfig, *, stage: str, task_id: str,
                   system: str, payload: dict[str, Any], workspace: Any,
                   model: dict[str, Any], parse_result: Callable[[str, Path], dict[str, Any]],
                   initial_tool: dict[str, Any] | None = None) -> tuple[Path, dict[str, Any] | None, dict[str, Any]]:
    require(config.max_turns > 0 and config.max_tool_calls >= 0, "max_turns must be positive and max_tool_calls nonnegative")
    run = create_run_directory(config.run_root, task_id)
    events = EventLog(run / "events.jsonl")
    write_json(run / "request.json", {"stage": stage, "task_id": task_id, "target_root": str(workspace.root) if hasattr(workspace, "root") else None, "created_at": utc_now(), "dry_run": config.dry_run,
                                      "model": model, "max_turns": config.max_turns,
                                      "max_tool_calls": config.max_tool_calls})
    tools = workspace.tool_definitions()
    messages = [{"role": "system", "content": system},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)}]
    write_json(run / "input.json", {"stage": stage, "task_id": task_id, "messages": messages, "tools": tools})
    if initial_tool is not None:
        events.append("tool_result", turn=0, **initial_tool)
    if config.dry_run:
        events.append("dry_run")
        summary = {"stage": stage, "task_id": task_id, "status": "dry_run", "turns": 0, "tool_calls": 0, "usage": {},
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
            events.append("llm_request", turn=turn, tools_enabled=not final and bool(tools),
                          response_format={"type": "json_object"} if final else None,
                          tool_choice="none" if final and tools else None)
            response = client.create_chat_completion(messages, tools,
                response_format={"type": "json_object"} if final else None,
                tool_choice="none" if final and tools else None)
            add_usage(usage, response.usage)
            events.append("llm_response", turn=turn, content=response.content,
                          reasoning_content=response.reasoning_content, tool_calls=list(response.tool_calls),
                          finish_reason=response.finish_reason, response_id=response.response_id,
                          model=response.model, usage=response.usage)
            (run / "response.md").write_text(response.content, encoding="utf-8")
            messages.append(response.assistant_message())
            if response.tool_calls:
                if final:
                    status, errors = "budget_exhausted", ["model requested tools after the final-turn budget was reached"]
                    break
                for call in response.tool_calls:
                    function = call.get("function")
                    function = function if isinstance(function, dict) else {}
                    name = str(function.get("name") or "")
                    arguments = function.get("arguments") or "{}"
                    if not isinstance(arguments, str):
                        arguments = json.dumps(arguments)
                    if calls >= config.max_tool_calls:
                        result = json.dumps({"ok": False, "error": "tool budget exhausted; retain unresolved items"})
                    else:
                        calls += 1
                        try:
                            result = workspace.execute_json(name, arguments)
                        except Exception as exc:
                            result = json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"})
                    events.append("tool_result", turn=turn, tool_call_id=call.get("id"),
                                  tool=name, arguments=arguments, result=result)
                    messages.append({"role": "tool", "tool_call_id": str(call.get("id") or ""), "content": result})
                continue
            try:
                require(response.finish_reason != "length", "output truncated by max_tokens")
                require(bool(response.content.strip()), "empty model response")
                parsed = parse_result(response.content, run)
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
    summary = {"stage": stage, "task_id": task_id, "status": status, "turns": turn, "tool_calls": calls, "usage": usage,
               "errors": errors, "format_recovery_used": recovery_used, "cost": cost_summary(usage, model)}
    write_json(run / "summary.json", summary)
    write_json(run / "evidence-manifest.json", build_evidence_manifest(run))
    return run, data, summary
