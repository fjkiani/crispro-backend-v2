# TMB Threshold Sensitivity Sweep (tcga_coadread)

- Cohort: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json`
- Endpoint: os_days/os_event
- Min group size (KM/log-rank): 20

| Cutoff | N | TMB-high | TMB-low | log-rank p | Cox HR (high vs low) | 95% CI | Cox p | Approx power |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 10 | 530 | 83 | 447 | 0.9768 | 1.01 | 0.61-1.67 | 0.9764 | 0.03 |
| 15 | 530 | 79 | 451 | 0.9657 | 0.99 | 0.59-1.66 | 0.9663 | 0.03 |
| 20 | 530 | 77 | 453 | 0.931 | 1.02 | 0.61-1.72 | 0.9307 | 0.03 |
| 25 | 530 | 75 | 455 | 0.861 | 1.05 | 0.62-1.76 | 0.8607 | 0.04 |
| 30 | 530 | 69 | 461 | 0.6928 | 1.11 | 0.65-1.89 | 0.6926 | 0.06 |

- Figure: `figures/figure_tmb_threshold_sweep_tcga_coadread.png`
