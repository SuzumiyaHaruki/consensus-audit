from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from consensus_audit.report import (
    revalidate_candidate_artifacts,
    write_candidate_artifacts,
)


def candidate(property_id: str | None = "Q-TEST-1") -> dict[str, object]:
    return {
        "status": "candidate_found",
        "property_id": property_id,
        "property_statement": "A node must not complete two votes in one term.",
        "summary": "A persistence ordering may permit a second vote after restart.",
        "source_evidence": [
            {
                "path": "main.go",
                "start_line": 2,
                "end_line": 3,
                "claim": "The guard omits the durable vote state.",
            }
        ],
        "mechanism": {
            "violated_obligation": "A completed vote must survive restart.",
            "decisive_relation": "The vote may become visible before durability.",
        },
        "causal_chain": [
            "The first vote becomes visible.",
            "The node crashes before durability and votes again after restart.",
        ],
        "test_sketch": {
            "precondition": "Three nodes and two candidates in term T.",
            "actions": ["Deliver one request, crash, restart, and deliver the other."],
            "violation": "One voter completes votes for two candidates in term T.",
            "oracle": "Observe both affirmative term-T responses.",
        },
        "uncertainties": ["Outbound publication ordering needs execution confirmation."],
    }


class CandidateReportTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, dict[str, object]]:
        target = root / "target"
        target.mkdir()
        (target / "main.go").write_text(
            "package main\nfunc main() {\n}\n", encoding="utf-8"
        )
        manifest: dict[str, object] = {
            "files": {
                "read": [
                    {
                        "path": "main.go",
                        "ranges": [{"start": 1, "end": 3}],
                    }
                ]
            }
        }
        return target, manifest

    def test_writes_parsed_candidate_and_validates_read_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)

            result = write_candidate_artifacts(
                run,
                json.dumps(candidate()),
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="property-directed",
                expected_property_id="Q-TEST-1",
            )

            self.assertEqual(result.status, "candidate_found")
            self.assertTrue(result.parse_recoverable)
            self.assertTrue(result.strict_output_compliant)
            self.assertTrue(result.schema_valid)
            self.assertTrue(result.provenance_valid)
            self.assertTrue((run / "parsed-candidate.json").is_file())

    def test_rejects_property_mismatch_without_semantic_judgment(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            value = candidate("Q-WRONG-1")

            result = write_candidate_artifacts(
                run,
                json.dumps(value),
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="property-directed",
                expected_property_id="Q-TEST-1",
            )

            self.assertEqual(result.status, "invalid_output")
            self.assertTrue(result.parse_recoverable)
            self.assertTrue(result.strict_output_compliant)
            self.assertFalse(result.schema_valid)
            validation = json.loads(
                (run / "candidate-format-validation.json").read_text(encoding="utf-8")
            )
            self.assertIn("must equal the selected property", validation["errors"][0])

    def test_marks_unread_source_interval_as_invalid_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            manifest["files"] = {"read": []}

            result = write_candidate_artifacts(
                run,
                json.dumps(candidate()),
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="property-directed",
                expected_property_id="Q-TEST-1",
            )

            self.assertTrue(result.schema_valid)
            self.assertFalse(result.provenance_valid)
            validation = json.loads(
                (run / "candidate-provenance-validation.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertIn("was not fully read", validation["errors"][0])

    def test_accepts_no_candidate_in_matched_no_property_mode(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            value = {
                "status": "no_candidate",
                "property_id": None,
                "property_statement": "A derived consensus obligation.",
                "summary": "No mechanism met the threshold in this run.",
                "source_evidence": [],
                "mechanism": None,
                "causal_chain": [],
                "test_sketch": None,
                "uncertainties": [],
            }

            result = write_candidate_artifacts(
                run,
                "```json\n" + json.dumps(value) + "\n```",
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="matched-no-property",
                expected_property_id=None,
            )

            self.assertEqual(result.status, "no_candidate")
            self.assertTrue(result.parse_recoverable)
            self.assertFalse(result.strict_output_compliant)
            self.assertTrue(result.schema_valid)
            self.assertTrue(result.provenance_valid)

    def test_extracts_one_fenced_candidate_surrounded_by_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            response = (
                "Investigation complete.\n\n```json\n"
                + json.dumps(candidate())
                + "\n```\n"
            )

            result = write_candidate_artifacts(
                run,
                response,
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="property-directed",
                expected_property_id="Q-TEST-1",
            )

            self.assertTrue(result.parse_recoverable)
            self.assertFalse(result.strict_output_compliant)
            self.assertTrue(result.schema_valid)
            validation = json.loads(
                (run / "candidate-format-validation.json").read_text(encoding="utf-8")
            )
            self.assertIn("ignored surrounding prose", validation["warnings"][1])

    def test_extracts_one_candidate_following_prose(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)

            result = write_candidate_artifacts(
                run,
                "Investigation complete.\n" + json.dumps(candidate()),
                target_root=target,
                evidence_manifest=manifest,
                audit_mode="property-directed",
                expected_property_id="Q-TEST-1",
            )

            self.assertTrue(result.parse_recoverable)
            self.assertFalse(result.strict_output_compliant)
            self.assertTrue(result.schema_valid)

    def test_rejects_multiple_bare_objects_instead_of_selecting_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            result = write_candidate_artifacts(
                run, "Candidate follows.\n{}\n" + json.dumps(candidate()),
                target_root=target, evidence_manifest=manifest,
                audit_mode="property-directed", expected_property_id="Q-TEST-1",
            )
            self.assertFalse(result.parse_recoverable)
            self.assertEqual(result.status, "invalid_output")

    def test_revalidate_updates_existing_run_without_model_call(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            target, manifest = self._fixture(run)
            (run / "request.json").write_text(
                json.dumps(
                    {
                        "target_root": str(target),
                        "audit_mode": "property-directed",
                        "property_id": "Q-TEST-1",
                    }
                ),
                encoding="utf-8",
            )
            (run / "evidence-manifest.json").write_text(
                json.dumps(manifest), encoding="utf-8"
            )
            (run / "response.md").write_text(
                "Done.\n```json\n" + json.dumps(candidate()) + "\n```\n",
                encoding="utf-8",
            )
            (run / "summary.json").write_text(
                json.dumps({"candidate_status": "invalid_output"}), encoding="utf-8"
            )

            result = revalidate_candidate_artifacts(run)

            self.assertEqual(result.status, "candidate_found")
            summary = json.loads((run / "summary.json").read_text(encoding="utf-8"))
            self.assertEqual(summary["candidate_status"], "candidate_found")
            self.assertTrue(summary["candidate_format_valid"])
            validation = json.loads(
                (run / "candidate-format-validation.json").read_text(encoding="utf-8")
            )
            self.assertTrue(validation["parse_recoverable"])
            self.assertFalse(validation["strict_output_compliant"])
            self.assertTrue(validation["schema_valid"])


if __name__ == "__main__":
    unittest.main()
