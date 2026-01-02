# Hypoxia Surrogate Validation for Platinum Resistance

**Generated:** 2026-01-02T18:12:24Z
**Cohort:** tcga_ov
**Hypoxia Score:** BUFFA

## Summary

- **Total Patients:** 203
- **High Hypoxia:** 101 (49.8%)
- **Low Hypoxia:** 102 (50.2%)
- **Platinum Resistant:** 33 (16.3%)
- **Median Threshold:** 11.00

## Survival Analysis

- **Log-rank p-value:** 0.7733
- **Median PFS (Low Hypoxia):** 547.4 days
- **Median PFS (High Hypoxia):** 473.4 days
- **Cox HR (High vs Low):** 1.05 (0.75-1.46), p=0.7758

## Classification Validation

### Hypoxia Alone
- **AUROC:** 0.495 (0.395-0.592)
- **Sensitivity:** 0.485
- **Specificity:** 0.588

### Baseline Model (BRCA/HRD Alone)
- **AUROC:** 0.429 (0.326-0.544)
- **Sensitivity:** 0.000
- **Specificity:** 1.000

### Combined Model (Hypoxia + BRCA/HRD)
- **AUROC:** 0.465 (0.365-0.564)
- **Sensitivity:** 0.485
- **Specificity:** 0.582

## Model Comparison

### Hypoxia vs Baseline
- **Improvement:** +0.070 (+15.8%)
- **DeLong test p-value:** 0.6948
- **Significant:** False

### Combined vs Baseline
- **Improvement:** +0.048 (+10.9%)
- **DeLong test p-value:** 0.7853
- **Significant:** False

## Figures

- **KM Curves:** /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_hypoxia_km_curves_tcga_ov.png
- **ROC Curves:** /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_hypoxia_roc_curves_tcga_ov.png
