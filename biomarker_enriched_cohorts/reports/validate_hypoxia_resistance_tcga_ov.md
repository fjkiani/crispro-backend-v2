# Hypoxia Surrogate Validation for Platinum Resistance

**Generated:** 2026-01-03T05:00:28Z
**Cohort:** tcga_ov
**Hypoxia score:** WINTER (median split threshold=10.000)
**Endpoint:** PFS (pfs_days/pfs_event)

## Cohort
- N total: 203
- Platinum resistant: 33 (16.3%)
- High hypoxia: 98 (48.3%)

## Survival (High vs Low hypoxia)
- Log-rank p: 0.2702750351573804
- Median PFS Low: 544.41 days
- Median PFS High: 505.38 days
- Cox HR (High vs Low): 0.83 (CI 0.59–1.16), p=0.26675734787643457

## Classification (5-fold CV logistic regression)
- n analyzed: 203
- Baseline features: brca_mutated, hrd_high

### AUROC
- Hypoxia: 0.452 (0.353-0.549)
- Baseline: 0.429 (0.326-0.544)
- Combined: 0.402 (0.312-0.503)

### DeLong comparisons (RUO approx)
- Combined vs baseline: Δ=-0.027, p=0.8692
- Hypoxia vs baseline: Δ=+0.022, p=0.8955

## Figures
- KM curves: figure_hypoxia_km_curves_tcga_ov.png
- ROC curves: figure_hypoxia_roc_curves_tcga_ov.png
