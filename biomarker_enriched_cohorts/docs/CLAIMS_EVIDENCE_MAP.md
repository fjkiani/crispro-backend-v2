# Claims → Evidence Mapping

## ✅ VALIDATED CLAIMS (Publication-Ready)

### Claim 1: IO boost validated in endometrial cancer (UCEC)
**Statement**: "TMB ≥20 and MSI-H stratify overall survival in TCGA-UCEC (OS; p<0.01)."
**Evidence**:
- Report: `reports/validate_io_boost_tcga_ucec_report.json`
- Figures: `figures/figure_io_tmb_tcga_ucec_os.png`, `figures/figure_io_msi_tcga_ucec_os.png`
- Receipt: `receipts/ucec_tcga_pan_can_atlas_2018_enriched_v1_receipt_20260101.json`

### Claim 2: Biomarker signals are cohort-dependent
**Statement**: "IO biomarkers show context-specific stratification (UCEC validated; COADREAD null on OS endpoint)."
**Evidence**:
- UCEC report: `reports/validate_io_boost_tcga_ucec_report.json`
- COADREAD report: `reports/validate_io_boost_tcga_coadread_report.json`
- Figures: `figures/figure_io_*_tcga_{ucec,coadread}_os.png`

### Claim 3: Confidence caps tiering robust under missingness
**Statement**: "Completeness tiering produces non-degenerate L0/L1/L2 distribution under realistic missingness." 
**Evidence**:
- Report: `reports/validate_confidence_caps_tcga_ucec_missingness_report.json`
- Simulated cohort: `data/ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json`


### Claim 4: IO robustness checks (threshold sweep + baseline strategies)
**Statement**: "In TCGA-UCEC, OS stratification remains significant across multiple TMB cutoffs (10-30 mut/Mb), and baseline IO strategies (TMB-only, MSI-only, OR) have consistent effect sizes (Cox HR<1)."
**Evidence**:
- Report: `reports/tmb_threshold_sweep_tcga_ucec.json`
- Figure: `figures/figure_tmb_threshold_sweep_tcga_ucec.png`
- Report: `reports/baseline_comparison_io_tcga_ucec.json`
- Figure: `figures/figure_baseline_comparison_io_tcga_ucec.png`
***

## ❌ EXPLICITLY FORBIDDEN CLAIMS (Do Not Publish)

### Forbidden 1: HRD/PARP outcome validation
**Why forbidden**: PanCancer Atlas TCGA via cBioPortal lacks commercial HRD scores (Myriad-style scarHRD).
**Blocker doc**: `docs/HRD_BLOCKER.md`
**Status**: Deferred to future work.

### Forbidden 2: Universal IO benefit across all cohorts
**Why forbidden**: COADREAD shows no OS stratification in this snapshot (p>0.75).
**Evidence**: `reports/validate_io_boost_tcga_coadread_report.json`
**Status**: Cohort-specific validation only.

### Forbidden 3: Numeric confidence caps are "optimal"
**Why forbidden**: 0.4/0.6 caps are safety policy, not empirically optimized.
**What we CAN claim**: Tiering mechanism works; caps are conservative choice.
