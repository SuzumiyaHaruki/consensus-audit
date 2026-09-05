from __future__ import annotations

import json
import re
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


def final_candidate(*, property_id: str | None) -> str:
    return json.dumps(
        {
            "status": "no_candidate",
            "property_id": property_id,
            "property_statement": "A test consensus property.",
            "summary": "No candidate met the evidence threshold in this run.",
            "source_evidence": [],
            "mechanism": None,
            "causal_chain": [],
            "test_sketch": None,
            "uncertainties": [],
        }
    )


class FakeClient:
    def __init__(
        self, *, tool_until_final: bool = False, early_output: str | None = None
    ) -> None:
        self.calls: list[list[dict[str, Any]]] = []
        self.tool_sets: list[list[dict[str, Any]]] = []
        self.request_options: list[dict[str, Any]] = []
        self.tool_until_final = tool_until_final
        self.early_output = early_output

    def create_chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tool_choice: str | dict[str, Any] | None = None,
    ) -> ChatResponse:
        self.calls.append([dict(message) for message in messages])
        self.tool_sets.append(list(tools))
        self.request_options.append(
            {"response_format": response_format, "tool_choice": tool_choice}
        )
        if tools and tool_choice != "none" and (
            self.tool_until_final or len(self.calls) == 1
        ):
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
        property_id = None
        for message in messages:
            match = re.search(
                r"TARGET_PROPERTY_ID=([^\s]+)", str(message.get("content") or "")
            )
            if match is not None:
                property_id = match.group(1)
        content = final_candidate(property_id=property_id)
        if self.early_output is not None and len(self.calls) == 2:
            content = self.early_output
        return ChatResponse(
            content=content,
            reasoning_content="No candidate met the evidence threshold.",
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
    common_files: [shared.md, task.md]
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
            self.assertTrue((result.run_directory / "parsed-candidate.json").is_file())
            self.assertTrue(result.candidate_format_valid)
            self.assertTrue(result.candidate_provenance_valid)
            self.assertEqual(result.candidate_status, "no_candidate")
            second_messages = client.calls[1]
            assistant = next(
                message for message in second_messages if message["role"] == "assistant"
            )
            self.assertEqual(
                assistant["reasoning_content"], "I should inspect the source."
            )
            self.assertEqual(second_messages[-1]["role"], "tool")

    def test_final_turn_forbids_tool_calls_and_forces_json(self) -> None:
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
            self.assertTrue(client.tool_sets[2])
            self.assertEqual(client.request_options[2]["tool_choice"], "none")
            self.assertEqual(
                client.request_options[2]["response_format"], {"type": "json_object"}
            )
            self.assertIn(
                "This is the final Candidate-v0 turn",
                client.calls[2][-1]["content"],
            )
            self.assertTrue((result.run_directory / "response.md").is_file())

    def test_unparseable_early_output_gets_one_json_recovery_turn(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            materials, target = self._fixture(root)
            client = FakeClient(early_output="No candidate met the evidence threshold.")

            result = run_audit(
                load_material_set(materials, "test"),
                client,
                RunConfig(
                    property_id="Q-TEST-1",
                    target_root=target,
                    run_root=root / "runs",
                    max_turns=4,
                ),
                model_metadata={"provider": "fake"},
            )

            self.assertEqual(result.turns, 3)
            self.assertEqual(result.tool_calls, 1)
            self.assertEqual(result.usage["total_tokens"], 50)
            self.assertEqual(client.request_options[2]["tool_choice"], "none")
            self.assertEqual(
                client.request_options[2]["response_format"], {"type": "json_object"}
            )
            events = (result.run_directory / "events.jsonl").read_text(encoding="utf-8")
            self.assertIn('"event_type": "candidate_format_recovery"', events)

    def test_recoverable_early_output_needs_no_model_repair(self) -> None:
        for wrapper in ("Candidate follows.\n{}", "```json\n{}\n```"):
            with self.subTest(wrapper=wrapper), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                materials, target = self._fixture(root)
                raw = wrapper.format(final_candidate(property_id="Q-TEST-1"))
                client = FakeClient(early_output=raw)
                result = run_audit(
                    load_material_set(materials, "test"), client,
                    RunConfig(property_id="Q-TEST-1", target_root=target,
                              run_root=root / "runs", max_turns=4),
                    model_metadata={"provider": "fake"},
                )
                self.assertEqual(len(client.calls), 2)
                self.assertEqual(result.usage["total_tokens"], 30)
                self.assertEqual(result.candidate_status, "no_candidate")
                self.assertEqual(result.response, raw)
                validation = json.loads(
                    (result.run_directory / "candidate-format-validation.json").read_text()
                )
                self.assertFalse(validation["strict_output_compliant"])
                self.assertTrue(validation["schema_valid"])

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
            self.assertIn('"audit_mode": "matched-no-property"', request)
            self.assertIn('"baseline_episode": 1', request)
            self.assertIn("AUDIT_MODE=matched-no-property", prompt)
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
