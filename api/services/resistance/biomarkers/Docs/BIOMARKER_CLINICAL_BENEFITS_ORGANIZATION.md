# Biomarker Organization by Clinical Benefits

**Date:** January 13, 2026  
**Status:** ✅ **REORGANIZATION PLAN - CLINICAL BENEFIT FOCUSED**  
**Source:** Clinical Benefits of Biomarkers framework (6 categories)

---

## 🎯 Clinical Benefits Framework

Based on the "Clinical Benefits of Biomarkers" framework, biomarkers are organized by their primary clinical purpose:

1. **Diagnostic** - "What type of cancer do I have?"
2. **Prognostic** - "What is my expected outlook?"
3. **Predictive** - "How likely am I to respond to immunotherapy/treatment?"
4. **Therapeutic** - "Is the immunotherapy/treatment working?"
5. **Safety** - "Am I experiencing side effects from treatment?"
6. **Long-Term Monitoring** - "Is my cancer in the process of relapsing?"

---

## 📊 Current Detectors → Clinical Benefit Mapping

### **1. Diagnostic** (`biomarkers/diagnostic/`)
**Purpose:** Identify cancer type, subtype, molecular characteristics

**Current Detectors:** None yet (future: subtype classification, molecular typing)

**Future:**
- Tumor subtype classification
- Molecular typing (HRD+, MSI-H, etc.)
- Disease staging biomarkers

---

### **2. Prognostic** (`biomarkers/prognostic/`)
**Purpose:** Predict patient outcome independent of treatment

**Current Detectors:**
- `genomic/mm_high_risk.py` - MM high-risk genes (DIS3, TP53) → Predicts poor prognosis
- `pathway/post_treatment.py` - Post-treatment pathway profiling → Predicts PFI/outcome

**Rationale:**
- MM high-risk genes predict overall survival/prognosis (DIS3 RR=2.08, TP53 RR=1.90)
- Post-treatment pathway scores correlate with PFI (predicts progression timing)

---

### **3. Predictive** (`biomarkers/predictive/`)
**Purpose:** Predict response to specific treatments

**Current Detectors:**
- `dna_repair/restoration.py` - DNA repair restoration → Predicts PARP inhibitor resistance
- `pathway/post_treatment.py` - Post-treatment pathway profiling → Predicts platinum resistance

**Rationale:**
- DNA repair restoration predicts PARP inhibitor resistance (predictive of drug response)
- Post-treatment pathway profiling predicts platinum resistance (predictive of chemo response)

---

### **4. Therapeutic** (`biomarkers/therapeutic/`)
**Purpose:** Monitor if treatment is working during therapy

**Current Detectors:**
- `dna_repair/restoration.py` - DNA repair restoration → Detects restoration during PARP therapy (therapeutic monitoring)
- `ca125/kinetics.py` - CA-125 kinetics → Monitors treatment response (future)

**Rationale:**
- DNA repair restoration is detected DURING therapy (monitors if PARP inhibitor is working)
- CA-125 kinetics tracks treatment response in real-time

---

### **5. Safety** (`biomarkers/safety/`)
**Purpose:** Detect treatment-related side effects

**Current Detectors:** None yet (future: toxicity biomarkers)

**Future:**
- Treatment-related toxicity markers
- Side effect prediction/detection

---

### **6. Long-Term Monitoring** (`biomarkers/long_term_monitoring/`)
**Purpose:** Detect relapse/recurrence after treatment

**Current Detectors:**
- `ca125/kinetics.py` - CA-125 kinetics → Detects rising CA-125 (relapse signal) (future)
- `dna_repair/restoration.py` - DNA repair restoration → Early resistance signal (3-6 months before progression)

**Rationale:**
- CA-125 rise after treatment completion indicates relapse
- DNA repair restoration predicts resistance 3-6 months before clinical progression (early relapse detection)

---

## 🔄 Detector Cross-Category Mapping

Some detectors serve multiple clinical purposes:

### **DNA Repair Restoration**
- **Primary:** Therapeutic (monitors treatment response during PARP therapy)
- **Secondary:** Predictive (predicts PARP resistance), Long-Term Monitoring (early resistance detection)

### **Post-Treatment Pathway Profiling**
- **Primary:** Prognostic (predicts PFI/outcome)
- **Secondary:** Predictive (predicts platinum resistance)

### **MM High-Risk Genes**
- **Primary:** Prognostic (predicts poor prognosis/outcome)
- **Secondary:** Predictive (predicts treatment response)

### **CA-125 Kinetics**
- **Primary:** Therapeutic (monitors treatment response)
- **Secondary:** Long-Term Monitoring (detects relapse)

---

## 📋 Proposed Structure (Primary Placement)

Each detector is placed in its **PRIMARY** clinical benefit category, with metadata indicating secondary benefits:

```
resistance/
├── biomarkers/
│   ├── __init__.py
│   ├── base.py                    # Base detector class
│   │
│   ├── diagnostic/                # "What type of cancer do I have?"
│   │   ├── __init__.py
│   │   └── (future: subtype classification)
│   │
│   ├── prognostic/                # "What is my expected outlook?"
│   │   ├── __init__.py
│   │   ├── mm_high_risk.py        # MM high-risk genes (DIS3, TP53) - PRIMARY: Prognostic
│   │   │                           # Secondary: Predictive
│   │   └── pathway_post_treatment.py  # Post-treatment pathway profiling - PRIMARY: Prognostic
│   │                                   # Secondary: Predictive
│   │
│   ├── predictive/                # "How likely am I to respond to treatment?"
│   │   ├── __init__.py
│   │   └── dna_repair_restoration.py  # DNA repair restoration - PRIMARY: Predictive
│   │                                   # Secondary: Therapeutic, Long-Term Monitoring
│   │
│   ├── therapeutic/               # "Is the treatment working?"
│   │   ├── __init__.py
│   │   └── ca125_kinetics.py      # CA-125 kinetics (future) - PRIMARY: Therapeutic
│   │                               # Secondary: Long-Term Monitoring
│   │
│   ├── safety/                    # "Am I experiencing side effects?"
│   │   ├── __init__.py
│   │   └── (future: toxicity markers)
│   │
│   └── long_term_monitoring/      # "Is my cancer relapsing?"
│       ├── __init__.py
│       └── (future: relapse detection)
│
├── orchestration/
├── events/
└── models.py
```

**Note:** Detectors are placed in their PRIMARY clinical benefit. Secondary benefits are documented in detector metadata.

---

## 🎯 Decision: Single vs Multiple Placement

**Option A: Single Placement (Primary Benefit)**
- Each detector lives in ONE category (primary benefit)
- Simpler structure, but loses cross-category visibility

**Option B: Multiple Placement (Symlinks/References)**
- Detectors can appear in multiple categories
- More complex, but reflects reality

**Option C: Primary + Tags**
- Detectors live in primary category
- Metadata/tags indicate secondary benefits
- Best of both worlds

**Recommendation:** **Option C** - Primary placement with metadata tags

---

## ✅ Benefits of Clinical Benefit Organization

1. **Clinically Intuitive:** Matches how clinicians think about biomarkers
2. **User-Focused:** Answers the questions clinicians/patients ask
3. **Aligns with Framework:** Matches the "Clinical Benefits of Biomarkers" framework
4. **Clear Purpose:** Each category has a clear clinical question

---

**Status:** ✅ **READY FOR IMPLEMENTATION**
