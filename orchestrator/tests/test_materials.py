from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from consensus_audit.materials import (
    MaterialError,
    build_audit_prompt,
    build_baseline_prompt,
    load_material_set,
)


class MaterialTests(unittest.TestCase):
    def test_load_and_build_prompt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "task.md").write_text(
                "Audit the selected property.", encoding="utf-8"
            )
            (root / "shared.md").write_text("shared boundary", encoding="utf-8")
            (root / "baseline-task.md").write_text("unguided task", encoding="utf-8")
            (root / "baseline-report.md").write_text("unguided report", encoding="utf-8")
            (root / "q1.md").write_text("Q-TEST-1 first property", encoding="utf-8")
            (root / "q2.md").write_text("Q-TEST-2 second property", encoding="utf-8")
            (root / "catalog.yaml").write_text(
                """
material_sets:
  test-set:
    protocol: test
    target: target
    shared_files:
      - shared.md
    guided_files:
      - task.md
    baseline_files:
      - baseline-task.md
      - baseline-report.md
    properties:
      Q-TEST-1: q1.md
      Q-TEST-2: q2.md
""".strip(),
                encoding="utf-8",
            )
            target = root / "target"
            target.mkdir()

            material_set = load_material_set(root, "test-set")
            system, user = build_audit_prompt(material_set, target, "Q-TEST-1")

            self.assertIn("autonomous source-code audit agent", system)
            self.assertIn("TARGET_PROPERTY_ID=Q-TEST-1", user)
            self.assertIn("Q-TEST-1 first property", user)
            self.assertNotIn("Q-TEST-2 second property", user)
            self.assertEqual(material_set.property_ids, ("Q-TEST-1", "Q-TEST-2"))

    def test_rejects_catalog_path_escape(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            outside = root.parent / "outside-material.md"
            outside.write_text("Q-TEST-1", encoding="utf-8")
            self.addCleanup(lambda: outside.unlink(missing_ok=True))
            (root / "catalog.yaml").write_text(
                """
material_sets:
  bad:
    shared_files:
      - ../outside-material.md
    guided_files:
      - task.md
    baseline_files:
      - task.md
    properties:
      Q-TEST-1: ../outside-material.md
""".strip(),
                encoding="utf-8",
            )
            (root / "task.md").write_text("task", encoding="utf-8")
            with self.assertRaises(MaterialError):
                load_material_set(root, "bad")

    def test_baseline_prompt_contains_no_property_material(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "shared.md").write_text("crash recovery model", encoding="utf-8")
            (root / "guided.md").write_text("guided task", encoding="utf-8")
            (root / "baseline.md").write_text("unguided task", encoding="utf-8")
            (root / "property.md").write_text("Q-TEST-1", encoding="utf-8")
            (root / "catalog.yaml").write_text(
                """
material_sets:
  test:
    shared_files: [shared.md]
    guided_files: [guided.md]
    baseline_files: [baseline.md]
    properties:
      Q-TEST-1: property.md
""".strip(),
                encoding="utf-8",
            )
            target = root / "target"
            target.mkdir()

            material_set = load_material_set(root, "test")
            _, user = build_baseline_prompt(material_set, target)

            self.assertIn("AUDIT_MODE=unguided-baseline", user)
            self.assertIn("crash recovery model", user)
            self.assertNotIn("TARGET_PROPERTY_ID", user)
            self.assertNotIn("EVENT_SEMANTICS", user)
            self.assertNotIn("PROTOCOL_CONTEXT", user)
            self.assertNotIn("Majority(C)", user)


if __name__ == "__main__":
    unittest.main()
