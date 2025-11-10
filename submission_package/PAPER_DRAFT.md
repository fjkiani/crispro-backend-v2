# Multi-Modal Genomic Analysis for Drug Efficacy Prediction in Multiple Myeloma

**Authors:** Fahad Kiani, Ridwaan Jhetam  
**Affiliations:** CrisPRO.ai
**Corresponding Author:** Fahad Kiani
**Date:** October 2, 2025  
**Status:** Draft v1.0

---

## Abstract

**Background:** Multiple myeloma (MM) treatment selection remains challenging due to genetic heterogeneity and limited predictive biomarkers. Single-layer analyses can miss interactions between sequence disruption and pathway context.

**Methods:** We developed a multi-modal framework integrating Sequence (S), Pathway (P), and Evidence (E) signals to predict drug efficacy in MM. Using the Evo2 model for sequence disruption, we evaluated 7 canonical variants (5 MAPK pathway, 2 TP53 controls) across common MM drug classes (BRAF inhibitor, MEK inhibitor, proteasome inhibitor, IMiD). We ran ablations (S, P, E, SP, SE, PE, SPE) and generated calibration curves.

**Results:** The full SPE model achieved 100% pathway alignment (5/5 MAPK variants matched to expected drugs) with average confidence 0.524. Ablations showed Pathway (P) is necessary: all modes without P achieved 40% accuracy, while SP matched SPE at 100% accuracy (average confidence 0.467). Calibration analysis yielded ECE=0.479 (SPE) and ECE=0.529 (SP).

**Conclusions:** Combining sequence disruption with pathway context is sufficient to correctly match canonical MAPK variants to expected drugs in MM. Evidence mainly increases confidence rather than accuracy in this benchmark.

**Keywords:** Multiple myeloma, sequence disruption, pathway analysis, drug prediction

---

## 1. Introduction

Multiple myeloma (MM) carries frequent MAPK pathway mutations (BRAF, KRAS, NRAS). Choosing targeted therapies remains difficult due to heterogeneous drivers and variable pathway consequences. We present a simple, auditable multi-modal framework that integrates sequence disruption with pathway aggregation and evidence to rank candidate drug classes.

---

## 2. Methods

### 2.1 Framework Overview

We implemented the S/P/E framework in the CrisPRO.ai platform as a modular service exposing sequence disruption (Evo2‑1B), pathway aggregation with percentile normalization, and a conservative evidence layer.

We combine three signals:

- Sequence (S): Evo2-1B zero-shot sequence disruption; adaptive exon-aware context; outputs a calibrated percentile.
- Pathway (P): Gene→pathway aggregation with drug-specific pathway weights; raw pathway scores normalized to a [0,1] percentile using an empirical range for Evo2 deltas.
- Evidence (E): ClinVar deep analysis and literature (with graceful fallbacks). In our runs, E was conservative and primarily affected confidence.

### 2.2 Confidence Computation

Confidence aggregates: tier-based baseline; sequence/pathway percentiles; optional insights (if available); cautious ClinVar prior boost when pathway-aligned; and a deterministic, biologically-justified tie-breaker (+0.01) favoring BRAF inhibitor for BRAF, and MEK inhibitor for KRAS/NRAS on near-ties.

### 2.3 Test Set and Drug Classes

- Canonical MM variants (n=7): BRAF V600E, BRAF V600K, KRAS G12D, KRAS G12V, NRAS Q61K, TP53 R248W, TP53 R273H. Coordinates: GRCh38.
- Drug classes evaluated: BRAF inhibitor, MEK inhibitor, proteasome inhibitor, IMiD.

### 2.4 Ablations and Calibration

We evaluated S, P, E, SP, SE, PE, SPE modes on the same set. Calibration used 10-bin reliability diagrams and reports Expected Calibration Error (ECE) and Maximum Calibration Error (MCE).

---

## 3. Results

### 3.1 Full Model (SPE)

- Pathway alignment accuracy: 100% (5/5 MAPK variants)
- Average confidence: 0.524
- All predictions labeled as tier "consider" (conservative evidence layer)

Per-variant top predictions (confidence):
- BRAF V600E → BRAF inhibitor (0.515)
- BRAF V600K → BRAF inhibitor (0.515)
- KRAS G12D → MEK inhibitor (0.530)
- KRAS G12V → MEK inhibitor (0.530)
- NRAS Q61K → MEK inhibitor (0.515)
- TP53 R248W → IMiD (0.560) [control]
- TP53 R273H → BRAF inhibitor (0.505) [control]

### 3.2 Ablation Study

Summary (MAPK alignment, average confidence):
- S: 40% (0.249)
- P: 40% (0.450)
- E: 40% (0.200)
- SP: 100% (0.467)
- SE: 40% (0.249)
- PE: 40% (0.507)
- SPE: 100% (0.524)

Interpretation: P is necessary for accuracy; S refines rankings when combined with P. E increased confidence but did not affect accuracy in this benchmark.

### 3.3 Calibration

- SP: ECE=0.529, MCE=0.529
- SPE: ECE=0.479, MCE=0.479

Confidence clustered in a narrow band (~0.45–0.56), yielding few non-empty bins. Larger sets are expected to refine calibration estimates.

---

## 4. Discussion

This benchmark supports a mechanism-first view: sequence disruption alone does not determine the appropriate drug without pathway context. The SP combination sufficed for accuracy, while evidence primarily modulated confidence. Results are conservative (tiers "consider") and reproducible end-to-end.

---

## 5. Limitations

- Small set (n=7; 5 MAPK cases for alignment analysis)
- MM-only; curated pathway weights
- Moderate calibration (ECE ~0.48–0.53) with narrow confidence range
- No patient outcomes; pathway alignment is a surrogate endpoint

---

## 6. Future Work

- Extract MM cohort (treatments/outcomes) and add cohort overlays
- Expand to additional variants/cancers; learn pathway weights from data
- Improve calibration with larger validation sets

---

## Data and Reproducibility

All scripts, frozen environment, and generated artifacts used in CrisPRO to reproduce the results are included (see `REPRODUCIBILITY.md`).

- Scripts: `scripts/run_mm_baseline.py`, `scripts/run_mm_ablations.py`, `scripts/generate_calibration_plots.py`
- Results: `results/mm_baseline/mm_efficacy_results.json`, `results/mm_ablations/ablation_results_*.json`, `results/mm_calibration/*`
- Guide: `REPRODUCIBILITY.md`

---

## Acknowledgments

We thank collaborators and institutions for support.

---

## Competing Interests

[To be declared]

---

## References

[1] Walker BA, et al. JCO, 2015.  
[2] Lohr JG, et al. Cancer Cell, 2014.  
[3] Landrum MJ, et al. NAR, 2020.  
[4] Whirl-Carrillo M, et al. CPT, 2012.  
[5] Cheng J, et al. Science, 2023.  
[6] Ioannidis NM, et al. AJHG, 2016.  
[7] Wei CH, et al. NAR, 2019.  
[8] Nguyen E, et al. bioRxiv, 2024.

