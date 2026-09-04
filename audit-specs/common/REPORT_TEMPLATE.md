# Candidate-v0 Output Contract

Return one JSON object and no surrounding prose or Markdown fence:

```json
{
  "status": "candidate_found",
  "property_id": "Q-EXAMPLE-1",
  "property_statement": "A precise statement of the selected or derived property.",
  "summary": "A short description of the candidate and its principal limitation.",
  "source_evidence": [
    {
      "path": "relative/source.go",
      "start_line": 10,
      "end_line": 25,
      "claim": "What executable behavior this inspected range establishes."
    }
  ],
  "mechanism": {
    "violated_obligation": "The implementation obligation derived from the property.",
    "decisive_relation": "The decisive ordering, guard, threshold, or state relation that may break the obligation."
  },
  "causal_chain": [
    "First implementation-level event.",
    "Decisive transition or fault.",
    "Minimal property contradiction."
  ],
  "test_sketch": {
    "precondition": "P: concrete topology, state, participants, and required setup.",
    "actions": [
      "A1: first message, timeout, persistence, or crash action.",
      "A2: next action."
    ],
    "violation": "V: the minimal event or predicate that negates the property.",
    "oracle": "O: exact externally observable condition for detecting V."
  },
  "uncertainties": [
    "A condition required by the scenario but not established by inspected source."
  ]
}
```

For `property-directed`, `property_id` must equal the selected property ID. For `matched-no-property`, it must be `null`; use `property_statement` for the self-derived obligation.

For `no_candidate` or `insufficient_evidence`, keep the same top-level keys but use an empty `source_evidence` list when there is no claim to support, set `mechanism` and `test_sketch` to `null`, use an empty `causal_chain`, and explain the result in `summary` and `uncertainties`.
