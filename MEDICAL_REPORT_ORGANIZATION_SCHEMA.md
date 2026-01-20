# Medical Report Organization Schema

**Purpose**: Hierarchical organization of medical reports for patient profiles

---

## 📊 **REPORT TYPE HIERARCHY**

```
PATIENT PROFILE
├── IMAGING_REPORTS
│   ├── CT_SCAN
│   │   ├── CT Abdomen/Pelvis
│   │   ├── CT Chest
│   │   └── CT Head
│   ├── PET_SCAN
│   │   ├── PET-CT Whole Body
│   │   └── PET-CT Skull Base to Mid-Thigh
│   ├── MRI
│   └── ULTRASOUND
│
├── PATHOLOGY_REPORTS
│   ├── CYTOPATHOLOGY (e.g., Pleural Fluid)
│   ├── SURGICAL_PATHOLOGY
│   ├── IMMUNOHISTOCHEMISTRY
│   └── MOLECULAR_PATHOLOGY
│
├── GENETIC_REPORTS
│   ├── GERMLINE_TESTING
│   │   ├── CustomNext-Cancer
│   │   └── BRCA1/2
│   ├── SOMATIC_TESTING
│   │   ├── Foundation Medicine
│   │   ├── Tempus
│   │   └── Guardant
│   └── PHARMACOGENOMICS
│
├── LAB_REPORTS
│   ├── CA-125 (Tumor Markers)
│   ├── CBC
│   ├── CMP
│   └── LIVER_FUNCTION
│
└── CLINICAL_NOTES
    ├── ONCOLOGY_CONSULT
    ├── TREATMENT_NOTES
    └── SURGERY_NOTES
```

---

## 🗂️ **DATA STRUCTURE**

### **Report Metadata**
```json
{
  "report_id": "auto-generated-uuid",
  "report_type": "IMAGING|PATHOLOGY|GENETIC|LAB|CLINICAL_NOTE",
  "report_subtype": "CT_SCAN|PET_SCAN|CYTOPATHOLOGY|GERMLINE|etc",
  "exam_type": "CT Abdomen and Pelvis with IV Contrast",
  "report_date": "2025-10-28",  // Relative date (year only for PII removal)
  "extraction_date": "2026-01-10",
  "source": "Epic|MyChart|Uploaded PDF",
  "raw_text": "full text...",  // Stored for re-extraction
  "de_identified": false  // Flag for PII stripping
}
```

### **Clinical Data (Type-Specific)**
```json
{
  "clinical_indication": "...",
  "technique": "...",
  "comparison": "...",
  "findings": {
    "structured": {...},
    "narrative": "..."
  },
  "impression": "...",
  "recommendations": [...]
}
```

### **Structured Findings (Per Report Type)**

#### **IMAGING Reports**
```json
{
  "findings": {
    "locations": [
      {
        "anatomy": "abdomen|pelvis|chest|etc",
        "findings": ["carcinomatosis", "ascites", "lymphadenopathy"],
        "measurements": {...},
        "suv_values": {...}  // For PET scans
      }
    ],
    "key_clinical_findings": {
      "carcinomatosis": true,
      "ascites": true,
      "pleural_effusions": true,
      "lymph_node_metastases": true,
      "suspected_primary": "gynecologic"
    },
    "measurements": {
      "largest_lesion": {"size": "8cm", "location": "right lower quadrant"},
      "lymph_nodes": {"largest": "1.5cm", "location": "right external iliac"}
    }
  }
}
```

#### **PATHOLOGY Reports**
```json
{
  "findings": {
    "diagnosis": "Metastatic adenocarcinoma, consistent with Mullerian primary",
    "specimen_type": "Pleural fluid",
    "immunohistochemistry": {
      "positive": ["claudin4", "MOC31", "CK7", "PAX8", "WT1"],
      "negative": ["calretinin", "CD163", "TTF1", "GATA3", "CK20"],
      "special_markers": {
        "p16": "Strong and diffuse",
        "p53": "Mutant type",
        "ER": "Weak to moderate (60%)",
        "PR": "Negative (0%)"
      }
    },
    "molecular_markers": {
      "p53": "mutant",
      "ER": "weakly_positive",
      "PR": "negative",
      "PD-L1": {"status": "positive", "cps": 10}
    }
  }
}
```

#### **GENETIC Reports**
```json
{
  "findings": {
    "test_type": "germline|somatic",
    "genes_tested": [...],
    "mutations": [
      {
        "gene": "BRCA1",
        "variant": "c.5266dupC",
        "classification": "pathogenic|VUS",
        "zygosity": "heterozygous|homozygous"
      }
    ],
    "biomarkers": {
      "TMB": 10.2,
      "MSI": "MSS|MSI-H",
      "HRD": {"score": 42, "status": "positive"}
    }
  }
}
```

---

## 🔄 **PATIENT PROFILE AGGREGATION**

### **Synthesized Patient Profile Fields**
```json
{
  "patient_profile": {
    "disease": "ovarian_cancer_hgs",  // From pathology
    "stage": "IVB",  // From imaging + pathology
    "primary_site": "ovarian|peritoneal",  // From pathology
    "histology": "high_grade_serous_carcinoma",  // From pathology
    
    "imaging_findings": {
      "latest_scan_date": "2025-11-11",  // Most recent imaging
      "disease_extent": {
        "carcinomatosis": true,
        "ascites": true,
        "pleural_effusions": true,
        "lymph_node_metastases": true,
        "distant_metastases": true
      },
      "locations": [
        "cervical_nodes",
        "mediastinal_nodes",
        "abdominopelvic",
        "pleural",
        "pericardial"
      ],
      "timeline": [
        {"date": "2024-01-31", "findings": "ovarian cysts, no carcinomatosis"},
        {"date": "2025-10-28", "findings": "extensive carcinomatosis, ascites"},
        {"date": "2025-11-11", "findings": "extensive carcinomatosis, widespread metastases"}
      ]
    },
    
    "pathology_findings": {
      "diagnosis": "Metastatic adenocarcinoma, Mullerian origin",
      "immunohistochemistry": {
        "p53": "mutant",
        "ER": "weakly_positive",
        "PR": "negative",
        "PD-L1": {"status": "positive", "cps": 10},
        "MMR": "preserved"
      }
    },
    
    "genetic_findings": {
      "germline_status": "positive",
      "germline_testing": {
        "test_date": "2025-11-24",
        "lab": "Ambry Genetics",
        "test_type": "CancerNext-Expanded + RNAinsight (77 genes)",
        "mutations": [
          {
            "gene": "MBD4",
            "variant": "c.1293delA",
            "protein_change": "p.K431Nfs*54",
            "zygosity": "homozygous",
            "classification": "pathogenic",
            "syndrome": "MBD4-associated neoplasia syndrome (MANS)"
          },
          {
            "gene": "PDGFRA",
            "variant": "c.2263T>C",
            "protein_change": "p.S755P",
            "zygosity": "heterozygous",
            "classification": "VUS"
          }
        ],
        "risk_increases": ["Acute myelogenous leukemia", "Colorectal cancer"]
      },
      "somatic_mutations": [...],
      "biomarkers": {
        "TMB": null,
        "MSI": "MSS",
        "HRD": null
      }
    },
    
    "report_history": {
      "imaging_reports": [...],  // All imaging reports, sorted by date
      "pathology_reports": [...],
      "genetic_reports": [...],
      "lab_reports": [...]
    }
  }
}
```

---

## 📝 **IMPLEMENTATION APPROACH**

### **1. Report Classification (LLM-based, not hard-coded)**
```python
def classify_report_type(text: str) -> Dict:
    """
    Classify report type using LLM (Gemini/GPT-4) with prompt:
    'Classify this medical report. Return: report_type, report_subtype, exam_type'
    """
    pass
```

### **2. Structured Extraction (Type-specific prompts)**
```python
def extract_structured_data(text: str, report_type: str) -> Dict:
    """
    Extract structured data using type-specific LLM prompts:
    - IMAGING: Extract locations, findings, measurements, SUV values
    - PATHOLOGY: Extract diagnosis, IHC markers, molecular markers
    - GENETIC: Extract mutations, biomarkers, test type
    """
    pass
```

### **3. Patient Profile Synthesis**
```python
def synthesize_patient_profile(reports: List[Dict]) -> Dict:
    """
    Aggregate findings from all reports:
    - Latest imaging findings
    - Pathology diagnosis
    - Genetic mutations
    - Timeline of disease progression
    """
    pass
```

---

## 🎯 **KEY PRINCIPLES**

1. **Hierarchical Organization**: Reports organized by type → subtype → individual reports
2. **Chronological Ordering**: Multiple reports of same type sorted by date
3. **Structured + Narrative**: Both structured fields and raw narrative preserved
4. **Flexible Extraction**: LLM-based (not hard-coded patterns)
5. **PII Separation**: Metadata stored separately, de-identified for clinical use
6. **Synthesis**: Key findings aggregated into patient profile fields

---

## 📊 **EXAMPLE: Multiple Reports Organization**

### **Input**: 7 Reports (2 CT Scans, 1 PET Scan, 3 Pathology Reports, 1 Genetic Test)

#### **Report 1: CT Scan - Baseline (2/1/2024)**
- **Type**: IMAGING → CT_SCAN
- **Key Findings**: Left ovarian cysts (5.2 cm and 4.4 cm), lower abdominal wall collection, status post total colectomy
- **Impression**: Lower abdominal wall/rectus collection with tract to skin surface. No bowel obstruction or intra-abdominal collection.
- **Clinical Context**: Status post robotic total colectomy 01/02/2024. Baseline scan - **NO CARCINOMATOSIS** detected at this time.

#### **Report 2: CT Scan - Progression (10/28/2025)**
- **Type**: IMAGING → CT_SCAN
- **Key Findings**: Peritoneal carcinomatosis, small volume ascites, lymphadenopathy, ovaries inseparable from peritoneal deposits
- **Impression**: Suspicious for metastatic disease, recommend tissue sampling
- **Clinical Context**: ~22 months later - **DISEASE PROGRESSION** detected

#### **Report 3: PET Scan (11/11/2025)**
- **Type**: IMAGING → PET_SCAN
- **Key Findings**: Extensive carcinomatosis, widespread metastases (SUV max 15.0)
- **Impression**: Suspect gynecologic primary (adnexal/endometrial/cervical)
- **Clinical Context**: ~2 weeks after progression CT - **WIDESPREAD METASTASES** confirmed

#### **Report 4: Pathology - Cytology Right Pleural Fluid (11/17/2025)**
- **Type**: PATHOLOGY → CYTOPATHOLOGY
- **Specimen**: Pleural fluid, right (1400 cc)
- **Report Number**: CN25-5777
- **Diagnosis**: POSITIVE FOR MALIGNANT CELLS - Metastatic adenocarcinoma, Mullerian primary
- **IHC Markers**:
  - **Positive**: claudin4, MOC31, CK7, PAX8, WT1
  - **Negative**: calretinin, CD163, TTF1, GATA3, CK20
  - **Special Markers**:
    - p16: strong and diffuse
    - p53: mutant type (strong and diffuse)
    - ER: weakly to moderately positive (60%)
    - PR: negative (0%)
- **Note**: Complete IHC workup performed on this specimen

#### **Report 5: Pathology - Cytology Left Pleural Fluid (11/17/2025)**
- **Type**: PATHOLOGY → CYTOPATHOLOGY
- **Specimen**: Pleural fluid, left (1200 cc)
- **Report Number**: CN25-5778
- **Diagnosis**: POSITIVE FOR MALIGNANT CELLS - Metastatic adenocarcinoma
- **Clinical Context**: Same cytomorphology as right pleural fluid (CN25-5777). References CN25-5777 for complete IHC workup.
- **Note**: Bilateral pleural metastases confirmed - same tumor type on both sides

#### **Report 6: Genetic Testing - Germline (11/24/2025)**
- **Type**: GENETIC → GERMLINE_TESTING
- **Test**: CancerNext-Expanded® + RNAinsight® (77 genes)
- **Lab**: Ambry Genetics
- **Specimen**: Blood EDTA (Purple top)
- **Accession**: #25-743747
- **Result**: POSITIVE - Pathogenic mutations detected
- **Indication**: Family history
- **Mutations**:
  - **MBD4**: Homozygous c.1293delA (p.K431Nfs*54) - **PATHOGENIC**
  - **PDGFRA**: Heterozygous p.S755P (c.2263T>C) - **VUS** (variant of unknown significance)
- **Diagnosis**: MBD4-associated neoplasia syndrome (MANS)
- **Risk**: Increased risk for acute myelogenous leukemia (AML) and colorectal cancer (CRC)
- **Inheritance**: Autosomal recessive (biallelic loss of function)
- **Note**: 77 genes analyzed, no additional pathogenic mutations or gross deletions/duplications detected

#### **Report 7: Pathology - Surgical Biopsies (11/17/2025 - Tissue)**
- **Type**: PATHOLOGY → SURGICAL_PATHOLOGY
- **Path Number**: GP25-3371
- **Date Obtained**: 11/17/2025
- **Report Date**: 11/20/2025 (addenda 12/3/2025)
- **Specimens** (4 parts):
  - **A. Biopsy of omentum**: Metastatic adenocarcinoma, Mullerian origin
  - **B. Endometrial curettings**: Fragments of high grade carcinoma
  - **C. Anterior perineal nodule**: Metastatic adenocarcinoma, Mullerian origin
  - **D. Biopsy of omentum #2**: Metastatic adenocarcinoma, Mullerian origin
- **Diagnosis**: Similar tumor identified in all parts. Strong WT-1 staining more consistent with high grade serous carcinoma of adnexal or primary peritoneal origin than endometrial primary.
- **IHC Markers**:
  - **Positive**: PAX8, CK7, WT-1
  - **Negative**: CK20, SATB2, GATA3
  - **Also references cytology**: negative calretinin, positive MOC31, Claudin4
- **Comprehensive Biomarkers**:
  - **MMR (Mismatch Repair)**: Preserved (MLH1+, PMS2+, MSH2+, MSH6+)
  - **ER (Estrogen Receptor)**: Weakly positive, 50%
  - **PR (Progesterone Receptor)**: Negative (<1%)
  - **p53**: Positive, favor mutant type
  - **HER-2**: Negative (score 0)
  - **FOLR1**: Negative (<1% - requires ≥75% for ELAHERE eligibility)
  - **PD-L1 (22C3)**: Positive (CPS = 10)
  - **NTRK**: Negative
- **Additional Tests** (addenda 12/3/2025):
  - Solid Tumor Gynecological Panel
  - Microsatellite Instability (MSI) Testing (likely MSS given preserved MMR)
- **Clinical Context**: Tissue biopsies confirming Mullerian origin with comprehensive biomarker panel. Most comprehensive pathology report with actionable biomarkers (PD-L1 positive, FOLR1 negative, MMR preserved).

### **Output**: Organized Patient Profile
```json
{
  "report_organization": {
    "IMAGING_REPORTS": {
      "CT_SCAN": [
        {
          "report_id": "img-ct-baseline",
          "exam_type": "CT Abdomen and Pelvis with IV Contrast",
          "exam_date": "2024-02-01",
          "key_findings": {
            "ovarian_cysts": true,
            "cysts_size": {"inferior": "5.2cm", "superior": "4.4cm"},
            "lower_abdominal_collection": true,
            "carcinomatosis": false,
            "ascites": false,
            "lymphadenopathy": false
          },
          "impression": "Lower abdominal wall/rectus collection with tract to skin surface. No bowel obstruction or intra-abdominal collection.",
          "clinical_context": "Baseline scan - status post total colectomy 01/02/2024. No evidence of carcinomatosis."
        },
        {
          "report_id": "img-ct-001",
          "exam_type": "CT Abdomen and Pelvis with IV Contrast",
          "exam_date": "2025-10-28",
          "key_findings": {
            "carcinomatosis": true,
            "ascites": true,
            "pleural_effusions": true,
            "lymphadenopathy": true,
            "ovaries_inseparable": true
          },
          "impression": "Peritoneal carcinomatosis, small volume ascites, and abdominopelvic lymphadenopathy suspicious for metastatic disease. The ovaries appear inseparable from the peritoneal deposits. Recommend tissue sampling for further evaluation."
        }
      ],
      "PET_SCAN": [
        {
          "report_id": "img-pet-001",
          "exam_type": "PET-CT Skull Base to Mid-Thigh",
          "exam_date": "2025-11-11",
          "key_findings": {
            "extensive_carcinomatosis": true,
            "ascites": true,
            "pleural_effusions": true,
            "lymph_node_metastases": true,
            "gynecologic_primary_suspected": true,
            "suv_max": 15.0
          },
          "impression": "Extensive carcinomatosis with moderate volume ascites, bilateral pleural metastatic disease with persistent large layering bilateral pleural effusions, soft tissue metastases, and extensive cervical, thoracic, and abdominopelvic nodal metastases. Suspect a gynecologic primary, either left adnexal, endometrial, or cervical."
        }
      ]
    },
    "PATHOLOGY_REPORTS": {
      "CYTOPATHOLOGY": [
        {
          "report_id": "path-cyto-right",
          "exam_type": "NON-GYN CYTOLOGY - Pleural Fluid",
          "specimen_type": "Pleural fluid, right",
          "specimen_volume": "1400 cc",
          "report_number": "CN25-5777",
          "report_date": "2025-11-17",
          "diagnosis": {
            "result": "POSITIVE FOR MALIGNANT CELLS",
            "tumor_type": "Metastatic adenocarcinoma",
            "primary_site": "Mullerian (gynecologic)"
          },
          "immunohistochemistry": {
            "positive_markers": ["claudin4", "MOC31", "CK7", "PAX8", "WT1"],
            "negative_markers": ["calretinin", "CD163", "TTF1", "GATA3", "CK20"],
            "special_markers": {
              "p16": "strong_and_diffuse",
              "p53": "mutant_type",
              "ER": {"status": "weakly_to_moderately_positive", "percent": 60},
              "PR": {"status": "negative", "percent": 0}
            }
          },
          "note": "Complete IHC workup performed on this specimen"
        },
        {
          "report_id": "path-cyto-left",
          "exam_type": "NON-GYN CYTOLOGY - Pleural Fluid",
          "specimen_type": "Pleural fluid, left",
          "specimen_volume": "1200 cc",
          "report_number": "CN25-5778",
          "report_date": "2025-11-17",
          "diagnosis": {
            "result": "POSITIVE FOR MALIGNANT CELLS",
            "tumor_type": "Metastatic adenocarcinoma",
            "primary_site": "Mullerian (gynecologic)"
          },
          "clinical_context": "Same cytomorphology as right pleural fluid (CN25-5777). References CN25-5777 for complete IHC workup.",
          "note": "Bilateral pleural metastases confirmed - same tumor type on both sides"
        }
      ],
      "SURGICAL_PATHOLOGY": [
        {
          "report_id": "path-surgical-001",
          "exam_type": "OBSTETRICAL & GYNECOLOGICAL PATHOLOGY",
          "path_number": "GP25-3371",
          "report_date": "2025-11-20",
          "date_obtained": "2025-11-17",
          "specimens": [
            {
              "specimen_id": "A",
              "specimen_type": "Biopsy of omentum",
              "diagnosis": "Metastatic adenocarcinoma consistent with Mullerian origin"
            },
            {
              "specimen_id": "B",
              "specimen_type": "Endometrial curettings",
              "diagnosis": "Fragments of high grade carcinoma"
            },
            {
              "specimen_id": "C",
              "specimen_type": "Anterior perineal nodule",
              "diagnosis": "Metastatic adenocarcinoma consistent with Mullerian origin"
            },
            {
              "specimen_id": "D",
              "specimen_type": "Biopsy of omentum #2",
              "diagnosis": "Metastatic adenocarcinoma consistent with Mullerian origin"
            }
          ],
          "diagnosis_summary": "Similar tumor identified in all parts. Metastatic adenocarcinoma consistent with Mullerian origin. Strong WT-1 staining more commonly seen in high grade serous carcinoma of adnexal or primary peritoneal origin than endometrial primary.",
          "immunohistochemistry": {
            "positive_markers": ["PAX8", "CK7", "WT-1"],
            "negative_markers": ["CK20", "SATB2", "GATA3"],
            "note": "Tumor stains positive for PAX8, CK7, WT-1, and negative for CK20, SATB2, GATA3. Per cytology report, tumor is negative for calretinin, and positive for MOC31 and Claudin4."
          },
          "biomarkers": {
            "mismatch_repair": {
              "status": "preserved",
              "markers": {
                "MLH1": "positive",
                "PMS2": "positive",
                "MSH2": "positive",
                "MSH6": "positive"
              }
            },
            "hormone_receptors": {
              "ER": {"status": "weakly_positive", "percent": 50},
              "PR": {"status": "negative", "percent": "<1%"}
            },
            "p53": {"status": "positive", "type": "mutant_type"},
            "HER2": {"status": "negative", "score": 0},
            "FOLR1": {"status": "negative", "percent": "<1%", "note": "Cases with staining in at least 75% of tumor cells are considered positive and eligible for treatment with ELAHERE"},
            "PDL1": {"assay": "22C3", "status": "positive", "cps": 10, "note": "Combined positive score (CPS): PD-L1 positive tumor cells and infiltrating immune cells / total viable tumor cells × 100"},
            "NTRK": {"status": "negative"}
          },
          "additional_tests": [
            {
              "test_name": "Solid Tumor Gynecological Panel",
              "date_ordered": "2025-11-20",
              "date_signed_out": "2025-12-03",
              "status": "signed_out",
              "reference_case": "GP25-3371"
            },
            {
              "test_name": "Microsatellite Instability (MSI) Testing",
              "date_ordered": "2025-11-20",
              "date_signed_out": "2025-12-03",
              "status": "signed_out",
              "reference_case": "GP25-3371",
              "note": "Likely MSS (Mismatch Repair Stable) given preserved MMR protein expression"
            }
          ],
          "clinical_notes": "Case was reviewed by additional members of the department. Dr. June Hou was informed via CUMC email on 11/20/2025."
        }
      ]
    },
    "GENETIC_REPORTS": {
      "GERMLINE_TESTING": [
        {
          "report_id": "genetic-germline-001",
          "exam_type": "CancerNext-Expanded + RNAinsight",
          "lab": "Ambry Genetics",
          "specimen_type": "Blood EDTA",
          "accession_number": "25-743747",
          "report_date": "2025-11-24",
          "collection_date": "2025-01-04",
          "indication": "Family history",
          "genes_analyzed": 77,
          "result": "POSITIVE - Pathogenic mutations detected",
          "mutations": [
            {
              "gene": "MBD4",
              "variant": "c.1293delA",
              "protein_change": "p.K431Nfs*54",
              "zygosity": "homozygous",
              "classification": "pathogenic",
              "inheritance": "autosomal_recessive"
            },
            {
              "gene": "PDGFRA",
              "variant": "c.2263T>C",
              "protein_change": "p.S755P",
              "zygosity": "heterozygous",
              "classification": "VUS",
              "inheritance": "unknown"
            }
          ],
          "diagnosis": {
            "syndrome": "MBD4-associated neoplasia syndrome (MANS)",
            "risk_increases": [
              "Acute myelogenous leukemia (AML)",
              "Colorectal cancer (CRC)"
            ],
            "additional_risks": [
              "Gastrointestinal adenomatous polyposis",
              "Myelodysplastic syndrome (MDS)"
            ]
          },
          "note": "No additional pathogenic mutations, VUS, or gross deletions/duplications detected in 77 genes analyzed"
        }
      ]
    }
  },
  "synthesized_profile": {
    "disease": "ovarian_cancer_hgs",
    "stage": "IVB",
    "primary_site": "ovarian/peritoneal (Mullerian origin)",
    "histology": "high_grade_serous_carcinoma",
    "disease_extent": {
      "carcinomatosis": true,
      "ascites": true,
      "pleural_effusions": true,
      "pleural_metastases": true,
      "lymph_node_metastases": true,
      "distant_metastases": true
    },
    "biomarkers": {
      "p53": "mutant",
      "p16": "strong_and_diffuse",
      "ER": {"status": "weakly_positive", "percent": 50},
      "PR": {"status": "negative", "percent": "<1%"},
      "IHC_profile": "Mullerian origin (WT1+, PAX8+, CK7+, MOC31+, claudin4+)",
      "mismatch_repair": {
        "status": "preserved",
        "msi_status": "MSS",
        "markers": {
          "MLH1": "positive",
          "PMS2": "positive",
          "MSH2": "positive",
          "MSH6": "positive"
        }
      },
      "HER2": {"status": "negative", "score": 0},
      "FOLR1": {"status": "negative", "percent": "<1%", "note": "Requires ≥75% for ELAHERE eligibility"},
      "PDL1": {"assay": "22C3", "status": "positive", "cps": 10},
      "NTRK": {"status": "negative"}
    },
    "diagnostic_timeline": [
      {
        "date": "2024-02-01",
        "report_type": "CT_SCAN",
        "finding": "Baseline: Left ovarian cysts (5.2cm, 4.4cm), lower abdominal wall collection. NO CARCINOMATOSIS detected.",
        "stage": "baseline"
      },
      {
        "date": "2025-10-28",
        "report_type": "CT_SCAN",
        "finding": "PROGRESSION DETECTED: Extensive peritoneal carcinomatosis, small volume ascites, lymphadenopathy. Ovaries inseparable from peritoneal deposits.",
        "stage": "metastatic_detected"
      },
      {
        "date": "2025-11-11",
        "report_type": "PET_SCAN",
        "finding": "WIDESPREAD METASTASES: Extensive carcinomatosis with widespread metastases (SUV max 15.0), suspected gynecologic primary",
        "stage": "widespread_metastases"
      },
      {
        "date": "2025-11-17",
        "report_type": "PATHOLOGY_CYTOLOGY",
        "finding": "DIAGNOSIS CONFIRMED: POSITIVE FOR MALIGNANT CELLS - Metastatic adenocarcinoma, Mullerian primary (p53 mutant, ER weakly positive, PR negative). BILATERAL pleural metastases (right and left).",
        "stage": "diagnosis_confirmed",
        "specimens": ["Pleural fluid, right (CN25-5777)", "Pleural fluid, left (CN25-5778)"]
      },
      {
        "date": "2025-11-20",
        "report_type": "PATHOLOGY_SURGICAL",
        "finding": "TISSUE BIOPSIES CONFIRMED: Metastatic adenocarcinoma, Mullerian origin in all 4 specimens (omentum x2, endometrial curettings, perineal nodule). Strong WT-1 staining suggests high grade serous carcinoma of adnexal/primary peritoneal origin. Comprehensive biomarkers: PD-L1 positive (CPS=10), FOLR1 negative (<1%), MMR preserved (MSS), HER2 negative, NTRK negative.",
        "stage": "tissue_confirmed",
        "specimens": ["Omentum biopsy #1", "Endometrial curettings", "Anterior perineal nodule", "Omentum biopsy #2"],
        "report_number": "GP25-3371"
      },
      {
        "date": "2025-11-24",
        "report_type": "GENETIC_GERMLINE",
        "finding": "GERMLINE TESTING: POSITIVE - MBD4 homozygous pathogenic mutation (c.1293delA) detected. MBD4-associated neoplasia syndrome (MANS) diagnosed. Increased risk for AML and colorectal cancer. PDGFRA VUS also detected.",
        "stage": "germline_diagnosis"
      }
    ],
    "disease_progression": {
      "baseline": {
        "date": "2024-02-01",
        "finding": "Ovarian cysts present, no carcinomatosis",
        "time_from_baseline": "0 months"
      },
      "progression_detected": {
        "date": "2025-10-28",
        "finding": "Extensive carcinomatosis, ascites, lymphadenopathy",
        "time_from_baseline": "~22 months"
      },
      "widespread_metastases": {
        "date": "2025-11-11",
        "finding": "Widespread metastases (SUV max 15.0)",
        "time_from_baseline": "~23 months"
      },
      "diagnosis_confirmed": {
        "date": "2025-11-17",
        "finding": "Metastatic adenocarcinoma, Mullerian primary confirmed (cytology - bilateral pleural fluid)",
        "time_from_baseline": "~23 months"
      },
      "tissue_confirmed": {
        "date": "2025-11-20",
        "finding": "Tissue biopsies confirmed - All 4 specimens positive. Comprehensive biomarker panel: PD-L1 positive (CPS=10), MMR preserved, FOLR1 negative",
        "time_from_baseline": "~23 months"
      },
      "germline_diagnosis": {
        "date": "2025-11-24",
        "finding": "MBD4 homozygous pathogenic mutation (MANS) diagnosed",
        "time_from_baseline": "~23 months"
      }
    }
  }
}
```

---

## 🎯 **HIERARCHY STRUCTURE SUMMARY**

```
PATIENT PROFILE (patient_ak)
│
├── IMAGING_REPORTS
│   ├── CT_SCAN
│   │   ├── [CT Abdomen/Pelvis - 2024-02-01] BASELINE
│   │   │   └── Findings: Ovarian cysts (5.2cm, 4.4cm), NO carcinomatosis
│   │   └── [CT Abdomen/Pelvis - 2025-10-28] PROGRESSION
│   │       └── Findings: Carcinomatosis, ascites, lymphadenopathy
│   │
│   └── PET_SCAN
│       └── [PET-CT Whole Body - 2025-11-11]
│           └── Findings: Extensive metastases (SUV max 15.0), suspected gynecologic primary
│
├── PATHOLOGY_REPORTS
│   ├── CYTOPATHOLOGY
│   │   ├── [Pleural Fluid, RIGHT - 2025-11-17] (CN25-5777)
│   │   │   └── Diagnosis: Metastatic adenocarcinoma, Mullerian primary
│   │   │   └── IHC: p53 mutant, ER weakly positive, PR negative (complete workup)
│   │   └── [Pleural Fluid, LEFT - 2025-11-17] (CN25-5778)
│   │       └── Diagnosis: Metastatic adenocarcinoma (same cytomorphology as right)
│   │       └── Note: Bilateral pleural metastases confirmed
│   │
│   └── SURGICAL_PATHOLOGY
│       └── [Tissue Biopsies - 2025-11-20] (GP25-3371)
│           └── Specimens: Omentum x2, Endometrial curettings, Perineal nodule
│           └── Diagnosis: Metastatic adenocarcinoma, Mullerian origin (all parts)
│           └── Comprehensive Biomarkers: PD-L1+ (CPS=10), FOLR1- (<1%), MMR preserved (MSS), HER2-, NTRK-
│           └── Note: Strong WT-1 suggests high grade serous carcinoma, adnexal/primary peritoneal origin
│
├── GENETIC_REPORTS
│   └── GERMLINE_TESTING
│       └── [CancerNext-Expanded + RNAinsight - 2025-11-24] (Ambry Genetics)
│           └── Result: POSITIVE - MBD4 homozygous pathogenic (c.1293delA)
│           └── Diagnosis: MBD4-associated neoplasia syndrome (MANS)
│           └── Risk: Increased risk for AML and colorectal cancer
│
└── SYNTHESIZED_PROFILE
    ├── disease: ovarian_cancer_hgs (from pathology)
    ├── stage: IVB (from imaging)
    ├── primary_site: ovarian/peritoneal (confirmed by pathology)
    ├── biomarkers: {p53: mutant, ER: weakly_positive (50%), PR: negative, PD-L1+ (CPS=10), FOLR1- (<1%), MMR preserved (MSS), HER2-, NTRK-}
    ├── diagnostic_timeline: [Baseline CT → Progression CT → PET → Cytology → Surgical Biopsies → Genetic Testing]
    └── disease_progression: Baseline (2/2024) → Progression (10/2025) → Widespread (11/2025) → Cytology Confirmed (11/17) → Tissue Confirmed (11/20) → Genetic Diagnosis (11/24)
```
