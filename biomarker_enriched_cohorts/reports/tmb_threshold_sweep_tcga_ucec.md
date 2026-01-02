# TMB Threshold Sensitivity Sweep (tcga_ucec)

- Cohort: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json`
- Endpoint: os_days/os_event
- Min group size (KM/log-rank): 20

| Cutoff | N | TMB-high | TMB-low | log-rank p | Cox HR (high vs low) | 95% CI | Cox p | Approx power |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 516 | 185 | 331 | 0.0002513 | 0.38 | 0.22-0.65 | 0.0004205 | 0.99 |
| 15 | 516 | 147 | 369 | 0.002448 | 0.41 | 0.23-0.75 | 0.00335 | 0.96 |
| 20 | 516 | 120 | 396 | 0.001045 | 0.32 | 0.15-0.65 | 0.001913 | 1.00 |
| 25 | 516 | 97 | 419 | 0.00375 | 0.34 | 0.16-0.73 | 0.005775 | 0.98 |
| 30 | 516 | 82 | 434 | 0.001577 | 0.26 | 0.10-0.64 | 0.003364 | 1.00 |

- Figure: `figures/figure_tmb_threshold_sweep_tcga_ucec.png`
