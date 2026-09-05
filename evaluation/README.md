> Research archive only. The following describes historical experiments, not the current runtime or output contract. Historical results are not model input.

# Hidden evaluation material

Files below `oracles/` describe the manually injected mechanism in each target. They are evaluator-only material: the material loader does not include this directory in model prompts, and target source trees must not contain these cards.

The oracle is semantic rather than keyword-based. Score the model's `mechanism.decisive_relation` against the causal relation in the card. Merely naming an anchor, downstream symptom, or related protocol concern is not a full mechanism hit.

For each parsed Candidate-v0 object, record these fields in `score-template.csv`:

- `mechanism_score`: 0 wrong or generic; 1 related region/effect but missing the decisive relation; 2 semantically equivalent decisive relation.
- `evidence_score`: 1 only when the cited source supports the claim and the provenance validator confirms that it was read.
- `property_linkage_score`: 1 when the mechanism is correctly connected to the selected or self-derived property.
- `P_score`, `A_score`, `V_score`, `O_score`: independently record whether each test-sketch component is sufficient to guide downstream construction.
- `uncertainty_discipline_score`: 1 when assumptions outside inspected source are identified without turning them into facts.
- `duplicate_group`: assign the same ID to reports that describe the same implementation mechanism, including reports reached through different properties.

`clean` means that no mutation was intentionally injected. It does not assert that the upstream implementation has no other defect. A candidate on the clean target therefore requires manual classification rather than automatic false-positive labeling.
