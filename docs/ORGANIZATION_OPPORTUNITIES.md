# Organization Opportunities - Other Work Areas

**Date:** January 1, 2025

Based on analysis of the codebase, here are other work areas that could benefit from dedicated folder organization (similar to `dosing_guidance_validation/`):

## 1. 🎯 Therapy Fit Validation

**Current Location:** Scattered across `scripts/` and `scripts/validation/`

**Files Found:**
- `scripts/test_therapy_fit_endpoint.py`
- `scripts/validate_therapy_fit_metrics.py`
- `scripts/generate_therapy_fit_results.py`
- `scripts/demo_therapy_fit.py`
- `scripts/run_therapy_fit_test_cases.py`
- `scripts/therapy_fit_metric_validation_results.json`
- `scripts/therapy_fit_endpoint_test_results.json`
- `.cursor/plans/therapy_fit_validation_plan_d7088ecc.plan.md`
- `.cursor/plans/THERAPY_FIT_PRODUCTION_PLAN.md`

**Suggested Folder:** `therapy_fit_validation/`

**Structure:**
```
therapy_t_validation/
├── README.md
├── docs/
│   ├── THERAPY_FIT_VALIDATION_PLAN.md
│   └── THERAPY_FIT_PRODUCTION_PLAN.md
├── scripts/
│   ├── test_therapy_fit_endpoint.py
│   ├── validate_therapy_fit_metrics.py
│   ├── generate_therapy_fit_results.py
│   └── run_therapy_fit_test_cases.py
└── data/
    ├── therapy_fit_metric_validation_results.json
    └── therapy_fit_endpoint_test_results.json
```

---

## 2. 🛡️ Resistance Validation

**Current Location:** `scripts/validation/`

**Files Found:**
- `scripts/validation/run_resistance_validation_suite.py`
- `scripts/validation/out/resistance_validation_suite/`
- `.cursor/plans/SAE_AND_RESISTANCE_PROPHET_AUDIT.md`
- Multiple resistance validation scripts in `scripts/validation/`

**Suggested Folder:** `resistance_validation/`

**Structure:**
```
resistance_validation/
├── README.md
├── docs/
│   └── SAE_AND_RESISTANCE_PROPHET_AUDIT.md
├── scripts/
│  c Cancer Strategy

**Current Location:** `scripts/validation/`

**Files Found:**
- `scripts/validation/e2e_sporadic_workflow.sh`
- `scripts/validation/validate_sporadic_gates.py`
- `scripts/test_sporadic_gates.py`
- `scripts/validation/out/e2e_sporadic/`
- `scripts/validation/out/sporadic_gates/`

**Suggested Folder:** `sporadic_cancer_validation/`

**Structure:**
```
sporadic_cancer_validation/
├── README.md
├── scripts/
│   ├── e2e_sporadic_workflow.sh
│   ├── validate_sporadic_gates.py
│   └── test_sporadic_gates.py
└── reports/
    ├── e2e_sporadic/
    └── sporadic_gates/
```

---

## 4. 📊 DDR Bin Analysis & Validation

**Current Location:** `scripts/validation/`

**Files Found:**
- `scripts/validation/analyze_ddr_bin_sparsity.py`
- `scripts/validation/compare_ddr_bin_aggregation_methods.py`
- `scripts/validation/compute_ddr_bin_competitive_benchmark.py`
- `scripts/validation/compute_per_diamond_auroc.py`
- `scripts/validation/compute_stage_subgr.py`
- `scripts/validation/ddr_bin_analysis_utils.py`
- `scripts/validation/generate_waterfall_ddr_bin_publication.py`
- `scripts/validation/validate_ddr_bin_tcga_ov_survival.py`
- `scripts/validation/validate_ddr_bin_generic_cohort.py`

**Suggested Folder:** `ddr_bin_validation/`

**Structure:**
```
ddr_bin_validation/
├── README.md
├── scripts/
│   ├── analyze_ddr_bin_sparsity.py
│   ├── compare_ddr_bin_aggregation_methods.py
│   ├── compute_ddr_bin_competitive_benchmark.py
│   ├── validate_ddr_bin_tcga_ov_survival.py
│   └── [other DDR bin scripts...]
└── utils/
    └── ddr_bin_analysis_utils.py
```

---

## 5. ⚠️ True SAE / SAE Validation

**Current Location:** `scripts/validation/`

**Files Found:**
- `scripts/validation/extract_true_sae_cohort_from_cbioportal.py`
- `scripts/validation/extract_ov_platinum_sae.py`
- `scripts/validation/compare_proxy_vs_true_sae.py`
- `scripts/validation/validate_true_sae_diamonds.py`
- `scripts/validatiAE_ENABLES.md`
- Multiple SAE-related JSON reports

**Suggested Folder:** `sae_validation/` or `true_sae_validation/`

**Structure:**
```
sae_validation/
├── README.md
├── docs/
│   ├── PROXY_VS_TRUE_SAE_EXPLAINED.md
│   └── WHAT_TRUE_SAE_ENABLES.md
├── scripts/
│   ├── extract_true_sae_cohort_from_cbioportal.py
│   ├── extract_ov_platinum_sae.py
│   ├── compare_proxy_vs_true_sae.py
│   └── validate_true_sae_diamonds.py
└── data/
    └── [SAE reports and data files]
```

---

## 6. 🔬 Mechanism Validation

**Current Location:** `scripts/validation/`

**Files Found:**
- `scripts/validation/validate_mechanism_resistance_prediction.py`
- `scripts/validation/validate_mechanism_trial_matching.py`
- `scripts/validation/validate_mbd4_tp53_mechanism_capabilities.py`
- `scripts/validation/validate_092_mechanism_fit_claim.py`
- Multiple mechanism-related JSON reports

**Suggested Folder:** `mechanism_validation/`

---

## Priority Recomme - Has validation plan, multiple scripts, and results
2. **Resistance Validation** - Has validation suite and dedicated output folder
3. **Sporadic Cancer Strategy** - Has workflow and validation scripts

### Medium Priority (Substantial Work)
4. **DDR Bin Validation** - Many analysis scripts, publication-ready
5. **True SAE Validation** - Has extraction and comparison scripts

### Lower Priority (Can Organize Later)
6. **Mechanism Validation** - Fewer files, can organize when more work is done

---

## Next Steps

1. Review each area to confirm file completeness
2. Create dedicated folders following `dosing_guidance_validation/` pattern
3. Move files and organize into docs/scripts/data/reports subfolders
4. Create README.md for each area
5. Update any path references in scripts

---

**Note:** This is a living document - update as new work areas are identified.
