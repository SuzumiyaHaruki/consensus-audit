from __future__ import annotations

import csv
import io
import json
import tempfile
import unittest
from pathlib import Path

from consensus_audit.results import collect_result_rows, render_result_csv


class ResultCollectionTests(unittest.TestCase):
    def test_collects_candidate_costs_and_leaves_human_scores_empty(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            run = root / "one-run"
            run.mkdir()
            (run / "request.json").write_text(
                json.dumps(
                    {
                        "audit_mode": "property-directed",
                        "property_id": "Q-VOTE-1",
                        "target_root": "/targets/target-v1",
                        "model": {"model": "test-model"},
                    }
                ),
                encoding="utf-8",
            )
            (run / "summary.json").write_text(
                json.dumps(
                    {
                        "candidate_status": "candidate_found",
                        "candidate_format_valid": True,
                        "candidate_provenance_valid": True,
                        "turns": 5,
                        "tool_calls": 8,
                        "duration_seconds": 3.5,
                        "usage": {
                            "prompt_tokens": 100,
                            "completion_tokens": 20,
                            "total_tokens": 120,
                        },
                    }
                ),
                encoding="utf-8",
            )
            (run / "evidence-manifest.json").write_text(
                json.dumps(
                    {
                        "source_cost": {
                            "files_read": 3,
                            "unique_source_lines_read": 75,
                        }
                    }
                ),
                encoding="utf-8",
            )
            (run / "candidate-format-validation.json").write_text(
                json.dumps(
                    {
                        "parse_recoverable": True,
                        "strict_output_compliant": True,
                        "schema_valid": True,
                    }
                ),
                encoding="utf-8",
            )

            rows = collect_result_rows(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["target_id"], "target-v1")
            self.assertEqual(rows[0]["arm"], "guided")
            self.assertEqual(rows[0]["input_tokens"], 100)
            self.assertEqual(rows[0]["source_lines_read"], 75)
            self.assertTrue(rows[0]["strict_output_compliant"])

            rendered = render_result_csv(rows)
            parsed = list(csv.DictReader(io.StringIO(rendered)))
            self.assertEqual(parsed[0]["run_id"], "Q-VOTE-1")
            self.assertEqual(parsed[0]["candidate_status"], "candidate_found")


if __name__ == "__main__":
    unittest.main()
