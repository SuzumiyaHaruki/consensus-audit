# Unguided Consensus Audit Report

- Target root: `<TARGET_ROOT>`
- Verdict: `credible_risk | no_credible_risk | insufficient_evidence`

## Scope

Describe the inspected boundary and relevant active modes.

## Summary

State the evidence-based conclusion and its main limitations.

## Path coverage

List public interfaces and configuration branches that can materially change the conclusion. Identify shared and branch-specific stages.

| Interface / mode | Inspected | Shared path | Branch-specific behavior | Conclusion |
|---|---|---|---|---|

## Search record

- Concepts and symbols searched:
- Files examined:
- Checks or tests run:
- Unresolved paths:

## Findings

Write `None` when no candidate meets the credible-risk standard. Otherwise, include for each finding:

### `<finding ID>: <title>`

- Draft candidate ID:
- Claimed correctness obligation:
- Possible downstream implications: `unverified | none`
- Confidence:
- Classification: `library_defect | integration_risk | configuration_dependent | unresolved`
- Source evidence:
- Expected implementation behavior:
- Risk mechanism:
- Ordered causal chain:
- Protocol precondition:
- Implementation precondition:
- Environment requirements:
- Concrete scenario, topology, participants, necessary decision sets, and size justification:
- Action or fault sequence `A`:
- Semantic contradiction `V`:
- Observable oracle `O`:
- Validation plan:
- Uncertainties:
- Confirmed by execution: `yes | no`

## Limitations

List assumptions, excluded behavior, and unavailable evidence.
