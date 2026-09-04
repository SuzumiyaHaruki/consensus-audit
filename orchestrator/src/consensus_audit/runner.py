from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .artifacts import EventLog, create_run_directory, utc_now, write_json
from .deepseek import ChatResponse
from .evidence import build_evidence_manifest, write_evidence_manifest
from .materials import (
    MaterialSet,
    build_audit_prompt,
    build_baseline_prompt,
)
from .report import write_candidate_artifacts
from .shared_context import SharedAuditContext
from .workspace import SourceWorkspace


class ChatClient(Protocol):
    def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatResponse: ...


class AuditRunError(RuntimeError):
    """Raised when an agent run cannot produce a final response."""

    def __init__(self, message: str, run_directory: Path | None = None):
        super().__init__(message)
        self.run_directory = run_directory


LATE_BUDGET_NOTICE = """\
The investigation budget is nearly exhausted. If you can already name a
provisional Candidate-v0 status and its decisive causal chain, use at most two
additional source-tool calls total. Each must be a targeted attempt to falsify
that result and must be capable of changing it. Do not spend remaining calls on
general coverage, line-number collection, unavailable execution, or facts
already inspected. Return the Candidate-v0 JSON object immediately when those
checks finish.
"""


FINAL_CANDIDATE_INSTRUCTION = """\
This is the final Candidate-v0 turn. No further source-tool calls are available.
Using only the evidence already inspected, return exactly one JSON object now
and follow REPORT_TEMPLATE.md. Choose exactly one status: `candidate_found`,
`no_candidate`, or `insufficient_evidence`.

Do not claim execution confirmation. If essential evidence is missing, use
`insufficient_evidence` and identify it in `summary` and `uncertainties`. Do not
request more checks or tools, return Markdown prose, respond with a plan, or
emit tool-call syntax such as XML/DSML tags. The first output character must be
`{` and the last must be `}`.
"""


SHARED_EVIDENCE_INSTRUCTION = """\
SHARED EVIDENCE MODE: `query_repository_index` exposes only mechanical file and
Go declaration locations. Source listing, reading, and search results may be
reused raw evidence first obtained during another isolated audit, but no other
audit's reasoning, candidate, or verdict is available. Treat every property as
a fresh proof attempt. Inspect raw source before making semantic claims and do
not infer that a previous audit found or failed to find anything.
"""


@dataclass(frozen=True)
class RunConfig:
    property_id: str
    target_root: Path
    run_root: Path
    max_turns: int = 24
    max_tool_calls: int = 80
    allow_tests: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class BaselineRunConfig:
    episode: int
    target_root: Path
    run_root: Path
    max_turns: int = 24
    max_tool_calls: int = 80
    allow_tests: bool = False
    dry_run: bool = False


@dataclass(frozen=True)
class RunResult:
    run_directory: Path
    response: str | None
    usage: dict[str, int]
    turns: int
    tool_calls: int
    dry_run: bool
    candidate_status: str | None
    candidate_format_valid: bool | None
    candidate_provenance_valid: bool | None


def _add_usage(total: dict[str, int], current: dict[str, int]) -> None:
    for key, value in current.items():
        total[key] = total.get(key, 0) + value


def run_audit(
    material_set: MaterialSet,
    client: ChatClient | None,
    config: RunConfig,
    *,
    model_metadata: dict[str, Any],
    shared_context: SharedAuditContext | None = None,
) -> RunResult:
    target_root = config.target_root.resolve()
    system_prompt, user_prompt = build_audit_prompt(
        material_set, target_root, config.property_id
    )
    metadata = {
        "created_at": utc_now(),
        "audit_mode": "property-directed",
        "material_set": material_set.name,
        "material_files": list(
            material_set.relative_files_for_property(config.property_id)
        ),
        "property_id": config.property_id,
        "target_root": str(target_root),
        "allow_tests": config.allow_tests,
        "max_turns": config.max_turns,
        "max_tool_calls": config.max_tool_calls,
        "dry_run": config.dry_run,
        "model": model_metadata,
    }
    if shared_context is not None:
        metadata.update(shared_context.metadata())
        user_prompt += "\n" + SHARED_EVIDENCE_INSTRUCTION
    return _run_prompt(
        client,
        config,
        run_label=config.property_id,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata=metadata,
        workspace=shared_context,
    )


def run_baseline_episode(
    material_set: MaterialSet,
    client: ChatClient | None,
    config: BaselineRunConfig,
    *,
    model_metadata: dict[str, Any],
    shared_context: SharedAuditContext | None = None,
) -> RunResult:
    target_root = config.target_root.resolve()
    system_prompt, user_prompt = build_baseline_prompt(material_set, target_root)
    run_label = f"baseline-{config.episode:02d}"
    metadata = {
        "created_at": utc_now(),
        "audit_mode": "matched-no-property",
        "baseline_episode": config.episode,
        "material_set": material_set.name,
        "material_files": list(material_set.relative_common_files),
        "target_root": str(target_root),
        "allow_tests": config.allow_tests,
        "max_turns": config.max_turns,
        "max_tool_calls": config.max_tool_calls,
        "dry_run": config.dry_run,
        "model": model_metadata,
    }
    if shared_context is not None:
        metadata.update(shared_context.metadata())
        user_prompt += "\n" + SHARED_EVIDENCE_INSTRUCTION
    return _run_prompt(
        client,
        config,
        run_label=run_label,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        metadata=metadata,
        workspace=shared_context,
    )


def _run_prompt(
    client: ChatClient | None,
    config: RunConfig | BaselineRunConfig,
    *,
    run_label: str,
    system_prompt: str,
    user_prompt: str,
    metadata: dict[str, Any],
    workspace: SourceWorkspace | SharedAuditContext | None = None,
) -> RunResult:
    target_root = config.target_root.resolve()
    if workspace is None:
        workspace = SourceWorkspace(target_root, allow_tests=config.allow_tests)
    elif workspace.target_root != target_root:
        raise AuditRunError(
            "shared evidence context target does not match the audit target"
        )
    user_prompt += (
        f"\nRUN BUDGET: at most {config.max_turns} model turns and "
        f"{config.max_tool_calls} source-tool calls. Reserve enough budget for "
        "the final Candidate-v0 JSON object. The final model turn is output-only and "
        "has no tools.\n"
    )
    if config.allow_tests:
        user_prompt += (
            "TOOL AVAILABILITY: source inspection and bounded existing Go tests "
            "are available. Arbitrary commands and new executable harnesses are "
            "not available. Static evidence may still support `candidate_found`.\n"
        )
    else:
        user_prompt += (
            "TOOL AVAILABILITY: only source listing, reading, and search are "
            "available. Test execution, arbitrary commands, and executable "
            "harnesses are unavailable. Do not spend turns planning them. Static "
            "evidence may support `candidate_found`; lack of execution alone does "
            "not require `insufficient_evidence`.\n"
        )
    run_directory = create_run_directory(config.run_root.resolve(), run_label)
    events = EventLog(run_directory / "events.jsonl")
    write_json(run_directory / "request.json", metadata)
    (run_directory / "prompt.md").write_text(
        f"# System\n\n{system_prompt}\n\n# User\n\n{user_prompt}",
        encoding="utf-8",
    )

    if config.dry_run:
        events.append("dry_run_prepared")
        write_evidence_manifest(run_directory)
        return RunResult(run_directory, None, {}, 0, 0, True, None, None, None)
    if client is None:
        raise AuditRunError("a chat client is required unless dry_run is enabled")
    if config.max_turns <= 0:
        raise AuditRunError("max_turns must be positive")
    if config.max_tool_calls <= 0:
        raise AuditRunError("max_tool_calls must be positive")

    messages: list[dict[str, Any]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tools = workspace.tool_definitions()
    total_usage: dict[str, int] = {}
    tool_call_count = 0
    start = time.monotonic()

    try:
        for turn in range(1, config.max_turns + 1):
            final_output_turn = turn == config.max_turns
            if turn == config.max_turns - 2 and not final_output_turn:
                messages.append({"role": "user", "content": LATE_BUDGET_NOTICE})
                events.append(
                    "budget_notice",
                    turn=turn,
                    remaining_turns=config.max_turns - turn + 1,
                )
            if final_output_turn:
                messages.append(
                    {"role": "user", "content": FINAL_CANDIDATE_INSTRUCTION}
                )
                events.append("final_candidate_turn", turn=turn, tools_enabled=False)

            request_tools = [] if final_output_turn else tools
            events.append(
                "llm_request",
                turn=turn,
                message_count=len(messages),
                tools_enabled=bool(request_tools),
                remaining_turns=config.max_turns - turn + 1,
            )
            response = client.create_chat_completion(messages, request_tools)
            _add_usage(total_usage, response.usage)
            events.append(
                "llm_response",
                turn=turn,
                response_id=response.response_id,
                model=response.model,
                finish_reason=response.finish_reason,
                usage=response.usage,
                content=response.content,
                reasoning_content=response.reasoning_content,
                tool_calls=list(response.tool_calls),
            )

            if response.tool_calls:
                if final_output_turn:
                    raise AuditRunError(
                        "model requested tools during the final Candidate-v0 turn"
                    )
                messages.append(response.assistant_message())
                for call in response.tool_calls:
                    if tool_call_count >= config.max_tool_calls:
                        raise AuditRunError(
                            f"agent exceeded max_tool_calls={config.max_tool_calls}"
                        )
                    call_id = str(call.get("id") or "")
                    function = call.get("function")
                    if not isinstance(function, dict):
                        name = ""
                        arguments = "{}"
                    else:
                        name = str(function.get("name") or "")
                        raw_arguments = function.get("arguments") or "{}"
                        arguments = (
                            json.dumps(raw_arguments)
                            if isinstance(raw_arguments, dict)
                            else str(raw_arguments)
                        )
                    result = workspace.execute_json(name, arguments)
                    tool_call_count += 1
                    events.append(
                        "tool_result",
                        turn=turn,
                        tool_call_id=call_id,
                        tool=name,
                        arguments=arguments,
                        result=result,
                    )
                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": call_id,
                            "content": result,
                        }
                    )
                continue

            if response.finish_reason == "length":
                raise AuditRunError("model output was truncated by max_tokens")
            if not response.content.strip():
                raise AuditRunError(
                    f"model returned no final content (finish_reason={response.finish_reason!r})"
                )

            raw_candidate = response.content.strip()
            (run_directory / "response.md").write_text(
                raw_candidate + "\n", encoding="utf-8"
            )
            evidence_manifest = build_evidence_manifest(run_directory)
            write_json(run_directory / "evidence-manifest.json", evidence_manifest)
            candidate_artifacts = write_candidate_artifacts(
                run_directory,
                raw_candidate,
                target_root=target_root,
                evidence_manifest=evidence_manifest,
                audit_mode=str(metadata.get("audit_mode") or ""),
                expected_property_id=(
                    str(metadata["property_id"])
                    if metadata.get("property_id") is not None
                    else None
                ),
            )
            write_json(
                run_directory / "summary.json",
                {
                    "completed_at": utc_now(),
                    "duration_seconds": round(time.monotonic() - start, 3),
                    "turns": turn,
                    "tool_calls": tool_call_count,
                    "usage": total_usage,
                    "response_file": "response.md",
                    "response_format": "candidate-v0-json",
                    "candidate_status": candidate_artifacts.status,
                    "candidate_format_valid": candidate_artifacts.format_valid,
                    "candidate_provenance_valid": candidate_artifacts.provenance_valid,
                    "parsed_candidate_file": candidate_artifacts.parsed_file,
                    "source_cost": evidence_manifest.get("source_cost", {}),
                },
            )
            return RunResult(
                run_directory,
                raw_candidate,
                total_usage,
                turn,
                tool_call_count,
                False,
                candidate_artifacts.status,
                candidate_artifacts.format_valid,
                candidate_artifacts.provenance_valid,
            )

        raise AuditRunError(f"agent exceeded max_turns={config.max_turns}")
    except Exception as exc:
        error_type = type(exc).__name__
        write_json(
            run_directory / "error.json",
            {
                "failed_at": utc_now(),
                "error_type": error_type,
                "error": str(exc),
                "duration_seconds": round(time.monotonic() - start, 3),
                "tool_calls": tool_call_count,
                "usage": total_usage,
            },
        )
        events.append("run_failed", error_type=error_type, error=str(exc))
        try:
            write_evidence_manifest(run_directory)
        except Exception as evidence_exc:
            events.append(
                "evidence_manifest_failed",
                error_type=type(evidence_exc).__name__,
                error=str(evidence_exc),
            )
        if isinstance(exc, AuditRunError):
            exc.run_directory = run_directory
            raise
        raise AuditRunError(str(exc), run_directory) from exc
