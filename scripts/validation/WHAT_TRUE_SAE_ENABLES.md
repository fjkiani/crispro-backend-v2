# 🎯 WHAT TRUE SAE ENABLES (publication-safe framing)

**Purpose:** Summarize what TRUE SAE unlocks beyond PROXY SAE, while staying consistent with SAE_RESISTANCE receipts (predictive vs prognostic, confounds, contracts).

## PROXY SAE vs TRUE SAE (one-liner)

- **PROXY SAE:** gene/pathway aggregation → interpretable pathway burdens + mechanism vector.
- **TRUE SAE:** sequence → Evo2 → sparse SAE features → (optional) mapped aggregates (e.g., DDR_bin from a mapped subset).

## What TRUE SAE unlocks (even before full mapping exists)

- **Variant-level specificity**
  - PROXY collapses all variants in a gene into one bucket.
  - TRUE SAE can distinguish variant-specific patterns via feature activations.

- **Feature-level auditability**
  - A “why” can be grounded in: which sparse features fired → which mapped bins they support → what downstream score changed.

- **Counterfactuals / steerability (future)**
  - Counterfactual reasoning becomes possible once you can intervene on mapped bins/features (e.g., clamp DDR_bin).
  - This should be treated as a roadmap item unless a concrete implementation + tests exist.

- **Longitudinal monitoring (future)**
  - Mutations may be stable, but feature/bin activity can change with tumor evolution and sampling.
  - This is the conceptual basis for “early resistance detection,” but it requires time-series data and should not be claimed as validated today.

## What is *not* unlocked yet (hard constraints)

- **“TRUE SAE predicts platinum response externally”**
  - Not currently supported; internal Tier-3 signal is contract-specific and confound-sensitive.

- **Full 32K feature → pathway/bin mapping**
  - A partial mapping exists for a small subset (enabling DDR_bin), but “complete mapping” is not done.

## Canonical receipts to cite when writing

- **External predictive biomarker (expression):** MFAP4 AUROC 0.763 on GSE63885  
  - `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/VALIDATION_SUMMARY_FINAL.md`

- **Why DDR_bin isn’t predictive for platinum response (baseline labels):**  
  - `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/WHY_DDR_BIN_ISNT_PREDICTIVE.md`

- **Confounding / contract drift warning (core):**  
  - `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/WHY_WE_ARE_OFF.md`
  - `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/ERRATA.md`

































