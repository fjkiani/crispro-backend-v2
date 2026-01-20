# ⏱️ Timing & Chemosensitivity Engine - Data Request (MDC)

**Date:** January 28, 2026  
**Status:** 📋 **DATA REQUEST**  
**Priority:** **P1 - High Priority**  
**Owner:** Resistance Prophet Team  
**Audience:** Data Team, Clinical Collaborators, Manager

---

## 🎯 Executive Summary

This document requests data needed to **validate the Timing & Chemosensitivity Engine** we've built. The engine computes PFI, PTPI, TFI, PFS, OS, and integrates KELIM/CA-125 features, but we need validation data to prove it works.

**Key Insight:** Similar to the SL Proxy Validation Framework, we can use **synthetic data** and **published benchmarks** when ground truth is unavailable. However, real-world data is still preferred for final validation.

---

## 📊 What We've Built (And What Needs Validation)

### ✅ **Timing Engine Core** (COMPLETE - Needs Validation)

**Components:**
- PFI (Platinum-Free Interval) computation
- PTPI (Platinum-to-PARPi Interval) computation
- TFI (Treatment-Free Interval) computation
- PFS/OS from regimen start
- CA-125/KELIM feature joining (from pre-computed table)

**Status:** ✅ Built, ✅ Unit tests passing (12/12), ⏳ Needs validation data

### ❌ **Kinetic Biomarker Framework** (PENDING - Needs Data Plan)

**Components (Not Yet Built):**
- CA-125 KELIM computation from raw measurements
- PSA KELIM computation (future)
- Hierarchical biomarker framework

**Status:** ⏳ Pending implementation, needs data plan for validation

---

## 📋 Data Request by Component

### **1. Timing Metrics Validation Data (PFI, PTPI, TFI, PFS, OS)**

#### **1.1 Required Data Schema**

**Minimum Viable Dataset:**
```
Target: 100-200 patients with complete regimen history

regimen_table = [
    {
        "patient_id": str,
        "regimen_id": str,
        "regimen_start_date": datetime,  # REQUIRED
        "regimen_end_date": datetime,    # REQUIRED
        "regimen_type": str,             # REQUIRED: "platinum", "PARPi", etc.
        "line_of_therapy": int,          # REQUIRED
        "setting": str,                  # REQUIRED: "frontline", "first_recurrence", etc.
        "last_platinum_dose_date": datetime,  # Optional but preferred
        "progression_date": datetime,    # Optional but preferred
        "best_response": str,            # Optional: "CR", "PR", "SD", "PD"
        "best_response_date": datetime,  # Optional
    }
]

survival_table = [
    {
        "patient_id": str,
        "vital_status": str,             # REQUIRED: "Alive", "Dead", "Unknown"
        "death_date": datetime,          # Optional (if vital_status == "Dead")
        "last_followup_date": datetime,  # REQUIRED
    }
]

clinical_table = [
    {
        "patient_id": str,
        "disease_site": str,             # REQUIRED: "ovary", "breast", etc.
        "tumor_subtype": str,            # Optional: "HGSOC", "TNBC", etc.
    }
]
```

#### **1.2 Ground Truth Data (Preferred but Not Required)**

**If available, we'd like:**
- **Manually computed PFI/PTPI/TFI** by clinical experts (for gold-standard validation)
- **Published cohort data** where timing metrics are pre-computed (e.g., ICON7, CHIVA, GOG-0218)
- **Clinical trial datasets** with treatment history and outcomes

**Why We Need It:**
- Validate our computation matches expert calculation
- Compare distributions to published cohorts
- Calibrate edge case handling

**What We Can Do Without It:**
- ✅ Generate **synthetic test cases** with known ground truth
- ✅ Use **published distributions** as targets (ICON7 reports ~30-40% <6m PFI)
- ✅ **Cross-validate** with internal consistency checks (PFI ≤ PTPI, etc.)

#### **1.3 What We Have (Audit)**

**Available Datasets:**
- ✅ **TCGA-OV** (~585 patients) - has PFS/OS, but limited treatment history
- ✅ **cBioPortal datasets** - have mutations, outcomes, but sparse regimen data
- ❌ **No serial CA-125 measurements** - GDC/cBioPortal don't typically include lab values
- ❌ **No treatment history tables** - regimen start/end dates not readily available

**Gap Analysis:**
- **Have:** PFS/OS outcomes, mutations, clinical metadata
- **Missing:** Regimen start/end dates, platinum dose dates, progression dates
- **Workaround:** Use synthetic data + published benchmarks for proxy validation

---

### **2. KELIM Computation Validation Data (CA-125 Kinetics)**

#### **2.1 Required Data Schema**

**Minimum Viable Dataset:**
```
Target: 50-100 ovarian cancer patients with serial CA-125 measurements

ca125_measurements = [
    {
        "patient_id": str,
        "regimen_id": str,               # REQUIRED: Links to regimen_table
        "measurement_date": datetime,    # REQUIRED
        "ca125_value": float,            # REQUIRED: U/mL
    }
]

# Each patient needs:
# - Baseline: 1 measurement within 30 days BEFORE treatment start
# - Treatment: ≥3 measurements within first 100 days AFTER treatment start
# - Total: ≥4 measurements per regimen
```

**Treatment Context Required:**
- Regimen start date (from `regimen_table`)
- Regimen type (platinum vs non-platinum)
- Treatment line (frontline vs recurrence)

#### **2.2 Ground Truth KELIM Scores (Preferred but Not Required)**

**If available, we'd like:**
- **Pre-computed KELIM scores** from ICON7, CHIVA, GOG-0218 trials
- **Published KELIM distributions** (e.g., ~40% favorable KELIM in ICON7)
- **KELIM cutpoints** from GCIG meta-analysis (≥1.0 = favorable)

**Why We Need It:**
- Validate our K computation matches published methodology
- Compare distributions to literature
- Calibrate categorization (favorable/intermediate/unfavorable)

**What We Can Do Without It:**
- ✅ Generate **synthetic CA-125 trajectories** with known K values (proxy ground truth)
- ✅ Use **published distributions** as targets (ICON7: ~40% favorable, mean K ≈ 0.8)
- ✅ **Monte Carlo simulation** with realistic noise to validate robustness
- ✅ **Cross-validate** with predictive associations (KELIM vs PFS/OS if outcomes available)

#### **2.3 What We Have (Audit)**

**Available Datasets:**
- ❌ **No serial CA-125 measurements** - GDC, cBioPortal, TCGA don't include lab values
- ❌ **No ground truth KELIM scores** - not available in public datasets
- ⚠️ **Published distributions** - ICON7, CHIVA report KELIM distributions (but not raw data)

**Gap Analysis:**
- **Have:** Published KELIM distributions, cutpoints, associations (literature)
- **Missing:** Raw CA-125 measurements, ground truth KELIM scores
- **Workaround:** Use synthetic data + published benchmarks for proxy validation

**What We Can Produce Using Proxies:**
- ✅ **Synthetic CA-125 data** with known K values (CA-125(t) = CA-125(0) * exp(-K * t))
- ✅ **Monte Carlo simulation** with realistic noise (CV = 10-15%)
- ✅ **Validation protocol** using published distributions as targets

---

## 🎯 Proxy Validation Strategy (What We Can Do Without Ground Truth)

### **Strategy 1: Synthetic Data with Known Ground Truth**

**For Timing Metrics:**
```python
# Known ground truth: PFI = 200 days (6.6 months)
regimen_1 = {
    "regimen_start_date": datetime(2020, 1, 1),
    "regimen_end_date": datetime(2020, 6, 1),
    "last_platinum_dose_date": datetime(2020, 5, 15),
    "progression_date": datetime(2020, 12, 1),  # 200 days after last dose
}

# Expected: PFI_days = 200, PFI_category = "6-12m"
```

**For KELIM:**
```python
# Known ground truth: K = 1.2 (favorable)
baseline_ca125 = 500.0  # U/mL
k_ground_truth = 1.2
treatment_start = datetime(2020, 1, 1)

# Generate measurements at days 0, 21, 42, 63
measurements = []
for days in [0, 21, 42, 63]:
    ca125_value = baseline_ca125 * np.exp(-k_ground_truth * (days / 30.0))
    measurements.append({
        "measurement_date": treatment_start + timedelta(days=days),
        "ca125_value": ca125_value
    })

# Expected: Computed K ≈ 1.2 (within ±0.1), category = "favorable"
```

**What This Proves:**
- ✅ Computation accuracy (computed value ≈ ground truth)
- ✅ Edge case handling (missing dates, overlapping regimens)
- ✅ Data validation (rejects insufficient measurements)

### **Strategy 2: Published Benchmark Validation**

**For Timing Metrics:**
- **ICON7, CHIVA, GOG-0218** - published PFI distributions (~30-40% <6m, ~30-40% 6-12m, ~20-30% >12m)
- **PARPi trials** (SOLO-2, NOVA) - published PTPI distributions
- **Compare our computed distributions** to published cohorts

**For KELIM:**
- **ICON7 trial** - ~40% favorable KELIM (K ≥ 1.0), mean K ≈ 0.8
- **CHIVA trial** - ~35-45% favorable KELIM
- **GCIG meta-analysis** - standardized cutpoints (≥1.0 = favorable)
- **Compare our computed distributions** to published cohorts

**What This Proves:**
- ✅ Distribution matching (our distribution ≈ published distribution)
- ✅ Calibration accuracy (cutpoints match literature)
- ✅ Realistic behavior (not just synthetic edge cases)

### **Strategy 3: Monte Carlo Simulation**

**For KELIM:**
- Generate 1000 synthetic patients with known K values
- Add realistic measurement noise (CV = 10-15%)
- Vary measurement timing (realistic clinical schedules)
- Compute K on noisy data
- Compare computed K to ground truth K

**What This Proves:**
- ✅ Robustness to noise (computed K correlates with ground truth: r > 0.8)
- ✅ Robustness to missing data (works with 3 measurements, better with 5+)
- ✅ Realistic performance characteristics

---

## 📁 Data Sources & Access

### **Internal Data (What We Have)**

| Source | Dataset | Patients | Has Timing? | Has CA-125? | Access |
|--------|---------|----------|-------------|-------------|--------|
| **TCGA-OV** | `tcga_ov_enriched_v2.json` | 585 | ⚠️ Limited | ❌ No | ✅ Available |
| **cBioPortal** | `ov_tcga_pan_can_atlas_2018` | 585 | ⚠️ Limited | ❌ No | ✅ Public |
| **cBioPortal** | MSK-IMPACT | 10,000+ | ⚠️ Limited | ❌ No | ✅ Public |

**Limitations:**
- TCGA-OV has PFS/OS outcomes, but **no detailed treatment history** (regimen start/end dates)
- cBioPortal has mutations, outcomes, but **no serial CA-125 measurements**
- Public datasets typically **don't include lab values** (CA-125, PSA, etc.)

### **Published Benchmarks (What We Can Use)**

| Source | What It Provides | How We Use It |
|--------|------------------|---------------|
| **ICON7 trial** | PFI distribution, KELIM distribution | Compare our computed distributions |
| **CHIVA trial** | PFI distribution, KELIM distribution | Compare our computed distributions |
| **GOG-0218** | PFI distribution, KELIM distribution | Compare our computed distributions |
| **GCIG meta-analysis** | KELIM cutpoints (≥1.0 = favorable) | Validate categorization |
| **PARPi trials** (SOLO-2, NOVA) | PTPI distribution | Compare our computed distributions |

**Access:** ✅ Published literature (extract distributions from papers)

### **Collaborator Data (What We Need)**

| Source | What We Need | Priority | Access |
|--------|--------------|----------|--------|
| **Clinical Trial Databases** | Regimen history + outcomes | **HIGH** | ⚠️ May require collaboration |
| **Institutional Datasets** | Serial CA-125 measurements | **HIGH** | ⚠️ May require collaboration |
| **ICON7/CHIVA Raw Data** | Raw CA-125 + KELIM scores | **MEDIUM** | ⚠️ May require collaboration |
| **Project Data Sphere** | Treatment history + outcomes | **MEDIUM** | ⚠️ May require collaboration |

**Gap:** Real-world data with complete treatment history is **sparse in public datasets**

---

## 🎯 Data Request Summary

### **Minimum Viable Dataset (MVP)**

**Timing Metrics Validation:**
```
Priority: HIGH
Quantity: 100-200 patients
Required Fields:
  ✅ Regimen start/end dates
  ✅ Regimen type (platinum, PARPi, etc.)
  ✅ Treatment line
  ✅ Progression dates (preferred)
  ✅ Survival outcomes (PFS/OS)

Optional Fields:
  ⚠️ Last platinum dose dates (preferred)
  ⚠️ Best response (CR/PR/SD/PD)
```

**KELIM Validation:**
```
Priority: HIGH (for framework validation)
Quantity: 50-100 ovarian cancer patients
Required Fields:
  ✅ Serial CA-125 measurements (≥4 per regimen)
  ✅ Measurement dates
  ✅ Treatment start dates (from regimen_table)
  ✅ Regimen type (platinum vs non-platinum)

Optional Fields:
  ⚠️ Pre-computed KELIM scores (preferred for gold-standard validation)
  ⚠️ Outcomes (PFS/OS) for predictive validation
```

### **What We Can Do With Proxies**

**If we don't have real-world data, we can:**

1. **Generate Synthetic Data** (with known ground truth)
   - Synthetic patient journeys with known PFI/PTPI/TFI values
   - Synthetic CA-125 trajectories with known K values
   - Test edge cases (missing dates, overlapping regimens, insufficient measurements)

2. **Use Published Benchmarks** (as distribution targets)
   - Compare our computed PFI distributions to ICON7/CHIVA (~30-40% <6m)
   - Compare our computed KELIM distributions to ICON7 (~40% favorable)
   - Validate cutpoints match GCIG standards (≥1.0 = favorable)

3. **Monte Carlo Simulation** (for robustness validation)
   - Generate 1000 synthetic patients with realistic noise
   - Validate robustness to noise, missing data, timing variation
   - Document performance characteristics

**Proxy Validation Success Criteria:**
- ✅ Computed values match ground truth within tolerance (synthetic data)
- ✅ Distributions match published cohorts (±10%)
- ✅ Robustness to noise (r > 0.8 correlation, ≥90% category accuracy)

---

## 📋 Specific Data Requests

### **Request 1: Treatment History Data (HIGH PRIORITY)**

**What We Need:**
- Regimen tables with start/end dates, regimen types, treatment lines
- Progression dates (when available)
- Survival outcomes (PFS/OS)

**Why We Need It:**
- Validate PFI/PTPI/TFI/PFS/OS computations
- Compare distributions to published cohorts
- Test edge cases (missing dates, overlapping regimens)

**What We Can Do Without It:**
- ✅ Generate synthetic test cases with known ground truth
- ✅ Use published distributions as targets
- ❌ Cannot validate on real-world data

**Where We Can Get It:**
- ⚠️ Clinical trial databases (may require collaboration)
- ⚠️ Institutional datasets (may require collaboration)
- ❌ Not available in public datasets (TCGA, cBioPortal)

**Requested Format:**
```json
{
  "regimen_table": [
    {
      "patient_id": "P001",
      "regimen_id": "R1",
      "regimen_start_date": "2020-01-15",
      "regimen_end_date": "2020-07-01",
      "regimen_type": "platinum",
      "line_of_therapy": 1,
      "setting": "frontline",
      "last_platinum_dose_date": "2020-06-15",
      "progression_date": "2020-12-01"
    }
  ],
  "survival_table": [
    {
      "patient_id": "P001",
      "vital_status": "Alive",
      "last_followup_date": "2021-06-01"
    }
  ],
  "clinical_table": [
    {
      "patient_id": "P001",
      "disease_site": "ovary",
      "tumor_subtype": "HGSOC"
    }
  ]
}
```

---

### **Request 2: Serial CA-125 Measurements (HIGH PRIORITY)**

**What We Need:**
- Longitudinal CA-125 measurements with dates
- Treatment start dates (to anchor measurements)
- Regimen context (regimen_id, regimen_type)

**Why We Need It:**
- Validate KELIM computation from raw measurements
- Test data validation logic (sufficient measurements, baseline, time window)
- Validate categorization (favorable/intermediate/unfavorable)

**What We Can Do Without It:**
- ✅ Generate synthetic CA-125 trajectories with known K values
- ✅ Use published distributions as targets
- ✅ Monte Carlo simulation for robustness validation
- ❌ Cannot validate on real-world data

**Where We Can Get It:**
- ❌ Not available in public datasets (GDC, cBioPortal, TCGA don't include lab values)
- ⚠️ Institutional datasets (may require collaboration)
- ⚠️ Clinical trial databases (ICON7, CHIVA - may require collaboration)
- ⚠️ Project Data Sphere (may require collaboration)

**Requested Format:**
```json
{
  "ca125_measurements": [
    {
      "patient_id": "P001",
      "regimen_id": "R1",
      "measurement_date": "2020-01-15",
      "ca125_value": 500.0
    },
    {
      "patient_id": "P001",
      "regimen_id": "R1",
      "measurement_date": "2020-02-05",
      "ca125_value": 350.0
    }
    // ... ≥4 measurements per regimen
  ]
}
```

---

### **Request 3: Pre-Computed KELIM Scores (MEDIUM PRIORITY)**

**What We Need:**
- Pre-computed KELIM scores (if available from ICON7, CHIVA, etc.)
- Associated CA-125 measurements (to validate our computation)

**Why We Need It:**
- Gold-standard validation (our computation vs published computation)
- Calibrate edge case handling
- Validate modeling approach (log-linear vs mixed-effects)

**What We Can Do Without It:**
- ✅ Use synthetic data with known K values
- ✅ Compare distributions to published cohorts
- ⚠️ Cannot validate exact computation methodology

**Where We Can Get It:**
- ⚠️ ICON7, CHIVA, GOG-0218 trials (may require collaboration)
- ⚠️ Published papers (extract distributions, but not raw scores)
- ❌ Not available in public datasets

**Requested Format:**
```json
{
  "kelim_scores": [
    {
      "patient_id": "P001",
      "regimen_id": "R1",
      "kelim_k_value": 1.2,
      "kelim_category": "favorable",
      "computation_method": "mixed_effects",
      "measurements_used": 5
    }
  ]
}
```

---

### **Request 4: Outcomes Data (MEDIUM PRIORITY)**

**What We Need:**
- PFS/OS from regimen start (if not already in survival_table)
- Best response (CR/PR/SD/PD) per regimen
- Platinum-free interval outcomes (for predictive validation)

**Why We Need It:**
- Validate predictive associations (KELIM vs PFS/OS)
- Validate PFI categorization predicts outcomes
- Cross-validate timing engine outputs

**What We Can Do Without It:**
- ✅ Validate computation accuracy (timing metrics computed correctly)
- ✅ Validate distribution matching (distributions match literature)
- ❌ Cannot validate predictive associations

**Where We Can Get It:**
- ✅ TCGA-OV has PFS/OS (but limited treatment history)
- ✅ cBioPortal has PFS/OS (but limited treatment history)
- ⚠️ Clinical trial databases (may have better treatment history linkage)

---

## 🔬 Validation Plan (What We Can Do With Each Data Type)

### **Scenario A: We Get Real-World Treatment History Data**

**What We Can Validate:**
1. ✅ PFI/PTPI/TFI/PFS/OS computation accuracy (if ground truth available)
2. ✅ Distribution matching (compare to published cohorts)
3. ✅ Edge case handling (missing dates, overlapping regimens)
4. ✅ Predictive associations (PFI category vs outcomes)

**Validation Protocol:**
- Compute timing metrics for all patients
- Compare distributions to ICON7/CHIVA (if ovarian cancer)
- If ground truth available, compute accuracy metrics
- Validate edge cases handled gracefully

---

### **Scenario B: We Get Serial CA-125 Measurements**

**What We Can Validate:**
1. ✅ KELIM computation accuracy (if ground truth KELIM available)
2. ✅ Distribution matching (compare to ICON7/CHIVA)
3. ✅ Data validation (rejects insufficient measurements)
4. ✅ Predictive associations (KELIM vs PFS/OS)

**Validation Protocol:**
- Compute KELIM for all patients with sufficient measurements
- Compare distribution to ICON7 (~40% favorable)
- If ground truth KELIM available, compute accuracy metrics
- Validate predictive associations (KELIM vs PFS/OS)

---

### **Scenario C: We Only Have Published Benchmarks (No Raw Data)**

**What We Can Validate:**
1. ✅ Distribution matching (synthetic data → compare to published distributions)
2. ✅ Cutpoint validation (categorization matches GCIG standards)
3. ✅ Computation accuracy (synthetic data with known ground truth)
4. ✅ Robustness validation (Monte Carlo simulation)

**Validation Protocol:**
- Generate synthetic cohort matching published characteristics
- Compute timing metrics / KELIM on synthetic data
- Compare distributions to published cohorts (±10%)
- Validate cutpoints match literature

**Limitations:**
- ❌ Cannot validate on real-world data
- ❌ Cannot validate predictive associations (need outcomes)
- ✅ Can still prove computation works correctly (synthetic ground truth)

---

## ✅ Success Criteria by Data Availability

### **With Real-World Data (Gold Standard)**

**Timing Metrics:**
- ✅ Computed values match ground truth (if available) or match published distributions (±10%)
- ✅ Category accuracy ≥95% (if ground truth available)
- ✅ Edge cases handled gracefully (missing dates, overlapping regimens)

**KELIM:**
- ✅ Computed K matches ground truth K (within ±10%) or matches published distributions
- ✅ Category accuracy ≥95% (if ground truth available)
- ✅ Predictive associations match literature (KELIM vs PFS/OS: HR ≈ published HR ±30%)

---

### **With Proxy Validation Only (No Real-World Data)**

**Timing Metrics:**
- ✅ Computed values match ground truth in synthetic test cases (within 1 day tolerance)
- ✅ Distributions match published cohorts (±10%)
- ✅ Internal consistency checks pass (PFI ≤ PTPI, PFS ≤ OS)

**KELIM:**
- ✅ Computed K matches ground truth K in synthetic data (within ±10%)
- ✅ Distributions match published cohorts (±10%)
- ✅ Robustness to noise (r > 0.8 correlation, ≥90% category accuracy)

**What This Proves:**
- ✅ Computation works correctly (synthetic ground truth)
- ✅ Distributions are realistic (match literature)
- ✅ System is robust (handles noise, missing data)
- ⚠️ Cannot prove predictive value without outcomes data

---

## 📋 Data Request Checklist

### **Timing Metrics Validation**

- [ ] **Treatment History Data**
  - [ ] Regimen tables with start/end dates (100-200 patients)
  - [ ] Progression dates (preferred)
  - [ ] Survival outcomes (PFS/OS)
  - [ ] Last platinum dose dates (preferred)
  - [ ] **Alternative:** Synthetic test cases with known ground truth

- [ ] **Published Benchmarks**
  - [ ] ICON7/CHIVA PFI distributions (extract from literature)
  - [ ] PARPi trial PTPI distributions (extract from literature)
  - [ ] **Status:** ✅ Available in published literature

---

### **KELIM Validation**

- [ ] **Serial CA-125 Measurements**
  - [ ] Longitudinal CA-125 with dates (50-100 patients)
  - [ ] Treatment start dates (to anchor measurements)
  - [ ] Regimen context (regimen_id, regimen_type)
  - [ ] **Alternative:** Synthetic CA-125 trajectories with known K values

- [ ] **Pre-Computed KELIM Scores**
  - [ ] ICON7/CHIVA KELIM scores (if accessible)
  - [ ] **Alternative:** Published distributions as targets

- [ ] **Published Benchmarks**
  - [ ] ICON7 KELIM distribution (~40% favorable, mean K ≈ 0.8)
  - [ ] CHIVA KELIM distribution (~35-45% favorable)
  - [ ] GCIG cutpoints (≥1.0 = favorable)
  - [ ] **Status:** ✅ Available in published literature

---

## 🎯 What We Can Produce Using Proxies

### **1. Synthetic Test Cases**

**For Timing Metrics:**
- Generate 100+ synthetic patient journeys with known PFI/PTPI/TFI values
- Test edge cases (missing dates, overlapping regimens, multiple platinum lines)
- Validate computation accuracy (computed value ≈ ground truth)

**For KELIM:**
- Generate 100+ synthetic CA-125 trajectories with known K values
- Test data validation (insufficient measurements, missing baseline)
- Validate computation accuracy (computed K ≈ ground truth K)

**Deliverable:** Test suite with known ground truth for continuous validation

---

### **2. Published Benchmark Comparisons**

**For Timing Metrics:**
- Extract PFI distributions from ICON7, CHIVA, GOG-0218 papers
- Compute PFI on available datasets (if any) or synthetic cohort
- Compare distributions (median, IQR, category proportions)

**For KELIM:**
- Extract KELIM distributions from ICON7, CHIVA papers
- Compute KELIM on synthetic cohort matching published characteristics
- Compare distributions (favorable %, mean K, SD)

**Deliverable:** Validation report comparing our distributions to published cohorts

---

### **3. Monte Carlo Simulation**

**For KELIM:**
- Generate 1000 synthetic patients with known K values
- Add realistic noise (CV = 10-15%)
- Vary measurement timing (realistic clinical schedules)
- Compute K on noisy data
- Document robustness (correlation, category accuracy)

**Deliverable:** Robustness validation report with performance characteristics

---

## 📊 Data Availability Matrix

| Data Type | Have | Need | Can Proxy? | Priority |
|-----------|------|------|------------|----------|
| **Treatment History** | ⚠️ Limited (TCGA-OV) | ✅ Yes | ✅ Yes (synthetic) | **HIGH** |
| **Serial CA-125** | ❌ No | ✅ Yes | ✅ Yes (synthetic) | **HIGH** |
| **Pre-Computed KELIM** | ❌ No | ⚠️ Preferred | ✅ Yes (synthetic) | **MEDIUM** |
| **Published Distributions** | ✅ Yes (literature) | ✅ Yes | N/A | **HIGH** |
| **Outcomes (PFS/OS)** | ✅ Yes (TCGA-OV) | ⚠️ Preferred | ❌ No | **MEDIUM** |
| **Ground Truth PFI/PTPI** | ❌ No | ⚠️ Preferred | ✅ Yes (synthetic) | **MEDIUM** |

---

## 🎯 Recommendations

### **Short-Term (Immediate - Proxy Validation)**

1. **Generate Synthetic Test Cases** (2-3 days)
   - Create 100+ synthetic patient journeys with known timing metrics
   - Create 100+ synthetic CA-125 trajectories with known K values
   - Implement test suite for continuous validation

2. **Extract Published Benchmarks** (1-2 days)
   - Extract PFI distributions from ICON7, CHIVA, GOG-0218 papers
   - Extract KELIM distributions from ICON7, CHIVA papers
   - Document published cutpoints and standards

3. **Run Proxy Validation** (3-5 days)
   - Compute timing metrics / KELIM on synthetic data
   - Compare distributions to published benchmarks
   - Document validation results

**Deliverable:** Validation report proving computation works (using proxies)

---

### **Medium-Term (3-6 months - Real-World Validation)**

1. **Request Collaborator Data**
   - Clinical trial databases (ICON7, CHIVA if accessible)
   - Institutional datasets (MSK, Dana-Farber if accessible)
   - Project Data Sphere (if accessible)

2. **Validate on Real-World Data**
   - Compute timing metrics / KELIM on real-world data
   - Compare to published distributions
   - Validate predictive associations (if outcomes available)

**Deliverable:** Validation report on real-world data (gold standard)

---

## 🔗 Related Documents

- **Validation Plan:** `TIMING_CHEMOSENSITIVITY_ENGINE_VALIDATION_PLAN.md`
- **Implementation Guide:** `TIMING_CHEMOSENSITIVITY_ENGINE_IMPLEMENTATION.md`
- **SL Proxy Framework:** `.cursor/MOAT/PREVENTION/PLUMBER_BUILD_SPEC.md` (similar proxy approach)

---

**Last Updated:** January 28, 2026  
**Status:** 📋 **DATA REQUEST PENDING**  
**Next Steps:** Generate synthetic test cases, extract published benchmarks, run proxy validation
