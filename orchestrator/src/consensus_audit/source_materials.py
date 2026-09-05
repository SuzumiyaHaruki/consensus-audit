"""Small, explicit material bundles; no access to an audit target or answers."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

class MaterialError(ValueError):
    """Invalid material or stage input/output."""


SOURCE_KINDS = ("protocol", "extension", "experiment_config", "environment")
REVIEW_STATES = ("pending", "accepted", "rejected")


def load_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise MaterialError(f"cannot read JSON object {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise MaterialError(f"expected a JSON object: {path}")
    return value


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MaterialError(message)


def nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def validate_bundle(bundle: dict[str, Any]) -> None:
    require(bundle.get("schema_version") == "source-bundle/v1", "invalid source bundle version")
    sources = bundle.get("sources")
    blocks = bundle.get("blocks")
    require(isinstance(sources, list) and bool(sources), "sources must be nonempty")
    require(isinstance(blocks, list) and bool(blocks), "blocks must be nonempty")
    ids = set()
    for source in sources:
        require(isinstance(source, dict), "source must be an object")
        require(nonempty(source.get("id")) and source["id"] not in ids, "duplicate/invalid source ID")
        ids.add(source["id"])
        require(source.get("category") in SOURCE_KINDS, "unsupported extraction source category")
        for field in ("location", "version", "license", "scope"):
            require(nonempty(source.get(field)), f"source {source['id']} lacks {field}")
    seen = set()
    for block in blocks:
        require(isinstance(block, dict), "block must be an object")
        require(nonempty(block.get("id")) and block["id"] not in seen, "duplicate/invalid block ID")
        seen.add(block["id"])
        require(isinstance(block.get("source_id"), str) and block["source_id"] in ids,
                "block refers to an unknown source")
        for field in ("section", "text"):
            require(nonempty(block.get(field)), f"block lacks {field}")
        require(type(block.get("source_start_line")) is int and block["source_start_line"] > 0,
                "block lacks original line coordinates")
        require(block.get("review_status") in REVIEW_STATES, "block review_status is invalid")
    require(isinstance(bundle.get("unresolved", []), list), "bundle unresolved must be an array")


def validate_refs(refs: Any, bundle: dict[str, Any], *, allow_empty: bool = False) -> None:
    require(isinstance(refs, list) and (allow_empty or bool(refs)), "source_refs must be a reference array")
    blocks = {b["id"]: b for b in bundle["blocks"]}
    for ref in refs:
        require(isinstance(ref, dict), "source reference must be an object")
        block_id = ref.get("block_id")
        require(isinstance(block_id, str) and block_id in blocks, f"unknown source block: {block_id}")
        start, end = ref.get("start_line"), ref.get("end_line")
        require(type(start) is int and type(end) is int and 1 <= start <= end <= len(blocks[block_id]["text"].splitlines()),
                f"invalid source interval in {block_id}")


def numbered_block(block: dict[str, Any]) -> dict[str, Any]:
    return {**block, "text": "\n".join(f"{n}: {line}" for n, line in enumerate(block["text"].splitlines(), 1))}


def block_index(bundle: dict[str, Any]) -> list[dict[str, Any]]:
    return [{k: v for k, v in b.items() if k != "text"} for b in bundle["blocks"]]


def referenced_blocks(requirements: list[dict[str, Any]], bundle: dict[str, Any]) -> list[dict[str, Any]]:
    selected = {ref["block_id"] for r in requirements for field in ("source_refs", "definitions")
                for ref in r.get(field, [])}
    # Scope and fault model are always included without rewriting their content.
    configs = {s["id"] for s in bundle["sources"] if s["category"] in {"experiment_config", "environment"}}
    return [numbered_block(b) for b in bundle["blocks"] if b["id"] in selected or b["source_id"] in configs]


class MaterialWorkspace:
    def __init__(self, bundle: dict[str, Any]):
        self.blocks = {b["id"]: b for b in bundle["blocks"]}

    def tool_definitions(self) -> list[dict[str, Any]]:
        return [{"type": "function", "function": {
            "name": "read_material", "description": "Read a source block from the supplied material index.",
            "parameters": {"type": "object", "properties": {"block_id": {"type": "string"}},
                           "required": ["block_id"], "additionalProperties": False}}}]

    def execute_json(self, name: str, arguments: str) -> str:
        try:
            require(name == "read_material", "only read_material is available during extraction")
            args = json.loads(arguments)
            require(isinstance(args, dict) and set(args) == {"block_id"}, "expected only block_id")
            block = self.blocks[args["block_id"]]
            result = {"ok": True, "result": numbered_block(block)}
        except (MaterialError, ValueError, KeyError, TypeError) as exc:
            result = {"ok": False, "error": str(exc)}
        return json.dumps(result)


def split_text(source_id: str, text: str, *, page: int | None = None,
               section: str | None = None, line_offset: int = 0) -> list[dict[str, Any]]:
    """Keep original lines; split at section headings, never model-selected topics."""
    lines = text.splitlines()
    heading = re.compile(r"^(?:#{1,6}\s+|\d+(?:\.\d+)*\s+[A-Z]|\\(?:sub)*section\*?\{)")
    starts = sorted({0, *(i for i, line in enumerate(lines) if heading.match(line.strip()))})
    result = []
    title = section or "Preamble"
    for pos, start in enumerate(starts):
        end = starts[pos + 1] if pos + 1 < len(starts) else len(lines)
        body = "\n".join(lines[start:end])
        if not body.strip():
            continue
        if heading.match(lines[start].strip()):
            title = lines[start].strip()
        result.append({"id": f"{source_id}:p{page or 0}:l{line_offset + start + 1}",
                       "source_id": source_id, "section": title, "page": page,
                       "source_start_line": line_offset + start + 1,
                       "text": body, "review_status": "pending"})
    return result
