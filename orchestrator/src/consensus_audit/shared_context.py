from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .artifacts import utc_now, write_json
from .workspace import SourceWorkspace


_FUNCTION = re.compile(
    r"^\s*func\s+(?:\([^\n)]*\)\s*)?([A-Za-z_][A-Za-z0-9_]*)\s*\("
)
_TYPE = re.compile(r"^\s*type\s+([A-Za-z_][A-Za-z0-9_]*)\b")
_CONST_OR_VAR = re.compile(r"^\s*(?:const|var)\s+([A-Za-z_][A-Za-z0-9_]*)\b")


@dataclass(frozen=True)
class RepositoryIndex:
    """A mechanical navigation index, deliberately free of semantic conclusions."""

    target_root: Path
    files: tuple[str, ...]
    symbols: tuple[dict[str, Any], ...]

    @classmethod
    def build(cls, target_root: Path) -> "RepositoryIndex":
        root = target_root.resolve()
        files: list[str] = []
        symbols: list[dict[str, Any]] = []
        for current, directories, names in os.walk(root):
            current_path = Path(current)
            directories[:] = sorted(name for name in directories if name != ".git")
            for name in sorted(names):
                path = current_path / name
                if not path.is_file():
                    continue
                try:
                    relative = path.resolve().relative_to(root).as_posix()
                except ValueError:
                    continue
                files.append(relative)
                if path.suffix != ".go":
                    continue
                try:
                    lines = path.read_text(encoding="utf-8").splitlines()
                except (OSError, UnicodeDecodeError):
                    continue
                for line_number, line in enumerate(lines, start=1):
                    matched = _FUNCTION.match(line)
                    kind = "function"
                    if matched is None:
                        matched = _TYPE.match(line)
                        kind = "type"
                    if matched is None:
                        matched = _CONST_OR_VAR.match(line)
                        kind = "declaration"
                    if matched is None:
                        continue
                    symbols.append(
                        {
                            "path": relative,
                            "line": line_number,
                            "kind": kind,
                            "name": matched.group(1),
                            "declaration": line.strip(),
                        }
                    )
        return cls(root, tuple(files), tuple(symbols))

    def as_json(self) -> dict[str, Any]:
        return {
            "schema_version": "repository-index/v1",
            "created_at": utc_now(),
            "target_root": str(self.target_root),
            "scope": "mechanical file and Go declaration locations only; no semantic conclusions",
            "files": list(self.files),
            "symbols": list(self.symbols),
        }

    def query(
        self,
        *,
        query: str = "",
        path: str = "",
        kind: str = "",
        max_results: int = 100,
    ) -> dict[str, Any]:
        limit = max(1, min(300, max_results if isinstance(max_results, int) else 100))
        query_folded = query.casefold().strip()
        path_prefix = path.strip().lstrip("./")
        kind_folded = kind.casefold().strip()

        def matches_path(candidate: str) -> bool:
            return not path_prefix or candidate.startswith(path_prefix)

        matching_files = [
            item
            for item in self.files
            if matches_path(item)
            and (not query_folded or query_folded in item.casefold())
        ]
        matching_symbols = []
        for symbol in self.symbols:
            if not matches_path(str(symbol["path"])):
                continue
            if kind_folded and symbol["kind"] != kind_folded:
                continue
            searchable = " ".join(
                (str(symbol["name"]), str(symbol["declaration"]), str(symbol["path"]))
            ).casefold()
            if query_folded and query_folded not in searchable:
                continue
            matching_symbols.append(symbol)

        return {
            "scope": "mechanical index; inspect source before drawing semantic conclusions",
            "files": matching_files[:limit],
            "symbols": matching_symbols[:limit],
            "files_truncated": len(matching_files) > limit,
            "symbols_truncated": len(matching_symbols) > limit,
        }


class SharedAuditContext:
    """Shared raw evidence and navigation facts for isolated audit conversations."""

    _CACHEABLE_TOOLS = frozenset({"list_files", "read_file", "search_code"})

    def __init__(
        self,
        target_root: Path,
        artifact_directory: Path,
        *,
        allow_tests: bool = False,
    ):
        self.target_root = target_root.resolve()
        self.artifact_directory = artifact_directory.resolve()
        self.artifact_directory.mkdir(parents=True, exist_ok=True)
        self.workspace = SourceWorkspace(self.target_root, allow_tests=allow_tests)
        self.index = RepositoryIndex.build(self.target_root)
        write_json(self.artifact_directory / "repository-index.json", self.index.as_json())
        self._cache: dict[str, dict[str, Any]] = {}
        self._next_evidence_id = 1
        self._new_evidence = 0
        self._reused_evidence = 0
        self._index_queries = 0
        self._evidence_log = self.artifact_directory / "shared-evidence.jsonl"
        self._evidence_log.touch(exist_ok=True)

    @property
    def context_mode(self) -> str:
        return "shared-mechanical-evidence-isolated-reasoning"

    def metadata(self) -> dict[str, Any]:
        return {
            "context_mode": self.context_mode,
            "shared_context_directory": str(self.artifact_directory),
            "repository_index": "repository-index.json",
            "shared_evidence_log": "shared-evidence.jsonl",
        }

    def finalize(self) -> dict[str, Any]:
        summary = {
            "schema_version": "shared-evidence-summary/v1",
            "completed_at": utc_now(),
            "target_root": str(self.target_root),
            "context_mode": self.context_mode,
            "repository_index": "repository-index.json",
            "shared_evidence_log": "shared-evidence.jsonl",
            "new_raw_evidence": self._new_evidence,
            "reused_raw_evidence": self._reused_evidence,
            "repository_index_queries": self._index_queries,
        }
        write_json(self.artifact_directory / "shared-evidence-summary.json", summary)
        return summary

    def tool_definitions(self) -> list[dict[str, Any]]:
        tools = list(self.workspace.tool_definitions())
        tools.append(
            {
                "type": "function",
                "function": {
                    "name": "query_repository_index",
                    "description": (
                        "Query a shared mechanical repository index containing only "
                        "file paths and Go declaration locations. It contains no "
                        "audit conclusions; inspect source before relying on a result."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "default": ""},
                            "path": {"type": "string", "default": ""},
                            "kind": {
                                "type": "string",
                                "enum": ["", "function", "type", "declaration"],
                                "default": "",
                            },
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 300},
                        },
                        "additionalProperties": False,
                    },
                },
            }
        )
        return tools

    @staticmethod
    def _arguments(arguments_json: str) -> tuple[dict[str, Any] | None, str | None]:
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            return None, f"invalid tool arguments JSON: {exc}"
        if not isinstance(arguments, dict):
            return None, "tool arguments must be a JSON object"
        return arguments, None

    @staticmethod
    def _cache_key(name: str, arguments: dict[str, Any]) -> str:
        return f"{name}:{json.dumps(arguments, sort_keys=True, ensure_ascii=False)}"

    def _append_evidence(self, evidence: dict[str, Any]) -> None:
        with self._evidence_log.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(evidence, ensure_ascii=False) + "\n")

    def execute_json(self, name: str, arguments_json: str) -> str:
        arguments, error = self._arguments(arguments_json)
        if error is not None:
            return json.dumps({"ok": False, "error": error}, ensure_ascii=False)
        assert arguments is not None

        if name == "query_repository_index":
            self._index_queries += 1
            try:
                result = self.index.query(**arguments)
            except TypeError as exc:
                return json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False)
            return json.dumps({"ok": True, "result": result}, ensure_ascii=False)

        if name not in self._CACHEABLE_TOOLS:
            return self.workspace.execute_json(name, arguments_json)

        key = self._cache_key(name, arguments)
        cached = self._cache.get(key)
        if cached is not None:
            self._reused_evidence += 1
            return json.dumps(
                {
                    "ok": True,
                    "result": cached["result"],
                    "shared_evidence": {"id": cached["id"], "status": "reused"},
                },
                ensure_ascii=False,
            )

        raw = json.loads(self.workspace.execute_json(name, arguments_json))
        if raw.get("ok") is not True or not isinstance(raw.get("result"), dict):
            return json.dumps(raw, ensure_ascii=False)

        evidence = {
            "id": f"F{self._next_evidence_id:04d}",
            "created_at": utc_now(),
            "tool": name,
            "arguments": arguments,
            "result": raw["result"],
            "scope": "raw source tool result; not an audit conclusion",
        }
        self._next_evidence_id += 1
        self._new_evidence += 1
        self._cache[key] = evidence
        self._append_evidence(evidence)
        return json.dumps(
            {
                "ok": True,
                "result": evidence["result"],
                "shared_evidence": {"id": evidence["id"], "status": "new"},
            },
            ensure_ascii=False,
        )
