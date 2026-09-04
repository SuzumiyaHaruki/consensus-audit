from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from consensus_audit.cli import (
    _baseline_episode_count,
    _selected_property_ids,
    build_parser,
)


class DummyMaterialSet:
    property_ids = ("Q-A", "Q-B", "Q-C")

    def property_file(self, property_id: str) -> Path:
        if property_id not in self.property_ids:
            raise ValueError(property_id)
        return Path(property_id)


class CliTests(unittest.TestCase):
    def test_repeated_properties_preserve_order_and_deduplicate(self) -> None:
        args = build_parser().parse_args(
            [
                "run",
                "--property",
                "Q-B",
                "--property",
                "Q-A",
                "--property",
                "Q-B",
                "--target-root",
                ".",
            ]
        )
        self.assertEqual(
            _selected_property_ids(args, DummyMaterialSet()), ["Q-B", "Q-A"]
        )

    def test_all_properties_use_catalog_order(self) -> None:
        args = build_parser().parse_args(
            ["run", "--all-properties", "--target-root", "."]
        )
        self.assertEqual(
            _selected_property_ids(args, DummyMaterialSet()), ["Q-A", "Q-B", "Q-C"]
        )

    def test_properties_file_ignores_comments_and_blank_lines(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "properties.txt"
            path.write_text("# related properties\nQ-A\n\nQ-C\n", encoding="utf-8")
            args = build_parser().parse_args(
                [
                    "run",
                    "--properties-file",
                    str(path),
                    "--target-root",
                    ".",
                ]
            )
            self.assertEqual(
                _selected_property_ids(args, DummyMaterialSet()), ["Q-A", "Q-C"]
            )

    def test_baseline_defaults_to_material_property_count(self) -> None:
        args = build_parser().parse_args(
            ["baseline", "--target-root", ".", "--dry-run"]
        )
        self.assertIsNone(args.episodes)
        self.assertEqual(_baseline_episode_count(args, DummyMaterialSet()), 3)
        self.assertEqual(args.max_turns, 24)
        self.assertEqual(args.max_tool_calls, 80)

    def test_shared_evidence_context_mode_is_available(self) -> None:
        args = build_parser().parse_args(
            [
                "run",
                "--all-properties",
                "--target-root",
                ".",
                "--context-mode",
                "shared-evidence",
                "--dry-run",
            ]
        )
        self.assertEqual(args.context_mode, "shared-evidence")


if __name__ == "__main__":
    unittest.main()
