# Multi-modal Risk Stratification Validation

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json` (sha256: `11f5428eb7c3d238efa8b2329ee8f8d6942f98a162898099ad93f7b1d2f2791d`)
- **Endpoint**: `os_days` / `os_event`

## Tier definition

- Favorable: BRCA_somatic OR (HRD-High AND (TMB-high OR MSI-H))
- Intermediate: HRD-High OR TMB-high OR MSI-H
- Unfavorable: else

## Counts

- Usable n (non-missing endpoint): 571
- Tier counts: {'Unfavorable': 302, 'Intermediate': 231, 'Favorable': 38}

## Results

- Log-rank p (3-group): 0.024835377386229134
- Median days by tier: {'Favorable': 2635.0, 'Intermediate': 1204.0, 'Unfavorable': 1471.0}

## Figure

- `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_multimodal_risk_os.png`

## Notes

- Retrospective stratification only; do not interpret as causal treatment effect.
