# Consensus Candidate Discovery Task

## Goal

Use the supplied consensus implementation, protocol material, and fault model to produce at most one primary test candidate. A candidate is a code-supported hypothesis for a protocol-property violation, not a confirmed defect or a proof that the scenario is reachable.

`AUDIT_MODE` determines how the property is obtained:

- `property-directed`: audit only the supplied selected property and copy its ID exactly into `property_id`.
- `matched-no-property`: no specific property is supplied. Do not commit to a property before inspecting the implementation. Search for one concrete, code-supported mechanism, then formulate or refine the protocol property and implementation obligation that it may violate. Set `property_id` to `null` and state the resulting property in `property_statement`.

The two modes otherwise have the same source access, protocol context, event semantics, fault model, budget, and output contract.

## Required investigation

1. Establish a code-supported property–obligation–mechanism chain. In `property-directed` mode, begin with the selected property and derive its implementation obligation. In `matched-no-property` mode, inspect protocol-relevant code without choosing a property in advance; let a concrete mechanism motivate the property and obligation, and revise that hypothesis as evidence is collected.
2. Identify and verify one decisive ordering, guard, threshold, or state relation connecting the implementation mechanism to the obligation.
3. Support it with executable source that you personally inspected.
4. Give the minimal causal chain from the implementation mechanism to the property contradiction.
5. Draft a downstream test scenario as `P/A/V/O` and state every condition not established by the inspected source.

The mechanism is the primary result. A detailed scenario without a valid source mechanism is not a useful candidate. Conversely, do not conceal an otherwise well-supported mechanism merely because integration code or execution evidence would still be needed to confirm reachability; record that limitation in `uncertainties`.

## Evidence and scope rules

- Use only the tools exposed by the runner and do not modify the source tree.
- Base source claims on executable code personally returned by source tools.
- Names, comments, documentation, tests, and prior familiarity may suggest a hypothesis but do not prove executable behavior.
- Do not use Git history, diffs, blame, patches, timestamps, remote comparisons, internet searches, remembered upstream code, project lineage, or reputation.
- Do not assume the target contains a defect.
- Verify decisive arithmetic or thresholds with representative boundary values.
- Distinguish implementation behavior from assumptions about unavailable host, transport, storage, or application code.
- Do not perform an exhaustive interface inventory, path-coverage matrix, search diary, downstream-impact analysis, or plan for unavailable execution.

Use paths relative to `TARGET_ROOT`. Every `source_evidence` range must have been read with a source tool during this run. A search hit alone is useful for navigation but is not enough provenance for a final source claim.

## Stopping rule

Return as soon as one primary candidate has a code-supported decisive relation, or as soon as the available evidence supports `no_candidate` or `insufficient_evidence`. After forming a provisional result, use at most two additional source-tool calls, each targeted at falsifying that result.

## Output statuses

- `candidate_found`: inspected source supports a concrete mechanism worth sending to downstream test construction. This does not assert a confirmed bug.
- `no_candidate`: no mechanism met the evidence threshold within this run and budget. This is not proof of correctness.
- `insufficient_evidence`: a candidate could not be assessed because decisive implementation or completion behavior was unavailable.

Return exactly one Candidate-v0 JSON object following `REPORT_TEMPLATE.md`. The evaluator, not the model, decides whether a returned candidate is actually test-worthy.
