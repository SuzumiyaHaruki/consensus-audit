from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from typing import Any

from consensus_audit.deepseek import ChatResponse
from consensus_audit.materials import load_material_set
from consensus_audit.runner import (
    BaselineRunConfig,
    RunConfig,
    run_audit,
    run_baseline_episode,
)
from consensus_audit.shared_context import SharedAuditContext


FINAL_REPORT = """\
# Consensus Property Audit Report

- Property: `Q-TEST-1`
- Verdict: `no_credible_risk`

## Summary

No credible risk found in the inspected test source.
"""


class FakeClient:
    def __init__(self, *, tool_until_final: bool = False) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self.tool_sets: list[list[dict[str, Any]]] = []
        self.tool_until_final = tool_until_final

    def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> ChatResponse:
        self.calls.append([dict(message) for message in messages])
        self.tool_sets.append(list(tools))
        if tools and (self.tool_until_final or len(self.calls) == 1):
            return ChatResponse(
                content="",
                reasoning_content="I should inspect the source.",
                tool_calls=(
                    {
                        "id": "call-1",
                        "type": "function",
                        "function": {
                            "name": "read_file",
                            "arguments": '{"path":"main.go"}',
                        },
                    },
                ),
                finish_reason="tool_calls",
                usage={"total_tokens": 10},
                response_id="one",
                model="fake",
            )
        return ChatResponse(
            content=FINAL_REPORT,
            reasoning_content="I found no credible risk.",
            tool_calls=(),
            finish_reason="stop",
            usage={"total_tokens": 20},
            response_id="two",
            model="fake",
        )


class RunnerTests(unittest.TestCase):
    def _fixture(self, root: Path) -> tuple[Path, Path]:
        materials = root / "materials"
        materials.mkdir()
        (materials / "task.md").write_text(
            "Audit Q-TEST-1 and return Markdown.", encoding="utf-8"
        )
        (materials / "shared.md").write_text("shared boundary", encoding="utf-8")
        (materials / "baseline-task.md").write_text("unguided task", encoding="utf-8")
        (materials / "baseline-report.md").write_text("unguided report", encoding="utf-8")
        (materials / "property.md").write_text(
            "Q-TEST-1 test property.", encoding="utf-8"
        )
        (materials / "property-two.md").write_text(
            "Q-TEST-2 second test property.", encoding="utf-8"
        )
        (materials / "catalog.yaml").write_text(
            """
material_sets:
  test:
    protocol: test
    target: test
    shared_files: [shared.md]
    guided_files: [task.md]
    baseline_files: [baseline-task.md, baseline-report.md]
    properties:
      Q-TEST-1: property.md
      Q-TEST-2: property-two.md
""".strip(),
            encoding="utf-8",
        )
        target = root / "target"
        target.mkdir()
        (target / "main.go").write_text("package main\n", encoding="utf-8")
        return materials, target

    def test_tool_loop_preserves_reasoning_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materials, target = self._fixture(root)
            client = FakeClient()

            result = run_audit(
                load_material_set(materials, "test"),
                client,
                RunConfig(
                    property_id="Q-TEST-1",
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=3,
                ),
                model_metadata={"provider": "fake"},
            )

            self.assertEqual(result.turns, 2)
            self.assertEqual(result.tool_calls, 1)
            self.assertEqual(result.usage["total_tokens"], 30)
            self.assertTrue((result.run_directory / "response.md").is_file())
            self.assertTrue(
                (result.run_directory / "evidence-manifest.json").is_file()
            )
            second_messages = client.calls[1]
            assistant = next(
                message for message in second_messages if message["role"] == "assistant"
            )
            self.assertEqual(
                assistant["reasoning_content"], "I should inspect the source."
            )
            self.assertEqual(second_messages[-1]["role"], "tool")

    def test_final_turn_disables_tools_and_forces_report(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materials, target = self._fixture(root)
            client = FakeClient(tool_until_final=True)

            result = run_audit(
                load_material_set(materials, "test"),
                client,
                RunConfig(
                    property_id="Q-TEST-1",
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=3,
                ),
                model_metadata={"provider": "fake"},
            )

            self.assertEqual(result.turns, 3)
            self.assertEqual(result.tool_calls, 2)
            self.assertTrue(client.tool_sets[0])
            self.assertTrue(client.tool_sets[1])
            self.assertEqual(client.tool_sets[2], [])
            self.assertIn(
                "This is the final report turn",
                client.calls[2][-1]["content"],
            )
            self.assertTrue((result.run_directory / "response.md").is_file())

    def test_baseline_episode_uses_shared_agent_loop(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materials, target = self._fixture(root)

            result = run_baseline_episode(
                load_material_set(materials, "test"),
                FakeClient(),
                BaselineRunConfig(
                    episode=1,
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=3,
                ),
                model_metadata={"provider": "fake"},
            )

            request = (result.run_directory / "request.json").read_text(
                encoding="utf-8"
            )
            prompt = (result.run_directory / "prompt.md").read_text(
                encoding="utf-8"
            )
            self.assertIn('"audit_mode": "unguided-baseline"', request)
            self.assertIn('"baseline_episode": 1', request)
            self.assertIn("AUDIT_MODE=unguided-baseline", prompt)
            self.assertNotIn("TARGET_PROPERTY_ID", prompt)

    def test_shared_evidence_keeps_property_conversations_isolated(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materials, target = self._fixture(root)
            material_set = load_material_set(materials, "test")
            shared = SharedAuditContext(target, root / "shared")
            first_client = FakeClient()
            second_client = FakeClient()

            run_audit(
                material_set,
                first_client,
                RunConfig(
                    property_id="Q-TEST-1",
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=3,
                ),
                model_metadata={"provider": "fake"},
                shared_context=shared,
            )
            run_audit(
                material_set,
                second_client,
                RunConfig(
                    property_id="Q-TEST-2",
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=3,
                ),
                model_metadata={"provider": "fake"},
                shared_context=shared,
            )

            second_initial_messages = second_client.calls[0]
            second_prompt = next(
                message["content"]
                for message in second_initial_messages
                if message["role"] == "user"
            )
            self.assertIn("Q-TEST-2 second test property", second_prompt)
            self.assertNotIn("Q-TEST-1 test property", second_prompt)
            self.assertIn("SHARED EVIDENCE MODE", second_prompt)
            summary = shared.finalize()
            self.assertEqual(summary["new_raw_evidence"], 1)
            self.assertEqual(summary["reused_raw_evidence"], 1)


if __name__ == "__main__":
    unittest.main()
