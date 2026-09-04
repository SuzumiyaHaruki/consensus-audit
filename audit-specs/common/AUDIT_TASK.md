# Consensus Property Audit Task

## Goal

Given one consensus-protocol property, a fault model, and a complete implementation source tree, determine whether the implementation contains a credible mechanism that could violate the property.

For each claim, derive the implementation obligation from the property, locate the responsible code, explain the causal chain, and propose a precondition `P`, an action or fault sequence `A`, the semantic violation `V`, and an observable oracle `O`.

This is a static audit. A credible risk is not a confirmed defect until its oracle is observed in a real execution. Finding no credible risk is not proof of correctness. Report at most three findings.

## Allowed work

You may read source code, public project documentation, existing tests, and build metadata through the tools exposed by the runner. Builds, static checks, and existing tests may be executed only when the corresponding tool is available. Do not modify the source tree.

Locate relevant code independently. You do not need to read the repository linearly; use property-directed, progressive inspection. Base final claims on source that you personally inspected.

Before treating any implementation obligation as satisfied, verify it from executable code rather than names, comments, documentation, tests, or familiarity, and explicitly derive or substitute representative boundary values for every decisive arithmetic or threshold expression.

You decide when the available evidence is sufficient. Return the final report as soon as you can support one of the allowed verdicts; do not exhaust the run budget merely because more code exists. A provisional verdict exists once you can name an allowed verdict and its decisive causal chain. After that point, perform at most two additional source-tool calls total, not two turns. Each must be a targeted attempt to falsify the provisional verdict and must be capable of changing it. Do not use those calls for broader coverage, collecting line numbers, planning unavailable execution, or reconfirming facts already inspected. Then return the final Markdown report immediately.

This is a static audit. Execution confirmation is not required for `credible_risk`; use `Confirmed by execution: no` when appropriate. Do not choose `insufficient_evidence` merely because execution tools are unavailable when the inspected source already supports a complete, testable risk mechanism.

## Blind-audit restrictions

Do not:

- use Git history, diffs, blame, patch files, remote comparisons, file timestamps, or internet searches to infer modifications;
- use remembered upstream code, assumed repository lineage, project reputation, maturity, or historical correctness as evidence for a verdict; treat the supplied target as an independent implementation and derive claims from inspected target source;
- assume the implementation contains a defect;
- treat a function name, comment, generic protocol concern, or vague concurrency suspicion as sufficient evidence;
- call a risk a confirmed violation without real execution evidence;
- carry source locations or conclusions across independently evaluated code versions.

## Required reasoning chain

A credible finding must contain:

1. the implementation obligation derived from the selected property;
2. inspected source locations and the actual order or completion semantics;
3. an ordered causal chain from an input or state transition to the possible violation;
4. protocol, implementation, and environment components of `P`;
5. the action or fault sequence `A`;
6. the minimal semantic violation event or predicate `V`;
7. observations and an exact oracle `O` for detecting `V`;
8. unresolved assumptions or missing code.

For the selected property, the causal chain, concrete scenario, action sequence `A`, violation `V`, and oracle `O` must terminate at the minimal event predicate that falsifies that property. Do not require or claim a stronger downstream violation merely because it could follow from the selected violation. Cross-property consequences may be listed only as unverified downstream implications; they must not affect the current verdict or be described as established without a separate audit under their own completion semantics.

Analyze size-dependent protocol logic parametrically unless the target scope fixes a deployment size. For each credible finding, also instantiate one concrete `P/A/V/O` scenario: choose the node count, identify the participating nodes, state only the quorums actually required by `V` or by reachability of `P`, and explain why that size is sufficient. If `V` requires no quorum, say so. Label any quorum used only to establish `P` as setup-only, and verify every claimed quorum against its named participants and threshold.

If the chain depends on unavailable host, transport, storage, or application code, report `insufficient_evidence`. Distinguish a library defect from integration risk caused by violating a documented caller contract. Classify a finding as an integration risk only if its causal chain requires an external component to violate a specific inspected API obligation, and cite that obligation. The mere participation of external code is not a contract violation; if the chain remains possible while all inspected obligations are followed, do not reject it on that basis.

The complete repository is available so that you can locate evidence independently. This does not require exhaustive review of every file. Stop after the property-relevant causal path and plausible alternative paths are sufficiently resolved for your stated verdict.

List the relevant public interfaces and configuration modes that you identified and actually inspected because they can change the selected property's implementation obligation. Determine which stages share code and which branch into different completion or persistence paths. Do not imply exhaustive repository coverage, and do not generalize a conclusion from one branch to uninspected branches.

## Verdicts

- `credible_risk`: inspected source supports a complete, testable risk mechanism.
- `no_credible_risk`: no candidate met the required evidence standard in the inspected scope.
- `insufficient_evidence`: required code or completion semantics were unavailable.

Return a Markdown report following the supplied template. Use paths relative to `TARGET_ROOT`. Report content is reviewed by a human; the orchestrator does not mechanically judge whether your evidence is sufficient.
