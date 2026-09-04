# Unguided Consensus Implementation Audit

## Goal

Inspect the supplied consensus implementation for credible correctness risks under the supplied fault model. Derive each claimed implementation obligation and its observable completion semantics yourself. Do not assume that the target contains a defect or that any particular class of defect is expected.

For each finding, locate the responsible executable code, explain the ordered causal chain, and propose a reachable precondition `P`, an action or fault sequence `A`, the semantic contradiction `V`, and an exact observable oracle `O`. A credible risk is not confirmed until its oracle is observed in execution. Report at most three findings.

## Audit rules

- Inspect source, public target documentation, existing tests, and build metadata through the supplied tools. Do not modify the target.
- Base final claims on executable source that you personally inspected. Names, comments, documentation, tests, and familiarity may suggest hypotheses but do not prove that the code enforces them.
- Verify decisive arithmetic and thresholds by deriving or substituting representative boundary values.
- Distinguish an implementation defect from a risk requiring violation of a specific inspected caller contract.
- Do not use Git history, diffs, blame, patches, timestamps, remote comparisons, internet searches, remembered upstream code, project lineage, or reputation.
- Do not claim execution confirmation when only static evidence is available.

List only relevant interfaces and modes that you identified and actually inspected. Do not imply exhaustive coverage of the repository. You do not need to inspect unrelated files once a causally sufficient slice and plausible alternatives have been resolved.

You decide when the evidence is sufficient. Once you can state a provisional verdict and its decisive causal chain, make at most two additional source-tool calls, both capable of falsifying that verdict, and then return the report.

## Finding standard

A credible finding must identify:

1. a concrete correctness obligation derived during the audit;
2. inspected source locations and actual ordering or completion behavior;
3. an ordered causal chain reaching a contradiction of that obligation;
4. protocol, implementation, and environment components of `P`;
5. the action or fault sequence `A`;
6. the minimal semantic contradiction `V`;
7. an exact observable oracle `O` for detecting `V`;
8. assumptions and unresolved code.

Choose a concrete topology and name participants when a distributed scenario is needed. Derive any required decision threshold from inspected source, state only the participant sets needed for the scenario, and explain why the chosen size is sufficient. Do not require a stronger downstream failure than the finding's own minimal contradiction.

If essential implementation or completion behavior is unavailable, use `insufficient_evidence`. Lack of execution tools alone does not require that verdict when inspected source already supports a complete, testable mechanism.
