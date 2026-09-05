from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from consensus_audit.cli import main
from consensus_audit.deepseek import ChatResponse
from consensus_audit.materials import MaterialError
from consensus_audit.preparation import (
    PreparationConfig, check_map_inputs, cost_summary, extract_requirements, locate_code,
    run_json_stage,
)
from consensus_audit.preparation_validation import validate_requirements
from consensus_audit.prepared import build_prepared_prompt, run_prepared
from consensus_audit.report import revalidate_candidate_artifacts, validate_candidate_format
from consensus_audit.source_materials import MaterialWorkspace, load_object, split_text
from test_runner import final_candidate
from test_report import candidate as candidate_fixture


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/preparation"


def response(value=None, *, calls=(), finish="stop", reasoning=None):
    return ChatResponse(value if isinstance(value, str) else json.dumps(value), reasoning,
                        tuple(calls), finish, {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
                        "fixture-response", "fake-offline")


def tool(name="read_file", **arguments):
    return {"id": "fixture-call", "type": "function", "function": {"name": name, "arguments": json.dumps(arguments)}}


class ScriptClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create_chat_completion(self, messages, tools, **options):
        self.calls.append(copy.deepcopy({"messages": messages, "tools": tools, **options}))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def mapping(rid, *, located=True):
    return {"requirement_id": rid, "status": "located" if located else "unresolved",
        "locations": [{"path": "state.go", "symbol": "Reply", "start_line": 3, "end_line": 5,
                       "responsibility": "Returns the completion flag.", "basis": "Read the return expression."}] if located else [],
        "contract_refs": [], "unresolved_dependencies": [] if located else ["Durable completion is unknown."],
        "not_applicable_refs": [], "not_applicable_reason": ""}


class PreparationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.target = self.root / "target"
        shutil.copytree(FIXTURE / "target", self.target)
        self.bundle = load_object(FIXTURE / "materials.json")
        self.requirements = load_object(FIXTURE / "requirements.json")
        self.config = PreparationConfig(self.root / "runs", ROOT / "audit-specs", max_turns=4)
        self.model = {"model": "fake-offline"}

    def located(self, *, second_located=False):
        client = ScriptClient([
            response("", calls=[tool(path="state.go")], finish="tool_calls", reasoning="LOCATION_ONLY_CONTEXT"),
            response({"mappings": [mapping("R-1")]}),
            *([response("", calls=[tool(path="state.go")], finish="tool_calls")] if second_located else []),
            response({"mappings": [mapping("R-2", located=second_located)]}),
        ])
        run = locate_code(self.requirements, self.bundle, self.target, client, self.config, self.model)
        return run, client

    def extraction_result(self, prefix="B1-", *, empty=False):
        req = copy.deepcopy(self.requirements["requirements"][0])
        req["id"] = prefix + "R1"
        return {"requirements": [] if empty else [req], "assumptions": [], "unresolved": [],
                "block_results": [{"block_id": "fixture:rules", "requirement_ids": [] if empty else [req["id"]], "reason": "Fixture processing."}]}

    def test_extraction_isolated_forces_pending_and_processes_every_block(self):
        second = {"requirements": [], "assumptions": [], "unresolved": [], "block_results": [
            {"block_id": "scope:config", "requirement_ids": [], "reason": "Configuration only."}]}
        client = ScriptClient([
            response("", calls=[tool("read_file", path="../evaluation/oracles/answer.md"),
                                 tool("read_material", block_id="scope:config")], finish="tool_calls"),
            response(self.extraction_result()), response(second)])
        run = extract_requirements(self.bundle, client, self.config, self.model)
        draft = load_object(run / "requirements.json")
        self.assertEqual(draft["generation"], "injected_client")
        self.assertEqual(draft["requirements"][0]["review_status"], "pending")
        self.assertEqual(len(draft["block_results"]), 2)
        for call in client.calls:
            self.assertEqual([t["function"]["name"] for t in call["tools"]], ["read_material"])
        tools = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
        self.assertFalse(json.loads(tools[0]["content"])["ok"])
        self.assertTrue(json.loads(tools[1]["content"])["ok"])
        self.assertNotIn("read_file", json.dumps(client.calls[-1]["messages"]))
        self.assertEqual(load_object(run / "summary.json")["usage"]["total_tokens"], 45)

    def test_extraction_missing_block_invalid_refs_and_duplicate_ids_fail(self):
        data = self.extraction_result()
        with self.assertRaisesRegex(MaterialError, "missing block_results"):
            validate_requirements(data, self.bundle)
        data["requirements"][0]["source_refs"][0]["end_line"] = 999
        with self.assertRaisesRegex(MaterialError, "invalid source interval"):
            validate_requirements(data, self.bundle, ["fixture:rules"])
        data = self.extraction_result()
        data["requirements"].append(copy.deepcopy(data["requirements"][0]))
        with self.assertRaisesRegex(MaterialError, "duplicate"):
            validate_requirements(data, self.bundle, ["fixture:rules"])

    def test_failed_extraction_blocks_are_retained_without_success_claim(self):
        client = ScriptClient([response({}), response({}), response(""), response("")])
        run = extract_requirements(self.bundle, client, self.config, self.model)
        draft = load_object(run / "requirements.json")
        self.assertEqual(draft["requirements"], [])
        self.assertEqual(len(draft["unresolved"]), 2)
        self.assertTrue(all(b["status"] == "failed" for b in draft["block_results"]))
        summary = load_object(run / "summary.json")
        self.assertEqual([b["status"] for b in summary["blocks"]], ["invalid_output", "empty_response"])
        self.assertEqual(summary["usage"]["total_tokens"], 60)

    def test_location_returns_all_accepted_and_keeps_unresolved(self):
        run, client = self.located()
        data = check_map_inputs(run / "code-map.json", self.requirements, self.bundle, self.target)
        self.assertEqual([m["requirement_id"] for m in data["mappings"]], ["R-1", "R-2"])
        self.assertEqual(data["mappings"][1]["status"], "unresolved")
        self.assertEqual(data["review"]["requirements"]["pending"], ["R-3"])
        self.assertNotIn("LOCATION_ONLY_CONTEXT", json.dumps(client.calls[-1]["messages"]))
        self.assertNotIn("run_go_test", json.dumps(client.calls[0]["tools"]))

    def test_omitted_requirement_and_unsupported_not_applicable_stay_unresolved(self):
        na = mapping("R-2", located=False)
        na["status"] = "not_applicable"
        client = ScriptClient([response({"mappings": []}), response({"mappings": []}),
                               response({"mappings": [na]}), response({"mappings": [na]})])
        run = locate_code(self.requirements, self.bundle, self.target, client, self.config, self.model)
        result = load_object(run / "code-map.json")
        self.assertEqual([m["status"] for m in result["mappings"]], ["unresolved", "unresolved"])
        self.assertEqual(load_object(run / "summary.json")["status"], "partial")

    def test_source_reference_requires_actual_read_and_safe_path(self):
        for path, start, end in [("state.go", 3, 5), ("../outside.go", 1, 2), ("state.go", 1, 999)]:
            bad = mapping("R-1")
            bad["locations"][0].update(path=path, start_line=start, end_line=end)
            client = ScriptClient([response({"mappings": [bad]}), response({"mappings": [bad]}),
                                   response({"mappings": [mapping("R-2", located=False)]})])
            run = locate_code(self.requirements, self.bundle, self.target, client, self.config, self.model)
            self.assertEqual(load_object(run / "code-map.json")["mappings"][0]["status"], "unresolved")

    def test_contract_references_and_supported_not_applicable_are_traceable(self):
        self.bundle["blocks"][0]["text"] += "\nDuring membership changes, preserve the configured quorum rule."
        self.requirements["requirements"][1].update(
            operation=["Membership"], applies_when="Dynamic membership changes are enabled.",
            requirement="Preserve the configured quorum rule during membership changes.",
            source_refs=[{"block_id": "fixture:rules", "start_line": 4, "end_line": 4}])
        first = mapping("R-1")
        first["contract_refs"] = [{"path": "README.md", "symbol": "Caller contract", "start_line": 2,
                                  "end_line": 2, "responsibility": "Caller supplies completion.",
                                  "basis": "The fixture README describes the caller obligation."}]
        second = mapping("R-2", located=False)
        second.update(status="not_applicable", not_applicable_reason="Dynamic membership is excluded by the synthetic scope.",
                      not_applicable_refs=[{"block_id": "scope:config", "start_line": 2, "end_line": 2}])
        client = ScriptClient([response("", calls=[tool(path="state.go"), tool(path="README.md")], finish="tool_calls"),
                               response({"mappings": [first]}), response({"mappings": [second]})])
        run = locate_code(self.requirements, self.bundle, self.target, client, self.config, self.model)
        data = check_map_inputs(run / "code-map.json", self.requirements, self.bundle, self.target)
        self.assertEqual(data["mappings"][0]["contract_refs"][0]["path"], "README.md")
        self.assertEqual(data["mappings"][1]["status"], "not_applicable")
        # Mechanical validation establishes an existing scope citation, not that
        # a model's applicability inference is semantically correct.

    def test_prepared_failure_keeps_later_tasks_and_all_reported_usage(self):
        mapping_run, _ = self.located()
        client = ScriptClient([response(""), response(final_candidate(property_id=None))])
        run = run_prepared(self.requirements, self.bundle, mapping_run / "code-map.json", self.target,
                           client, self.config, self.model)
        summary = load_object(run / "summary.json")
        self.assertEqual([t["status"] for t in summary["tasks"]], ["failed", "no_candidate"])
        self.assertIn("no final content", summary["tasks"][0]["error"])
        self.assertEqual(summary["usage"]["total_tokens"], 30)

    def test_no_accepted_requirements_does_not_read_key(self):
        requirements = copy.deepcopy(self.requirements)
        for req in requirements["requirements"]:
            req["review_status"] = "pending"
        path = self.root / "pending.json"
        path.write_text(json.dumps(requirements))
        out = io.StringIO()
        with patch("consensus_audit.cli.read_api_key_file", side_effect=AssertionError("key read")), \
             redirect_stdout(out), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
            main(["locate-code", "--materials", str(FIXTURE / "materials.json"), "--requirements", str(path),
                  "--target-root", str(self.target), "--run-root", str(self.root / "pending")])
        self.assertEqual(exit.exception.code, 2)
        summary = load_object(Path(out.getvalue().strip()) / "summary.json")
        self.assertEqual(summary["status"], "needs_review")
        self.assertEqual(summary["usage"], {})

    def test_changed_inputs_or_read_source_require_fresh_location(self):
        run, _ = self.located()
        updated = copy.deepcopy(self.requirements)
        updated["requirements"][0]["requirement"] += " Updated."
        with self.assertRaisesRegex(MaterialError, "input changed"):
            check_map_inputs(run / "code-map.json", updated, self.bundle, self.target)
        (self.target / "state.go").write_text("package fixture\n\nfunc Reply(complete bool) bool {\n return false\n}\n")
        with self.assertRaisesRegex(MaterialError, "source changed"):
            check_map_inputs(run / "code-map.json", self.requirements, self.bundle, self.target)

    def test_prepared_isolated_contexts_allow_extra_reads_and_preserve_gaps(self):
        mapping_run, _ = self.located()
        client = ScriptClient([
            response("", calls=[tool(path="storage.go")], finish="tool_calls", reasoning="FIRST_AUDIT_ONLY"),
            response(final_candidate(property_id="R-1")),
            response("", calls=[tool(path="state.go")], finish="tool_calls"),
            response(final_candidate(property_id="R-2")),
        ])
        run = run_prepared(self.requirements, self.bundle, mapping_run / "code-map.json", self.target,
                           client, self.config, self.model)
        summary = load_object(run / "summary.json")
        self.assertEqual(len(summary["tasks"]), 2)
        self.assertEqual(summary["tasks"][1]["requirement_ids"], ["R-1", "R-2"])
        self.assertEqual(summary["tasks"][1]["location_statuses"]["R-2"], "unresolved")
        self.assertEqual(summary["review"]["requirements"]["pending"], ["R-3"])
        self.assertEqual(summary["pipeline_cost"]["usage"]["total_tokens"], 105)
        second = json.dumps(client.calls[2]["messages"])
        self.assertNotIn("FIRST_AUDIT_ONLY", second)
        self.assertNotIn("LOCATION_ONLY_CONTEXT", second)
        self.assertIn("Durable completion is unknown", second)
        self.assertNotIn("Audit only", second)
        self.assertNotIn("TARGET_PROPERTY_ID", second)
        first_run = run / summary["tasks"][0]["run"]
        self.assertIn("storage.go", (first_run / "evidence-manifest.json").read_text())
        self.assertTrue(revalidate_candidate_artifacts(first_run).schema_valid)

    def test_prepared_deduplicates_locations_and_validates_task_ids(self):
        group = {"operation": "Reply", "requirements": self.requirements["requirements"][:2]}
        _, prompt = build_prepared_prompt(group, self.bundle, [mapping("R-1"), mapping("R-2")],
                                          self.config.spec_root, [])
        payload = json.loads(prompt.split("\n\n===== Candidate-v0 contract")[0])
        self.assertEqual(len(payload["starting_locations"]), 1)
        self.assertEqual(payload["code_map"][0]["locations"][0]["location_id"], "L1")
        self.assertNotIn("path", payload["code_map"][1]["locations"][0])
        for pid, valid in [("R-2", True), (None, True), ("R-3", False)]:
            candidate = json.loads(final_candidate(property_id=pid))
            errors, _ = validate_candidate_format(candidate, audit_mode="prepared", expected_property_id=None,
                                                  allowed_requirement_ids=["R-1", "R-2"])
            self.assertEqual(not errors, valid)
        for pid, valid in [("R-2", True), (None, False), ("R-3", False)]:
            errors, _ = validate_candidate_format(candidate_fixture(property_id=pid), audit_mode="prepared",
                                                  expected_property_id=None, allowed_requirement_ids=["R-1", "R-2"])
            self.assertEqual(not errors, valid)

    def test_complete_offline_chain_preserves_stage_costs_and_manual_review(self):
        empty = {"requirements": [], "assumptions": [], "unresolved": [], "block_results": [
            {"block_id": "scope:config", "requirement_ids": [], "reason": "Scope only."}]}
        extraction = extract_requirements(self.bundle, ScriptClient([response(self.extraction_result()), response(empty)]),
                                           self.config, self.model)
        requirements = load_object(extraction / "requirements.json")
        self.assertEqual(requirements["requirements"][0]["review_status"], "pending")
        # Explicitly simulate a human edit in this synthetic test only.
        requirements["requirements"][0]["review_status"] = "accepted"
        location = locate_code(requirements, self.bundle, self.target, ScriptClient([
            response("", calls=[tool(path="state.go")], finish="tool_calls"),
            response({"mappings": [mapping("B1-R1")]})]), self.config, self.model)
        audit = run_prepared(requirements, self.bundle, location / "code-map.json", self.target,
                              ScriptClient([response(final_candidate(property_id="B1-R1")),
                                            response(final_candidate(property_id=None))]), self.config, self.model)
        costs = load_object(audit / "summary.json")["pipeline_cost"]
        self.assertEqual(costs["missing_stages"], [])
        self.assertEqual(set(costs["stages"]), {"extraction", "location", "audit"})
        self.assertEqual(costs["usage"]["total_tokens"], 90)

    def test_stage_specific_repair_is_bounded_and_usage_survives_errors(self):
        client = ScriptClient([response("broken"), response("broken"), response("unused")])
        run, data, summary = run_json_stage(client, self.config, label="fixture-stage", system="Extract JSON.",
            payload={}, workspace=MaterialWorkspace(self.bundle), model=self.model, validate=lambda data, run: None)
        self.assertIsNone(data)
        self.assertEqual(summary["status"], "invalid_output")
        self.assertEqual(len(client.calls), 2)
        self.assertEqual(summary["usage"]["total_tokens"], 30)
        self.assertEqual(client.calls[-1]["tool_choice"], "none")
        self.assertNotIn("Candidate-v0", json.dumps(client.calls))
        self.assertEqual((run / "response.md").read_text(), "broken")
        client = ScriptClient([response("", calls=[tool("read_material", block_id="fixture:rules")], finish="tool_calls"),
                               RuntimeError("fixture transport failure")])
        _, _, summary = run_json_stage(client, self.config, label="fixture-error", system="Extract JSON.",
            payload={}, workspace=MaterialWorkspace(self.bundle), model=self.model, validate=lambda data, run: None)
        self.assertEqual(summary["status"], "failed")
        self.assertEqual(summary["usage"]["total_tokens"], 15)

    def test_all_three_cli_dry_runs_never_read_key_or_create_fake_outputs(self):
        mapping_run, _ = self.located()
        for command in ("extract-requirements", "locate-code", "prepared"):
            args = [command, "--materials", str(FIXTURE / "materials.json"), "--dry-run",
                    "--run-root", str(self.root / command), "--api-key-file", str(self.root / "DO_NOT_READ")]
            if command != "extract-requirements":
                args.extend(["--requirements", str(FIXTURE / "requirements.json"), "--target-root", str(self.target)])
            if command == "prepared":
                args.extend(["--code-map", str(mapping_run / "code-map.json")])
            out = io.StringIO()
            with patch("consensus_audit.cli.read_api_key_file", side_effect=AssertionError("key read")), \
                 patch("consensus_audit.cli.DeepSeekClient", side_effect=AssertionError("client created")), \
                 redirect_stdout(out), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
                main(args)
            self.assertEqual(exit.exception.code, 0)
            root = Path(out.getvalue().strip())
            self.assertTrue(list(root.rglob("input.json")))
            self.assertFalse(list(root.rglob("response.md")))
            self.assertFalse(list(root.rglob("requirements.json")))
            self.assertFalse(list(root.rglob("code-map.json")))
            self.assertFalse(list(root.rglob("parsed-candidate.json")))

    def test_splitter_keeps_heading_lines_and_global_blocks(self):
        blocks = split_text("fixture", "# Definition\nA means B.\n# Global property\nAlways C.\n")
        self.assertEqual([b["source_start_line"] for b in blocks], [1, 3])
        self.assertEqual("\n".join(b["text"] for b in blocks), "# Definition\nA means B.\n# Global property\nAlways C.")

    def test_cost_does_not_guess_prices(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 50, "prompt_cache_hit_tokens": 20}
        self.assertIsNone(cost_summary(usage, {})["estimated_cost"])
        cost = cost_summary(usage, {"prices_per_million": {"input": 1, "cached_input": .5, "output": 2}})
        self.assertAlmostEqual(cost["estimated_cost"], .00019)


if __name__ == "__main__":
    unittest.main()
