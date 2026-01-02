# TCGA-OV Cohort Enrichment - Agent Handoff

**Date:** January 1, 2026  
**Status:** ✅ **READY FOR EXECUTION**  
**Owner:** JR (Data/Backend)

---

## ✅ What's Been Done

### 1. Base Cohort Extractor
- **Script:** `extract_tcga_outcomes.py`
- **Status:** ✅ Created and syntax-validated
- **Purpose:** Extracts TCGA-OV cohort with OS/PFS outcomes from cBioPortal
- **Output:** `data/cohorts/tcga_ov_outcomes_v1.json`

### 2. Enrichment Script
- **Script:** `enrich_tcga_ov_biomarkers.py`
- **Status:** ✅ Created and syntax-validated
- **Purpose:** Enriches base cohort with HRD, TMB, MSI, germline BRCA
- **Output:** `data/cohorts/tcga_ov_outcomes_v1_enriched.json`

### 3. Documentation
- **README:** `data/cohorts/README.md` (complete field definitions)
- **This Handoff:** `scripts/cohorts/HANDOFF.md`

### 4. Testing
- ✅ cBioPortal API accessible
- ✅ Study `ov_tcga_pan_can_atlas_2018` exists
- ✅ Clinical attributes available: 60 total
- ✅ TMB attribute found: `TMB_NONSYNONYMOUS`
- ✅ MSI attributes found: `MSI_SCORE_MANTIS`, `MSI_SENSOR_SCORE`
- ⚠️ HRD attributes: 0 in clinical data (will use GISTIC fallback)

---

## 🚀 Execution Steps

### Step 1: Extract Base Cohort

```bash
cd oncology-coPilot/oncology-backend-minimal
python3 scripts/cohorts/extract_tcga_outcomes.py
```

**Expected Output:**
- `data/cohorts/tcga_ov_outcomes_v1.json`
- `data/cohorts/receipts/tcga_ov_outcomes_v1_receipt_YYYYMMDD.json`

**Validation:**
- Check receipt for `cohort_size` (should be ≥400)
- Check receipt for `os_labels` coverage (should be ≥400)
- Verify `os_days` and `os_event` fields are populated

### Step 2: Enrich with Biomarkers

```bash
python3 scripts/cohorts/enrich_tcga_ov_biomarkers.py
```

**Prerequisites:**
- Base cohort must exist (from Step 1)

**Expected Output:**
- `data/cohorts/tcga_ov_outcomes_v1_enriched.json`
- `data/cohorts/receipts/tcga_ov_outcomes_v1_enriched_receipt_YYYYMMDD.json`

**Validation:**
- Check receipt for biomarker coverage:
  - `hrd_score`: May be low if GISTIC extraction needed
  - `tmb`: Should be high (TMB_NONSYNONYMOUS available)
  - `msi_status`: Should be moderate (MSI_SCORE_MANTIS available)
  - `germline_brca_status`: Will be "unknown" (expected)

---

## 📊 Expected Results

### Base Cohort
- **Cohort Size:** ~300-400 patients (TCGA-OV PanCan Atlas)
- **OS Coverage:** ~98% (based on previous extractions)
- **PFS Coverage:** ~95% (may use DFS/OS proxy for some)
- **PFI Coverage:** ~50-70% (when progression < 6 months)

### Enriched Cohort
- **HRD Coverage:** ~30-50% (if GISTIC extraction works) or 0% (if not)
- **TMB Coverage:** ~90-95% (TMB_NONSYNONYMOUS available)
- **MSI Coverage:** ~60-80% (MSI_SCORE_MANTIS available)
- **Germline BRCA:** 0% known (all "unknown" - expected)

---

## ⚠️ Known Issues & Workarounds

### Issue 1: HRD Not in Clinical Attributes
**Status:** ✅ Handled  
**Workaround:** Script attempts GISTIC-based HRD extraction as fallback  
**If GISTIC fails:** HRD scores will be `null` (acceptable per acceptance criteria)

### Issue 2: Base Cohort Must Exist First
**Status:** ✅ Documented  
**Workaround:** Run `extract_tcga_outcomes.py` before enrichment

### Issue 3: API Rate Limiting
**Status:** ✅ Handled  
**Workaround:** Script includes 1s delay between API calls (`API_DELAY = 1.0`)

---

## 🔍 Verification Checklist

After running both scripts, verify:

- [ ] Base cohort JSON exists and is valid JSON
- [ ] Base cohort receipt shows ≥400 patients with OS labels
- [ ] Enriched cohort JSON exists and is valid JSON
- [ ] Enriched cohort has `biomarkers` field for each patient
- [ ] Enrichment receipt shows coverage statistics
- [ ] All biomarker fields are either populated or explicitly `null`/`unknown`
- [ ] Receipt documents biomarker sources and missingness

---

## 📝 Reporting Back

When complete, report:

1. **Base Cohort:**
   - Cohort size (N)
   - OS/PFS coverage (%)
   - Paths to artifact + receipt

2. **Enriched Cohort:**
   - Enriched N
   - HRD coverage (n_with_hrd, %)
   - TMB coverage (n_with_tmb, %)
   - MSI coverage (n_with_msi_status, %)
   - Paths to artifact + receipt

3. **Any Issues:**
   - Script errors
   - Low coverage (explain why)
   - Missing data sources

---

## 🛠️ Script Details

### `extract_tcga_outcomes.py`
- **Dependencies:** `extract_cbioportal_trial_datasets.py`, `pfs_status_parser.py`
- **API Calls:** cBioPortal clinical data endpoint
- **Output Format:** JSON with standardized schema
- **Reproducibility:** Deterministic (except timestamps)

### `enrich_tcga_ov_biomarkers.py`
- **Dependencies:** `tmb_calculator.py`, cBioPortal API
- **API Calls:** cBioPortal clinical attributes + clinical data endpoints
- **Fallback:** GISTIC-based HRD extraction (if needed)
- **Output Format:** JSON with biomarkers added
- **Reproducibility:** Deterministic (except timestamps)

---

## 📚 Reference Documents

- **Mission:** `.cursor/rules/agents/AGENT_JR_OUTCOME_LABELED_COHORT_CONTEXT.mdc`
- **Enrichment Mission:** `.cursor/rules/agents/AGENT_JR_COHORT_ENRICHMENT_HRD_TMB_MSI.mdc`
- **README:** `data/cohorts/README.md`
- **Existing HRD Scripts:**
  - `tools/benchmarks/extract_gistic_hrd.py`
  - `tools/benchmarks/extract_cbioportal_hrd_cohort.py`
- **TMB Calculator:** `scripts/data_acquisition/utils/tmb_calculator.py`

---

## ✅ Ready to Execute

All scripts are:
- ✅ Created
- ✅ Syntax-validated
- ✅ Documented
- ✅ Tested for API access

**Next Step:** Run Step 1 (extract base cohort), then Step 2 (enrich).

Good luck! 🚀

