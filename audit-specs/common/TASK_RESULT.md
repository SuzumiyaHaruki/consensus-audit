# Audit task result

Return one JSON object with task_id, candidates, requirement_results, and an unresolved array of strings. Do not surround it with prose or Markdown fences.

Each candidate uses a task-local unique ID and links only this task's accepted requirements. It has these fields (multiple candidate objects are permitted):

```json
{
  "id": "C1",
  "requirement_ids": ["R2", "R4"],
  "summary": "A concise mechanism and its principal limitation.",
  "source_evidence": [
    {"path": "relative/source.go", "start_line": 10, "end_line": 25,
     "claim": "What the inspected executable code establishes."}
  ],
  "mechanism": {
    "violated_obligation": "The obligation grounded in the linked requirements.",
    "decisive_relation": "The ordering, guard, threshold or state relation that may violate it."
  },
  "causal_chain": ["Implementation action.", "Decisive transition or fault.", "Protocol contradiction."],
  "test_sketch": {
    "precondition": "P: state and setup, with unsupported reachability conditions identified.",
    "actions": ["A: implementation action or permitted fault."],
    "violation": "V: a predicate contradicting the linked requirement.",
    "oracle": "O: an observable condition distinguishing the violation."
  },
  "uncertainties": ["An essential condition not established by inspected evidence."]
}
```

Each requirement_results entry has requirement_id, status, candidate_ids and note. Return exactly one entry per input requirement. Use:

- candidate_found: candidate_ids lists all task candidates linked to this requirement. A candidate may link several requirements and vice versa.
- no_candidate: no supported candidate was formed for this requirement in the present investigation; note explains what was examined. This is not safety.
- insufficient_evidence: note identifies the missing evidence or dependency.
- not_checked: note explains what remains unprocessed, including budget limits.
- not_applicable: note states a configuration/specification reason and source_refs cites its basis using {block_id, start_line, end_line}. A missing search result never establishes non-applicability.

Use an empty candidate_ids list when there are no linked candidates. Every ID must exist and links must agree with candidates.requirement_ids. Every source interval must actually have been returned by read_file in this task. Optional source_evidence on a requirement result uses the same reference shape. Keep unresolved issues visible even when candidates were found. Return candidates: [] when none meets the common criteria; still return the requirement records.
