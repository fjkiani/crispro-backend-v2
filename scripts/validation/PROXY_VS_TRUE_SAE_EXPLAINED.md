# 🔬 PROXY SAE vs TRUE SAE (publication-safe framing)

**Purpose:** Explain PROXY SAE vs TRUE SAE in a way that stays consistent with the SAE_RESISTANCE publication receipts.  

## Definitions

- **PROXY SAE (gene-level, production-friendly):**
  - Input: mutations as gene/variant annotations (e.g., TP53, MBD4).
  - Output: interpretable pathway burdens and a 7D mechanism vector \([DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]\).
  - Strength: cheap, interpretable, works without GPU.

- **TRUE SAE (feature-level, Evo2→SAE):**
  - Input: sequence → Evo2 activations → sparse SAE features.
  - Output: sparse feature activations (32K feature space), plus any *mapped* aggregates (e.g., DDR_bin from a small mapped subset).
  - Strength: variant/sequence-level specificity; the only path to “feature-level” auditability/steerability.

## What changed (conceptually)

**PROXY path:**

Gene mutations → pathway aggregation → mechanism vector / heuristic risk features

**TRUE path:**

Sequence → Evo2 activations → SAE features → (optional) mapped aggregates like DDR_bin

## What we can claim today (based on publication receipts)

- **Externally validated predictive platinum resistance signal (expression):**
  - **MFAP4 AUROC = 0.763 on GSE63885** (n=101; 34 resistant / 67 sensitive).
  - See `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/VALIDATION_SUMMARY_FINAL.md`.

- **TRUE SAE / DDR_bin internal signal (contract-specific):**
  - Tier-3 internal cohort shows a mean CV-AUROC ≈ **0.783 ± 0.100** for a 29-feature baseline under a **specific label contract** (pos = resistant+refractory).
  - This is **not** external validation and must be framed as exploratory until replicated with confound controls.
  - See `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/ERRATA.md`.

- **DDR_bin is not predictive for TCGA-style platinum response labels:**
  - DDR_bin AUROC(resistant) ≈ **0.517** (≈ random) under TCGA-style platinum labels.
  - See `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/ERRATA.md` and linked report artifacts.

- **DDR_bin appears prognostic for OS in v2 analyses, but is confounding-sensitive:**
  - OS association exists in the publication summary, but DDR_bin is confounded by extraction coverage / variant count in linked cohorts.
  - See `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/WHY_WE_ARE_OFF.md`.

## Why TRUE SAE still matters (even with the publication constraints)

- **Variant-level specificity:** different variants in the same gene can produce different feature patterns.
- **Feature-level audit trail:** you can point to “which sparse features fired,” then (when mapped) translate to biological bins.
- **Steerability (future):** counterfactuals are only meaningful at feature/bin level (e.g., “what if DDR_bin were clamped?”).

## Linking to the canonical story

If you are writing or updating the paper, always anchor to:
- `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/WHY_DDR_BIN_ISNT_PREDICTIVE.md`
- `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/WHY_WE_ARE_OFF.md`
- `.cursor/MOAT/SAE_INTELLIGENCE/Publication-1/SAE_RESISTANCE/ERRATA.md`


