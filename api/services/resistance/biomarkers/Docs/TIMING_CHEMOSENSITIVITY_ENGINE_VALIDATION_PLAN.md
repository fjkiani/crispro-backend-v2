# ⏱️ Timing & Chemosensitivity Engine - Validation Plan

**Date:** January 28, 2026  
**Status:** 📋 **VALIDATION PLAN**  
**Priority:** **P1 - High Priority**  
**Owner:** Resistance Prophet Team

---

## 🎯 Executive Summary

This document outlines **what data we need**, **how to use proxy validation** for KELIM scores when ground truth is unavailable, and **how to prove the system works** for both the timing engine (already built) and the kinetic biomarker framework (pending).

**Key Insight:** Similar to the SL Proxy Validation Framework, we can use **synthetic data**, **published benchmarks**, and **cross-validation** to validate components where clinical outcomes are sparse.

---

## 📊 What We've Built (And What Needs Validation)

### ✅ **Timing Engine Core** (COMPLETE - Needs Validation)

**Components:**
- PFI (Platinum-Free Interval) computation
- PTPI (Platinum-to-PARPi Interval) computation
- TFI (Treatment-Free Interval) computation
- PFS/OS from regimen start
- CA-125/KELIM feature joining (from pre-computed table)

**Validation Needs:**
- Regimen data with dates (start, end, progression)
- Survival data (death dates, follow-up dates)
- Ground truth PFI/PTPI/TFI/PFS/OS (if available)

### ❌ **Kinetic Biomarker Framework** (PENDING - Needs Validation Plan)

**Components (Not Yet Built):**
- CA-125 KELIM computation from raw measurements
- PSA KELIM computation (future)
- Hierarchical biomarker framework

**Validation Needs:**
- Raw CA-125 measurements with dates
- Ground truth KELIM scores (if available)
- **OR: Synthetic CA-125 data with known K values**

---

## 📋 Data Requirements by Component

### **1. Timing Metrics Validation (PFI, PTPI, TFI, PFS, OS)**

#### **1.1 Required Data Schema**

```python
# Input Data Required
regimen_table = [
    {
        "patient_id": str,
        "regimen_id": str,
        "regimen_start_date": datetime,
        "regimen_end_date": datetime,
        "regimen_type": str,  # "platinum", "PARPi", etc.
        "line_of_therapy": int,
        "setting": str,  # "frontline", "first_recurrence", etc.
        "last_platinum_dose_date": datetime,  # Optional
        "progression_date": datetime,  # Optional
    }
]

survival_table = [
    {
        "patient_id": str,
        "vital_status": str,  # "Alive", "Dead", "Unknown"
        "death_date": datetime,  # Optional
        "last_followup_date": datetime,
    }
]

clinical_table = [
    {
        "patient_id": str,
        "disease_site": str,  # "ovary", "breast", etc.
        "tumor_subtype": str,  # Optional
    }
]
```

#### **1.2 Ground Truth (If Available)**

For **gold-standard validation**, we need:
- **Manually computed PFI/PTPI/TFI** by clinical experts
- **Published cohorts** where timing metrics are pre-computed (e.g., clinical trial datasets)
- **ICON7, CHIVA, GOG-0218** trial data (if accessible) - these have computed PFI/KELIM

#### **1.3 Proxy Validation Strategy**

**When ground truth is unavailable:**

1. **Synthetic Data with Known Ground Truth:**
   - Generate synthetic patient journeys with known PFI/PTPI/TFI values
   - Test edge cases (missing dates, overlapping regimens, multiple platinum lines)
   - Validate that our computation matches known ground truth

2. **Cross-Validation with Published Benchmarks:**
   - Use published studies that report PFI distributions
   - Validate our PFI categorization (<6m, 6-12m, >12m) matches literature cutpoints
   - Compare our PTPI distributions with published PARPi studies

3. **Internal Consistency Checks:**
   - PFI should be ≤ PTPI when PARPi is next platinum regimen
   - TFI should be ≤ PFI when regimens are platinum-based
   - PFS should be ≤ OS (by definition)

**Example Synthetic Test Case:**
```python
# Known ground truth: PFI = 200 days (6.6 months)
regimen_1 = {
    "patient_id": "SYNTH001",
    "regimen_id": "R1",
    "regimen_start_date": datetime(2020, 1, 1),
    "regimen_end_date": datetime(2020, 6, 1),
    "regimen_type": "platinum",
    "last_platinum_dose_date": datetime(2020, 5, 15),
}

regimen_2 = {
    "patient_id": "SYNTH001",
    "regimen_id": "R2",
    "regimen_start_date": datetime(2020, 12, 1),  # 200 days after R1 last dose
    "regimen_type": "platinum",
}

# Expected: PFI_days = 200, PFI_category = "6-12m"
```

---

### **2. KELIM Computation Validation (Kinetic Biomarker Framework)**

#### **2.1 Required Data Schema**

```python
# Raw CA-125 Measurements
ca125_measurements = [
    {
        "patient_id": str,
        "regimen_id": str,
        "measurement_date": datetime,
        "ca125_value": float,  # U/mL
    }
]

# Treatment Start Date
treatment_start_date = datetime  # Regimen start date
```

#### **2.2 Ground Truth KELIM Scores (If Available)**

**Published Datasets:**
- **ICON7, CHIVA, GOG-0218 trials** - these have computed KELIM scores
- **GCIG meta-analysis** - has standardized KELIM cutpoints (≥1.0 = favorable)
- **Real-world validation studies** - may have KELIM scores for cross-validation

**Data Sources to Explore:**
- TCGA-OV (if CA-125 measurements available)
- Published cohorts with longitudinal CA-125
- Clinical trial databases (if accessible)

#### **2.3 Proxy Validation Strategy for KELIM**

**When ground truth KELIM is unavailable, use proxy validation similar to SL framework:**

##### **Strategy 1: Synthetic CA-125 Data with Known K Values**

**Approach:** Generate synthetic CA-125 decay curves with known elimination rate constant K.

**Model:** CA-125(t) = CA-125(0) * exp(-K * t)

**Validation Protocol:**
1. **Generate synthetic measurements** with known K values:
   ```python
   # Known ground truth: K = 1.2 (favorable)
   baseline_ca125 = 500.0  # U/mL
   k_ground_truth = 1.2
   
   # Generate measurements at days 0, 21, 42, 63, 90
   measurements = []
   for days in [0, 21, 42, 63, 90]:
       ca125_value = baseline_ca125 * np.exp(-k_ground_truth * (days / 30.0))
       measurements.append({
           "measurement_date": treatment_start + timedelta(days=days),
           "ca125_value": ca125_value
       })
   ```

2. **Compute K using our engine:**
   ```python
   result = ca125_kelim_engine.compute_k_value(
       marker_values=measurements,
       treatment_start_date=treatment_start
   )
   ```

3. **Validate:**
   - Computed K ≈ ground truth K (within tolerance, e.g., ±0.1)
   - Category matches expected (K ≥ 1.0 → "favorable")
   - Confidence reflects data quality (more measurements → higher confidence)

**Success Criteria:**
- Computed K within 5-10% of ground truth for synthetic data
- Category accuracy ≥95% for synthetic cases
- Confidence correlates with data quality (number of measurements, time span)

##### **Strategy 2: Cross-Validation with Published Benchmarks**

**Approach:** Use published KELIM cutpoints and distributions to validate our computation.

**Validation Protocol:**
1. **Use published cutpoints:**
   - KELIM ≥ 1.0 = favorable (standardized, from GCIG)
   - KELIM 0.5-1.0 = intermediate
   - KELIM < 0.5 = unfavorable

2. **Validate against published distributions:**
   - ICON7: ~40% favorable KELIM (K ≥ 1.0)
   - CHIVA: ~35-45% favorable KELIM
   - Compare our computed distributions with published cohorts

3. **Validate predictive value (if outcomes available):**
   - Favorable KELIM → longer PFS/OS (HR < 1.0)
   - Favorable KELIM → higher complete IDS resection rate
   - Favorable KELIM → longer platinum-free interval

**Success Criteria:**
- KELIM distribution matches published cohorts (±5-10%)
- Predictive associations (KELIM vs PFS/OS) match published HRs (±20%)
- Categorization accuracy matches GCIG standards

##### **Strategy 3: Simulation-Based Validation (Monte Carlo)**

**Approach:** Simulate realistic CA-125 trajectories with known K values and noise.

**Validation Protocol:**
1. **Generate realistic trajectories:**
   - Sample K from known distribution (e.g., mean K = 0.8, SD = 0.4)
   - Add measurement noise (coefficient of variation = 10-15%)
   - Vary measurement timing (realistic clinical schedules)

2. **Compute K on simulated data:**
   - Run our KELIM engine on simulated measurements
   - Compare computed K to ground truth K

3. **Validate robustness:**
   - Effect of missing measurements (3 vs 4 vs 5 measurements)
   - Effect of measurement noise (0%, 10%, 20% CV)
   - Effect of timing variation (ideal vs realistic schedules)

**Success Criteria:**
- Computed K correlates with ground truth (r > 0.8) across noise levels
- Category accuracy ≥90% even with realistic noise
- Robust to missing measurements (works with 3 measurements, better with 5+)

---

## 🔬 Validation Protocol for Timing Engine (Already Built)

### **Phase 1: Unit Tests (✅ COMPLETE)**

**Status:** Already implemented in `test_timing_chemo_features.py`

**Coverage:**
- ✅ TFI computation (first regimen, multiple regimens)
- ✅ PFI computation (single platinum, multiple platinum lines)
- ✅ PTPI computation (PARPi after platinum, no prior platinum)
- ✅ PFS/OS computation (with/without progression, with/without death)
- ✅ CA-125 integration (ovary uses CA-125, breast doesn't)
- ✅ Missing data handling

**Result:** 12/12 tests passing ✅

### **Phase 2: Synthetic Data Validation**

**Objective:** Validate timing computations with known ground truth.

**Test Cases:**

#### **Test Case 1: Simple PFI (Known Ground Truth)**
```python
# Ground truth: PFI = 169 days (5.6 months) → category "6-12m"
regimen_1 = {
    "patient_id": "VALID001",
    "regimen_id": "R1",
    "regimen_start_date": datetime(2020, 1, 1),
    "regimen_end_date": datetime(2020, 7, 1),
    "regimen_type": "platinum",
    "last_platinum_dose_date": datetime(2020, 6, 15),
    "progression_date": datetime(2020, 12, 1),  # 169 days after last dose
}

# Expected: PFI_days = 169, PFI_category = "6-12m"
```

#### **Test Case 2: Multiple Platinum Lines (Known Ground Truth)**
```python
# Ground truth: PFI for R3 = 243 days (8 months) → category "6-12m"
regimen_1 = {
    "regimen_id": "R1",
    "regimen_start_date": datetime(2020, 1, 1),
    "regimen_end_date": datetime(2020, 7, 1),
    "regimen_type": "platinum",
}

regimen_2 = {
    "regimen_id": "R2",
    "regimen_start_date": datetime(2020, 9, 1),
    "regimen_end_date": datetime(2020, 12, 1),
    "regimen_type": "non_platinum_chemo",
}

regimen_3 = {
    "regimen_id": "R3",
    "regimen_start_date": datetime(2021, 3, 1),  # 243 days after R1 end
    "regimen_type": "platinum",
}

# Expected: R3 PFI_days = 243, PFI_category = "6-12m"
```

#### **Test Case 3: PTPI (Known Ground Truth)**
```python
# Ground truth: PTPI = 169 days
regimen_1 = {
    "regimen_id": "R1",
    "regimen_start_date": datetime(2020, 1, 1),
    "regimen_end_date": datetime(2020, 7, 1),
    "regimen_type": "platinum",
    "last_platinum_dose_date": datetime(2020, 6, 15),
}

regimen_2 = {
    "regimen_id": "R2",
    "regimen_start_date": datetime(2020, 12, 1),  # 169 days after last dose
    "regimen_type": "PARPi",
}

# Expected: R2 PTPI_days = 169
```

**Success Criteria:**
- Computed values match ground truth within 1 day tolerance
- Categories match expected categories (100% accuracy)
- Missing data handled gracefully (returns None, not 0)

### **Phase 3: Published Benchmark Validation**

**Objective:** Validate timing distributions match published cohorts.

**Data Sources:**
- **ICON7, CHIVA, GOG-0218** - published PFI distributions
- **PARPi trials** (SOLO-2, NOVA, etc.) - published PTPI distributions

**Validation Protocol:**
1. Extract published PFI/PTPI distributions from literature
2. Compute PFI/PTPI using our engine on available datasets
3. Compare distributions (median, IQR, categories)

**Success Criteria:**
- PFI distribution matches published cohorts (±10%)
- PTPI distribution matches published PARPi trials (±15%)
- Category proportions match literature (e.g., ~30-40% <6m PFI)

---

## 🔬 Validation Protocol for KELIM (Kinetic Biomarker Framework)

### **Phase 1: Synthetic Data Validation (Proxy Validation)**

**Objective:** Validate KELIM computation with known K values.

#### **Test Case 1: Favorable KELIM (K = 1.2)**
```python
# Ground truth: K = 1.2 (favorable)
baseline_ca125 = 500.0  # U/mL
k_ground_truth = 1.2
treatment_start = datetime(2020, 1, 1)

# Generate measurements at days 0, 21, 42, 63
measurements = []
for days in [0, 21, 42, 63]:
    ca125_value = baseline_ca125 * np.exp(-k_ground_truth * (days / 30.0))
    measurements.append({
        "measurement_date": treatment_start + timedelta(days=days),
        "ca125_value": ca125_value,
    })

# Compute K
result = ca125_kelim_engine.compute_k_value(measurements, treatment_start)

# Expected:
# - k_value ≈ 1.2 (within ±0.1)
# - category = "favorable"
# - confidence > 0.7 (4 measurements, good time span)
```

#### **Test Case 2: Intermediate KELIM (K = 0.7)**
```python
# Ground truth: K = 0.7 (intermediate)
k_ground_truth = 0.7

# Expected:
# - k_value ≈ 0.7 (within ±0.1)
# - category = "intermediate"
```

#### **Test Case 3: Unfavorable KELIM (K = 0.3)**
```python
# Ground truth: K = 0.3 (unfavorable)
k_ground_truth = 0.3

# Expected:
# - k_value ≈ 0.3 (within ±0.1)
# - category = "unfavorable"
```

#### **Test Case 4: Insufficient Measurements**
```python
# Only 2 measurements (need ≥3)
measurements = [
    {"measurement_date": treatment_start, "ca125_value": 500.0},
    {"measurement_date": treatment_start + timedelta(days=21), "ca125_value": 400.0},
]

# Expected:
# - k_value = None
# - category = None
# - warnings = ["Insufficient measurements in first 100 days: 2 < 3"]
```

#### **Test Case 5: Missing Baseline**
```python
# Measurements start after treatment (no baseline)
measurements = [
    {"measurement_date": treatment_start + timedelta(days=21), "ca125_value": 400.0},
    {"measurement_date": treatment_start + timedelta(days=42), "ca125_value": 300.0},
    {"measurement_date": treatment_start + timedelta(days=63), "ca125_value": 250.0},
]

# Expected:
# - k_value = None (if requires_baseline = True)
# - warnings = ["Missing baseline measurement within 30 days before treatment start"]
```

**Success Criteria:**
- Computed K within 10% of ground truth for synthetic cases
- Category accuracy ≥95% for synthetic cases
- Data validation works correctly (rejects insufficient data)

### **Phase 2: Monte Carlo Simulation Validation**

**Objective:** Validate KELIM computation with realistic noise.

**Protocol:**
1. Generate 1000 synthetic patients with known K values
2. Add realistic measurement noise (CV = 10-15%)
3. Vary measurement timing (realistic clinical schedules)
4. Compute K on noisy data
5. Compare computed K to ground truth K

**Metrics:**
- Correlation coefficient (computed K vs ground truth K): r > 0.8
- Category accuracy: ≥90%
- Robustness to noise: category accuracy ≥85% even with 20% CV

**Success Criteria:**
- Strong correlation with ground truth (r > 0.8)
- Category accuracy ≥90% with realistic noise
- Robust to missing measurements (works with 3, better with 5+)

### **Phase 3: Published Benchmark Validation**

**Objective:** Validate KELIM distributions match published cohorts.

**Data Sources:**
- **ICON7 trial** - published KELIM distribution (mean K ≈ 0.8, ~40% favorable)
- **CHIVA trial** - published KELIM distribution (~35-45% favorable)
- **GCIG meta-analysis** - standardized KELIM cutpoints (≥1.0 = favorable)

**Validation Protocol:**
1. If we have access to ICON7/CHIVA CA-125 measurements:
   - Compute KELIM using our engine
   - Compare distribution to published distribution
   
2. If we only have published distributions:
   - Generate synthetic cohort matching published characteristics
   - Validate our engine produces similar distribution

**Success Criteria:**
- KELIM distribution matches published cohorts (±10%)
- Favorable proportion matches literature (~35-45%)
- Category cutpoints match GCIG standards (≥1.0 = favorable)

### **Phase 4: Predictive Value Validation (If Outcomes Available)**

**Objective:** Validate KELIM predicts outcomes as expected.

**If we have outcomes data:**
1. Compute KELIM for each patient
2. Stratify by KELIM category (favorable/intermediate/unfavorable)
3. Compare outcomes (PFS, OS, platinum-free interval)
4. Compute hazard ratios (favorable vs unfavorable)

**Expected Associations:**
- Favorable KELIM → longer PFS (HR < 1.0, p < 0.05)
- Favorable KELIM → longer OS (HR < 1.0, p < 0.05)
- Favorable KELIM → longer PFI (HR < 1.0, p < 0.05)

**Success Criteria:**
- HRs match published associations (±30%)
- Statistical significance matches literature (p < 0.05 for favorable vs unfavorable)

---

## 📊 Proxy Validation Framework (Similar to SL Framework)

### **Key Parallels with SL Proxy Framework**

| **SL Proxy Framework** | **KELIM Proxy Framework** |
|------------------------|---------------------------|
| GDSC2 drug response labels | Synthetic CA-125 with known K values |
| DepMap dependency priors | Published KELIM distributions/cutpoints |
| Preclinical cell lines | Synthetic/simulated CA-125 trajectories |
| Drug class sensitivity | KELIM category (favorable/intermediate/unfavorable) |
| S/P/D architecture | K computation (log-linear/mixed-effects) |

### **Proxy Validation Protocol (Similar to SL)**

#### **Track A: Synthetic Data Proxy (Like GDSC2)**

**Goal:** Predict KELIM category from synthetic CA-125 measurements with known K values.

**Protocol:**
1. Generate synthetic cohort (100-1000 patients) with known K values
2. Create realistic CA-125 trajectories (with noise)
3. Compute K using our engine
4. Compare computed category to ground truth category

**Metrics:**
- Category accuracy (≥90%)
- K value correlation (r > 0.8)
- Robustness to noise (category accuracy ≥85% with 20% CV)

#### **Track B: Published Benchmark Proxy (Like DepMap)**

**Goal:** Validate KELIM distributions match published cohorts.

**Protocol:**
1. Extract published KELIM distributions from ICON7/CHIVA/GCIG
2. Compute KELIM using our engine (if data available) OR
3. Generate synthetic cohort matching published characteristics
4. Compare distributions (median, IQR, category proportions)

**Metrics:**
- Distribution match (±10%)
- Category proportion match (±5%)
- Predictive associations match literature (if outcomes available)

---

## 🎯 Validation Roadmap

### **Timing Engine Validation (Priority 1)**

**Status:** ✅ Unit tests complete (12/12 passing)

**Next Steps:**
1. **Phase 2: Synthetic Data Validation** (2-3 hours)
   - Create synthetic test cases with known ground truth
   - Validate PFI/PTPI/TFI/PFS/OS computations
   - Document edge cases

2. **Phase 3: Published Benchmark Validation** (4-6 hours)
   - Extract PFI/PTPI distributions from literature
   - Compare our computed distributions to published
   - Document discrepancies and calibrations

**Estimated Time:** 6-9 hours

### **KELIM Framework Validation (Priority 2 - After Framework Built)**

**Status:** ⏳ Waiting for kinetic biomarker framework implementation

**Next Steps (After Framework Built):**
1. **Phase 1: Synthetic Data Validation** (4-6 hours)
   - Generate synthetic CA-125 with known K values
   - Validate K computation and categorization
   - Test data validation logic

2. **Phase 2: Monte Carlo Simulation** (6-8 hours)
   - Generate 1000 synthetic patients with noise
   - Validate robustness to noise and missing data
   - Document performance characteristics

3. **Phase 3: Published Benchmark Validation** (4-6 hours)
   - Compare distributions to ICON7/CHIVA/GCIG
   - Validate predictive associations (if outcomes available)
   - Document calibration requirements

**Estimated Time:** 14-20 hours (after framework built)

---

## 📁 Data Sources & Access

### **Timing Metrics Data**

**Internal Data:**
- Patient regimen tables (if available in database)
- Survival outcomes (if available in database)
- Clinical metadata (if available in database)

**Published Benchmarks:**
- **ICON7, CHIVA, GOG-0218** trials - PFI distributions
- **PARPi trials** (SOLO-2, NOVA, etc.) - PTPI distributions
- **TCGA-OV** - if treatment history available

### **KELIM Data**

**Published Benchmarks:**
- **ICON7 trial** - published KELIM scores (if accessible)
- **CHIVA trial** - published KELIM scores (if accessible)
- **GCIG meta-analysis** - standardized cutpoints

**Synthetic Data (Proxy):**
- Generate synthetic CA-125 trajectories with known K values
- Monte Carlo simulation with realistic noise

**Real-World Data (If Available):**
- Longitudinal CA-125 measurements from patient databases
- Clinical trial datasets with CA-125 kinetics

---

## ✅ Success Criteria Summary

### **Timing Engine Validation:**

**Unit Tests:**
- ✅ 12/12 tests passing (COMPLETE)

**Synthetic Data:**
- Computed values match ground truth within 1 day tolerance
- Categories match expected (100% accuracy)

**Published Benchmarks:**
- PFI/PTPI distributions match literature (±10%)
- Category proportions match literature (±5%)

### **KELIM Framework Validation:**

**Synthetic Data:**
- Computed K within 10% of ground truth
- Category accuracy ≥95%

**Monte Carlo Simulation:**
- Correlation with ground truth (r > 0.8)
- Category accuracy ≥90% with realistic noise

**Published Benchmarks:**
- KELIM distribution matches literature (±10%)
- Favorable proportion matches literature (±5%)
- Predictive associations match literature (if outcomes available)

---

## 🔗 Related Documents

- **Implementation Guide:** `TIMING_CHEMOSENSITIVITY_ENGINE_IMPLEMENTATION.md`
- **SL Proxy Framework:** `SL_PROXY_VALIDATION_FRAMEWORK.mdc`
- **Timing Engine Spec:** `TIMING_CHEMOSENSITIVITY_ENGINE.md`
- **DDR_bin Validation:** (Reference DDR_bin validation approach if similar)

---

## 🎯 Key Takeaways

### **What Data Do We Need?**

1. **Timing Engine:**
   - Regimen tables with dates (start, end, progression)
   - Survival data (death, follow-up dates)
   - Ground truth PFI/PTPI/TFI (if available) OR synthetic test cases

2. **KELIM Framework:**
   - Raw CA-125 measurements with dates (if available)
   - Ground truth KELIM scores (if available) OR synthetic data with known K values

### **Can We Use Proxy Validation for KELIM?**

**Yes!** Similar to SL proxy framework:
- Use **synthetic CA-125 data with known K values** (like GDSC2 drug labels)
- Use **published KELIM distributions** (like DepMap dependency priors)
- Use **Monte Carlo simulation** with realistic noise
- **Cross-validate** with published benchmarks (ICON7, CHIVA, GCIG)

### **How Can We Prove It Works?**

1. **Unit Tests:** ✅ 12/12 passing (timing engine)
2. **Synthetic Data:** Known ground truth → validate computation accuracy
3. **Monte Carlo Simulation:** Validate robustness to noise
4. **Published Benchmarks:** Compare distributions to literature
5. **Predictive Validation:** If outcomes available, validate associations match literature

**Proxy validation is valid** when:
- Ground truth is unavailable or sparse
- Synthetic data has known ground truth
- Published benchmarks provide distribution targets
- Internal consistency checks pass

---

**Last Updated:** January 28, 2026  
**Status:** 📋 **VALIDATION PLAN READY**  
**Next Steps:** Implement synthetic data validation for timing engine, then KELIM framework once built
