# Baseline Comparison: IO Biomarkers (tcga_coadread)

- Cohort: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json`
- Endpoint: os_days/os_event
- TMB threshold: 20.0
- Min group size (KM/log-rank): 20

| Strategy | N | Positive | Negative | log-rank p | Cox HR (pos vs neg) | 95% CI | Cox p | Approx power |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TMB-only | 530 | 77 | 453 | 0.931 | 1.02 | 0.61-1.72 | 0.9307 | 0.03 |
| MSI-only | 588 | 107 | 481 | 0.7565 | 0.93 | 0.57-1.50 | 0.756 | 0.05 |
| OR (TMB or MSI) | 590 | 116 | 474 | 0.6228 | 0.89 | 0.55-1.42 | 0.6229 | 0.07 |

- Figure: `figures/figure_baseline_comparison_io_tcga_coadread.png`
