from __future__ import annotations

import unittest
from pathlib import Path

import yaml


class EvaluationOracleTests(unittest.TestCase):
    def test_mutation_oracles_have_semantic_mechanisms(self) -> None:
        root = Path(__file__).resolve().parents[2]
        oracle_root = root / "evaluation" / "oracles"
        files = sorted(oracle_root.glob("target-v*.yaml"))

        self.assertEqual([path.stem for path in files], [f"target-v{i}" for i in range(1, 8)])
        for path in files:
            value = yaml.safe_load(path.read_text(encoding="utf-8"))
            self.assertEqual(value["schema_version"], "mechanism-oracle/v1")
            self.assertEqual(value["label"], "mutant")
            mechanism = value["ground_truth_mechanism"]
            self.assertTrue(mechanism["mechanism_id"])
            self.assertTrue(mechanism["anchor_regions"])
            self.assertTrue(mechanism["violated_obligation"])
            self.assertTrue(mechanism["decisive_relation"])
            self.assertTrue(value["scenario_requirements"]["oracle"])

    def test_evaluation_oracles_are_not_ai_materials(self) -> None:
        root = Path(__file__).resolve().parents[2]
        catalog = (root / "audit-specs" / "catalog.yaml").read_text(encoding="utf-8")
        self.assertNotIn("evaluation/", catalog)


if __name__ == "__main__":
    unittest.main()
