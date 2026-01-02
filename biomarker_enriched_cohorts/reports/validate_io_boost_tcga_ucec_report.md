# IO Boost Biomarker Validation (TMB / MSI) — tcga_ucec

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json` (sha256: `3cf180238e9d78f107c4e8b645489be894c010de7f0e2833fd48bf69aa75f494`)
- **Endpoint**: `os_days` / `os_event`

## TMB stratification

- Threshold: 20.0
- Usable n: 516 (TMB-high=120, TMB-low=396)
- Log-rank p: 0.0010453813970284502
- Median days (high): None
- Median days (low): None
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_tmb_tcga_ucec_os.png`

## MSI stratification

- MSI source: msi_status
- Usable n: 527 (MSI-H=174, MSS=353)
- Log-rank p: 0.007320339714802806
- Median days (MSI-H): None
- Median days (MSS): 3351.2571100625
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_msi_tcga_ucec_os.png`

## Notes

- Retrospective stratification only; do not interpret as proof of treatment effect.
