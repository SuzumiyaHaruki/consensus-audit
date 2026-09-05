"""Synthetic offline responses, not protocol evidence or real API output."""
import copy
import json

from consensus_audit.deepseek import ChatResponse


class FakeClient:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def create_chat_completion(self, messages, tools, **options):
        self.calls.append(copy.deepcopy({"messages": messages, "tools": tools, **options}))
        if not self.responses:
            raise AssertionError("Fake response script exhausted")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


def reply(value="", *, calls=(), reasoning=None):
    return ChatResponse(value if isinstance(value, str) else json.dumps(value), reasoning,
                        tuple(calls), "tool_calls" if calls else "stop",
                        {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15}, "offline", "fake")


def tool(name="read_file", **args):
    return {"id": name + str(args), "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}


def mapping(rid, path="state.go"):
    return {"requirement_id": rid, "status": "located", "locations": [
        {"path": path, "symbol": "Synthetic function", "start_line": 3, "end_line": 3,
         "responsibility": "Fixture completion path.", "basis": "Inspected fixture declaration."}],
        "contract_refs": [], "unresolved_dependencies": [], "not_applicable_refs": [], "not_applicable_reason": ""}


def candidate(cid, rids, *, summary="Synthetic mechanism.", path="state.go"):
    return {"id": cid, "requirement_ids": rids, "summary": summary,
        "source_evidence": [{"path": path, "start_line": 3, "end_line": 3, "claim": "Synthetic declaration inspected."}],
        "mechanism": {"violated_obligation": "A synthetic obligation.", "decisive_relation": "Synthetic ordering."},
        "causal_chain": ["Synthetic starting action.", "Synthetic resulting contradiction."],
        "test_sketch": {"precondition": "Synthetic setup.", "actions": ["Synthetic action."],
                        "violation": "Synthetic contradiction.", "oracle": "Synthetic observation."},
        "uncertainties": ["Fixture only; not an actual finding."]}


def result(task_id, rids, candidates=()):
    return {"task_id": task_id, "candidates": list(candidates), "requirement_results": [
        {"requirement_id": rid, "status": "candidate_found" if any(rid in c["requirement_ids"] for c in candidates) else "no_candidate",
         "candidate_ids": [c["id"] for c in candidates if rid in c["requirement_ids"]], "note": "Synthetic processing record."}
        for rid in rids], "unresolved": []}
