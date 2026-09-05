from __future__ import annotations

import copy
import io
import json
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import patch

from consensus_audit.audit import audit
from consensus_audit.cli import main
from consensus_audit.preparation import check_map_inputs, extract_requirements, locate_code, unresolved_mapping
from consensus_audit.preparation_validation import validate_requirements
from consensus_audit.report import parse_json, validate_task_result
from consensus_audit.runner import RunConfig
from consensus_audit.source_materials import MaterialError, load_object
from fakes import FakeClient, candidate, mapping, reply, result, tool


ROOT = Path(__file__).resolve().parents[2]
FIXTURE = Path(__file__).parent / "fixtures/preparation"


class PipelineTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.target = self.root / "target"
        shutil.copytree(FIXTURE / "target", self.target)
        self.bundle = load_object(FIXTURE / "materials.json")
        self.requirements = load_object(FIXTURE / "requirements.json")
        self.config = RunConfig(self.root / "runs", ROOT / "audit-specs", max_turns=6)
        self.model = {"provider": "offline-fake"}

    def locate(self):
        client = FakeClient([
            reply(calls=[tool(path="state.go")], reasoning="LOCATION_PRIVATE"),
            reply({"mappings": [mapping("R-1")]}),
            reply(calls=[tool(path="state.go"), tool(path="storage.go")]),
            reply({"mappings": [mapping("R-1"), mapping("R-2", "storage.go")]})])
        return locate_code(self.requirements, self.bundle, self.target, client, self.config, self.model), client

    def test_full_chain_multi_candidate_links_and_isolated_tasks(self):
        draft = copy.deepcopy(self.requirements)
        for r in draft["requirements"]:
            r["id"] = "B1-" + r["id"]
        first = {"requirements": draft["requirements"], "assumptions": [], "unresolved": [], "block_results": [
            {"block_id": "fixture:rules", "requirement_ids": [r["id"] for r in draft["requirements"]], "reason": "Fixture."}]}
        second = {"requirements": [], "assumptions": [], "unresolved": [], "block_results": [
            {"block_id": "scope:config", "requirement_ids": [], "reason": "Configuration only."}]}
        first["assumptions"] = [{"id": "B1-A1", "assumption": "The synthetic scope applies.",
                                 "source_refs": [{"block_id": "scope:config", "start_line": 1, "end_line": 1}],
                                 "review_status": "accepted"}]
        extraction_client = FakeClient([
            reply(calls=[tool(path="../evaluation/answers"), tool("read_material", block_id="scope:config")]),
            reply(first), reply(second)])
        extracted = extract_requirements(self.bundle, extraction_client, self.config, self.model)
        requirements = load_object(extracted / "requirements.json")
        self.assertTrue(all(r["review_status"] == "pending" for r in requirements["requirements"]))
        self.assertEqual(requirements["generation"], "injected_client")
        self.assertEqual(requirements["assumptions"][0]["review_status"], "pending")
        for call in extraction_client.calls:
            self.assertEqual([t["function"]["name"] for t in call["tools"]], ["read_material"])
        evidence = [m for m in extraction_client.calls[1]["messages"] if m["role"] == "tool"]
        self.assertFalse(json.loads(evidence[0]["content"])["ok"])
        self.assertTrue(json.loads(evidence[1]["content"])["ok"])
        # Simulate two explicit human accepts, leaving recovery pending.
        for r in requirements["requirements"][:2]:
            r["review_status"] = "accepted"
        requirements["assumptions"][0]["review_status"] = "accepted"
        self.requirements = requirements
        locate_client = FakeClient([
            reply(calls=[tool(path="state.go")], reasoning="LOCATION_PRIVATE"),
            reply({"mappings": [mapping("B1-R-1")]}),
            reply(calls=[tool(path="state.go"), tool(path="storage.go"), tool(path="README.md")]),
            reply({"mappings": [mapping("B1-R-1"), mapping("B1-R-2", "storage.go")]})])
        located = locate_code(requirements, self.bundle, self.target, locate_client, self.config, self.model)
        maps = check_map_inputs(located / "code-map.json", requirements, self.bundle, self.target)["mappings"]
        self.assertEqual([(m["operation"], m["requirement_id"]) for m in maps],
                         [("Persist", "B1-R-1"), ("Reply", "B1-R-1"), ("Reply", "B1-R-2")])
        for call_index in (0, 2):
            payload = json.loads(locate_client.calls[call_index]["messages"][1]["content"])
            self.assertEqual(payload["requirements"][0]["operation"], ["Persist", "Reply"])
        audit_client = FakeClient([
            reply(calls=[tool(path="state.go"), tool("read_material", block_id="scope:config")], reasoning="FIRST_AUDIT_PRIVATE"),
            reply(result("operation-1", ["B1-R-1"], [candidate("C1", ["B1-R-1"], summary="FIRST_MECHANISM")])),
            reply(calls=[tool(path="state.go"), tool(path="storage.go")]),
            reply(result("operation-2", ["B1-R-1", "B1-R-2"], [candidate("C1", ["B1-R-1", "B1-R-2"]),
                                                              candidate("C2", ["B1-R-2"], path="storage.go")]))])
        audited = audit(requirements, self.bundle, located / "code-map.json", self.target, audit_client, self.config, self.model)
        summary = load_object(audited / "summary.json")
        self.assertEqual(summary["status"], "completed")
        self.assertEqual([t["candidate_count"] for t in summary["tasks"]], [1, 2])
        self.assertEqual(summary["tasks"][1]["requirement_results"][1]["candidate_ids"], ["C1", "C2"])
        self.assertEqual(summary["unassigned_requirement_ids"], ["B1-R-3"])
        self.assertEqual(summary["pipeline_cost"]["usage"]["total_tokens"], 165)
        self.assertEqual(summary["pipeline_cost"]["missing_stages"], [])
        second_input = json.dumps(audit_client.calls[2]["messages"])
        self.assertIn("B1-A1", second_input)
        for private in ("LOCATION_PRIVATE", "FIRST_AUDIT_PRIVATE", "FIRST_MECHANISM"):
            self.assertNotIn(private, second_input)
        run = audited / summary["tasks"][1]["run"]
        self.assertEqual(load_object(run / "request.json")["stage"], "audit")
        self.assertTrue((run / "result.json").is_file())

    def test_empty_extraction_location_failure_and_omissions_are_visible(self):
        failed = extract_requirements(self.bundle, FakeClient([reply(""), reply(""), reply("invalid"), reply("invalid")]),
                                      self.config, self.model)
        summary = load_object(failed / "summary.json")
        self.assertEqual([b["status"] for b in summary["blocks"]], ["empty_response", "invalid_output"])
        self.assertEqual(summary["usage"]["total_tokens"], 60)
        self.assertEqual(len(load_object(failed / "requirements.json")["unresolved"]), 2)
        locator = FakeClient([reply(calls=[tool(path="state.go")]), RuntimeError("offline transport failure"),
                              reply({"mappings": [unresolved_mapping("R-2", "Completion missing.")]})])
        located = locate_code(self.requirements, self.bundle, self.target, locator, self.config, self.model)
        summary = load_object(located / "summary.json")
        self.assertEqual(summary["status"], "partial")
        self.assertEqual(summary["usage"]["total_tokens"], 30)
        self.assertEqual(len(summary["mapping_results"]), 3)
        self.assertTrue(all(m["status"] == "unresolved" for m in summary["mapping_results"]))
        client = FakeClient([reply(""), reply(""), reply(result("operation-2", ["R-1"]))])
        audited = audit(self.requirements, self.bundle, located / "code-map.json", self.target, client, self.config, self.model)
        summary = load_object(audited / "summary.json")
        self.assertEqual([t["status"] for t in summary["tasks"]], ["empty_response", "completed"])
        self.assertEqual(summary["tasks"][0]["requirement_results"][0]["status"], "not_checked")
        self.assertEqual(summary["tasks"][1]["requirement_results"][1]["status"], "not_checked")
        self.assertIn("omitted", summary["tasks"][1]["requirement_results"][1]["note"])
        self.assertEqual(summary["usage"]["total_tokens"], 45)
        self.assertEqual(client.calls[1]["tool_choice"], "none")

    def test_budget_exhaustion_preserves_usage_and_runs_later_task(self):
        located, _ = self.locate()
        config = RunConfig(self.root / "limited", self.config.spec_root, max_turns=2, max_tool_calls=1)
        client = FakeClient([
            reply(calls=[tool(path="state.go"), tool(path="storage.go")]),
            reply(calls=[tool(path="state.go")]), reply(result("operation-2", ["R-1", "R-2"]))])
        audited = audit(self.requirements, self.bundle, located / "code-map.json", self.target, client, config, self.model)
        summary = load_object(audited / "summary.json")
        self.assertEqual([t["status"] for t in summary["tasks"]], ["budget_exhausted", "completed"])
        self.assertEqual(summary["tasks"][0]["tool_calls"], 1)
        self.assertEqual(summary["tasks"][0]["requirement_results"][0]["status"], "not_checked")
        self.assertEqual(summary["usage"]["total_tokens"], 45)
        tool_results = [m for m in client.calls[1]["messages"] if m["role"] == "tool"]
        self.assertFalse(json.loads(tool_results[1]["content"])["ok"])

    def test_references_and_input_changes_are_checked_without_semantic_approval(self):
        located, _ = self.locate()
        task = {"task_id": "operation-2", "requirements": self.requirements["requirements"][:2]}
        evidence = {"files": {"read": [{"path": "state.go", "ranges": [{"start": 1, "end": 5}]}]}}
        valid = result(task["task_id"], ["R-1", "R-2"], [candidate("C1", ["R-1", "R-2"])])
        validate_task_result(valid, task, self.bundle, target_root=self.target, evidence=evidence)
        for path in ("../state.go", "storage.go"):
            bad = result(task["task_id"], ["R-1", "R-2"], [candidate("C1", ["R-1"], path=path)])
            with self.assertRaises(MaterialError):
                validate_task_result(bad, task, self.bundle, target_root=self.target, evidence=evidence)
        bad = copy.deepcopy(valid)
        bad["requirement_results"][0]["candidate_ids"] = ["MISSING"]
        with self.assertRaises(MaterialError):
            validate_task_result(bad, task, self.bundle, target_root=self.target, evidence=evidence)
        bad = result(task["task_id"], ["R-1", "R-2"])
        bad["requirement_results"][0]["status"] = "not_applicable"
        with self.assertRaises(MaterialError):
            validate_task_result(bad, task, self.bundle, target_root=self.target, evidence=evidence)
        self.assertEqual(parse_json('```json\n{"task_id":"x"}\n```')["task_id"], "x")
        with self.assertRaises(ValueError):
            parse_json('{"a":1} {"b":2}')
        bad_requirements = copy.deepcopy(self.requirements)
        bad_requirements["requirements"][0]["source_refs"][0]["block_id"] = "missing"
        with self.assertRaises(MaterialError):
            validate_requirements(bad_requirements, self.bundle)
        updated = copy.deepcopy(self.requirements)
        updated["requirements"][0]["requirement"] += " Updated."
        with self.assertRaisesRegex(MaterialError, "input changed"):
            check_map_inputs(located / "code-map.json", updated, self.bundle, self.target)
        (self.target / "state.go").write_text("package changed\n")
        with self.assertRaisesRegex(MaterialError, "source changed"):
            check_map_inputs(located / "code-map.json", self.requirements, self.bundle, self.target)

    def test_three_cli_dry_runs_do_not_construct_clients_or_fabricate_results(self):
        located, _ = self.locate()
        for command in ("extract-requirements", "locate-code", "audit"):
            args = [command, "--materials", str(FIXTURE / "materials.json"), "--dry-run", "--run-root", str(self.root / command)]
            if command != "extract-requirements":
                args += ["--requirements", str(FIXTURE / "requirements.json"), "--target-root", str(self.target)]
            if command == "audit":
                args += ["--code-map", str(located / "code-map.json")]
            out = io.StringIO()
            with patch("consensus_audit.cli.read_api_key_file", side_effect=AssertionError("key access")), \
                 patch("consensus_audit.cli.DeepSeekClient", side_effect=AssertionError("client construction")), \
                 redirect_stdout(out), redirect_stderr(io.StringIO()), self.assertRaises(SystemExit) as exit:
                main(args)
            self.assertEqual(exit.exception.code, 0)
            run = Path(out.getvalue().strip())
            self.assertTrue(list(run.rglob("input.json")))
            for filename in ("response.md", "result.json", "requirements.json", "code-map.json"):
                self.assertFalse(list(run.rglob(filename)))


if __name__ == "__main__":
    unittest.main()
