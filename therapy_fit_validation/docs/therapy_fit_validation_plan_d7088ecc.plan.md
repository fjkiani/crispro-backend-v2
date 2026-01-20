---
name: Therapy Fit Validation Plan
overview: Comprehensive validation plan for Therapy Fit (S/P/E Framework) that moves beyond claims to real-world validation across 7 pathways and 10+ cancer types, integrating pathway validation data requirements and insight chips validation.
todos:
  - id: data_acquisition_ovarian
    content: "Acquire additional ovarian cancer data: HRD scores, PARP inhibitor response, bevacizumab response for 469 existing patients"
    status: cancelled
  - id: therapy_fit_predictions_ovarian
    content: Run /api/efficacy/predict for all 469 ovarian cancer patients and extract predictions (efficacy_score, confidence, badges, insights, rationale)
    status: cancelled
    dependencies:
      - data_acquisition_ovarian
  - id: ddr_pathway_validation_ovarian
    content: "Validate DDR pathway: DDR-high patients → PARP inhibitors ranked #1-3 with ≥0.80 efficacy (target: 100% pathway alignment like MM)"
    status: cancelled
    dependencies:
      - therapy_fit_predictions_ovarian
  - id: mapk_pathway_validation_ovarian
    content: "Validate MAPK pathway: MAPK mutations → MEK inhibitors ranked high with PathwayAligned badge (target: match MM 100% alignment)"
    status: cancelled
    dependencies:
      - therapy_fit_predictions_ovarian
  - id: data_acquisition_breast
    content: "Download breast cancer data from cBioPortal: mutations, HER2 status, treatment response (trastuzumab, PARP, alpelisib)"
    status: cancelled
  - id: therapy_fit_predictions_breast
    content: Run /api/efficacy/predict for breast cancer patients and validate DDR (BRCA) → PARP, HER2 → trastuzumab, PI3K → alpelisib
    status: cancelled
    dependencies:
      - data_acquisition_breast
  - id: data_acquisition_melanoma
    content: "Download melanoma data from cBioPortal: mutations, BRAF status, TMB, treatment response (BRAF inhibitors, IO)"
    status: cancelled
  - id: mapk_pathway_validation_melanoma
    content: "Validate MAPK pathway in melanoma: BRAF V600E → BRAF inhibitor ranked #1 with ≥0.85 confidence (match MM validation)"
    status: cancelled
    dependencies:
      - data_acquisition_melanoma
  - id: insight_chips_validation
    content: "Validate insight chips: Compute chips for all patients, compare rankings with vs. without chips, validate threshold-based lifts"
    status: cancelled
    dependencies:
      - therapy_fit_predictions_ovarian
  - id: spe_component_ablation
    content: "Run S/P/E component ablation studies: S only, P only, E only, S+P, S+P+E to validate pathway component importance (40% weight)"
    status: cancelled
    dependencies:
      - therapy_fit_predictions_ovarian
  - id: statistical_analysis
    content: "Calculate validation metrics: pathway alignment accuracy, efficacy score correlation, confidence calibration (ECE), insight chips impact"
    status: cancelled
    dependencies:
      - ddr_pathway_validation_ovarian
      - mapk_pathway_validation_ovarian
      - insight_chips_validation
  - id: cross_cancer_validation
    content: Validate same pathway across different cancers (e.g., DDR in Ovarian vs. Breast) to ensure pathway weights are cancer-agnostic
    status: cancelled
    dependencies:
      - ddr_pathway_validation_ovarian
      - therapy_fit_predictions_breast
---

# Therapy Fit Validation Plan: From Claims to Real-World Validation

## Executive Summary

This plan validates the **Therapy Fit (S/P/E Framework)** system using real-world data across **7 pathways** and **10+ cancer types**. Instead of relying on claims, we will prove that:

1. **S/P/E Framework** accurately predicts drug efficacy (Sequence 30%, Pathway 40%, Evidence 30%)
2. **Insight Chips** (Functionality, Chromatin, Essentiality, Regulatory) provide meaningful confidence lifts
3. **Pathway alignment** (40% weight) correctly matches patients to mechanism-aligned drugs

**Current Status**: Production-ready with validated examples (Multiple Myeloma 100% pathway alignment, Ayesha MBD4+TP53), but needs systematic validation across all pathways and cancer types.---

## Part 1: S/P/E Framework Architecture (Current Understanding)

### Core Formula

```javascript
efficacy_score = 0.3 × Sequence + 0.4 × Pathway + 0.3 × Evidence + ClinVar_prior
```

**Components**:

- **Sequence (S)**: 30% - Evo2 adaptive multi-window scoring (4096, 8192, 16384, 25000 bp windows)
- **Pathway (P)**: 40% - Gene-to-pathway mapping (HIGHEST WEIGHT - mechanism alignment importance)
- **Evidence (E)**: 30% - Literature + ClinVar classification
- **ClinVar_prior**: Additive boost [-0.2, +0.2]

**Key Finding**: Pathway (P) component is **ESSENTIAL** — 100% accuracy with P, 40% without (validated ablation study).

### Insight Chips System

**Four Chips with Threshold-Based Lifts**:| Chip | Threshold | Lift (Legacy) | Lift (V2) | Purpose ||------|-----------|---------------|-----------|---------|| **Functionality** | ≥0.6 | +0.05 | +0.04 | Protein function change prediction || **Chromatin** | ≥0.5 | +0.03 | +0.04 | Regulatory impact assessment || **Essentiality** | ≥0.7 | +0.07 | +0.02 | Gene dependency scoring || **Regulatory** | ≥0.6 | +0.02 | +0.02 | Splicing and non-coding impact |**Total lifts capped at +0.08** (V2 only, proportionally scaled if exceeded).**Implementation**:

- Location: `api/services/confidence/insights_lifts.py`
- Chips computed via: `/api/insights/predict_protein_functionality_change`, `/api/insights/predict_chromatin_accessibility`, `/api/insights/predict_gene_essentiality`, `/api/insights/predict_splicing_regulatory`

---

## Part 2: Validation Strategy - The 7 Pathways

### The 7 Pathways We Must Validate

| Index | Pathway | Key Genes | Clinical Relevance | Therapy Fit Validation ||-------|---------|-----------|-------------------|----------------------|| 0 | **DDR** | BRCA1, BRCA2, ATM, ATR, PALB2, RAD51, CHEK2 | PARP inhibitors, platinum sensitivity | Validate: DDR-high → PARP inhibitors ranked #1-3 || 1 | **MAPK** | BRAF, KRAS, NRAS, NF1, MEK1/2 | BRAF/MEK inhibitors, resistance | Validate: BRAF V600E → BRAF inhibitor (0.85 confidence) || 2 | **PI3K** | PIK3CA, PTEN, AKT1, MTOR | PI3K inhibitors (alpelisib) | Validate: PIK3CA → alpelisib ranked high || 3 | **VEGF** | VEGFA, VHL, HIF1A, KDR | Anti-angiogenics (bevacizumab) | Validate: VHL → TKI ranked high || 4 | **HER2** | ERBB2/HER2, ERBB3 | Trastuzumab, T-DXd | Validate: HER2+ → trastuzumab ranked #1 || 5 | **IO** | CD274/PD-L1, TMB, MSI, POLE | Checkpoint inhibitors | Validate: TMB-high/MSI-H → IO ranked high || 6 | **Efflux** | ABCB1/MDR1, ABCC1, ABCG2 | Multi-drug resistance | Validate: MDR1 high → resistance prediction |---

## Part 3: Cancer Type Priorities for Validation

### TIER 1: CORE FOCUS (Gynecological) - P0

| Cancer | TCGA Code | Priority | Therapy Fit Validation Targets ||--------|-----------|----------|-------------------------------|| **Ovarian (HGSOC)** | TCGA-OV | P0 | ✅ Have 469 patients - Validate DDR → PARP, MAPK → MEK, VEGF → bevacizumab || **Endometrial** | TCGA-UCEC | P1 | Validate PI3K → alpelisib, MSI-H → IO || **Cervical** | TCGA-CESC | P1 | Validate IO → pembrolizumab |

### TIER 2: PATHWAY VALIDATION (High Signal) - P2

| Cancer | TCGA Code | Priority | Therapy Fit Validation Targets ||--------|-----------|----------|-------------------------------|| **Breast** | TCGA-BRCA | P2 | Validate DDR (BRCA) → PARP, HER2 → trastuzumab, PI3K → alpelisib || **Melanoma** | TCGA-SKCM | P2 | Validate MAPK (BRAF) → BRAF inhibitor, IO → checkpoint inhibitors || **Lung Adeno** | TCGA-LUAD | P2 | Validate MAPK (KRAS) → KRAS inhibitor, IO → checkpoint inhibitors || **Colorectal** | TCGA-COAD | P2 | Validate MAPK (KRAS/BRAF) → targeted therapy, MSI-H → IO |

### TIER 3: COMPLETE COVERAGE - P3

| Cancer | TCGA Code | Priority | Therapy Fit Validation Targets ||--------|-----------|----------|-------------------------------|| **Kidney Clear Cell** | TCGA-KIRC | P3 | Validate VEGF (VHL) → TKI || **Pancreatic** | TCGA-PAAD | P3 | Validate DDR, MAPK (KRAS) || **Prostate** | TCGA-PRAD | P3 | Validate DDR (BRCA2) || **Gastric** | TCGA-STAD | P3 | Validate HER2, MSI || **Bladder** | TCGA-BLCA | P3 | Validate IO (TMB) |---

## Part 4: Validation Matrix - What We Need to Prove

### S/P/E Framework Validation Goals

| Pathway | Validation Goal | Metric | Target | Therapy Fit Specific ||---------|----------------|--------|--------|---------------------|| **DDR** | BRCA → platinum/PARP response | Sensitivity rate difference | >10% | DDR-high patients: PARP inhibitors ranked #1-3 with ≥0.80 efficacy || **MAPK** | BRAF → BRAF-i response | ORR difference | >30% | BRAF V600E: BRAF inhibitor ranked #1 with ≥0.85 confidence || **MAPK** | KRAS → MEK-i response | Pathway alignment | 100% | KRAS G12D: MEK inhibitor ranked #1 with PathwayAligned badge || **PI3K** | PIK3CA → alpelisib response | PFS difference | >2 months | PIK3CA mutation: alpelisib ranked high with ≥0.70 efficacy || **VEGF** | VHL → TKI response | Response rate | >50% | VHL mutation: TKI ranked #1 with PathwayAligned badge || **HER2** | HER2+ → trastuzumab response | pCR rate | >40% | HER2 amplification: trastuzumab ranked #1 with Guideline badge || **IO** | TMB-high → IO response | ORR difference | >20% | TMB-high: Checkpoint inhibitor ranked high with IO pathway alignment || **IO** | MSI-H → IO response | ORR | >40% | MSI-H: Checkpoint inhibitor ranked #1 with PathwayAligned badge || **Efflux** | MDR1 high → resistance | Resistance rate | >2x baseline | MDR1 high: Lower efficacy scores for affected drugs |

### Insight Chips Validation Goals

| Chip | Validation Goal | Metric | Target ||------|----------------|--------|--------|| **Functionality** | High functionality → higher confidence | Confidence lift correlation | Functionality ≥0.6 → +0.05 lift improves ranking || **Chromatin** | High chromatin → higher confidence | Confidence lift correlation | Chromatin ≥0.5 → +0.04 lift improves ranking || **Essentiality** | High essentiality → higher confidence | Confidence lift correlation | Essentiality ≥0.7 → +0.07 lift improves ranking || **Regulatory** | High regulatory → higher confidence | Confidence lift correlation | Regulatory ≥0.6 → +0.02 lift improves ranking |**Validation Method**: Compare drug rankings with vs. without insight chips lifts. Chips should help differentiate drugs with similar S/P/E scores.---

## Part 5: Data Requirements Per Cancer Type

### For EACH cancer type, we need:

```yaml
cancer_type:
  tcga_code: "TCGA-XX"
  
  # REQUIRED: Mutation Data
  mutations:
    source: "cBioPortal or TCGA GDC"
    format: "MAF or JSON"
    fields:
            - patient_id
            - gene
            - hgvs_p (protein change)
            - hgvs_c (cDNA change)
            - variant_classification
            - chromosome
            - position
            - ref_allele
            - alt_allele
    min_patients: 100
    
  # REQUIRED: Treatment Response Data (CRITICAL FOR VALIDATION)
  treatment_response:
    source: "TCGA clinical, cBioPortal, or trial data"
    format: "JSON or TSV"
    fields:
            - patient_id
            - treatment_type (chemo, targeted, IO)
            - drug_name
            - response (CR, PR, SD, PD)
            - response_category (sensitive, resistant, refractory)
            - pfs_months (if available)
            - os_months (if available)
    min_patients_with_response: 50
    
  # REQUIRED: Therapy Fit Predictions
  therapy_fit_predictions:
    source: "Run /api/efficacy/predict for each patient"
    fields:
            - patient_id
            - drug_name
            - efficacy_score (0-1)
            - confidence (0-1)
            - evidence_tier (Supported/Consider/Insufficient)
            - badges[] (RCT, Guideline, ClinVar-Strong, PathwayAligned)
            - insights {functionality, chromatin, essentiality, regulatory}
            - rationale[] (S/P/E breakdown)
    validation: "Compare predicted rankings to actual response"
    
  # OPTIONAL: Biomarker Data
  biomarkers:
    fields:
            - hrd_score
            - tmb_score
            - msi_status
            - pd_l1_expression
    source: "TCGA or computed from mutations"
    
  # OPTIONAL: Copy Number Data
  copy_number:
    fields:
            - gene
            - cn_status (amplification, deletion, neutral)
            - log2_ratio
    source: "TCGA GISTIC or cBioPortal"
```

---

## Part 6: Specific Validation Tasks by Cancer Type

### 1. OVARIAN CANCER (TCGA-OV) - ✅ HAVE PARTIAL

**Current Status**: 469 patients with mutations + platinum response**What We Have**:

- ✅ Mutations for 469 patients
- ✅ Platinum response (sensitive/resistant/refractory)
- ❌ Missing: HRD scores
- ❌ Missing: PARP inhibitor response
- ❌ Missing: Bevacizumab response

**Therapy Fit Validation Tasks**:

1. **DDR Pathway Validation**:

- Run `/api/efficacy/predict` for all 469 patients
- Identify DDR-high patients (BRCA1/2, MBD4, TP53 mutations)
- Validate: PARP inhibitors (olaparib, niraparib, rucaparib) ranked #1-3 with ≥0.80 efficacy
- Compare predicted rankings to actual PARP response (if available)
- **Target**: 100% pathway alignment (like Multiple Myeloma validation)

2. **MAPK Pathway Validation**:

- Identify MAPK mutations (KRAS, NRAS, BRAF)
- Validate: MEK inhibitors ranked high with PathwayAligned badge
- **Target**: Match Multiple Myeloma 100% pathway alignment

3. **VEGF Pathway Validation**:

- Validate: Bevacizumab ranked high for VEGF pathway patients
- Compare to actual bevacizumab response

4. **Insight Chips Validation**:

- Compute chips for all patients
- Validate: Chips provide meaningful confidence lifts
- Compare rankings with vs. without chips

**Additional Data Needed**:

```yaml
ovarian_additional:
  hrd_scores:
    source: "TCGA HRD paper or Myriad-style computation"
    patients_needed: 469 (match existing)
    fields: [genomic_loh_score, tai_score, lst_score, hrd_sum]
    
  parp_response:
    source: "ARIEL trials, PRIMA trial, or real-world data"
    fields: [patient_id, parp_drug, response, pfs_months]
    min_patients: 50
    
  io_response:
    source: "KEYNOTE trials, IMagyn050"
    fields: [patient_id, io_drug, response, pfs_months]
    min_patients: 30
```



### 2. BREAST CANCER (TCGA-BRCA) - ⏸️ NEED

**Why Important**:

- Highest BRCA1/2 frequency (validate DDR pathway)
- HER2+ subset (validate HER2 pathway)
- PIK3CA common (validate PI3K pathway)

**Therapy Fit Validation Tasks**:

1. **DDR Pathway Validation**:

- BRCA1/2 mutations → Validate PARP inhibitors ranked #1-3
- Compare to actual PARP response (SOLO-1, SOLO-2 trials)

2. **HER2 Pathway Validation**:

- HER2 amplification → Validate trastuzumab ranked #1 with Guideline badge
- Compare to actual trastuzumab response (neoadjuvant pCR rates)

3. **PI3K Pathway Validation**:

- PIK3CA mutations → Validate alpelisib ranked high
- Compare to actual alpelisib response (SOLAR-1 trial)

**Data Needed**:

```yaml
breast:
  mutations:
    source: "cBioPortal TCGA-BRCA"
    expected_patients: 1000+
    key_genes: [BRCA1, BRCA2, PIK3CA, ERBB2, TP53, CDH1]
    
  subtypes:
    source: "TCGA PAM50"
    categories: [Luminal_A, Luminal_B, HER2_enriched, Basal, Normal]
    
  her2_status:
    source: "TCGA clinical"
    categories: [HER2+, HER2-]
    
  treatment_response:
    source: "I-SPY, CALGB, or cBioPortal clinical"
    treatments:
            - neoadjuvant_chemo (pCR yes/no)
            - trastuzumab (HER2+ response)
            - parp_inhibitor (BRCA+ response)
            - alpelisib (PIK3CA+ response)
```



### 3. MELANOMA (TCGA-SKCM) - ⏸️ NEED

**Why Important**:

- BRAF V600E 50% (validate MAPK pathway)
- IO standard of care (validate IO pathway)
- High TMB (validate IO pathway)

**Therapy Fit Validation Tasks**:

1. **MAPK Pathway Validation**:

- BRAF V600E → Validate BRAF inhibitor ranked #1 with ≥0.85 confidence
- Compare to actual BRAF inhibitor response (CheckMate, KEYNOTE trials)
- **Target**: Match Multiple Myeloma validation (KRAS G12D → MEK inhibitor, 0.85 confidence)

2. **IO Pathway Validation**:

- TMB-high → Validate checkpoint inhibitor ranked high
- Compare to actual IO response

**Data Needed**:

```yaml
melanoma:
  mutations:
    source: "cBioPortal TCGA-SKCM"
    expected_patients: 400+
    key_genes: [BRAF, NRAS, NF1, KIT, CDKN2A]
    
  braf_status:
    source: "TCGA or derived from mutations"
    categories: [V600E, V600K, other_BRAF, BRAF_WT]
    
  tmb_score:
    source: "Computed from mutations"
    threshold: 10 mut/Mb for TMB-high
    
  treatment_response:
    source: "CheckMate, KEYNOTE, coBRIM trials"
    treatments:
            - braf_inhibitor (vemurafenib, dabrafenib)
            - mek_inhibitor (trametinib, cobimetinib)
            - anti_pd1 (nivolumab, pembrolizumab)
            - anti_ctla4 (ipilimumab)
```

---

## Part 7: Validation Methodology

### Step 1: Data Acquisition

1. **Download mutation data** from cBioPortal for each cancer type
2. **Extract treatment response data** (hardest to find - prioritize this)
3. **Run Therapy Fit predictions** using `/api/efficacy/predict` for each patient
4. **Compute insight chips** for all patients
5. **Link predictions to outcomes** by patient_id

### Step 2: Pathway Validation

For each pathway × cancer type combination:

1. **Identify pathway-positive patients** (e.g., BRCA1/2 mutations for DDR)
2. **Run Therapy Fit predictions** for these patients
3. **Validate drug rankings**:

- Expected drug ranked #1-3? (e.g., PARP inhibitors for DDR-high)
- Efficacy score ≥0.80? (for high-confidence predictions)
- Confidence ≥0.85? (for supported tier)
- PathwayAligned badge present?

4. **Compare to actual response** (if available):

- Sensitivity rate difference >10%?
- ORR difference >20%?
- PFS difference >2 months?

### Step 3: Insight Chips Validation

1. **Compute chips** for all patients
2. **Compare rankings**:

- With chips (full confidence computation)
- Without chips (base confidence only)

3. **Validate lifts**:

- Functionality ≥0.6 → +0.05 lift improves ranking?
- Chromatin ≥0.5 → +0.04 lift improves ranking?
- Essentiality ≥0.7 → +0.07 lift improves ranking?
- Regulatory ≥0.6 → +0.02 lift improves ranking?

4. **Statistical validation**:

- Correlation between chip scores and confidence lifts
- Impact on drug ranking accuracy

### Step 4: S/P/E Component Validation

1. **Ablation studies**:

- S only (30% weight)
- P only (40% weight)
- E only (30% weight)
- S+P (70% weight)
- S+P+E (100% weight)

2. **Validate pathway component importance**:

- 100% accuracy with P (like Multiple Myeloma)
- 40% accuracy without P (from ablation study)

3. **Validate weights**:

- 30%/40%/30% optimal?
- Test alternative weights (e.g., 35%/35%/30%)

---

## Part 8: Minimum Viable Dataset

### To claim pathway validation, we need:

```yaml
minimum_requirements:
  patients_per_group: 30  # Min 30 in each arm
  
  for_therapy_fit_validation:
        - pathway_positive_patients: 30+ patients
        - pathway_negative_patients: 30+ patients (control)
        - therapy_fit_predictions: Complete (efficacy_score, confidence, badges)
        - treatment_response: binary (responder/non-responder) or continuous (PFS)
    
  for_insight_chips_validation:
        - patients_with_chips: 100+ patients
        - chip_scores: Complete (functionality, chromatin, essentiality, regulatory)
        - confidence_comparison: With vs. without chips
    
  statistical_threshold:
        - p_value: <0.05
        - relative_risk: >1.5 or <0.67
        - confidence_interval: 95%
        - pathway_alignment_accuracy: ≥90% (like Multiple Myeloma 100%)
```

---

## Part 9: Success Criteria

### Phase 1: Gynecological Cancers (2 weeks)

- [ ] **Ovarian**: DDR → PARP validated (100% pathway alignment like MM)
- [ ] **Ovarian**: MAPK → MEK validated
- [ ] **Ovarian**: VEGF → bevacizumab validated
- [ ] **Endometrial**: PI3K → alpelisib validated
- [ ] **Endometrial**: MSI-H → IO validated
- [ ] **Cervical**: IO → pembrolizumab validated

### Phase 2: High-Signal Cancers (2 weeks)

- [ ] **Breast**: DDR (BRCA) → PARP validated
- [ ] **Breast**: HER2 → trastuzumab validated
- [ ] **Breast**: PI3K → alpelisib validated
- [ ] **Melanoma**: MAPK (BRAF) → BRAF inhibitor validated (match MM 0.85 confidence)
- [ ] **Melanoma**: IO → checkpoint inhibitor validated
- [ ] **Lung**: MAPK (KRAS) → KRAS inhibitor validated
- [ ] **Lung**: IO → checkpoint inhibitor validated

### Phase 3: Complete Coverage (2 weeks)

- [ ] All 7 pathways validated in at least 2 cancer types each
- [ ] Cross-cancer validation (same pathway, different cancers)
- [ ] Insight chips validated across all pathways
- [ ] S/P/E component ablation studies complete

### Final Deliverable

- **Validation matrix**: 7 pathways × 10+ cancer types
- **Real metrics** (not synthetic):
- Pathway alignment accuracy (target: ≥90%, like MM 100%)
- Efficacy score correlation with actual response
- Confidence score calibration (ECE <0.3 target)
- Insight chips impact on ranking accuracy
- **Production-ready pathway weights** per cancer type
- **Validated insight chip thresholds** (current: Functionality ≥0.6, Chromatin ≥0.5, Essentiality ≥0.7, Regulatory ≥0.6)

---

## Part 10: Data Sources

### Primary Sources (Free, Public)

| Source | URL | Data Type | Use Case ||--------|-----|-----------|----------|| **cBioPortal** | https://www.cbioportal.org/ | Mutations, clinical, CNA | Primary source for mutation + clinical data || **GDC Data Portal** | https://portal.gdc.cancer.gov/ | TCGA raw data | Backup source for mutations || **ICGC** | https://dcc.icgc.org/ | International cancer genomes | Additional validation data || **EGA** | https://ega-archive.org/ | European trial data | Treatment response data |

### Trial Data Sources (For Treatment Response)

| Trial | Cancer | Pathway | Data Availability | Therapy Fit Validation ||-------|--------|---------|-------------------|----------------------|| ARIEL2/3 | Ovarian | DDR | Request from Clovis | Validate PARP inhibitor rankings || PRIMA | Ovarian | DDR | Request from GSK | Validate PARP inhibitor rankings || SOLAR-1 | Breast | PI3K | cBioPortal | Validate alpelisib rankings || BOLERO-2 | Breast | PI3K | cBioPortal | Validate PI3K inhibitor rankings || CheckMate-067 | Melanoma | IO | Request from BMS | Validate checkpoint inhibitor rankings || KEYNOTE-006 | Melanoma | IO | Request from Merck | Validate checkpoint inhibitor rankings || CheckMate-227 | Lung | IO | Request from BMS | Validate checkpoint inhibitor rankings || KEYNOTE-177 | Colorectal | IO | Request from Merck | Validate MSI-H → IO rankings |---

## Part 11: Implementation Tasks

### Data Acquisition Tasks

1. **Download cBioPortal datasets** for each cancer type (Ovarian, Breast, Melanoma, Lung, Colorectal, etc.)
2. **Extract treatment response data** (highest priority - hardest to find)
3. **Compute derived biomarkers** (HRD, TMB, MSI) from mutations
4. **Link mutations to outcomes** by patient_id

### Therapy Fit Prediction Tasks

1. **Run `/api/efficacy/predict`** for all patients in each cancer type
2. **Extract predictions**:

- Drug rankings (efficacy_score, confidence)
- Evidence tiers (Supported/Consider/Insufficient)
- Badges (RCT, Guideline, ClinVar-Strong, PathwayAligned)
- Insight chips (functionality, chromatin, essentiality, regulatory)
- S/P/E breakdown (rationale)

3. **Store predictions** in standardized JSON format

### Validation Tasks

1. **Pathway validation**:

- Identify pathway-positive patients
- Validate expected drugs ranked #1-3
- Calculate pathway alignment accuracy (target: ≥90%)
- Compare to actual response (if available)

2. **Insight chips validation**:

- Compute chips for all patients
- Compare rankings with vs. without chips
- Validate threshold-based lifts
- Calculate impact on ranking accuracy

3. **S/P/E component validation**:

- Run ablation studies (S only, P only, E only, S+P, S+P+E)
- Validate pathway component importance (40% weight)
- Test alternative weights

### Statistical Analysis Tasks

1. **Calculate metrics**:

- Pathway alignment accuracy
- Efficacy score correlation with response
- Confidence score calibration (ECE)
- Insight chips impact on ranking

2. **Statistical tests**:

- Relative risk (RR >1.5 or <0.67)
- Sensitivity/specificity
- AUC (area under ROC curve)
- P-value (<0.05)

---

## Part 12: Standard Output Format

### Therapy Fit Validation Results

```json
{
  "cancer_type": "TCGA-OV",
  "pathway": "DDR",
  "validation_date": "2025-01-28",
  "patients": {
    "pathway_positive": 150,
    "pathway_negative": 319,
    "total": 469
  },
  "therapy_fit_predictions": {
    "pathway_positive_patients": [
      {
        "patient_id": "TCGA-XX-XXXX",
        "mutations": ["BRCA1 p.E1685*"],
        "predicted_drugs": [
          {
            "drug_name": "Olaparib",
            "efficacy_score": 0.85,
            "confidence": 0.88,
            "evidence_tier": "supported",
            "badges": ["PathwayAligned", "ClinVar-Strong"],
            "insights": {
              "functionality": 0.65,
              "chromatin": 0.58,
              "essentiality": 0.42,
              "regulatory": 0.15
            },
            "rank": 1
          }
        ],
        "actual_response": {
          "treatment": "olaparib",
          "response": "sensitive",
          "pfs_months": 18.5
        }
      }
    ]
  },
  "validation_metrics": {
    "pathway_alignment_accuracy": 0.95,
    "top_3_accuracy": 0.92,
    "efficacy_score_correlation": 0.78,
    "confidence_calibration_ece": 0.32,
    "insight_chips_impact": 0.15
  },
  "statistical_tests": {
    "relative_risk": 2.1,
    "p_value": 0.003,
    "sensitivity": 0.88,
    "specificity": 0.76,
    "auc": 0.82
  }
}
```

---

## Summary

This validation plan moves Therapy Fit from **claims to real-world validation** by:

1. **Systematic validation** across 7 pathways and 10+ cancer types
2. **Real-world data** from cBioPortal, TCGA, and clinical trials