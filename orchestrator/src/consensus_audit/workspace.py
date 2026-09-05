from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Callable


class WorkspaceError(ValueError):
    """Raised when a requested source operation is invalid."""


def _bounded_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise WorkspaceError("expected an integer")
    return max(minimum, min(maximum, value))


class SourceWorkspace:
    """Read-only source tools scoped to one target tree."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise WorkspaceError(f"target root is not a directory: {self.root}")

    def _resolve(self, relative: str, *, require_file: bool = False) -> Path:
        relative = relative or "."
        if Path(relative).is_absolute():
            raise WorkspaceError("paths must be relative to TARGET_ROOT")
        candidate = (self.root / relative).resolve()
        try:
            rel = candidate.relative_to(self.root)
        except ValueError as exc:
            raise WorkspaceError("path escapes TARGET_ROOT") from exc
        if ".git" in rel.parts:
            raise WorkspaceError("access to .git is forbidden in blind audits")
        if not candidate.exists():
            raise WorkspaceError(f"path does not exist: {relative}")
        if require_file and not candidate.is_file():
            raise WorkspaceError(f"path is not a file: {relative}")
        return candidate

    def _relative(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    def list_files(
        self,
        path: str = ".",
        max_depth: int = 3,
        max_results: int = 200,
    ) -> dict[str, Any]:
        base = self._resolve(path)
        if not base.is_dir():
            raise WorkspaceError(f"path is not a directory: {path}")
        depth_limit = _bounded_int(max_depth, default=3, minimum=0, maximum=8)
        result_limit = _bounded_int(max_results, default=200, minimum=1, maximum=500)
        base_depth = len(base.parts)
        results: list[str] = []

        for current, dirs, files in os.walk(base):
            current_path = Path(current)
            depth = len(current_path.parts) - base_depth
            dirs[:] = sorted(d for d in dirs if d != ".git")
            if depth >= depth_limit:
                dirs[:] = []
            for name in sorted(files):
                candidate = current_path / name
                try:
                    candidate.resolve().relative_to(self.root)
                except ValueError:
                    continue
                results.append(self._relative(candidate))
                if len(results) >= result_limit:
                    return {"files": results, "truncated": True}
        return {"files": results, "truncated": False}

    def read_file(
        self,
        path: str,
        start_line: int = 1,
        end_line: int = 240,
    ) -> dict[str, Any]:
        source = self._resolve(path, require_file=True)
        start = _bounded_int(start_line, default=1, minimum=1, maximum=10_000_000)
        end = _bounded_int(end_line, default=start + 239, minimum=start, maximum=10_000_000)
        if end - start + 1 > 400:
            end = start + 399

        try:
            text = source.read_text(encoding="utf-8")
        except UnicodeDecodeError as exc:
            raise WorkspaceError(f"file is not UTF-8 text: {path}") from exc
        lines = text.splitlines()
        selected = lines[start - 1 : end]
        numbered = "\n".join(
            f"{number}: {line}" for number, line in enumerate(selected, start=start)
        )
        return {
            "path": self._relative(source),
            "start_line": start,
            "end_line": start + len(selected) - 1 if selected else start - 1,
            "total_lines": len(lines),
            "content": numbered,
            "truncated": end < len(lines),
        }

    def search_code(
        self,
        pattern: str,
        path: str = ".",
        glob: str = "*",
        fixed_strings: bool = False,
        max_results: int = 100,
    ) -> dict[str, Any]:
        if not pattern or len(pattern) > 500:
            raise WorkspaceError("search pattern must contain 1-500 characters")
        if not glob or len(glob) > 100 or "\x00" in glob:
            raise WorkspaceError("invalid glob")
        base = self._resolve(path)
        limit = _bounded_int(max_results, default=100, minimum=1, maximum=300)
        rg = shutil.which("rg")
        if rg is None:
            return self._search_code_fallback(
                pattern=pattern,
                base=base,
                glob=glob,
                fixed_strings=fixed_strings,
                limit=limit,
            )

        relative_base = self._relative(base) or "."
        command = [
            rg,
            "--line-number",
            "--no-heading",
            "--color",
            "never",
            "--max-columns",
            "500",
            "--glob",
            glob,
            "--glob",
            "!.git/**",
            "--glob",
            "!**/.git/**",
        ]
        if fixed_strings:
            command.append("--fixed-strings")
        command.extend(["--", pattern, relative_base])
        try:
            completed = subprocess.run(
                command,
                cwd=self.root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=15,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WorkspaceError("search timed out after 15 seconds") from exc

        if completed.returncode not in (0, 1):
            message = completed.stderr.strip()[:1000]
            raise WorkspaceError(f"rg failed with exit {completed.returncode}: {message}")
        matches = completed.stdout.splitlines()
        return {
            "matches": matches[:limit],
            "match_count_returned": min(len(matches), limit),
            "truncated": len(matches) > limit,
            "engine": "rg",
        }

    def _search_code_fallback(
        self,
        *,
        pattern: str,
        base: Path,
        glob: str,
        fixed_strings: bool,
        limit: int,
    ) -> dict[str, Any]:
        if fixed_strings:
            matcher = lambda line: pattern in line
        else:
            try:
                expression = re.compile(pattern)
            except re.error as exc:
                raise WorkspaceError(f"invalid regular expression: {exc}") from exc
            matcher = lambda line: expression.search(line) is not None

        if base.is_file():
            candidates = [base]
        else:
            candidates = base.rglob("*")

        matches: list[str] = []
        truncated = False
        for candidate in candidates:
            if not candidate.is_file() or ".git" in candidate.parts:
                continue
            try:
                candidate.resolve().relative_to(self.root)
            except ValueError:
                continue
            relative = Path(self._relative(candidate))
            if not relative.match(glob):
                continue
            try:
                with candidate.open("r", encoding="utf-8") as handle:
                    for line_number, line in enumerate(handle, start=1):
                        if matcher(line):
                            matches.append(
                                f"{relative.as_posix()}:{line_number}:{line.rstrip()}"
                            )
                            if len(matches) >= limit:
                                truncated = True
                                break
            except (OSError, UnicodeDecodeError):
                continue
            if truncated:
                break
        return {
            "matches": matches,
            "match_count_returned": len(matches),
            "truncated": truncated,
            "engine": "python-fallback",
        }

    def tool_definitions(self) -> list[dict[str, Any]]:
        tools: list[dict[str, Any]] = [
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": "List source files under a target-relative directory.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {"type": "string", "default": "."},
                            "max_depth": {"type": "integer", "minimum": 0, "maximum": 8},
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 500},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": "Read at most 400 numbered lines from one UTF-8 source file.",
                    "parameters": {
                        "type": "object",
                        "required": ["path"],
                        "properties": {
                            "path": {"type": "string"},
                            "start_line": {"type": "integer", "minimum": 1},
                            "end_line": {"type": "integer", "minimum": 1},
                        },
                        "additionalProperties": False,
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_code",
                    "description": "Search target source text with ripgrep and return bounded matches.",
                    "parameters": {
                        "type": "object",
                        "required": ["pattern"],
                        "properties": {
                            "pattern": {"type": "string"},
                            "path": {"type": "string", "default": "."},
                            "glob": {"type": "string", "default": "*"},
                            "fixed_strings": {"type": "boolean", "default": False},
                            "max_results": {"type": "integer", "minimum": 1, "maximum": 300},
                        },
                        "additionalProperties": False,
                    },
                },
            },
        ]
        return tools

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        handlers: dict[str, Callable[..., dict[str, Any]]] = {
            "list_files": self.list_files,
            "read_file": self.read_file,
            "search_code": self.search_code,
        }
        handler = handlers.get(name)
        if handler is None:
            return {"ok": False, "error": f"unknown or disabled tool: {name}"}
        try:
            return {"ok": True, "result": handler(**arguments)}
        except (WorkspaceError, TypeError) as exc:
            return {"ok": False, "error": str(exc)}

    def execute_json(self, name: str, arguments_json: str) -> str:
        try:
            arguments = json.loads(arguments_json or "{}")
        except json.JSONDecodeError as exc:
            result = {"ok": False, "error": f"invalid tool arguments JSON: {exc}"}
        else:
            if not isinstance(arguments, dict):
                result = {"ok": False, "error": "tool arguments must be a JSON object"}
            else:
                result = self.execute(name, arguments)
        return json.dumps(result, ensure_ascii=False)


class InspectionWorkspace(SourceWorkspace):
    """Source tools plus explicit access to the registered material bundle."""

    def __init__(self, root: Path, bundle: dict[str, Any]):
        from .source_materials import MaterialWorkspace
        super().__init__(root)
        self.materials = MaterialWorkspace(bundle)

    def tool_definitions(self) -> list[dict[str, Any]]:
        return super().tool_definitions() + self.materials.tool_definitions()

    def execute_json(self, name: str, arguments_json: str) -> str:
        if name == "read_material":
            return self.materials.execute_json(name, arguments_json)
        return super().execute_json(name, arguments_json)
