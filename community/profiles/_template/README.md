# `ppi-template`: synthetic protein–protein interactions

**Copy this folder to start a new profile.** All data here is synthetic.

- **Assertion:** protein A `physically_interacts_with` protein B.
- **Uses:**
  - `pathway_draft` needs an `interaction_assay` evidence item that was not produced by an
    LLM alone.
  - `curated_network` additionally needs an explicit human acceptance.
- **Basis:** illustrative only. A real profile should cite the community guideline or
  database policy it encodes, or say that it is the author's proposal.
- **Maintainer:** project maintainers.

| Case | Expected |
|---|---|
| `cases/curated_assay.yaml` | admitted for `pathway_draft` |
| `cases/llm_only.yaml` | review required for `pathway_draft` (`BEV008`) |
| `cases/network_without_review.yaml` | admitted for `pathway_draft`; rejected for `curated_network` (`BEV010`) |
