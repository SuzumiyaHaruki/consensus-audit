from __future__ import annotations

import argparse
import copy
import json
from pathlib import Path

from .preparation import PreparationConfig, extract_requirements, locate_code
from .preparation_validation import review_summary, validate_requirements
from .prepared import run_prepared
from .source_materials import load_object, require, validate_bundle


def add_preparation_parsers(subparsers: argparse._SubParsersAction, root: Path) -> None:
    review = subparsers.add_parser("validate-requirements", help="Check edited requirements and summarize pending items")
    review.add_argument("--requirements", type=Path, required=True)
    review.add_argument("--materials", type=Path, required=True)
    for name, help_text in (("extract-requirements", "Extract a pending draft from source material blocks"),
                            ("locate-code", "Locate accepted requirements in an explicit target"),
                            ("prepared", "Audit accepted requirements grouped by operation")):
        parser = subparsers.add_parser(name, help=help_text)
        parser.add_argument("--materials", type=Path, required=True)
        if name != "extract-requirements":
            parser.add_argument("--requirements", type=Path, required=True)
            parser.add_argument("--target-root", type=Path, required=True)
        if name == "prepared":
            parser.add_argument("--code-map", type=Path, required=True)
        parser.add_argument("--run-root", type=Path, default=root / "runs")
        parser.add_argument("--dry-run", action="store_true")
        parser.add_argument("--api-key-file", type=Path)
        parser.add_argument("--model", default="deepseek-v4-flash")
        parser.add_argument("--base-url", default="https://api.deepseek.com")
        parser.add_argument("--reasoning-effort", choices=("low", "high", "max"), default="high")
        parser.add_argument("--thinking", action=argparse.BooleanOptionalAction, default=True)
        parser.add_argument("--max-output-tokens", type=int, default=32_768)
        parser.add_argument("--max-turns", type=int, default=12)
        parser.add_argument("--max-tool-calls", type=int, default=40)
        parser.add_argument("--request-timeout", type=float, default=600.0)
        parser.add_argument("--max-retries", type=int, default=2)
        for price in ("input", "cached-input", "output"):
            parser.add_argument(f"--{price}-price", type=float,
                                help="Optional cost per million tokens, using one consistent currency")


def preparation_command(args: argparse.Namespace) -> int:
    from .cli import _client_and_model_metadata
    from .preparation import check_map_inputs
    from .workspace import SourceWorkspace

    bundle = load_object(args.materials)
    validate_bundle(bundle)
    requirements = None
    if args.command != "extract-requirements":
        requirements = load_object(args.requirements)
        validate_requirements(requirements, bundle)
    if args.command == "validate-requirements":
        print(json.dumps(review_summary(requirements, bundle), indent=2))
        return 0
    require(args.max_turns > 0 and args.max_tool_calls > 0, "budgets must be positive")
    prices = {"input": args.input_price, "cached_input": args.cached_input_price, "output": args.output_price}
    require(all(p is None or p >= 0 for p in prices.values()), "prices cannot be negative")
    if args.command != "extract-requirements":
        SourceWorkspace(args.target_root)
    if args.command == "prepared":
        check_map_inputs(args.code_map, requirements, bundle, args.target_root)
    # Validate inputs before constructing the client; dry-run never reads a key.
    client_args = copy.copy(args)
    if requirements is not None and not any(r["review_status"] == "accepted" for r in requirements["requirements"]):
        client_args.dry_run = True  # No model work exists yet; do not read a key.
    client, model = _client_and_model_metadata(client_args)
    model["prices_per_million"] = prices
    config = PreparationConfig(args.run_root, args.spec_root, args.dry_run, args.max_turns, args.max_tool_calls)
    if args.command == "extract-requirements":
        run = extract_requirements(bundle, client, config, model)
    elif args.command == "locate-code":
        run = locate_code(requirements, bundle, args.target_root, client, config, model)
    else:
        run = run_prepared(requirements, bundle, args.code_map, args.target_root, client, config, model)
    print(run)
    summary = load_object(run / "summary.json")
    return 2 if summary["status"] in {"partial", "failed", "needs_review"} else 0
