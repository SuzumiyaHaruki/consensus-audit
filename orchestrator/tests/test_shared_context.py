from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from consensus_audit.shared_context import SharedAuditContext


class SharedAuditContextTests(unittest.TestCase):
    def test_index_and_raw_evidence_cache_are_mechanical_and_reusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "target"
            root.mkdir()
            (root / "raft.go").write_text(
                "package raft\n\ntype raft struct{}\nfunc (r *raft) Step() {}\n",
                encoding="utf-8",
            )
            (root / ".git").mkdir()
            (root / ".git" / "config").write_text("hidden", encoding="utf-8")
            artifacts = Path(temporary) / "artifacts"
            context = SharedAuditContext(root, artifacts)

            index = json.loads(
                context.execute_json(
                    "query_repository_index", '{"query":"Step","kind":"function"}'
                )
            )
            self.assertTrue(index["ok"])
            self.assertEqual(index["result"]["symbols"][0]["name"], "Step")
            self.assertNotIn(".git/config", index["result"]["files"])

            first = json.loads(
                context.execute_json(
                    "read_file", '{"path":"raft.go","start_line":1,"end_line":4}'
                )
            )
            second = json.loads(
                context.execute_json(
                    "read_file", '{"path":"raft.go","start_line":1,"end_line":4}'
                )
            )
            self.assertEqual(first["shared_evidence"]["status"], "new")
            self.assertEqual(second["shared_evidence"]["status"], "reused")
            self.assertEqual(first["result"], second["result"])
            evidence = (artifacts / "shared-evidence.jsonl").read_text(
                encoding="utf-8"
            ).splitlines()
            self.assertEqual(len(evidence), 1)
            summary = context.finalize()
            self.assertEqual(summary["new_raw_evidence"], 1)
            self.assertEqual(summary["reused_raw_evidence"], 1)


if __name__ == "__main__":
    unittest.main()
