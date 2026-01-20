# Hypoxia Surrogate Validation for Platinum Resistance

**Generated:** 2026-01-03T04:59:53Z
**Cohort:** tcga_ov_buffa
**Hypoxia score:** BUFFA (median split threshold=11.000)
**Endpoint:** PFS (pfs_days/pfs_event)

## Cohort
- N total: 203
- Platinum resistant: 33 (16.3%)
- High hypoxia: 101 (49.8%)

## Survival (High vs Low hypoxia)
- Log-rank p: 0.7733389237649865
- Median PFS Low: 547.41 days
- Median PFS High: 473.36 days
- Cox HR (High vs Low): 1.05 (CI 0.75–1.46), p=0.7757848095545007

## Classification (5-fold CV logistic regression)
- n analyzed: 203
- Baseline features: brca_mutated, hrd_high

### AUROC
- Hypoxia: 0.495 (0.395-0.592)
- Baseline: 0.429 (0.326-0.544)
- Combined: 0.465 (0.365-0.564)

### DeLong comparisons (RUO approx)
- Combined vs baseline: Δ=+0.035, p=0.8363
- Hypoxia vs baseline: Δ=+0.066, p=0.7051

## Figures
- KM curves: figure_hypoxia_km_curves_tcga_ov_buffa.png
- ROC curves: figure_hypoxia_roc_curves_tcga_ov_buffa.png
