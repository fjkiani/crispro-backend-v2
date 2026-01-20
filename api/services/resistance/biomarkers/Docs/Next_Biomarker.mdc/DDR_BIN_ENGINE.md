# 🧬 DDR_bin Scoring Engine - Pan-Solid-Tumor DDR Deficiency Classifier

**Date:** January 13, 2026  
**Status:** 📋 **PLANNING**  
**Priority:** **P1 - High Priority**  
**Owner:** Resistance Prophet Team

---

## 🎯 Mission

Build a **pan-solid-tumor DDR deficiency scoring engine** that takes standard NGS outputs and optionally HRD assays as input, and returns a simple, interpretable label per patient:

- **DDR_bin_status** ∈ {`DDR_defective`, `DDR_proficient`, `unknown`}
- **Supporting features**: HRD score, BRCA/DDR gene hits, DDR_score summary

The engine must be **parameterized by disease and site** (ovary, breast, pancreas, prostate, etc.) so that thresholds and gene lists can be tuned per disease while maintaining the same core architecture.

---

## 🎯 Core Capabilities

### **1. Ingest Routine Data**

The engine should accept:
- **Gene-level variants** for a curated DDR gene set (BRCA1/2, PALB2, RAD51C/D, ATM, ATR, CHEK1/2, FANCA/D2, RAD50/MRE11/NBN, etc.)
- **Copy-number alterations** (biallelic loss where possible)
- **HRD assay outputs** (HRD score, HRD+/–) from any vendor (Myriad, Leuven, Geneva, etc.)

### **2. Apply Disease-Parameterized Rules**

Same architecture for all solid tumors, but:
- **Thresholds** can be tuned per disease (e.g., HRD cutoff = 42 for ovary vs 40 for breast)
- **Gene lists** can be tuned per disease (e.g., extended DDR genes may differ)
- **Rules priority** can be customized per disease

### **3. Output Per-Patient DDR Status**

For each patient, mark **`DDR_defective`** if any of:
1. **Pathogenic BRCA1/2** (preferably biallelic when CNA data confirm)
2. **HRD score above disease-specific cut-off** or HRD_status = positive
3. **Pathogenic variant in core HRR genes** (BRCA1/2, PALB2, RAD51C/D, BARD1, BRIP1)
4. **Pathogenic variant in extended DDR genes** (ATM, ATR, CHEK1/2, FANCA/D2, RAD50/MRE11/NBN, POLQ, etc.)

**Output includes:**
- **DDR_bin_status** (primary label)
- **HRD_status_inferred**, **HRD_score_raw**
- **Flags**: `BRCA_pathogenic`, `core_HRR_pathogenic`, `extended_DDR_pathogenic`
- **Optional numeric DDR_score** summarizing burden of DDR defects
- **DDR_features_used** (JSON/log of which rules fired)

---

## 📥 Inputs and Interfaces

### **1.1 Function Signature (Core Engine)**

```python
assign_ddr_status(
    mutations_table,   # DataFrame: one row per (patient_id, gene), includes variant_call info
    cna_table,         # DataFrame: copy-number alterations per (patient_id, gene), optional
    hrd_assay_table,   # DataFrame: HRD scores/status per patient (Myriad-like or others), optional
    clinical_table,    # DataFrame: patient-level metadata (disease_site, tumor_subtype, etc.)
    config             # dict: disease- and site-specific parameters
) -> ddr_status_table  # DataFrame: one row per patient_id
```

### **1.2 Expected Columns (Inputs)**

#### **mutations_table:**
- `patient_id` (str/int): Patient identifier
- `gene_symbol` (str): Gene name (e.g., "BRCA1", "BRCA2")
- `variant_classification` (str): `pathogenic` / `likely_pathogenic` / `VUS` / `benign` / etc.
- `variant_type` (str): `SNV`, `indel`, `rearrangement`, etc.

#### **cna_table (optional but supported):**
- `patient_id` (str/int): Patient identifier
- `gene_symbol` (str): Gene name
- `copy_number_state` (str): `deletion`, `loss`, `neutral`, `gain`, `amplification`
- `copy_number` (float): Optional numeric value

#### **hrd_assay_table (optional):**
- `patient_id` (str/int): Patient identifier
- `hrd_score` (float): Continuous HRD score (e.g., Myriad GIS-like score)
- `hrd_status` (str): `HRD_positive` / `HRD_negative` / `equivocal` / `unknown`
- `assay_name` (str): `Myriad`, `Leuven`, `Geneva`, `other`

#### **clinical_table:**
- `patient_id` (str/int): Patient identifier
- `disease_site` (str): `ovary`, `breast`, `pancreas`, `prostate`, `other`
- `tumor_subtype` (str): `HGSOC`, `TNBC`, `PDAC`, etc. (may be null)

---

## ⚙️ Disease- and Site-Specific Configuration

### **2.1 Config Structure**

Implement a config layer that can be extended over time. Use a dictionary keyed by `disease_site` (and optionally `tumor_subtype`).

```python
DDR_CONFIG = {
    "ovary": {
        "hrd_score_cutoff": 42,           # GIS-like threshold for HRD+ (can be updated)
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "RAD51C", "RAD51D", 
            "PALB2", "BARD1", "BRIP1"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK1", "CHEK2", 
            "FANCA", "FANCD2", "RAD50", "MRE11", "NBN", "POLQ"
        ],
        "require_biallelic_if_cn_available": True,  # Require CNA confirmation for BRCA biallelic
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ]
    },
    "breast": {
        "hrd_score_cutoff": 42,           # Can differ per disease if evidence supports it
        "core_hrr_genes": [
            "BRCA1", "BRCA2", "PALB2", 
            "RAD51C", "RAD51D", "BARD1", "BRIP1"
        ],
        "extended_ddr_genes": [
            "ATM", "ATR", "CHEK2", 
            "FANCA", "FANCD2", "RAD50", "MRE11", "NBN"
        ],
        "require_biallelic_if_cn_available": True,
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ]
    },
    "pancreas": {
        "hrd_score_cutoff": 42,           # Default, can be calibrated
        "core_hrr_genes": ["BRCA1", "BRCA2", "PALB2"],
        "extended_ddr_genes": ["ATM", "ATR", "CHEK2"],
        "require_biallelic_if_cn_available": False,  # May be less strict
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic"
        ]
    },
    "prostate": {
        "hrd_score_cutoff": 42,
        "core_hrr_genes": ["BRCA1", "BRCA2", "ATM"],
        "extended_ddr_genes": ["CHEK2", "BRCA2"],
        "require_biallelic_if_cn_available": False,
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic"
        ]
    },
    "default": {
        "hrd_score_cutoff": 42,
        "core_hrr_genes": ["BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D"],
        "extended_ddr_genes": ["ATM", "ATR", "CHEK2", "FANCA", "FANCD2", "RAD50", "MRE11", "NBN"],
        "require_biallelic_if_cn_available": False,
        "rules_priority": [
            "BRCA_pathogenic",
            "HRD_score_high",
            "core_hrr_pathogenic",
            "extended_ddr_pathogenic"
        ]
    }
}
```

### **2.2 Key Points**

- **Cutoffs** (e.g., HRD ≥ 42) should be configurable per disease; same algorithm, different thresholds
- **Gene lists** can be shared but allow per-disease overrides as evidence evolves
- **Rules priority** can be customized (e.g., BRCA first, then HRD, then core HRR, then extended DDR)

---

## 🔬 DDR_bin Decision Logic

### **3.1 Per-Patient Decision Tree**

For each patient:

#### **Step 1: Determine Context**
```python
site = clinical_table[disease_site] or "default"
config = DDR_CONFIG.get(site, DDR_CONFIG["default"])
```

#### **Step 2: Initialize Flags**
```python
# BRCA flags
has_pathogenic_BRCA = any(
    variant_classification in ["pathogenic", "likely_pathogenic"]
    for row in mutations_table
    if row["gene_symbol"] in ["BRCA1", "BRCA2"]
)

# Core HRR flags (excluding BRCA if desired)
has_pathogenic_core_HRR = any(
    variant_classification in ["pathogenic", "likely_pathogenic"]
    for row in mutations_table
    if row["gene_symbol"] in config["core_hrr_genes"]
    and row["gene_symbol"] not in ["BRCA1", "BRCA2"]  # Exclude BRCA if checking separately
)

# Extended DDR flags
has_pathogenic_extended_DDR = any(
    variant_classification in ["pathogenic", "likely_pathogenic"]
    for row in mutations_table
    if row["gene_symbol"] in config["extended_ddr_genes"]
)

# HRD flags (from assay table if present)
hrd_score = hrd_assay_table.get("hrd_score", None)
hrd_status = hrd_assay_table.get("hrd_status", None)
```

#### **Step 3: Check Biallelic Loss (if CNA available)**
```python
if config["require_biallelic_if_cn_available"] and cna_table:
    # Check for biallelic loss (LOH or deletion + pathogenic variant)
    brca_biallelic = (
        has_pathogenic_BRCA and
        any(
            cna_row["copy_number_state"] in ["deletion", "loss"]
            for cna_row in cna_table
            if cna_row["gene_symbol"] in ["BRCA1", "BRCA2"]
        )
    )
else:
    brca_biallelic = has_pathogenic_BRCA  # Fallback to pathogenic-only
```

#### **Step 4: HRD Positive Inference**
```python
hrd_positive_inferred = False

if hrd_status == "HRD_positive":
    hrd_positive_inferred = True
elif hrd_score is not None and hrd_score >= config["hrd_score_cutoff"]:
    hrd_positive_inferred = True
```

#### **Step 5: Assign DDR_bin_status (Priority-Ordered Rules)**
```python
ddr_bin_status = None
ddr_features_used = []

# Rule 1: BRCA pathogenic (highest priority)
if has_pathogenic_BRCA:
    ddr_bin_status = "DDR_defective"
    ddr_features_used.append("BRCA_pathogenic")

# Rule 2: HRD positive (genomic scar)
elif hrd_positive_inferred:
    ddr_bin_status = "DDR_defective"
    ddr_features_used.append("HRD_score_high" if hrd_score else "HRD_status_positive")

# Rule 3: Core HRR pathogenic
elif has_pathogenic_core_HRR:
    ddr_bin_status = "DDR_defective"
    ddr_features_used.append("core_hrr_pathogenic")

# Rule 4: Extended DDR pathogenic
elif has_pathogenic_extended_DDR:
    ddr_bin_status = "DDR_defective"
    ddr_features_used.append("extended_ddr_pathogenic")

# Rule 5: No DDR/HRD information
elif not has_pathogenic_BRCA and not has_pathogenic_core_HRR and not has_pathogenic_extended_DDR and not hrd_score:
    ddr_bin_status = "unknown"

# Rule 6: DDR proficient (default)
else:
    ddr_bin_status = "DDR_proficient"
```

#### **Step 6: Compute Optional DDR_score**
```python
# Weighted sum of DDR hits (for continuous scoring)
ddr_score = (
    3.0 if has_pathogenic_BRCA else 0.0 +  # BRCA = highest weight
    2.5 if hrd_positive_inferred else 0.0 +  # HRD = high weight
    2.0 if has_pathogenic_core_HRR else 0.0 +  # Core HRR = medium-high weight
    1.0 if has_pathogenic_extended_DDR else 0.0  # Extended DDR = lower weight
)
```

---

## 📊 Output Schema

### **5.1 Output Table (ddr_status_table)**

One row per `patient_id`:

| Column | Type | Description |
|--------|------|-------------|
| `patient_id` | str/int | Patient identifier |
| `disease_site` | str | Disease site (ovary, breast, pancreas, prostate, other) |
| `tumor_subtype` | str | Tumor subtype (HGSOC, TNBC, PDAC, etc.) or null |
| `DDR_bin_status` | str | `DDR_defective` / `DDR_proficient` / `unknown` |
| `HRD_status_inferred` | str | `HRD_positive` / `HRD_negative` / `unknown` |
| `HRD_score_raw` | float | Raw HRD score from assay (or null) |
| `BRCA_pathogenic` | bool | True if pathogenic BRCA1/2 variant found |
| `core_HRR_pathogenic` | bool | True if pathogenic core HRR variant found |
| `extended_DDR_pathogenic` | bool | True if pathogenic extended DDR variant found |
| `DDR_score` | float | Numeric summary (weighted sum of hits) |
| `DDR_features_used` | JSON/list | List of rules that fired (for auditability) |

**Joinability:** This table must be joinable to existing PFI/PTPI and outcome tables for modeling across cancers.

---

## 🧪 Testing Requirements

### **6.1 Unit Tests**

Include at least one unit test per `disease_site` (ovary, breast, pancreas, prostate, default) with synthetic inputs to prove parameterization works.

**Test Cases:**

1. **BRCA Pathogenic (All Sites)**
   - Input: BRCA1 pathogenic variant
   - Expected: `DDR_defective`, `BRCA_pathogenic=True`, `DDR_features_used=["BRCA_pathogenic"]`

2. **HRD Positive by Score (Ovary)**
   - Input: HRD score = 45, no mutations
   - Expected: `DDR_defective`, `HRD_status_inferred="HRD_positive"`, `DDR_features_used=["HRD_score_high"]`

3. **HRD Positive by Status (Breast)**
   - Input: `hrd_status="HRD_positive"`, no mutations
   - Expected: `DDR_defective`, `HRD_status_inferred="HRD_positive"`, `DDR_features_used=["HRD_status_positive"]`

4. **Core HRR Pathogenic (All Sites)**
   - Input: PALB2 pathogenic variant, no BRCA, no HRD
   - Expected: `DDR_defective`, `core_HRR_pathogenic=True`, `DDR_features_used=["core_hrr_pathogenic"]`

5. **Extended DDR Pathogenic (All Sites)**
   - Input: ATM pathogenic variant, no BRCA/HRD/core HRR
   - Expected: `DDR_defective`, `extended_DDR_pathogenic=True`, `DDR_features_used=["extended_ddr_pathogenic"]`

6. **No DDR Info (All Sites)**
   - Input: No mutations, no HRD data
   - Expected: `DDR_bin_status="unknown"`, all flags=False

7. **DDR Proficient (All Sites)**
   - Input: VUS only, no pathogenic variants, HRD negative
   - Expected: `DDR_bin_status="DDR_proficient"`, all flags=False

8. **Different Cutoffs (Site-Specific)**
   - Input: HRD score = 41 (below ovary cutoff 42, but above breast cutoff 40 if configured)
   - Expected: Different results per site if cutoffs differ

9. **Biallelic BRCA (Ovary - require_biallelic_if_cn_available=True)**
   - Input: BRCA1 pathogenic + CNA deletion
   - Expected: `DDR_defective`, biallelic confirmed

10. **Non-Biallelic BRCA (Pancreas - require_biallelic_if_cn_available=False)**
    - Input: BRCA1 pathogenic, no CNA deletion
    - Expected: `DDR_defective` (biallelic not required)

---

## 🚫 Non-Goals (For Now)

1. **No survival modeling** - Just scoring and classification
2. **No disease-specific outcome models** - No PARPi benefit prediction here
3. **No hard-coded "ovary only" logic** - Everything must be driven by `DDR_CONFIG` and `disease_site`
4. **No proprietary test internals** - Treat HRD score and status as black-box inputs (don't try to replicate Myriad algorithm)

---

## 📋 Deliverable

A tested module (Python) that:

1. **Takes the 4 tables + config as input** (mutations, CNA, HRD assay, clinical)
2. **Returns ddr_status_table** (one row per patient_id)
3. **Includes unit tests** covering:
   - Different `disease_site` values using different cutoffs/lists
   - Patients with BRCA only, HRD only, non-BRCA DDR only, and no DDR info
   - Biallelic vs non-biallelic scenarios
   - Different HRD assay types (Myriad, Leuven, Geneva)

---

## 🔗 Integration Points

### **7.1 With Resistance Prophet**

The DDR_bin engine should integrate with the Resistance Prophet modular architecture:
- Location: `api/services/resistance/biomarkers/diagnostic/ddr_bin_scoring.py`
- Follows `BaseResistanceDetector` pattern (if applicable) or standalone utility
- Uses config system: `api/services/resistance/config/ddr_config.py`

### **7.2 With PARPi/DDR Outcome Feature Layer**

Output (`ddr_status_table`) will be used by:
- PARPi/DDR outcome feature layer (Task 2 from NEXT_DELIVERABLE.md)
- Resistance prediction models
- Treatment eligibility scoring

---

## 📚 References

- **HRD Score Cutoff (42)**: GIS-like threshold (Myriad MyChoice HRD)
- **Core HRR Genes**: BRCA1/2, PALB2, RAD51C/D, BARD1, BRIP1 (standard HRR pathway)
- **Extended DDR Genes**: ATM, ATR, CHEK1/2, FANCA/D2, RAD50/MRE11/NBN, POLQ (DDR pathway)

---

**Last Updated:** January 13, 2026  
**Status:** 📋 **READY FOR IMPLEMENTATION**
