# IO Boost Biomarker Validation (TMB / MSI)

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json` (sha256: `11f5428eb7c3d238efa8b2329ee8f8d6942f98a162898099ad93f7b1d2f2791d`)
- **Endpoint**: `os_days` / `os_event`

## TMB stratification

- Threshold: 20.0
- Usable n: 519 (TMB-high=3, TMB-low=516)
- Log-rank p: 0.49021287781052103
- Median days (high): 2438.0
- Median days (low): 1367.0
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_tmb_os.png`

## MSI stratification

- MSI source: msi_status
- Usable n: 508 (MSI-H=18, MSS=490)
- Log-rank p: 0.451248821709356
- Median days (MSI-H): 887.0
- Median days (MSS): 1364.0
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_msi_os.png`

## Notes

- Retrospective stratification only; do not interpret as proof of treatment effect.
