import importlib.util
import tempfile
import unittest
from pathlib import Path

import yaml

from consensus_audit.source_materials import MaterialError


ROOT = Path(__file__).resolve().parents[4]
SPEC = importlib.util.spec_from_file_location("raft_material_import", ROOT / "scripts/protocols/raft/prepare_materials.py")
IMPORTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(IMPORTER)


class RaftMaterialTests(unittest.TestCase):
    def test_protocol_materials_combine_only_with_the_selected_implementation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protocol = root / "protocol"
            protocol.mkdir()
            original = root / "original.md"
            original.write_text("# Synthetic protocol material\nA test rule.\n")

            def source(sid, category, path):
                return {"id": sid, "category": category, "local": str(path), "location": "synthetic fixture",
                        "version": "fixture", "license": "test fixture", "scope": "synthetic test only"}

            (protocol / "sources.yaml").write_text(yaml.safe_dump({"protocol": "raft", "sources": [
                source("test-protocol", "protocol", original)], "unresolved": ["Protocol issue."]}))
            targets = []
            for name in ("first", "second"):
                boundary = root / f"{name}.md"
                boundary.write_text(f"# {name} synthetic scope\nOnly this implementation.\n")
                target = root / f"{name}.yaml"
                target.write_text(yaml.safe_dump({"protocol": "raft", "implementation": name,
                    "sources": [source(name, "experiment_config", boundary)], "unresolved": [f"{name} issue."]}))
                targets.append(target)
            shared = IMPORTER.build_bundle(root, protocol_root=protocol)
            self.assertIsNone(shared["implementation"])
            self.assertEqual([s["id"] for s in shared["sources"]], ["test-protocol"])
            self.assertTrue(any("No implementation scope" in issue for issue in shared["unresolved"]))
            for target in targets:
                bundle = IMPORTER.build_bundle(root, protocol_root=protocol, target_spec=target)
                name = target.stem
                self.assertEqual(bundle["implementation"], name)
                self.assertEqual([s["id"] for s in bundle["sources"]], ["test-protocol", name])
                self.assertEqual(bundle["unresolved"], ["Protocol issue.", f"{name} issue."])
            targets[0].write_text(yaml.safe_dump({"protocol": "different-protocol", "sources": []}))
            with self.assertRaisesRegex(MaterialError, "same protocol"):
                IMPORTER.build_bundle(root, protocol_root=protocol, target_spec=targets[0])
