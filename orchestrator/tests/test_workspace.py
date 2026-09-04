from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from consensus_audit.workspace import SourceWorkspace, WorkspaceError


class WorkspaceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        (self.root / "main.go").write_text(
            "package main\n\nfunc Vote() {}\n", encoding="utf-8"
        )
        (self.root / ".git").mkdir()
        (self.root / ".git" / "config").write_text("secret", encoding="utf-8")
        self.workspace = SourceWorkspace(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_read_file_is_numbered(self) -> None:
        result = self.workspace.read_file("main.go", 1, 2)
        self.assertEqual(result["content"], "1: package main\n2: ")

    def test_path_escape_and_git_are_rejected(self) -> None:
        with self.assertRaises(WorkspaceError):
            self.workspace.read_file("../outside")
        with self.assertRaises(WorkspaceError):
            self.workspace.read_file(".git/config")

    def test_search_and_tool_error(self) -> None:
        result = self.workspace.search_code("Vote", fixed_strings=True)
        self.assertTrue(any("main.go" in match for match in result["matches"]))

        output = json.loads(self.workspace.execute_json("missing", "{}"))
        self.assertFalse(output["ok"])

    def test_search_falls_back_when_rg_is_unavailable(self) -> None:
        with patch("consensus_audit.workspace.shutil.which", return_value=None):
            result = self.workspace.search_code("func\\s+Vote", fixed_strings=False)
        self.assertEqual(result["engine"], "python-fallback")
        self.assertTrue(any("main.go:3" in match for match in result["matches"]))

    def test_tests_are_disabled_by_default(self) -> None:
        result = self.workspace.execute("run_go_test", {})
        self.assertFalse(result["ok"])


if __name__ == "__main__":
    unittest.main()
