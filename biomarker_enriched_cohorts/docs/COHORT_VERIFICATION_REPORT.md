COHORT VERIFICATION REPORT
==========================

Artifact: biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json
Study: TCGA-OV (PanCancer Atlas biomarker enrichment)
Total patients: 585

1) Required fields present
--------------------------

Outcomes (per patient):
- outcomes.os_days ✅
- outcomes.os_event ✅
- outcomes.pfs_days ✅
- outcomes.pfs_event ✅

Biomarkers (per patient):
- tmb ✅
- msi_score_mantis ✅
- msi_sensor_score ✅
- msi_status ✅
- aneuploidy_score ✅
- fraction_genome_altered ✅
- hrd_proxy ✅
- brca_somatic ✅
- germline_brca_status ✅

2) Coverage (n / 585, %)
-----------------------

Outcomes coverage:
- OS days: 571 / 585 (97.6%)
- OS event: 574 / 585 (98.1%)
- PFS days: 571 / 585 (97.6%)
.3%)

Biomarker coverage:
- TMB: 523 / 585 (89.4%)
- MSI (MANTIS score): 436 / 585 (74.5%)
- MSI (MSIsensor score): 512 / 585 (87.5%)
- MSI status: 585 / 585 (100.0%)  [derived; includes Unknown]
- Aneuploidy score: 552 / 585 (94.4%)
- Fraction genome altered (FGA): 574 / 585 (98.1%)
- HRD proxy: 585 / 585 (100.0%)  [derived; includes Unknown]
- BRCA somatic: 33 / 585 (5.6%)
- Germline BRCA status: 585 / 585 (100.0%)  [all unknown]

3) Derived label distributions
------------------------------

MSI status:
- MSS: 494
- MSI-H: 18
- Unknown: 73

HRD proxy:
- HRD-High: 233
- HRD-Intermediate: 291
- HRD-Low: 28
- Unknown: 33

BRCA somatic:
- BRCA1: 18
- BRCA2: 15
- None: 552

Germline BRCA status:
- unknown: 585

Verdict
-------

✅ Cohort verified — schema + required fields present; coverage statistics computed and consistent with enrichment outputs.
Proceed to Phase 2 validation scripts (missingness-aware handling for OS/PFS days and raw MSI/TMB fields).
