# IO Boost Biomarker Validation (TMB / MSI) — tcga_coadread

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json` (sha256: `8d78e14e30bccba3697fc2906b54881900015c534d416e88c87d12487274bee1`)
- **Endpoint**: `os_days` / `os_event`

## TMB stratification

- Threshold: 20.0
- Usable n: 530 (TMB-high=77, TMB-low=453)
- Log-rank p: 0.9310311851606116
- Median days (high): 2135.438241671875
- Median days (low): 2822.901256035625
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_tmb_tcga_coadread_os.png`

## MSI stratification

- MSI source: msi_status
- Usable n: 588 (MSI-H=107, MSS=481)
- Log-rank p: 0.7564597234812143
- Median days (MSI-H): 2135.438241671875
- Median days (MSS): 2476.66806394375
- Figure: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_io_msi_tcga_coadread_os.png`

## Notes

- Retrospective stratification only; do not interpret as proof of treatment effect.
