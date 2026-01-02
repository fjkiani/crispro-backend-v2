# Baseline Comparison: IO Biomarkers (tcga_ucec)

- Cohort: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json`
- Endpoint: os_days/os_event
- TMB threshold: 20.0
- Min group size (KM/log-rank): 20

| Strategy | N | Positive | Negative | log-rank p | Cox HR (pos vs neg) | 95% CI | Cox p | Approx power |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TMB-only | 516 | 120 | 396 | 0.001045 | 0.32 | 0.15-0.65 | 0.001913 | 0.99 |
| MSI-only | 527 | 174 | 353 | 0.00732 | 0.49 | 0.29-0.83 | 0.008618 | 0.88 |
| OR (TMB or MSI) | 527 | 210 | 317 | 0.0001676 | 0.39 | 0.23-0.65 | 0.0002841 | 0.99 |

- Figure: `figures/figure_baseline_comparison_io_tcga_ucec.png`
