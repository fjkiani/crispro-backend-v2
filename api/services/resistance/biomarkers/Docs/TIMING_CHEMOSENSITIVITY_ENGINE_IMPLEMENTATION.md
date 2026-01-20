# ⏱️ Timing & Chemosensitivity Engine - Implementation Guide for Plumber

**Date:** January 13, 2026  
**Status:** 📋 **READY FOR IMPLEMENTATION**  
**Priority:** **P1 - High Priority**  
**Owner:** Plumber (Implementation Team)

---

## 🔍 EXECUTIVE SUMMARY (January 28, 2026 Audit)

**Current Status:** ⚠️ **PARTIALLY COMPLETE** - Timing engine core is done, kinetic biomarker framework is not implemented.

### ✅ **What's Working:**
- **Timing Engine Core:** Fully functional (`timing_chemo_features.py`)
  - Computes PFI, PTPI, TFI, PFS, OS correctly
  - Disease-specific configuration working
  - Joins pre-computed CA-125/KELIM features when available

### ❌ **What's Missing:**
- **Kinetic Biomarker Framework:** Not implemented
  - Cannot compute KELIM from raw CA-125 measurements
  - No hierarchical architecture for CA-125/PSA/future markers
  - Timing engine currently requires pre-computed KELIM values

### 📋 **Next Steps:**
1. Build kinetic biomarker config system (2-3 hours)
2. Create kinetic biomarker base class (4-5 hours)
3. Implement CA-125 KELIM computation (6-8 hours)
4. Integrate with timing engine (3-4 hours)
5. Add unit tests (6-8 hours)

**Total Remaining Work:** 25-33 hours

---

## 🎯 Mission

Build a **reusable timing & chemosensitivity engine** that standardizes, for any solid tumor:

- **PFI (Platinum-Free Interval)** and platinum sensitivity categories
- **PTPI (Platinum-to-PARPi Interval)** and general "last-drug-to-DDR-drug" intervals
- **TFI (Treatment-Free Interval)** between lines of therapy
- **Per-regimen PFS/OS** from regimen start
- **KELIM-like kinetic biomarkers** (CA-125, PSA, and future markers) with hierarchical architecture

**Output:** A per-regimen feature table that captures **"how the tumor behaved under prior therapies"**, parameterized by disease and regimen class.

---

## 🏗️ Architectural Overview: Kinetic Biomarker Hierarchy

### **Core Design Principle**

KELIM (and kinetic biomarkers in general) are **generalizing beyond ovarian cancer**. We need a **hierarchical architecture** that supports:

1. **Conceptual Framework** (Class-level): "Model-based serum tumor marker elimination constants" (KELIM-like)
2. **Disease-Specific Implementations**: Ovarian (CA-125), Prostate (PSA), Future (CEA, CA15-3, etc.)
3. **Use-Case Domains**: Prognostic, Predictive, Therapeutic monitoring
4. **Technical Implementation**: Modeling approach, data requirements, cut-offs

### **Four-Layer Hierarchy**

```
Layer 1: Conceptual Framework (KELIM-like kinetics)
  └─ Definition: Modeled elimination rate constant K of serum tumor marker
  └─ Requirements: Baseline + ≥2 measurements in first ~100 days
  └─ Applicable to: Any marker that declines with effective therapy

Layer 2: Disease-Specific Implementations
  ├─ Ovarian: CA-125 KELIM (validated, SOC/approaching standard)
  ├─ Prostate: PSA KELIM / PRO-KELIM (validated, RUO)
  └─ Future: CEA (GI/lung), CA15-3 (breast), etc. (exploratory)

Layer 3: Use-Case Domains (within each disease)
  ├─ Prognostic: PFS/OS prediction
  ├─ Predictive: Treatment benefit stratification
  └─ Therapeutic: On-treatment monitoring, decision tools

Layer 4: Technical Implementation
  ├─ Modeling approach (population PK vs log-linear K)
  ├─ Data requirements (≥3 values, first 100 days)
  └─ Standardized vs trial-specific K cut-offs
```

### **Biomarker Object Model**

Each kinetic biomarker becomes an object:

```python
{
    "name": "CA125_KELIM_OC",  # or "PSA_KELIM_Prostate", "CEA_KELIM_GI"
    "class": "ELIM_RATE_CONSTANT_K",
    "disease": "ovarian",  # or "prostate", "breast", etc.
    "marker": "CA-125",  # or "PSA", "CEA", "CA15-3", etc.
    "use_cases": ["prognostic", "predictive", "therapeutic"],
    "evidence_level": "SOC",  # or "RUO", "EXPLORATORY"
    "validation_status": {
        "prognostic": "validated",  # or "exploratory"
        "predictive": "validated",
        "therapeutic": "validated"
    },
    "modeling_approach": "mixed_effects",  # or "log_linear", "population_pk"
    "data_requirements": {
        "min_measurements": 3,
        "time_window_days": 100,
        "requires_baseline": True
    },
    "cutoffs": {
        "favorable": 1.0,  # KELIM ≥1.0 = favorable
        "intermediate": 0.5,
        "unfavorable": 0.0  # KELIM <0.5 = unfavorable
    }
}
```

---

## 📋 Implementation Tasks for Plumber

### **Task 1: Create Kinetic Biomarker Framework** (Priority 1)

**Objective:** Build the base framework for KELIM-like kinetic biomarkers that can be extended across diseases and markers.

#### **1.1 Create Kinetic Biomarker Config System**

**Location:** `api/services/resistance/config/kinetic_biomarker_config.py`

**Deliverable:**
```python
KINETIC_BIOMARKER_CONFIG = {
    "ovarian": {
        "ca125": {
            "class": "ELIM_RATE_CONSTANT_K",
            "marker_name": "CA-125",
            "use_cases": ["prognostic", "predictive", "therapeutic"],
            "evidence_level": "SOC",  # Standard of care / approaching standard
            "validation_status": {
                "prognostic": "validated",  # Multiple RCTs
                "predictive": "validated",  # ICON7, CHIVA, GOG-0218
                "therapeutic": "validated"  # IDS decision support
            },
            "modeling_approach": "mixed_effects",  # Population PK mixed-effects
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30  # Baseline within 30 days of treatment start
            },
            "cutoffs": {
                "favorable": 1.0,  # KELIM ≥1.0 = favorable (standardized)
                "intermediate": 0.5,  # 0.5-1.0 = intermediate
                "unfavorable": 0.0  # <0.5 = unfavorable
            },
            "categories": {
                "favorable": {"min": 1.0, "label": "Favorable"},
                "intermediate": {"min": 0.5, "max": 1.0, "label": "Intermediate"},
                "unfavorable": {"max": 0.5, "label": "Unfavorable"}
            }
        }
    },
    "prostate": {
        "psa": {
            "class": "ELIM_RATE_CONSTANT_K",
            "marker_name": "PSA",
            "use_cases": ["prognostic", "predictive", "therapeutic"],
            "evidence_level": "RUO",  # Research use only
            "validation_status": {
                "prognostic": "validated",  # Multiple studies
                "predictive": "exploratory",  # Early evidence
                "therapeutic": "exploratory"  # Early evidence
            },
            "modeling_approach": "mixed_effects",  # Same as CA-125
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30
            },
            "cutoffs": {
                "favorable": 1.0,  # PRO-KELIM ≥1.0 (may differ, TBD)
                "intermediate": 0.5,
                "unfavorable": 0.0
            },
            "categories": {
                "favorable": {"min": 1.0, "label": "Favorable"},
                "intermediate": {"min": 0.5, "max": 1.0, "label": "Intermediate"},
                "unfavorable": {"max": 0.5, "label": "Unfavorable"}
            }
        }
    },
    "default": {
        # Template for future markers (CEA, CA15-3, etc.)
        "marker_template": {
            "class": "ELIM_RATE_CONSTANT_K",
            "use_cases": ["prognostic"],  # Start with prognostic, expand
            "evidence_level": "EXPLORATORY",
            "validation_status": {
                "prognostic": "exploratory",
                "predictive": "exploratory",
                "therapeutic": "exploratory"
            },
            "modeling_approach": "mixed_effects",
            "data_requirements": {
                "min_measurements": 3,
                "time_window_days": 100,
                "requires_baseline": True,
                "baseline_window_days": 30
            }
        }
    }
}

def get_kinetic_biomarker_config(disease_site: str, marker: str) -> dict:
    """
    Get kinetic biomarker configuration for a given disease and marker.
    
    Args:
        disease_site: Disease site (ovary, prostate, etc.)
        marker: Marker name (ca125, psa, cea, etc.)
    
    Returns:
        Configuration dict for the biomarker, or default template if not found
    """
    disease_site_lower = disease_site.lower() if disease_site else "default"
    marker_lower = marker.lower() if marker else None
    
    if disease_site_lower in KINETIC_BIOMARKER_CONFIG:
        disease_config = KINETIC_BIOMARKER_CONFIG[disease_site_lower]
        if marker_lower and marker_lower in disease_config:
            return disease_config[marker_lower]
    
    # Return default template
    return KINETIC_BIOMARKER_CONFIG["default"].get("marker_template", {})
```

**Estimated Time:** 2-3 hours

#### **1.2 Create Kinetic Biomarker Base Class**

**Location:** `api/services/resistance/biomarkers/therapeutic/kinetic_biomarker_base.py`

**Deliverable:**
```python
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

class KineticBiomarkerBase(ABC):
    """
    Base class for KELIM-like kinetic biomarkers.
    
    Supports: CA-125 (ovary), PSA (prostate), future markers (CEA, CA15-3, etc.)
    """
    
    def __init__(self, disease_site: str, marker: str, config: Dict[str, Any]):
        self.disease_site = disease_site
        self.marker = marker
        self.config = config
        self.class_name = config.get("class", "ELIM_RATE_CONSTANT_K")
        self.marker_name = config.get("marker_name", marker.upper())
        self.use_cases = config.get("use_cases", [])
        self.evidence_level = config.get("evidence_level", "EXPLORATORY")
        self.data_requirements = config.get("data_requirements", {})
        self.cutoffs = config.get("cutoffs", {})
        self.categories = config.get("categories", {})
    
    @abstractmethod
    def compute_k_value(
        self,
        marker_values: List[Dict[str, Any]],  # [{date, value, ...}, ...]
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Compute KELIM-like elimination rate constant K.
        
        Args:
            marker_values: List of marker measurements with dates and values
            treatment_start_date: Start date of treatment regimen
        
        Returns:
            {
                "k_value": float,  # Computed K value
                "category": str,   # "favorable", "intermediate", "unfavorable"
                "measurements_used": int,  # Number of measurements used
                "time_window_days": int,  # Actual time window covered
                "modeling_approach": str,  # "mixed_effects", "log_linear", etc.
                "confidence": float,  # 0.0-1.0 confidence in K value
                "warnings": List[str]  # Data quality warnings
            }
        """
        pass
    
    def validate_data_requirements(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Validate that marker data meets requirements for K computation.
        
        Returns:
            {
                "valid": bool,
                "warnings": List[str],
                "measurements_in_window": int,
                "has_baseline": bool,
                "time_window_days": int
            }
        """
        min_measurements = self.data_requirements.get("min_measurements", 3)
        time_window_days = self.data_requirements.get("time_window_days", 100)
        requires_baseline = self.data_requirements.get("requires_baseline", True)
        baseline_window_days = self.data_requirements.get("baseline_window_days", 30)
        
        # Filter measurements within time window
        window_end = treatment_start_date + timedelta(days=time_window_days)
        measurements_in_window = [
            m for m in marker_values
            if self._parse_date(m.get("date")) and
            treatment_start_date <= self._parse_date(m.get("date")) <= window_end
        ]
        
        # Check for baseline (within baseline_window_days before treatment start)
        baseline_start = treatment_start_date - timedelta(days=baseline_window_days)
        has_baseline = any(
            self._parse_date(m.get("date")) >= baseline_start and
            self._parse_date(m.get("date")) < treatment_start_date
            for m in marker_values
        )
        
        valid = len(measurements_in_window) >= min_measurements
        if requires_baseline:
            valid = valid and has_baseline
        
        warnings = []
        if len(measurements_in_window) < min_measurements:
            warnings.append(f"Insufficient measurements in first {time_window_days} days: {len(measurements_in_window)} < {min_measurements}")
        if requires_baseline and not has_baseline:
            warnings.append(f"Missing baseline measurement within {baseline_window_days} days before treatment start")
        
        return {
            "valid": valid,
            "warnings": warnings,
            "measurements_in_window": len(measurements_in_window),
            "has_baseline": has_baseline,
            "time_window_days": time_window_days
        }
    
    def categorize_k_value(self, k_value: float) -> str:
        """Categorize K value into favorable/intermediate/unfavorable."""
        if k_value >= self.cutoffs.get("favorable", 1.0):
            return "favorable"
        elif k_value >= self.cutoffs.get("intermediate", 0.5):
            return "intermediate"
        else:
            return "unfavorable"
    
    def _parse_date(self, date_value: Any) -> Optional[datetime]:
        """Parse date value to datetime object."""
        # Implementation: handle string, datetime, date, etc.
        pass
```

**Estimated Time:** 4-5 hours

#### **1.3 Implement CA-125 KELIM (Ovarian)**

**Location:** `api/services/resistance/biomarkers/therapeutic/ca125_kelim_ovarian.py`

**Deliverable:**
```python
from .kinetic_biomarker_base import KineticBiomarkerBase

class CA125KELIMOvarian(KineticBiomarkerBase):
    """
    CA-125 KELIM for ovarian cancer.
    
    Evidence Level: SOC (Standard of Care / approaching standard)
    Validated: Prognostic, Predictive, Therapeutic
    
    References:
    - ICON7, CHIVA, GOG-0218 trials
    - GCIG meta-analysis
    - Real-world validation studies
    """
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if config is None:
            from ...config.kinetic_biomarker_config import get_kinetic_biomarker_config
            config = get_kinetic_biomarker_config("ovarian", "ca125")
        super().__init__("ovarian", "ca125", config)
    
    def compute_k_value(
        self,
        marker_values: List[Dict[str, Any]],
        treatment_start_date: datetime
    ) -> Dict[str, Any]:
        """
        Compute CA-125 KELIM using mixed-effects modeling.
        
        Model: CA-125(t) = CA-125(0) * exp(-K * t)
        Approach: Mixed-effects population PK model (standard for CA-125 KELIM)
        """
        # Validate data requirements
        validation = self.validate_data_requirements(marker_values, treatment_start_date)
        if not validation["valid"]:
            return {
                "k_value": None,
                "category": None,
                "measurements_used": validation["measurements_in_window"],
                "time_window_days": validation["time_window_days"],
                "modeling_approach": "mixed_effects",
                "confidence": 0.0,
                "warnings": validation["warnings"]
            }
        
        # Filter and prepare data
        measurements = self._prepare_measurements(marker_values, treatment_start_date)
        
        # Compute K using mixed-effects modeling
        # TODO: Implement actual modeling (can start with simplified log-linear)
        k_value = self._compute_mixed_effects_k(measurements)
        
        # Categorize
        category = self.categorize_k_value(k_value)
        
        return {
            "k_value": round(k_value, 2),
            "category": category,
            "measurements_used": len(measurements),
            "time_window_days": validation["time_window_days"],
            "modeling_approach": "mixed_effects",
            "confidence": self._compute_confidence(measurements, k_value),
            "warnings": validation["warnings"]
        }
    
    def _compute_mixed_effects_k(self, measurements: List[Dict[str, Any]]) -> float:
        """
        Compute K using mixed-effects population PK model.
        
        For now, can use simplified log-linear regression:
        log(CA-125(t)) = log(CA-125(0)) - K * t
        
        Future: Implement full mixed-effects model using statsmodels or similar
        """
        # Simplified implementation (log-linear)
        # TODO: Upgrade to full mixed-effects model
        import numpy as np
        
        times = [m["days_since_start"] for m in measurements]
        values = [m["value"] for m in measurements]
        
        # Log-linear regression: log(value) = log(baseline) - K * t
        log_values = np.log(np.array(values))
        times_array = np.array(times)
        
        # Fit: log(value) ~ -K * t (with intercept = log(baseline))
        # K = -slope
        from scipy import stats
        slope, intercept, r_value, p_value, std_err = stats.linregress(times_array, log_values)
        k_value = -slope  # K is negative of slope
        
        return max(0.0, k_value)  # Ensure non-negative
```

**Estimated Time:** 6-8 hours (including modeling implementation)

#### **1.4 Implement PSA KELIM (Prostate) - Optional Phase 1**

**Location:** `api/services/resistance/biomarkers/therapeutic/psa_kelim_prostate.py`

**Deliverable:** Similar structure to CA-125, but for PSA in prostate cancer.

**Status:** Can be implemented in Phase 1 or deferred to Phase 2 (focus on CA-125 first)

**Estimated Time:** 4-6 hours (if included in Phase 1)

---

### **Task 2: Create Timing Engine Core** (Priority 1)

**Objective:** Build the core timing engine that computes PFI, PTPI, TFI, PFS, OS.

#### **2.1 Create Timing Config System**

**Location:** `api/services/resistance/config/timing_config.py`

**Deliverable:** See original TIMING_CHEMOSENSITIVITY_ENGINE.md for config structure.

**Estimated Time:** 2-3 hours

#### **2.2 Implement Core Timing Engine**

**Location:** `api/services/resistance/biomarkers/therapeutic/timing_chemo_features.py`

**Deliverable:** Main `build_timing_chemo_features()` function with PFI, PTPI, TFI, PFS, OS computation.

**Estimated Time:** 8-10 hours

---

### **Task 3: Integrate Kinetic Biomarkers with Timing Engine** (Priority 1)

**Objective:** Integrate KELIM/kinetic biomarker features into timing engine output.

#### **3.1 Modify Timing Engine to Accept Kinetic Biomarker Engine**

**Location:** `api/services/resistance/biomarkers/therapeutic/timing_chemo_features.py`

**Deliverable:**
```python
def build_timing_chemo_features(
    regimen_table: List[Dict[str, Any]],
    survival_table: List[Dict[str, Any]],
    ca125_features_table: Optional[List[Dict[str, Any]]] = None,
    clinical_table: List[Dict[str, Any]],
    config: Optional[Dict[str, Any]] = None,
    kinetic_biomarker_engine: Optional[Any] = None  # NEW: Kinetic biomarker engine
) -> List[Dict[str, Any]]:
    """
    Build timing and chemosensitivity features.
    
    Args:
        ...
        kinetic_biomarker_engine: Optional kinetic biomarker engine instance
            If provided, will compute KELIM/kinetic features on-the-fly
            If None, will use ca125_features_table if available
    """
    # ... timing computations ...
    
    # Integrate kinetic biomarkers
    if kinetic_biomarker_engine:
        # Compute KELIM for each regimen using kinetic biomarker engine
        for regimen in timing_features:
            kelim_features = kinetic_biomarker_engine.compute_for_regimen(
                patient_id=regimen["patient_id"],
                regimen_id=regimen["regimen_id"],
                marker_values=...,  # From marker values table
                treatment_start_date=regimen["regimen_start_date"]
            )
            regimen.update(kelim_features)
    elif ca125_features_table:
        # Join pre-computed CA-125 features (legacy support)
        # ...
```

**Estimated Time:** 3-4 hours

---

### **Task 4: Unit Tests** (Priority 1)

**Location:** `api/services/resistance/biomarkers/therapeutic/test_timing_chemo_features.py`

**Test Cases:**

1. **Kinetic Biomarker Framework Tests:**
   - CA-125 KELIM computation (ovarian)
   - Data validation (insufficient measurements, missing baseline)
   - K value categorization (favorable/intermediate/unfavorable)
   - PSA KELIM computation (prostate) - if implemented

2. **Timing Engine Tests:**
   - PFI computation and categorization
   - PTPI computation
   - TFI computation
   - PFS/OS computation
   - Missing data handling

3. **Integration Tests:**
   - Timing + Kinetic biomarker integration
   - Different disease sites (ovary uses CA-125, breast doesn't)
   - Multiple platinum lines
   - PARPi after platinum

**Estimated Time:** 6-8 hours

---

## 📊 Overall Implementation Timeline

### **Phase 1: Core Framework (Weeks 1-2)**

- **Week 1:**
  - Task 1.1: Kinetic biomarker config system (2-3 hours)
  - Task 1.2: Kinetic biomarker base class (4-5 hours)
  - Task 1.3: CA-125 KELIM implementation (6-8 hours)
  - **Subtotal: 12-16 hours**

- **Week 2:**
  - Task 2.1: Timing config system (2-3 hours)
  - Task 2.2: Core timing engine (8-10 hours)
  - Task 3.1: Integration (3-4 hours)
  - **Subtotal: 13-17 hours**

**Phase 1 Total: 25-33 hours**

### **Phase 2: Testing & Refinement (Week 3)**

- Task 4: Unit tests (6-8 hours)
- Bug fixes and refinements (4-6 hours)

**Phase 2 Total: 10-14 hours**

### **Phase 3: Optional Extensions (Future)**

- PSA KELIM (prostate) - 4-6 hours
- Other markers (CEA, CA15-3) - TBD
- Advanced modeling (full mixed-effects) - TBD

---

## ✅ Acceptance Criteria

### **Kinetic Biomarker Framework:**
- [ ] `KineticBiomarkerBase` class implemented and tested
- [ ] `KINETIC_BIOMARKER_CONFIG` supports at least 2 diseases (ovary, prostate)
- [ ] Data validation works correctly (min measurements, baseline, time window)
- [ ] K value computation works (can start with simplified, upgrade to full model later)
- [ ] Categorization works (favorable/intermediate/unfavorable)
- [ ] Extensible for future markers (CEA, CA15-3, etc.)

### **CA-125 KELIM (Ovarian):**
- [ ] `CA125KELIMOvarian` class implemented
- [ ] Computes K value from CA-125 measurements
- [ ] Validates data requirements (≥3 measurements, baseline, 100-day window)
- [ ] Categorizes correctly (≥1.0 = favorable, etc.)
- [ ] Unit tests cover all scenarios

### **Timing Engine:**
- [ ] `build_timing_chemo_features()` implemented
- [ ] PFI, PTPI, TFI, PFS, OS computation works
- [ ] Integration with kinetic biomarkers works
- [ ] Missing data handled gracefully
- [ ] Unit tests cover all scenarios

### **Integration:**
- [ ] Timing engine can use kinetic biomarker engine or pre-computed features
- [ ] Output schema includes KELIM features when available
- [ ] Disease-specific behavior (ovary uses CA-125, breast doesn't)

---

## 📚 Key References

### **CA-125 KELIM (Ovarian):**
- ICON7, CHIVA, GOG-0218 trials
- GCIG meta-analysis
- Real-world validation studies

### **PSA KELIM (Prostate):**
- PRO-KELIM studies in mHSPC/mCRPC
- PSA kinetics under ADT ± docetaxel

### **General Framework:**
- Model-based serum tumor marker elimination constants
- Early dynamic response biomarkers (first 100 days)
- Use-case domains: Prognostic, Predictive, Therapeutic

---

## 🎯 Design Principles

### **1. Hierarchical Architecture**
- Layer 1: Conceptual framework (KELIM-like)
- Layer 2: Disease-specific (ovary/CA-125, prostate/PSA)
- Layer 3: Use-case domains (prognostic, predictive, therapeutic)
- Layer 4: Technical implementation (modeling, data requirements, cut-offs)

### **2. Extensibility**
- Easy to add new diseases (breast, pancreas, etc.)
- Easy to add new markers (CEA, CA15-3, etc.)
- Easy to add new use-cases

### **3. Evidence-Based**
- Track evidence level (SOC, RUO, EXPLORATORY)
- Track validation status per use-case
- Enable evidence-based decision making

### **4. Backward Compatibility**
- Support legacy CA-125 features table
- Support new kinetic biomarker engine
- Gradual migration path

---

**Last Updated:** January 28, 2026  
**Status:** ⚠️ **PARTIALLY COMPLETE - KINETIC BIOMARKER FRAMEWORK PENDING**  
**Estimated Remaining Time:** 25-33 hours (Kinetic Biomarker Framework only)

---

## 📊 IMPLEMENTATION STATUS AUDIT (January 28, 2026)

### ✅ **COMPLETE** (Timing Engine Core)

**Already Implemented:**
- ✅ **Timing Engine Core** (`biomarkers/therapeutic/timing_chemo_features.py`)
  - PFI, PTPI, TFI, PFS, OS computation fully functional
  - Disease-specific configuration support
  - CA-125 feature joining from pre-computed `ca125_features_table`
  - Unit tests exist (`test_timing_chemo_features.py`)

- ✅ **Timing Config System** (`config/timing_config.py`)
  - Disease-specific PFI cutpoints configured
  - `use_ca125_for_chemosensitivity` flags per disease
  - Regimen type classification helpers

**Current Architecture:**
- Timing engine accepts pre-computed KELIM features via `ca125_features_table`
- Joins CA-125 features when `use_ca125_for_chemosensitivity == True`
- No on-the-fly KELIM computation from raw marker values

### ❌ **NOT IMPLEMENTED** (Kinetic Biomarker Framework)

**Missing Components:**
- ❌ **Kinetic Biomarker Config System** (`config/kinetic_biomarker_config.py`)
  - No hierarchical config for CA-125, PSA, future markers
  - No evidence level tracking (SOC/RUO/EXPLORATORY)

- ❌ **Kinetic Biomarker Base Class** (`biomarkers/therapeutic/kinetic_biomarker_base.py`)
  - No abstract base for KELIM-like biomarkers
  - No data validation framework for marker measurements
  - No K value categorization logic

- ❌ **CA-125 KELIM Computation** (`biomarkers/therapeutic/ca125_kelim_ovarian.py`)
  - No implementation to compute K from raw CA-125 measurements
  - No mixed-effects or log-linear modeling
  - Current system requires pre-computed KELIM values

**Gap Analysis:**
- **Current Flow:** Raw CA-125 → External computation → `ca125_features_table` → Timing Engine
- **Desired Flow:** Raw CA-125 → Kinetic Biomarker Engine → KELIM features → Timing Engine
- **Impact:** Cannot compute KELIM on-the-fly from patient marker measurements

### 📋 **REVISED IMPLEMENTATION PLAN**

**What Remains:**
1. **Task 1: Kinetic Biomarker Framework** (25-33 hours)
   - Task 1.1: Create config system (2-3 hours)
   - Task 1.2: Create base class (4-5 hours)
   - Task 1.3: Implement CA-125 KELIM (6-8 hours)
   - Task 1.4: Integration with timing engine (3-4 hours)
   - Task 1.5: Unit tests (6-8 hours)
   - Task 1.6: Update timing engine to use kinetic biomarker engine (4-5 hours)

**What's Already Done:**
- Task 2 (Timing Engine Core) - ✅ **COMPLETE**
- Task 3 (Timing Engine Integration) - ✅ **COMPLETE** (for pre-computed features)

**Critical Path:**
- Kinetic biomarker framework must be built to enable on-the-fly KELIM computation
- Once complete, timing engine can be enhanced to optionally use kinetic biomarker engine instead of pre-computed table

---

## 📋 Quick Reference: What Needs to Be Done

### ✅ **Step 2: Build Timing Engine Core** - **COMPLETE**
1. ✅ **Timing config** (`config/timing_config.py`) - **EXISTS**
   - `TIMING_CONFIG` with disease-specific PFI cutpoints ✅

2. ✅ **Core engine** (`biomarkers/therapeutic/timing_chemo_features.py`) - **EXISTS**
   - `build_timing_chemo_features()` function ✅
   - PFI, PTPI, TFI, PFS, OS computation ✅
   - CA-125 feature joining from pre-computed table ✅

3. ✅ **Unit tests** (`test_timing_chemo_features.py`) - **EXISTS**
   - Comprehensive test coverage ✅

### ❌ **Step 1: Build Kinetic Biomarker Framework** - **PENDING**
1. **Create config system** (`config/kinetic_biomarker_config.py`) - **NOT CREATED**
   - Define `KINETIC_BIOMARKER_CONFIG` with ovarian/CA-125 and prostate/PSA
   - Add helper function `get_kinetic_biomarker_config()`

2. **Create base class** (`biomarkers/therapeutic/kinetic_biomarker_base.py`) - **NOT CREATED**
   - Abstract `KineticBiomarkerBase` class
   - Data validation logic
   - K value categorization

3. **Implement CA-125 KELIM** (`biomarkers/therapeutic/ca125_kelim_ovarian.py`) - **NOT CREATED**
   - `CA125KELIMOvarian` class inheriting from base
   - K computation (can start with simplified log-linear, upgrade to mixed-effects later)
   - Integration with timing engine

4. **Enhance timing engine integration** - **PENDING**
   - Add optional `kinetic_biomarker_engine` parameter to `build_timing_chemo_features()`
   - Enable on-the-fly KELIM computation from raw marker values
   - Maintain backward compatibility with pre-computed `ca125_features_table`

### **Key Files Status:**

```
api/services/resistance/
├── config/
│   ├── kinetic_biomarker_config.py      # ❌ NEEDS CREATION
│   └── timing_config.py                  # ✅ EXISTS
├── biomarkers/
│   └── therapeutic/
│       ├── kinetic_biomarker_base.py     # ❌ NEEDS CREATION
│       ├── ca125_kelim_ovarian.py        # ❌ NEEDS CREATION
│       ├── timing_chemo_features.py      # ✅ EXISTS (needs enhancement for kinetic engine)
│       ├── test_timing_chemo_features.py # ✅ EXISTS (needs tests for kinetic engine)
│       └── __init__.py                   # ⚠️ UPDATE: Export new classes when created
```

---

## 🎯 Success Criteria

### ✅ **Already Achieved:**
1. ✅ Compute PFI, PTPI, TFI, PFS, OS for any regimen table
2. ✅ Integrate pre-computed KELIM features into timing engine output (via `ca125_features_table`)
3. ✅ Handle missing data gracefully (use None, not 0)
4. ✅ Support multiple disease sites with different configurations
5. ✅ Unit tests for timing engine (existing tests cover PFI, PTPI, TFI, PFS, OS, CA-125 joining)

### ❌ **Remaining (Kinetic Biomarker Framework):**
1. ❌ Compute KELIM for CA-125 (ovarian) from raw marker values and treatment start date
2. ❌ Integrate kinetic biomarker engine into timing engine (on-the-fly computation)
3. ❌ Extend framework for future markers (PSA, CEA, etc.)
4. ❌ Unit tests for kinetic biomarker computation (K value calculation, data validation, categorization)

---

## 💡 Key Insights from Manager

### **Why Hierarchical Architecture?**

**Problem:** KELIM is generalizing beyond ovarian cancer (PSA in prostate, CEA in GI/lung, etc.). We can't put everything in one flat "CA-125" bucket.

**Solution:** Build a 4-layer hierarchy:
1. **Conceptual Framework** (KELIM-like kinetics) - shared across all markers
2. **Disease-Specific** (ovary/CA-125, prostate/PSA) - each disease has its own implementation
3. **Use-Case Domains** (prognostic, predictive, therapeutic) - each marker can serve multiple use-cases
4. **Technical Implementation** (modeling, data, cut-offs) - technical details

**Benefit:** 
- Reuse modeling infrastructure (same K computation logic)
- Easy to add new markers (PSA, CEA, CA15-3, etc.)
- Keep evidence levels separate (SOC vs RUO vs EXPLORATORY)

### **What Makes a KELIM-like Biomarker?**

**Criteria (from manager):**
1. **Marker that declines with effective therapy** (CA-125, PSA, potentially others)
2. **Baseline + ≥2 additional measurements** (≥3 total) in first ~100 days
3. **Modeled elimination rate constant K** using longitudinal kinetics and mixed-effects modeling

**Evidence Levels:**
- **SOC (Standard of Care):** CA-125 KELIM in ovarian (validated in multiple RCTs, approaching standard)
- **RUO (Research Use Only):** PSA KELIM in prostate (validated, but not yet standard)
- **EXPLORATORY:** CEA, CA15-3, other markers (early evidence, prototype)

---

## 🔗 Related Documents

- **Original Specification:** `api/services/resistance/TIMING_CHEMOSENSITIVITY_ENGINE.md`
- **Source Requirements:** `biomarkers/Docs/Next_Biomarker.mdc/KELIM-125.md`
- **Task Breakdown:** `api/services/resistance/NEXT_DELIVERABLE.md` (Task 2)

---

**Next Steps:** Plumber reviews this document and begins Task 1 (Kinetic Biomarker Framework).
