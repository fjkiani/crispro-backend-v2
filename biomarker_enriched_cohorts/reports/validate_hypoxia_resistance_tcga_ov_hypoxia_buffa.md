# Hypoxia Surrogate Validation for Platinum Resistance

**Generated:** 2026-01-02T21:45:43Z
**Cohort:** tcga_ov_hypoxia_buffa
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
- n analyzed: 194
- Baseline features: brca_mutated, hrd_proxy_score, age

### AUROC
- Hypoxia: 0.502 (0.383-0.613)
- Baseline: 0.457 (0.348-0.568)
- Combined: 0.493 (0.392-0.599)

### DeLong comparisons (RUO approx)
- Combined vs baseline: Δ=+0.036, p=0.8491
- Hypoxia vs baseline: Δ=+0.044, p=0.8142

## Figures
- KM curves: figure_hypoxia_km_curves_tcga_ov_hypoxia_buffa.png
- ROC curves: figure_hypoxia_roc_curves_tcga_ov_hypoxia_buffa.png
