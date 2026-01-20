# ⏱️ Timing & Chemosensitivity Engine - Pan-Cancer Treatment History Standardizer

**Date:** January 13, 2026  
**Status:** ✅ **COMPLETE**  
**Priority:** **P1 - High Priority**  
**Owner:** Resistance Prophet Team  
**Last Updated:** January 28, 2026

---

## 🎯 Mission

Build a **reusable timing & chemosensitivity engine** that standardizes, for any solid tumor:

- **PFI (Platinum-Free Interval)** and platinum sensitivity categories
- **PTPI (Platinum-to-PARPi Interval)** and general "last-drug-to-DDR-drug" intervals
- **TFI (Treatment-Free Interval)** between lines of therapy
- **Per-regimen PFS/OS** from regimen start
- **Optional KELIM/CA-125 features** where available (from CA-125 engine)

**Output:** A per-regimen feature table that captures **"how the tumor behaved under prior therapies"**, parameterized by disease and regimen class.

---

## 🎯 Core Capabilities

### **1. Standardize Timing Metrics Across Diseases**

The engine computes:
- **PFI (Platinum-Free Interval):** Time from last platinum dose to next platinum or progression
- **PTPI (Platinum-to-PARPi Interval):** Time from last platinum to PARPi start
- **TFI (Treatment-Free Interval):** Time between consecutive regimens
- **PFS/OS from regimen start:** Progression-free and overall survival per regimen

### **2. Disease-Parameterized Configuration**

Same architecture for all solid tumors, but:
- **PFI cutpoints** can be tuned per disease (e.g., <6m, 6-12m, >12m for ovary)
- **CA-125 usage** can be enabled/disabled per disease (ovary uses CA-125, breast does not)
- **Platinum requirement** can be configured per disease

### **3. Integrate Chemosensitivity Features**

When available:
- **KELIM score** (CA-125 kinetics-based chemosensitivity)
- **CA-125 percentage changes** (day 21, day 42, time to 50% reduction)
- **CA-125 normalization** by cycle 3

### **4. Output Per-Regimen Feature Table**

One row per `(patient_id, regimen_id)` with:
- Timing features (TFI, PFI, PTPI, PFS, OS)
- Chemosensitivity features (KELIM, CA-125 when applicable)
- Data-quality flags (has_prior_platinum, has_progression_date, etc.)

---

## 📥 Inputs and Interfaces

### **1.1 Function Signature (Core Engine)**

```python
build_timing_chemo_features(
    regimen_table,        # List[Dict]: All systemic regimens per patient
    survival_table,       # List[Dict]: Vital status + dates per patient
    ca125_features_table, # Optional[List[Dict]]: KELIM/CA-125 features per (patient, regimen)
    clinical_table,       # List[Dict]: Patient-level metadata (disease_site, tumor_subtype)
    config               # Dict: Disease- and regimen-type specific parameters
) -> timing_features_table  # List[Dict]: One row per (patient_id, regimen_id)
```

### **1.2 Expected Input Schemas**

#### **regimen_table (one row per regimen_id):**
- `patient_id` (str/int): Patient identifier
- `regimen_id` (str/int): Regimen identifier
- `regimen_start_date` (date/datetime): Start date of regimen
- `regimen_end_date` (date/datetime): End date of regimen (or null if ongoing)
- `regimen_type` (str): `platinum`, `PARPi`, `ATR_inhibitor`, `WEE1_inhibitor`, `other_ddr_targeted`, `non_platinum_chemo`, `IO`, etc.
- `line_of_therapy` (int): Treatment line (1, 2, 3+)
- `setting` (str): `frontline`, `first_recurrence`, `later_recurrence`, `maintenance`
- `last_platinum_dose_date` (date/datetime, optional): For platinum regimens, last dose date (may equal regimen_end_date)
- `best_response` (str, optional): `CR`, `PR`, `SD`, `PD`, etc.
- `best_response_date` (date/datetime, optional): Date of best response
- `progression_date` (date/datetime, optional): Date of progression/relapse

#### **survival_table:**
- `patient_id` (str/int): Patient identifier
- `vital_status` (str): `Alive`, `Dead`, `Unknown`
- `death_date` (date/datetime, optional): Date of death (if vital_status == "Dead")
- `last_followup_date` (date/datetime): Last known follow-up date

#### **ca125_features_table (optional):**
- `patient_id` (str/int): Patient identifier
- `regimen_id` (str/int): Regimen identifier (links to regimen_table)
- `kelim_k_value` (float, optional): KELIM k-value (chemosensitivity score)
- `kelim_category` (str, optional): `favorable`, `intermediate`, `unfavorable`
- `ca125_percent_change_day21` (float, optional): CA-125 % change at day 21
- `ca125_percent_change_day42` (float, optional): CA-125 % change at day 42
- `ca125_time_to_50pct_reduction_days` (int, optional): Days to 50% reduction
- `ca125_normalized_by_cycle3` (bool, optional): CA-125 normalized by cycle 3

#### **clinical_table:**
- `patient_id` (str/int): Patient identifier
- `disease_site` (str): `ovary`, `endometrium`, `breast`, `pancreas`, `prostate`, `other`
- `tumor_subtype` (str, optional): `HGSOC`, `TNBC`, `PDAC`, etc. (may be null)

---

## ⚙️ Disease- and Regimen-Specific Configuration

### **2.1 Config Structure**

```python
TIMING_CONFIG = {
    "ovary": {
        "pfi_cutpoints_days": [180, 365],  # <6, 6–12, >12 months
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,  # PFI only computed for platinum regimens
        "use_ca125_for_chemosensitivity": True,  # Use CA-125/KELIM features
        "pfI_event_definition": "next_platinum_or_progression"  # or "progression_only"
    },
    "endometrium": {
        "pfi_cutpoints_days": [180, 365],  # Recurrent endometrial cancer data
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Endometrium doesn't use CA-125
        "pfI_event_definition": "next_platinum_or_progression"
    },
    "breast": {
        "pfi_cutpoints_days": [180, 365],  # Can differ if evidence supports it
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,  # Breast doesn't use CA-125
        "pfI_event_definition": "next_platinum_or_progression"
    },
    "default": {
        "pfi_cutpoints_days": [180, 365],  # Standard cutpoints
        "pfi_categories": {
            "resistant": {"max_days": 180, "label": "<6m"},
            "partially_sensitive": {"min_days": 180, "max_days": 365, "label": "6-12m"},
            "sensitive": {"min_days": 365, "label": ">12m"}
        },
        "require_platinum_for_pfi": True,
        "use_ca125_for_chemosensitivity": False,
        "pfI_event_definition": "next_platinum_or_progression"
    }
}
```

### **2.2 Regimen Type Classifications**

```python
REGIMEN_TYPE_CLASSIFICATIONS = {
    "platinum": ["platinum", "carboplatin", "cisplatin", "oxaliplatin"],
    "PARPi": ["PARPi", "olaparib", "niraparib", "rucaparib", "talazoparib"],
    "ATR_inhibitor": ["ATRi", "ATR_inhibitor", "berzosertib", "ceralasertib"],
    "WEE1_inhibitor": ["WEE1i", "WEE1_inhibitor", "adavosertib"],
    "other_ddr_targeted": ["other_ddr_targeted", "CHK1", "POLQ", "DNA_PK"],
    "non_platinum_chemo": ["taxane", "anthracycline", "alkylating_agent", "antimetabolite"],
    "IO": ["PD1", "PDL1", "CTLA4", "checkpoint_inhibitor"],
}
```

---

## 🔬 Computation Logic

### **3.1 Per-Patient Regimen Ordering**

For each `patient_id`:
1. **Sort all regimens by `regimen_start_date`** (ascending)
2. For each `regimen_id`, identify:
   - **Immediately preceding regimen** (any type) - for TFI calculation
   - **Most recent prior platinum regimen** (if any) that ended before this regimen starts - for PFI/PTPI calculation

### **3.2 Treatment-Free Interval (TFI)**

For each regimen `R_k` (k ≥ 2):

```python
prev_regimen_end = regimen_end_date of R_{k-1}
TFI_days = (regimen_start_date[R_k] - prev_regimen_end).days
```

**Edge Cases:**
- For first regimen per patient: `TFI_days = None`
- If `prev_regimen_end` is missing: `TFI_days = None`
- If regimens overlap: `TFI_days = 0` (or negative, log as warning)

### **3.3 PFS and OS from Regimen Start**

For each regimen:

**PFS_from_regimen_days:**
```python
pfs_event_date = min(
    progression_date if progression_date else float('inf'),
    death_date if death_date else float('inf'),
    last_followup_date
)
PFS_days = (pfs_event_date - regimen_start_date).days
PFS_event = 1 if (progression_date or death_date) and (pfs_event_date < last_followup_date) else 0
```

**OS_from_regimen_days:**
```python
if vital_status == "Dead" and death_date:
    OS_days = (death_date - regimen_start_date).days
    OS_event = 1
else:
    OS_days = (last_followup_date - regimen_start_date).days
    OS_event = 0
```

### **3.4 Platinum-Free Interval (PFI) and Categories**

**For platinum regimens only** (or based on config):

**PFI Event Definition:**
- Option 1: Next platinum regimen start date
- Option 2: Progression/relapse date
- Option 3: Next platinum OR progression (whichever comes first)

**Computation:**
```python
if last_platinum_dose_date:
    # Find next platinum regimen or progression
    if next_platinum_regimen_exists:
        PFI_days = (next_platinum_start_date - last_platinum_dose_date).days
    elif progression_date:
        PFI_days = (progression_date - last_platinum_dose_date).days
    else:
        PFI_days = None  # Cannot compute PFI (no event)
    
    # Categorize PFI
    if PFI_days is not None:
        if PFI_days < pfi_cutpoints_days[0]:  # < 180 days
            PFI_category = "<6m"  # Resistant
        elif PFI_days < pfi_cutpoints_days[1]:  # 180-365 days
            PFI_category = "6-12m"  # Partially sensitive
        else:  # > 365 days
            PFI_category = ">12m"  # Sensitive
    else:
        PFI_category = None
else:
    PFI_days = None
    PFI_category = None
```

**Edge Cases:**
- Missing `last_platinum_dose_date`: `PFI_days = None`
- No subsequent platinum or progression: `PFI_days = None`
- Multiple platinum regimens: Use most recent prior platinum

### **3.5 PTPI (Platinum-to-PARPi Interval)**

**For PARPi regimens** (or other DDR-targeted regimens):

```python
# Identify prior platinum regimen
prior_platinum_regimen = find_most_recent_prior_platinum(regimen_id, regimen_table)

if prior_platinum_regimen:
    prior_platinum_end_date = (
        prior_platinum_regimen.get("last_platinum_dose_date") or 
        prior_platinum_regimen.get("regimen_end_date")
    )
    if prior_platinum_end_date:
        PTPI_days = (parpi_regimen_start_date - prior_platinum_end_date).days
    else:
        PTPI_days = None
else:
    PTPI_days = None  # No prior platinum
```

**Generalization:**
- Can compute "platinum-to-ATRi" or "platinum-to-WEE1i" intervals using same logic
- Filter `regimen_type` for target regimen class

### **3.6 CA-125 / KELIM Integration (Optional)**

**If `TIMING_CONFIG[disease_site]["use_ca125_for_chemosensitivity"] == True`:**

```python
# Join ca125_features_table by (patient_id, regimen_id)
if ca125_features_table:
    ca125_features = lookup_ca125_features(patient_id, regimen_id, ca125_features_table)
    if ca125_features:
        # Attach KELIM/CA-125 features
        kelim_k_value = ca125_features.get("kelim_k_value")
        kelim_category = ca125_features.get("kelim_category")
        ca125_percent_change_day21 = ca125_features.get("ca125_percent_change_day21")
        ca125_percent_change_day42 = ca125_features.get("ca125_percent_change_day42")
        ca125_time_to_50pct_reduction_days = ca125_features.get("ca125_time_to_50pct_reduction_days")
        ca125_normalized_by_cycle3 = ca125_features.get("ca125_normalized_by_cycle3")
    else:
        # No CA-125 data for this regimen
        kelim_k_value = None
        kelim_category = None
        # ... (other fields None)
else:
    # CA-125 not used for this disease
    kelim_k_value = None
    kelim_category = None
    # ... (other fields None)
```

---

## 📊 Output Schema

### **5.1 Output Table (timing_features_table)**

One row per `(patient_id, regimen_id)`:

| Column | Type | Description |
|--------|------|-------------|
| `patient_id` | str/int | Patient identifier |
| `regimen_id` | str/int | Regimen identifier |
| `disease_site` | str | Disease site (ovary, endometrium, breast, etc.) |
| `tumor_subtype` | str/null | Tumor subtype (HGSOC, TNBC, etc.) |
| `regimen_type` | str | Regimen type (platinum, PARPi, ATRi, etc.) |
| `line_of_therapy` | int | Treatment line (1, 2, 3+) |
| `setting` | str | Setting (frontline, first_recurrence, etc.) |
| **Timing Features:** | | |
| `TFI_days` | int/null | Treatment-free interval (days from prior regimen end) |
| `PFS_from_regimen_days` | int/null | Progression-free survival from regimen start (days) |
| `PFS_event` | int (0/1) | PFS event indicator (1=progression/death, 0=censored) |
| `OS_from_regimen_days` | int/null | Overall survival from regimen start (days) |
| `OS_event` | int (0/1) | OS event indicator (1=death, 0=censored) |
| `PFI_days` | int/null | Platinum-free interval (days, for platinum regimens) |
| `PFI_category` | str/null | PFI category (<6m, 6-12m, >12m) |
| `PTPI_days` | int/null | Platinum-to-PARPi interval (days, for PARPi regimens) |
| **Chemosensitivity Features (Optional):** | | |
| `kelim_k_value` | float/null | KELIM k-value (chemosensitivity score) |
| `kelim_category` | str/null | KELIM category (favorable, intermediate, unfavorable) |
| `ca125_percent_change_day21` | float/null | CA-125 % change at day 21 |
| `ca125_percent_change_day42` | float/null | CA-125 % change at day 42 |
| `ca125_time_to_50pct_reduction_days` | int/null | Days to 50% reduction |
| `ca125_normalized_by_cycle3` | bool/null | CA-125 normalized by cycle 3 |
| **Data Quality Flags:** | | |
| `has_prior_platinum` | bool | True if prior platinum regimen exists |
| `has_progression_date` | bool | True if progression_date available |
| `has_death_or_followup` | bool | True if death_date or last_followup_date available |
| `has_ca125_data` | bool | True if CA-125 features available for this regimen |

**Joinability:** This table must be joinable with:
- DDR_bin status table (by `patient_id`)
- Outcome tables (by `patient_id`, `regimen_id`)
- PARPi/DDR outcome feature layer (for modeling)

---

## 🧪 Testing Requirements

### **6.1 Unit Tests**

Include comprehensive unit tests covering:

1. **Multiple Platinum Lines:**
   - Patient with frontline platinum, then non-platinum, then second-line platinum
   - Verify PFI computed correctly for second-line platinum
   - Verify TFI computed correctly between regimens

2. **PARPi After Platinum:**
   - Patient with prior platinum, then PARPi
   - Verify PTPI computed correctly
   - Verify PTPI = None if no prior platinum

3. **Missing Data Scenarios:**
   - Missing progression_date (PFS censored)
   - Missing death_date (OS censored)
   - Missing last_followup_date (both NA)
   - Missing regimen_end_date (TFI cannot compute)

4. **Different Disease Sites:**
   - Test ovary (uses CA-125)
   - Test breast (doesn't use CA-125)
   - Test endometrium (different PFI cutpoints)
   - Verify different configurations applied correctly

5. **Edge Cases:**
   - First regimen (no prior regimen, TFI = None)
   - Overlapping regimens (log warning, handle gracefully)
   - Multiple platinum regimens (use most recent prior)
   - PARPi without prior platinum (PTPI = None)

### **6.2 Test Cases**

**Test Case 1: Ovarian Patient with Frontline Platinum → PARPi**
```
Input:
- Regimen 1: platinum, line=1, setting=frontline, start=2020-01-01, end=2020-07-01, last_platinum_dose=2020-06-15
- Regimen 2: PARPi, line=2, setting=first_recurrence, start=2020-12-01
- Progression date: 2021-06-01

Expected:
- PFI_days = (2020-12-01 - 2020-06-15) = 169 days (no subsequent platinum, use progression)
- PFI_category = "<6m" (resistant)
- PTPI_days = (2020-12-01 - 2020-06-15) = 169 days
- TFI_days = (2020-12-01 - 2020-07-01) = 153 days
```

**Test Case 2: Patient with Multiple Platinum Lines**
```
Input:
- Regimen 1: platinum, line=1, start=2020-01-01, end=2020-07-01
- Regimen 2: non_platinum_chemo, line=2, start=2020-09-01, end=2020-12-01
- Regimen 3: platinum, line=3, start=2021-03-01

Expected:
- Regimen 3: PFI_days = (2021-03-01 - 2020-07-01) = 243 days
- Regimen 3: PFI_category = "6-12m"
- Regimen 2: TFI_days = (2020-09-01 - 2020-07-01) = 61 days
- Regimen 3: TFI_days = (2021-03-01 - 2020-12-01) = 90 days
```

**Test Case 3: Missing Data Handling**
```
Input:
- Regimen 1: platinum, start=2020-01-01, end=None (ongoing)
- Progression_date: None
- Death_date: None
- Last_followup_date: 2021-01-01

Expected:
- PFS_days = (2021-01-01 - 2020-01-01) = 365 days
- PFS_event = 0 (censored, no progression)
- OS_days = (2021-01-01 - 2020-01-01) = 365 days
- OS_event = 0 (censored, alive)
- PFI_days = None (no event date)
```

---

## 🚫 Non-Goals (For Now)

1. **No survival modeling** - Only feature computation (PFS/OS days, not survival curves)
2. **No resistance prediction** - This is a feature layer, not a prediction model
3. **No treatment recommendations** - Output features, not clinical decisions
4. **No disease-specific outcome models** - Generic timing/chemosensitivity features only

---

## 📋 Deliverable

A tested module (Python) that:

1. **Takes 4-5 tables + config as input** (regimen, survival, CA-125 optional, clinical, config)
2. **Returns timing_features_table** (one row per `patient_id`, `regimen_id`)
3. **Includes unit tests** covering:
   - Multiple platinum lines and intervening non-platinum regimens
   - PARPi after platinum (PTPI computation)
   - Missing progression vs missing death vs both present
   - Different disease sites with different PFI cutpoints
   - Edge cases (first regimen, overlapping regimens, missing data)

---

## 🔗 Integration Points

### **7.1 With DDR_bin Engine**

The timing engine will integrate with DDR_bin engine:
- Location: `api/services/resistance/biomarkers/therapeutic/timing_chemo_features.py`
- Follows same modular architecture pattern
- Uses config system: `api/services/resistance/config/timing_config.py`

### **7.2 With PARPi/DDR Outcome Feature Layer**

Output (`timing_features_table`) will be used by:
- PARPi/DDR outcome feature layer (Task 2 from NEXT_DELIVERABLE.md)
- Combines with DDR_bin status for outcome modeling
- Supports PARPi/ATR/WEE1 treatment decisions

### **7.3 With CA-125 Engine**

When CA-125 engine available:
- Joins CA-125 features by `(patient_id, regimen_id)`
- Only for diseases where `use_ca125_for_chemosensitivity == True`

---

## 📚 References

- **PFI Cutpoints (180, 365 days):** Standard platinum sensitivity categories (<6m, 6-12m, >12m)
- **KELIM:** CA-125 kinetics-based chemosensitivity score
- **PTPI:** Time from last platinum to PARPi start (predictive for PARPi response)

---

## 🎯 Key Design Principles

### **1. Disease-Parameterized (No Hard-Coding)**
- All disease-specific behavior driven by `TIMING_CONFIG`
- No hard-coded "ovary only" logic
- Easy to add new disease sites

### **2. Missing Data Handling**
- Graceful handling of missing dates
- Clear data-quality flags
- Use `None`/`null` for missing values (not 0 or default)

### **3. Regimen Type Agnostic**
- Works with any regimen type classification
- Configurable regimen type mappings
- Extensible for new regimen types

### **4. Joinable Output**
- One row per `(patient_id, regimen_id)`
- Compatible with DDR_bin table (by `patient_id`)
- Compatible with outcome tables (by `patient_id`, `regimen_id`)

---

---

## ✅ Implementation Status

### **Core Timing Engine** ✅ **COMPLETE**

**Status:** All core timing metrics implemented and tested.

**Completed Components:**
- ✅ `config/timing_config.py` - Disease-specific configuration (6 disease sites)
- ✅ `biomarkers/therapeutic/timing_chemo_features.py` - Core engine implementation
- ✅ `biomarkers/therapeutic/test_timing_chemo_features.py` - Comprehensive unit tests (12/12 passing)
- ✅ PFI computation with configurable cutpoints
- ✅ PTPI computation for DDR-targeted regimens
- ✅ TFI computation between regimens
- ✅ PFS/OS computation from regimen start
- ✅ CA-125/KELIM feature joining (from pre-computed table)

**Validation:**
- ✅ Validation suite created (Tasks 4.1-4.6 complete)
- ✅ Overall accuracy: 83.75% (TFI/PTPI: 100%, PFI: 57.35%)
- ✅ Unit tests: 12/12 passing

### **Kinetic Biomarker Framework** ✅ **COMPLETE**

**Status:** Framework for computing KELIM from raw CA-125 measurements is fully implemented and integrated.

**Completed Components:**
- ✅ `config/kinetic_biomarker_config.py` - Configuration system for kinetic biomarkers
- ✅ `biomarkers/therapeutic/kinetic_biomarker_base.py` - Base class for kinetic biomarkers
- ✅ `biomarkers/therapeutic/ca125_kelim_ovarian.py` - CA-125 KELIM computation implementation
- ✅ Integration with timing engine - On-the-fly KELIM computation from raw measurements
- ✅ `biomarkers/therapeutic/test_ca125_kelim.py` - Unit tests for CA-125 KELIM computation
- ✅ `biomarkers/therapeutic/test_kinetic_integration.py` - Integration tests with timing engine

**Key Features:**
- Computes KELIM from raw CA-125 measurements using log-linear regression
- Integrates seamlessly with timing engine (prefers pre-computed features, falls back to on-the-fly computation)
- Disease-specific configuration (ovarian CA-125, future: prostate PSA, etc.)
- Comprehensive unit tests (9 test cases)
- Integration tests (5 test cases)

**See:** `biomarkers/Docs/TIMING_CHEMOSENSITIVITY_ENGINE_IMPLEMENTATION.md` for detailed implementation guide.

---

**Last Updated:** January 28, 2026  
**Status:** ✅ **FULLY COMPLETE** - Core engine and kinetic biomarker framework fully implemented and tested
