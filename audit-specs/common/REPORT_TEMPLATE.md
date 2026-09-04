# Consensus Property Audit Report

- Target root: `<TARGET_ROOT>`
- Property: `<TARGET_PROPERTY_ID>`
- Verdict: `credible_risk | no_credible_risk | insufficient_evidence`

## Scope

Describe the inspected implementation boundary and active configurations.

## Summary

State the evidence-based conclusion and its main limitations.

## Path coverage

List every public interface and configuration branch that can affect the selected property. Identify which stages are shared and which are branch-specific.

| Interface / mode | Inspected | Shared path | Branch-specific behavior | Conclusion |
|---|---|---|---|---|

## Search record

- Concepts and symbols searched:
- Files examined:
- Checks or tests run:
- Unresolved paths:

## Findings

Write `None` when no candidate meets the credible-risk standard. Otherwise, for each finding include:

### `<finding ID>: <title>`

- Draft candidate ID:
- Target property:
- Possible downstream implications: `unverified | none`
- Confidence:
- Classification: `library_defect | integration_risk | configuration_dependent | unresolved`
- Source evidence:
- Expected implementation obligation:
- Risk mechanism:
- Ordered causal chain:
- Protocol precondition:
- Implementation precondition:
- Environment requirements:
- Concrete scenario, node count, participants, target-property quorum (or `none`), setup-only quorums, and size justification:
- Action or fault sequence `A`:
- Semantic violation event or predicate `V`:
- Observable oracle `O`:
- Validation plan:
- Uncertainties:
- Confirmed by execution: `yes | no`

## Limitations

List assumptions, excluded behavior, and evidence that was unavailable.
