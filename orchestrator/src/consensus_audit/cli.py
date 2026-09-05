from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Sequence

from .audit import audit
from .deepseek import DeepSeekClient, DeepSeekConfig, DeepSeekError, read_api_key_file
from .preparation import check_map_inputs, extract_requirements, locate_code
from .preparation_validation import review_summary, validate_requirements
from .runner import RunConfig
from .source_materials import MaterialError, load_object, require, validate_bundle
from .workspace import SourceWorkspace, WorkspaceError


def project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="consensus-audit", description="Extract, review, locate and audit consensus requirements.")
    parser.add_argument("--spec-root", type=Path, default=project_root() / "audit-specs")
    commands = parser.add_subparsers(dest="command", required=True)
    review = commands.add_parser("validate-requirements", help="Check edited requirements and display pending items")
    review.add_argument("--requirements", type=Path, required=True)
    review.add_argument("--materials", type=Path, required=True)
    for name in ("extract-requirements", "locate-code", "audit"):
        sub = commands.add_parser(name)
        sub.add_argument("--materials", type=Path, required=True)
        if name != "extract-requirements":
            sub.add_argument("--requirements", type=Path, required=True)
            sub.add_argument("--target-root", type=Path, required=True)
        if name == "audit":
            sub.add_argument("--code-map", type=Path, required=True)
        sub.add_argument("--run-root", type=Path, default=project_root() / "runs")
        sub.add_argument("--dry-run", action="store_true")
        sub.add_argument("--api-key-file", type=Path)
        sub.add_argument("--model", default="deepseek-v4-flash")
        sub.add_argument("--base-url", default="https://api.deepseek.com")
        sub.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
        sub.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="high")
        sub.add_argument("--max-output-tokens", type=int, default=32_768)
        sub.add_argument("--max-turns", type=int, default=12)
        sub.add_argument("--max-tool-calls", type=int, default=40)
        sub.add_argument("--request-timeout", type=float, default=600.0)
        sub.add_argument("--max-retries", type=int, default=2)
        for price in ("input", "cached-input", "output"):
            sub.add_argument(f"--{price}-price", type=float, help="Cost per million tokens in one consistent currency")
    return parser


def execute(args: argparse.Namespace) -> int:
    bundle = load_object(args.materials)
    validate_bundle(bundle)
    requirements = None
    if args.command != "extract-requirements":
        requirements = load_object(args.requirements)
        validate_requirements(requirements, bundle)
    if args.command == "validate-requirements":
        print(json.dumps(review_summary(requirements, bundle), indent=2))
        return 0
    require(args.max_turns > 0 and args.max_tool_calls >= 0, "invalid model/tool budget")
    require(args.max_output_tokens > 0 and args.request_timeout > 0 and args.max_retries >= 0,
            "invalid model request settings")
    prices = {"input": args.input_price, "cached_input": args.cached_input_price, "output": args.output_price}
    require(all(p is None or p >= 0 for p in prices.values()), "prices cannot be negative")
    if requirements is not None:
        SourceWorkspace(args.target_root)
    if args.command == "audit":
        check_map_inputs(args.code_map, requirements, bundle, args.target_root)
    model = {"provider": "deepseek-official", "model": args.model, "base_url": args.base_url,
             "thinking": args.thinking, "reasoning_effort": args.reasoning_effort,
             "max_output_tokens": args.max_output_tokens, "request_timeout": args.request_timeout,
             "max_retries": args.max_retries, "prices_per_million": prices}
    client = None
    has_work = requirements is None or any(r["review_status"] == "accepted" for r in requirements["requirements"])
    if not args.dry_run and has_work:
        require(args.api_key_file is not None, "--api-key-file is required unless --dry-run is enabled")
        client = DeepSeekClient(DeepSeekConfig(api_key=read_api_key_file(args.api_key_file), base_url=args.base_url,
            model=args.model, thinking=args.thinking, reasoning_effort=args.reasoning_effort,
            max_tokens=args.max_output_tokens, timeout_seconds=args.request_timeout, max_retries=args.max_retries))
    config = RunConfig(args.run_root, args.spec_root, args.dry_run, args.max_turns, args.max_tool_calls)
    if args.command == "extract-requirements":
        run = extract_requirements(bundle, client, config, model)
    elif args.command == "locate-code":
        run = locate_code(requirements, bundle, args.target_root, client, config, model)
    else:
        run = audit(requirements, bundle, args.code_map, args.target_root, client, config, model)
    print(run)
    return 2 if load_object(run / "summary.json")["status"] in {"partial", "failed", "needs_review"} else 0


def main(argv: Sequence[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    try:
        raise SystemExit(execute(args))
    except (MaterialError, WorkspaceError, DeepSeekError, OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc
