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
            (root / "q1.md").write_text("Q-TEST-1 first property", encoding="utf-8")
            (root / "q2.md").write_text("Q-TEST-2 second property", encoding="utf-8")
            (root / "catalog.yaml").write_text(
                """
material_sets:
  test-set:
    protocol: test
    target: target
    common_files:
      - shared.md
      - task.md
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
            self.assertIn("TARGET_ALIAS=anonymous-target", user)
            self.assertNotIn(str(target.resolve()), user)
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
    common_files:
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
            (root / "task.md").write_text("shared candidate task", encoding="utf-8")
            (root / "protocol.md").write_text("PROTOCOL_CONTEXT", encoding="utf-8")
            (root / "events.md").write_text("EVENT_SEMANTICS", encoding="utf-8")
            (root / "property.md").write_text("Q-TEST-1", encoding="utf-8")
            (root / "catalog.yaml").write_text(
                """
material_sets:
  test:
    common_files: [shared.md, task.md, protocol.md, events.md]
    properties:
      Q-TEST-1: property.md
""".strip(),
                encoding="utf-8",
            )
            target = root / "target"
            target.mkdir()

            material_set = load_material_set(root, "test")
            _, user = build_baseline_prompt(material_set, target)

            self.assertIn("AUDIT_MODE=matched-no-property", user)
            self.assertIn("MATERIAL_SET=test", user)
            self.assertIn("crash recovery model", user)
            self.assertIn("No target property is supplied or privileged", user)
            self.assertIn("form, revise, or abandon", user)
            self.assertIn("TARGET_ALIAS=anonymous-target", user)
            self.assertNotIn(str(target.resolve()), user)
            self.assertNotIn("TARGET_PROPERTY_ID", user)
            self.assertIn("EVENT_SEMANTICS", user)
            self.assertIn("PROTOCOL_CONTEXT", user)

    def test_baseline_and_guided_share_every_non_property_material(self) -> None:
        project = Path(__file__).resolve().parents[2]
        material_set = load_material_set(project / "audit-specs", "raft-etcd-v1")

        self.assertEqual(
            material_set.relative_common_files,
            material_set.relative_paths(material_set.common_files),
        )
        guided_system, guided_user = build_audit_prompt(
            material_set, project, "Q-VOTE-1"
        )
        baseline_system, baseline_user = build_baseline_prompt(material_set, project)
        self.assertEqual(guided_system, baseline_system)
        for path in material_set.common_files:
            content = path.read_text(encoding="utf-8").strip()
            self.assertIn(content, guided_user)
            self.assertIn(content, baseline_user)
        self.assertNotIn(
            material_set.property_file("Q-VOTE-1").read_text(encoding="utf-8").strip(),
            baseline_user,
        )

    def test_local_log_matching_forms_differ_only_in_property_material(self) -> None:
        project = Path(__file__).resolve().parents[2]
        original = load_material_set(
            project / "audit-specs", "raft-etcd-logmatching-local-original-v1"
        )
        expanded = load_material_set(
            project / "audit-specs", "raft-etcd-logmatching-local-expanded-v1"
        )

        self.assertEqual(original.relative_common_files, expanded.relative_common_files)
        self.assertEqual(original.property_ids, ("Q-LOG-2",))
        self.assertEqual(expanded.property_ids, ("Q-LOG-2",))
        original_property = original.property_file("Q-LOG-2").read_text(encoding="utf-8")
        expanded_property = expanded.property_file("Q-LOG-2").read_text(encoding="utf-8")
        self.assertNotIn("Equivalent violation form", original_property)
        self.assertIn("Equivalent violation form", expanded_property)


if __name__ == "__main__":
    unittest.main()
