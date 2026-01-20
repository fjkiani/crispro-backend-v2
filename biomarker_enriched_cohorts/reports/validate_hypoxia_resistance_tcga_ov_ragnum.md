# Hypoxia Surrogate Validation for Platinum Resistance

**Generated:** 2026-01-03T04:46:24Z
**Cohort:** tcga_ov_ragnum
**Hypoxia score:** RAGNUM (median split threshold=8.000)
**Endpoint:** PFS (pfs_days/pfs_event)

## Cohort
- N total: 203
- Platinum resistant: 33 (16.3%)
- High hypoxia: 91 (44.8%)

## Survival (High vs Low hypoxia)
- Log-rank p: 0.9497418058936216
- Median PFS Low: 537.41 days
- Median PFS High: 500.38 days
- Cox HR (High vs Low): 1.01 (CI 0.72–1.41), p=0.956971045975891

## Classification (5-fold CV logistic regression)
- n analyzed: 203
- Baseline features: brca_mutated, hrd_high

### AUROC
- Hypoxia: 0.443 (0.347-0.545)
- Baseline: 0.429 (0.326-0.544)
- Combined: 0.388 (0.296-0.482)

### DeLong comparisons (RUO approx)
- Combined vs baseline: Δ=-0.042, p=0.7987
- Hypoxia vs baseline: Δ=+0.014, p=0.9328

## Figures
- KM curves: figure_hypoxia_km_curves_tcga_ov_ragnum.png
- ROC curves: figure_hypoxia_roc_curves_tcga_ov_ragnum.png
