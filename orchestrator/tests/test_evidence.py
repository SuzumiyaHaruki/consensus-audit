from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from consensus_audit.evidence import build_evidence_manifest


class EvidenceManifestTests(unittest.TestCase):
    def test_distinguishes_read_files_from_search_only_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            (run / "request.json").write_text(
                json.dumps(
                    {"target_root": "/target", "property_id": "Q-TEST-1"}
                ),
                encoding="utf-8",
            )
            events = [
                {
                    "event_type": "tool_result",
                    "turn": 1,
                    "tool": "search_code",
                    "arguments": json.dumps(
                        {"pattern": "Vote", "path": ".", "glob": "*.go"}
                    ),
                    "result": json.dumps(
                        {
                            "ok": True,
                            "result": {
                                "engine": "python-fallback",
                                "matches": [
                                    "raft.go:10:func Vote() {}",
                                    "only_search.go:3:var Vote int",
                                ],
                                "match_count_returned": 2,
                                "truncated": False,
                            },
                        }
                    ),
                },
                {
                    "event_type": "tool_result",
                    "turn": 2,
                    "tool": "read_file",
                    "arguments": json.dumps(
                        {"path": "raft.go", "start_line": 8, "end_line": 20}
                    ),
                    "result": json.dumps(
                        {
                            "ok": True,
                            "result": {
                                "path": "raft.go",
                                "start_line": 8,
                                "end_line": 20,
                            },
                        }
                    ),
                },
                {
                    "event_type": "tool_result",
                    "turn": 3,
                    "tool": "read_file",
                    "arguments": json.dumps(
                        {"path": ".git/config", "start_line": 1, "end_line": 2}
                    ),
                    "result": json.dumps(
                        {"ok": False, "error": "access to .git is forbidden"}
                    ),
                },
            ]
            (run / "events.jsonl").write_text(
                "".join(json.dumps(event) + "\n" for event in events),
                encoding="utf-8",
            )

            manifest = build_evidence_manifest(run)

            self.assertEqual(manifest["tool_calls"]["total"], 3)
            self.assertEqual(manifest["tool_calls"]["failed"], 1)
            self.assertEqual(manifest["files"]["read"][0]["path"], "raft.go")
            self.assertEqual(
                manifest["files"]["search_only"], ["only_search.go"]
            )
            self.assertEqual(manifest["tool_errors"][0]["tool"], "read_file")


if __name__ == "__main__":
    unittest.main()

