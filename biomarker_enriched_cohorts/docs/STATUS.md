# biomarker_enriched_cohorts — Execution Status (Reproducible)

## What exists (confirmed)

- **OV cohort (legacy)**: `data/tcga_ov_enriched_v2.json` (TCGA-OV PanCan Atlas)
- **New cohorts (added today)**:
  - `data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json`
  - `data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json`
- **Validators**:
  - `scripts/validate_io_boost.py` (now taggable via `COHORT_TAG`)
  - `scripts/validate_confidence_caps.py` (now taggable via `COHORT_TAG`)
  - `scripts/validate_parp_gating.py` (OV-only for now)
  - `scripts/validate_multimodal_risk.py` (OV-only for now)

## Why we added non-OV cohorts

- **IO gates (TMB/MSI)** cannot be validated on TCGA-OV (rare MSI-H/TMB-high → no power).
- We validate IO on cohorts where those biomarkers exat meaningful rates:
  - **UCEC** and **COADREAD**.

## One-command run (recommended)

From `oncology-coPilot/oncology-backend-minimal`:

```bash
python3 biomarker_enriched_cohorts/scripts/run_validation_suite.py
```

## Manual run (explicit)

### 1) Build outcome + biomarker cohorts from cBioPortal

```bash
python3 biomarker_enriched_cohorts/scripts/build_cbioportal_enriched_cohort.py --study_id ucec_tcga_pan_can_atlas_2018
python3 biomarker_enriched_cohorts/scripts/build_cbioportal_enriched_cohort.py --study_id coadread_tcga_pan_can_atlas_2018
```

### 2) Validate IO biomarkers vs OS (with correct cohorts)

```bash
COHORT_JSON=$PWD/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json COHORT_TAG=tcga_ucec python3 biomarker_enriched_cohorts/scripts/validate_io_boost.py --time_col os_days --event_col os_event

COHORT_JSON=$PWD/biomarker_enriched_cohorts/data/coadread_tcga_pan_can_atlas_2018_enriched_v1.json COHORT_TAG=tcga_coadread python3 biomarker_enriched_cohorts/scripts/validate_io_boost.py --time_col os_days --event_col os_event
```

Artifacts:
- `reports/validate_io_boost_tcga_ucec_report.json`
- `reports/validate_io_boost_tcga_coadread_report.json`
- `figures/figure_io_*_tcga_ucec_os.png`
- `figures/figure_io_*_tcga_coadread_os.png`

### 3) Validate confidence caps under missingness stress-test

```bash
python3 biomarker_enriched_cohorts/scripts/simulate_missingness.py   --in_cohort  biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1.json   --out_cohort biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json   --seed 42 --drop_tmb 0.55 --drop_msi 0.55 --drop_hrd_inputs 0.55

COHORT_JSON=$PWD/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json COHORT_TAG=tcga_ucec_missingness python3 biomarker_enriched_cohorts/scripts/validate_confidence_caps.py --endpoint os_days --k 2
```

Artifacts:
- `reports/validate_confidence_caps_tcga_ucec_missingness_report.json`

## Known limitations (honest)

- **HRD**: cBioPortal TCGA PanCan Atlas does **not** expose a true Myriad-style HRD score (scarHRD/LOH/LST/ntAI).
  - Our `hrd_proxy` (aneuploidy+FGA) is **exploratory**, and should not be claimed as validated HRD.
- **PARP gate**: outcome-labeled validation of the HRD rescue gate requires a cohort with real HRD labels.
