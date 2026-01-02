# Sporadic Gates — Validation Receipt Summary (current)

## IO Biomarkers (TMB/MSI) → OS stratification (retrospective)

### TCGA-OV (legacy)
- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json`
- **TMB**: n=519 (high=3, low=516), log-rank p=0.49021287781052103
- **MSI**: n=508 (MSI-H=18, MSS=490), log-rank p=0.451248821709356

### TCGA-UCEC
- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json`
- **TMB**: n=516 (high=120, low=396), log-rank p=0.0010453813970284502
- **MSI**: n=527 (MSI-H=174, MSS=353), log-rank p=0.007320339714802806

### TCGA-COADREAD
- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json`
- **TMB**: n=530 (high=77, low=453), log-rank p=0.9310311851606116
- **MSI**: n=588 (MSI-H=107, MSS=481), log-rank p=0.7564597234812143

## Confidence Caps (completeness tiers) — missingness stress-test

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json`
- **Usable n**: 528
- **Tier counts**: {'L2': 228, 'L1': 214, 'L0': 86}

## Honest interpretation

- **IO gate validation is cohort-dependent**: UCEC shows strong stratification for both TMB and MSI on OS; COADREAD does not in this OS endpoint snapshot; OV is underpowered for MSI/TMB (rare MSI-H/TMB-high).
- **Confidence caps are validated as an engineering safety mechanism** under realistic missingness (L0/L1/L2 non-trivial counts).
- **HRD/PARP rescue validation is still blocked on ground truth**: PanCan Atlas does not provide a Myriad-style HRD score; any aneuploidy/FGA “HRD proxy” must be labeled exploratory until we ingest an HRD-labeled cohort.
