# Biomarker-Focused File Hierarchy

**Date:** January 13, 2026  
**Status:** ✅ **REORGANIZATION PLAN**  
**Purpose:** Organize resistance detectors by biomarker type rather than validation status

---

## 🎯 Current Problem

**Current Structure:**
```
resistance/
├── detectors/
│   ├── validated/
│   │   ├── dna_repair_detector.py
│   │   ├── post_treatment_pathway_detector.py
│   │   └── mm_high_risk_gene_detector.py
│   ├── pending_revalidation/
│   └── literature_based/
```

**Issues:**
- Organized by validation status (not intuitive for developers)
- Long file names (`post_treatment_pathway_detector.py`)
- Hard to find by biomarker type
- Doesn't reflect biomarker hierarchy

---

## ✅ Proposed Structure (Biomarker-Focused)

```
resistance/
├── biomarkers/                           # All biomarker detectors
│   ├── __init__.py
│   ├── base.py                           # Base detector class
│   │
│   ├── dna_repair/                       # DNA repair biomarkers
│   │   ├── __init__.py
│   │   └── restoration.py                # DNA repair restoration detector
│   │
│   ├── pathway/                          # Pathway-based biomarkers
│   │   ├── __init__.py
│   │   └── post_treatment.py             # Post-treatment pathway profiling
│   │
│   ├── ca125/                            # CA-125 biomarkers
│   │   ├── __init__.py
│   │   └── kinetics.py                   # CA-125 kinetics detector
│   │
│   ├── genomic/                          # Genomic biomarkers
│   │   ├── __init__.py
│   │   ├── mm_high_risk.py               # MM high-risk genes (DIS3, TP53)
│   │   └── cytogenetics.py               # Cytogenetics (del(17p), t(4;14))
│   │
│   └── molecular/                        # Molecular biomarkers (future)
│       ├── __init__.py
│       └── ctDNA.py                      # ctDNA MRD (future)
│
├── orchestration/                        # Orchestration logic
│   ├── __init__.py
│   ├── probability.py
│   ├── risk_stratifier.py
│   ├── confidence.py
│   ├── actions.py
│   └── orchestrator.py
│
├── events/                               # Event system
│   ├── __init__.py
│   ├── events.py
│   └── dispatcher.py
│
├── models.py                             # Shared dataclasses
├── MODULARIZATION_PLAN.md
└── POST_TREATMENT_PATHWAY_PROFILING.md
```

---

## 📊 Biomarker Type Hierarchy

### 1. **DNA Repair Biomarkers** (`biomarkers/dna_repair/`)
**Purpose:** DNA damage response and repair capacity

**Detectors:**
- `restoration.py` - DNA repair restoration (Signal 1)

**Future:**
- `baseline_capacity.py` - Baseline DNA repair capacity
- `hrd_dynamics.py` - HRD score changes over time

---

### 2. **Pathway Biomarkers** (`biomarkers/pathway/`)
**Purpose:** Pathway-level profiling and kinetics

**Detectors:**
- `post_treatment.py` - Post-treatment pathway profiling (Signal 7)

**Future:**
- `baseline_profiling.py` - Baseline pathway burden
- `kinetics.py` - Pathway kinetics (when validated)

---

### 3. **CA-125 Biomarkers** (`biomarkers/ca125/`)
**Purpose:** CA-125 kinetics and monitoring

**Detectors:**
- `kinetics.py` - CA-125 kinetics detector (Signal 3)

**Future:**
- `kelim.py` - KELIM score calculation
- `early_decline.py` - Early decline patterns

---

### 4. **Genomic Biomarkers** (`biomarkers/genomic/`)
**Purpose:** Gene-level and chromosomal biomarkers

**Detectors:**
- `mm_high_risk.py` - MM high-risk genes (DIS3, TP53) (Signal 4)
- `cytogenetics.py` - Cytogenetics (del(17p), t(4;14)) (Signal 5)

**Future:**
- `ov_resistance_genes.py` - Ovarian resistance genes (NF1, MAPK)
- `pathway_escape.py` - Pathway escape detection (when validated)

---

### 5. **Molecular Biomarkers** (`biomarkers/molecular/`) - Future
**Purpose:** Molecular-level biomarkers

**Future Detectors:**
- `ctDNA.py` - ctDNA MRD detection
- `tmb_dynamics.py` - TMB changes over time

---

## 🔄 Migration Plan

### Step 1: Create New Structure
```bash
mkdir -p resistance/biomarkers/{dna_repair,pathway,ca125,genomic,molecular}
```

### Step 2: Move Files
- `detectors/validated/dna_repair_detector.py` → `biomarkers/dna_repair/restoration.py`
- `detectors/validated/post_treatment_pathway_detector.py` → `biomarkers/pathway/post_treatment.py`
- `detectors/validated/mm_high_risk_gene_detector.py` → `biomarkers/genomic/mm_high_risk.py`

### Step 3: Update Imports
- Update all import paths
- Update `__init__.py` files
- Update orchestrator imports

### Step 4: Remove Old Structure
- Remove `detectors/validated/`, `detectors/pending_revalidation/`, `detectors/literature_based/`
- Keep `detectors/base_detector.py` → move to `biomarkers/base.py`

---

## ✅ Benefits

1. **Intuitive Organization:** Find detectors by biomarker type
2. **Clearer Names:** `pathway/post_treatment.py` vs `post_treatment_pathway_detector.py`
3. **Scalable:** Easy to add new biomarker types
4. **Reflects Hierarchy:** Biomarker type → specific detector

---

**Status:** ✅ **READY FOR IMPLEMENTATION**
