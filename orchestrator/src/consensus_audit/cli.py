from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .artifacts import create_run_directory, utc_now, write_json
from .deepseek import (
    DeepSeekClient,
    DeepSeekConfig,
    DeepSeekError,
    read_api_key_file,
)
from .evidence import EvidenceError, write_evidence_manifest
from .materials import (
    MaterialError,
    MaterialSet,
    list_material_sets,
    load_material_set,
)
from .runner import (
    AuditRunError,
    BaselineRunConfig,
    RunConfig,
    RunResult,
    run_audit,
    run_baseline_episode,
)
from .shared_context import SharedAuditContext


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _add_execution_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--target-root", required=True, type=Path)
    parser.add_argument("--run-root", type=Path, default=project_root() / "runs")
    parser.add_argument("--model", default="deepseek-v4-flash")
    parser.add_argument("--base-url", default="https://api.deepseek.com")
    parser.add_argument(
        "--reasoning-effort", choices=("low", "high", "max"), default="high"
    )
    parser.add_argument(
        "--thinking",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    parser.add_argument("--max-output-tokens", type=int, default=32_768)
    parser.add_argument("--max-turns", type=int, default=24)
    parser.add_argument("--max-tool-calls", type=int, default=80)
    parser.add_argument(
        "--context-mode",
        choices=("isolated", "shared-evidence"),
        default="isolated",
        help=(
            "isolated creates independent source workspaces; shared-evidence reuses "
            "a mechanical repository index and raw source evidence while keeping "
            "model reasoning contexts separate"
        ),
    )
    parser.add_argument("--request-timeout", type=float, default=600.0)
    parser.add_argument("--max-retries", type=int, default=2)
    parser.add_argument("--allow-tests", action="store_true")
    parser.add_argument(
        "--api-key-file",
        type=Path,
        help="UTF-8 text file containing one raw DeepSeek API key",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="assemble and save the prompt without calling DeepSeek",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="consensus-audit",
        description="Run consensus implementation audits.",
    )
    parser.add_argument(
        "--spec-root",
        type=Path,
        default=project_root() / "audit-specs",
        help="audit specification root (default: project audit-specs directory)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-materials", help="List available material sets")

    evidence = subparsers.add_parser(
        "build-evidence", help="Generate evidence-manifest.json for an existing run"
    )
    evidence.add_argument("--run-directory", required=True, type=Path)

    run = subparsers.add_parser("run", help="Run one independent audit")
    run.add_argument("--material-set", default="raft-etcd-v1")
    property_selection = run.add_mutually_exclusive_group(required=True)
    property_selection.add_argument(
        "--property",
        action="append",
        dest="property_ids",
        help="property ID; repeat this option to run multiple isolated audits",
    )
    property_selection.add_argument(
        "--all-properties",
        action="store_true",
        help="run every property in catalog order",
    )
    property_selection.add_argument(
        "--properties-file",
        type=Path,
        help="UTF-8 text file with one property ID per line",
    )
    _add_execution_arguments(run)

    baseline = subparsers.add_parser(
        "baseline", help="Run independent unguided baseline episodes"
    )
    baseline.add_argument("--material-set", default="raft-etcd-v1")
    baseline.add_argument(
        "--episodes",
        type=int,
        help="independent episodes (default: property count in material set)",
    )
    _add_execution_arguments(baseline)
    return parser


def _selected_property_ids(
    args: argparse.Namespace, material_set: MaterialSet
) -> list[str]:
    available = list(material_set.property_ids)
    if args.all_properties:
        selected = available
    elif args.properties_file is not None:
        try:
            lines = args.properties_file.expanduser().read_text(encoding="utf-8").splitlines()
        except OSError as exc:
            raise MaterialError(
                f"cannot read properties file {args.properties_file}: {exc}"
            ) from exc
        selected = [line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#")]
    else:
        selected = list(args.property_ids or [])

    unique: list[str] = []
    for property_id in selected:
        if property_id not in unique:
            unique.append(property_id)
    if not unique:
        raise MaterialError("no properties were selected")
    for property_id in unique:
        material_set.property_file(property_id)
    return unique


def _baseline_episode_count(
    args: argparse.Namespace, material_set: MaterialSet
) -> int:
    episodes = (
        len(material_set.property_ids) if args.episodes is None else args.episodes
    )
    if episodes <= 0:
        raise MaterialError("--episodes must be positive")
    return episodes


def _print_run_result(result: RunResult) -> None:
    print(
        json.dumps(
            {
                "turns": result.turns,
                "tool_calls": result.tool_calls,
                "usage": result.usage,
                "response_file": "response.md" if result.report else None,
            },
            ensure_ascii=False,
        ),
        file=sys.stderr,
    )


def _client_and_model_metadata(
    args: argparse.Namespace,
) -> tuple[DeepSeekClient | None, dict[str, object]]:
    metadata: dict[str, object] = {
        "provider": "deepseek-official",
        "base_url": args.base_url,
        "model": args.model,
        "thinking": args.thinking,
        "reasoning_effort": args.reasoning_effort,
        "max_output_tokens": args.max_output_tokens,
        "request_timeout_seconds": args.request_timeout,
        "max_retries": args.max_retries,
        "max_turns": args.max_turns,
        "max_tool_calls": args.max_tool_calls,
    }
    if args.dry_run:
        return None, metadata
    if args.api_key_file is None:
        raise DeepSeekError("--api-key-file is required unless --dry-run is enabled")
    api_key = read_api_key_file(args.api_key_file)
    client = DeepSeekClient(
        DeepSeekConfig(
            api_key=api_key,
            base_url=args.base_url,
            model=args.model,
            thinking=args.thinking,
            reasoning_effort=args.reasoning_effort,
            max_tokens=args.max_output_tokens,
            timeout_seconds=args.request_timeout,
            max_retries=args.max_retries,
        )
    )
    return client, metadata


def _create_shared_context(
    args: argparse.Namespace,
    target_root: Path,
    suite_directory: Path,
) -> SharedAuditContext | None:
    if args.context_mode != "shared-evidence":
        return None
    return SharedAuditContext(
        target_root,
        suite_directory / "shared-context",
        allow_tests=args.allow_tests,
    )


def _run_command(args: argparse.Namespace) -> int:
    material_set = load_material_set(args.spec_root, args.material_set)
    property_ids = _selected_property_ids(args, material_set)
    target_root = args.target_root.resolve()
    if not target_root.is_dir():
        raise MaterialError(f"target root is not a directory: {target_root}")

    client, model_metadata = _client_and_model_metadata(args)

    def execute_one(
        property_id: str,
        run_root: Path,
        shared_context: SharedAuditContext | None = None,
    ):
        return run_audit(
            material_set,
            client,
            RunConfig(
                property_id=property_id,
                target_root=target_root,
                run_root=run_root,
                max_turns=args.max_turns,
                max_tool_calls=args.max_tool_calls,
                allow_tests=args.allow_tests,
                dry_run=args.dry_run,
            ),
            model_metadata=model_metadata,
            shared_context=shared_context,
        )

    if len(property_ids) == 1 and args.context_mode == "isolated":
        result = execute_one(property_ids[0], args.run_root)
        print(result.run_directory)
        if result.dry_run:
            print("dry run: prompt assembled; no API request was sent", file=sys.stderr)
        else:
            _print_run_result(result)
        return 0

    batch_label = "batch" if args.context_mode == "isolated" else "shared-evidence-batch"
    batch_directory = create_run_directory(args.run_root.resolve(), batch_label)
    shared_context = _create_shared_context(args, target_root, batch_directory)
    write_json(
        batch_directory / "batch-request.json",
        {
            "created_at": utc_now(),
            "material_set": material_set.name,
            "target_root": str(target_root),
            "property_ids": property_ids,
            "execution": (
                "sequential-isolated-contexts"
                if shared_context is None
                else "sequential-isolated-reasoning-shared-mechanical-evidence"
            ),
            "context_mode": args.context_mode,
            "shared_context": shared_context.metadata() if shared_context else None,
            "dry_run": args.dry_run,
            "model": model_metadata,
        },
    )
    entries: list[dict[str, object]] = []
    aggregate_usage: dict[str, int] = {}
    failures = 0
    for index, property_id in enumerate(property_ids, start=1):
        print(
            f"[{index}/{len(property_ids)}] auditing {property_id} in a fresh context",
            file=sys.stderr,
        )
        try:
            result = execute_one(property_id, batch_directory, shared_context)
        except AuditRunError as exc:
            failures += 1
            entries.append(
                {
                    "property_id": property_id,
                    "status": "failed",
                    "run_directory": str(exc.run_directory) if exc.run_directory else None,
                    "error": str(exc),
                }
            )
            print(f"[{property_id}] failed: {exc}", file=sys.stderr)
            continue

        for key, value in result.usage.items():
            aggregate_usage[key] = aggregate_usage.get(key, 0) + value
        entries.append(
            {
                "property_id": property_id,
                "status": "prepared" if result.dry_run else "completed",
                "run_directory": str(result.run_directory),
                "turns": result.turns,
                "tool_calls": result.tool_calls,
                "usage": result.usage,
            }
        )
        if not result.dry_run:
            _print_run_result(result)

    shared_summary = shared_context.finalize() if shared_context else None
    write_json(
        batch_directory / "batch-summary.json",
        {
            "completed_at": utc_now(),
            "material_set": material_set.name,
            "execution": (
                "sequential-isolated-contexts"
                if shared_context is None
                else "sequential-isolated-reasoning-shared-mechanical-evidence"
            ),
            "context_mode": args.context_mode,
            "shared_evidence": shared_summary,
            "properties": entries,
            "aggregate_usage": aggregate_usage,
            "completed": len(property_ids) - failures,
            "failed": failures,
        },
    )
    print(batch_directory)
    if args.dry_run:
        print(
            "dry run: prompts assembled; no API requests were sent",
            file=sys.stderr,
        )
    return 2 if failures else 0


def _baseline_command(args: argparse.Namespace) -> int:
    material_set = load_material_set(args.spec_root, args.material_set)
    episodes = _baseline_episode_count(args, material_set)
    target_root = args.target_root.resolve()
    if not target_root.is_dir():
        raise MaterialError(f"target root is not a directory: {target_root}")

    client, model_metadata = _client_and_model_metadata(args)
    suite_directory = create_run_directory(
        args.run_root.resolve(), "baseline-batch"
    )
    shared_context = _create_shared_context(args, target_root, suite_directory)
    write_json(
        suite_directory / "baseline-request.json",
        {
            "created_at": utc_now(),
            "audit_mode": "unguided-baseline",
            "target_root": str(target_root),
            "material_set": material_set.name,
            "episodes": episodes,
            "execution": (
                "sequential-isolated-contexts"
                if shared_context is None
                else "sequential-isolated-reasoning-shared-mechanical-evidence"
            ),
            "context_mode": args.context_mode,
            "shared_context": shared_context.metadata() if shared_context else None,
            "per_episode_max_turns": args.max_turns,
            "total_max_turns": episodes * args.max_turns,
            "per_episode_max_tool_calls": args.max_tool_calls,
            "total_max_tool_calls": episodes * args.max_tool_calls,
            "material_files": list(material_set.relative_baseline_files),
            "dry_run": args.dry_run,
            "model": model_metadata,
        },
    )

    entries: list[dict[str, object]] = []
    aggregate_usage: dict[str, int] = {}
    failures = 0
    for episode in range(1, episodes + 1):
        print(
            f"[{episode}/{episodes}] running unguided baseline in a fresh context",
            file=sys.stderr,
        )
        try:
            result = run_baseline_episode(
                material_set,
                client,
                BaselineRunConfig(
                    episode=episode,
                    target_root=target_root,
                    run_root=suite_directory,
                    max_turns=args.max_turns,
                    max_tool_calls=args.max_tool_calls,
                    allow_tests=args.allow_tests,
                    dry_run=args.dry_run,
                ),
                model_metadata=model_metadata,
                shared_context=shared_context,
            )
        except AuditRunError as exc:
            failures += 1
            entries.append(
                {
                    "episode": episode,
                    "status": "failed",
                    "run_directory": str(exc.run_directory) if exc.run_directory else None,
                    "error": str(exc),
                }
            )
            print(f"[baseline-{episode:02d}] failed: {exc}", file=sys.stderr)
            continue

        for key, value in result.usage.items():
            aggregate_usage[key] = aggregate_usage.get(key, 0) + value
        entries.append(
            {
                "episode": episode,
                "status": "prepared" if result.dry_run else "completed",
                "run_directory": str(result.run_directory),
                "turns": result.turns,
                "tool_calls": result.tool_calls,
                "usage": result.usage,
            }
        )
        if not result.dry_run:
            _print_run_result(result)

    shared_summary = shared_context.finalize() if shared_context else None
    write_json(
        suite_directory / "baseline-summary.json",
        {
            "completed_at": utc_now(),
            "audit_mode": "unguided-baseline",
            "execution": (
                "sequential-isolated-contexts"
                if shared_context is None
                else "sequential-isolated-reasoning-shared-mechanical-evidence"
            ),
            "context_mode": args.context_mode,
            "shared_evidence": shared_summary,
            "episodes": entries,
            "aggregate_usage": aggregate_usage,
            "completed": episodes - failures,
            "failed": failures,
        },
    )
    print(suite_directory)
    if args.dry_run:
        print(
            "dry run: baseline prompts assembled; no API requests were sent",
            file=sys.stderr,
        )
    return 2 if failures else 0


def main(argv: Sequence[str] | None = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "list-materials":
            print(
                json.dumps(
                    list_material_sets(args.spec_root),
                    ensure_ascii=False,
                    indent=2,
                )
            )
            raise SystemExit(0)
        if args.command == "build-evidence":
            print(write_evidence_manifest(args.run_directory))
            raise SystemExit(0)
        if args.command == "run":
            raise SystemExit(_run_command(args))
        if args.command == "baseline":
            raise SystemExit(_baseline_command(args))
        parser.error(f"unsupported command: {args.command}")
    except (MaterialError, DeepSeekError, EvidenceError, AuditRunError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
