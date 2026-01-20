# Multi-Modal Platinum Resistance Detection: Validation Protocol
## IRB-Ready Protocol for External Collaborators

**Version:** 1.0  
**Date:** December 26, 2024  
**Principal Investigator:** Fahad Kiani, CrisPRO.ai  
**Contact:** Fahad@CrisPRO.ai

---

## 1. STUDY OBJECTIVE

### 1.1 Primary Objective

To validate a **multi-modal resistance detection model** combining:
- **MAPK genetics** (baseline genetic signal)
- **KELIM kinetics** (on-therapy adaptive signal)

**Hypothesis:** Multi-modal (MAPK + KELIM) will outperform either signal alone in predicting platinum resistance in ovarian cancer.

**Target Performance:**
- MAPK only: AUROC ~0.60 (baseline, validated)
- KELIM only: AUROC ~0.60-0.65 (literature)
- **MAPK + KELIM:** AUROC 0.65-0.75 (hypothesis, needs validation)

### 1.2 Secondary Objectives

1. **Lead Time Analysis:** Quantify weeks earlier than standard imaging (week 12-18)
2. **Risk Stratification:** Validate 2×2 matrix (MAPK × KELIM) for clinical decision-making
3. **Cost-Effectiveness:** Estimate cost savings from early detection ($10K-$40K per patient)

---

## 2. ENDPOINT DEFINITION

### 2.1 Primary Endpoint

**Platinum Resistance:** Platinum-Free Interval (PFI) < 6 months

**Definition:**
- **Platinum-RESISTANT:** Progression < 6 months after last platinum dose
- **Platinum-SENSITIVE:** Progression ≥ 6 months after last platinum dose

**Rationale:**
- Standard clinical definition (NCCN, ASCO, ESMO guidelines)
- Binary endpoint (resistant vs. sensitive)
- Available in most cohorts (treatment history + outcomes)

### 2.2 Secondary Endpoints

1. **Progression-Free Survival (PFS):** Time from treatment start to progression
2. **Overall Survival (OS):** Time from treatment start to death
3. **Lead Time:** Weeks earlier detection vs. standard imaging (week 12-18)

---

## 3. INPUT CONTRACT

### 3.1 Required Data

**1. Mutations (Baseline Genetic Signal)**
- Format: VCF/MAF file, or gene-level status list
- Required genes: MAPK pathway (BRAF, KRAS, NRAS, NF1)
- Minimum: Binary status (mutated vs. wild-type) per gene
- Ideal: Full mutation list with variant details

**2. Serial CA-125 (On-Therapy Adaptive Signal)**
- Format: `[{date, value}, ...]` (JSON array)
- Minimum: ≥3 measurements within 100 days of chemotherapy start
- Ideal: 4-6 measurements, evenly spaced
- Required fields:
  - Date: Chemotherapy start date
  - CA-125 measurements: Date + value pairs
  - Time calculation: Days from chemo start to each measurement

**3. Outcomes (Gold Standard Labels)**
- Platinum-Free Interval (PFI): Days from last platinum dose to progression
- Resistance label: Binary (resistant if PFI < 6 months, sensitive if ≥ 6 months)
- Progression date: Date of disease progression (if available)
- Death date: Date of death (if available, for OS analysis)

### 3.2 Optional Data

- Treatment dates: Chemotherapy start, last platinum dose, progression
- Additional biomarkers: HRD score, expression data, CNV/cytogenetics
- Patient demographics: Age, stage, histology (for stratification)
- Imaging dates: First imaging showing progression (for lead time analysis)

### 3.3 Data Quality Requirements

- **Completeness:** ≥80% of patients must have all required fields
- **Temporal alignment:** CA-125 dates must align with chemotherapy timeline
- **Outcome availability:** ≥90% of patients must have PFI/resistance labels

---

## 4. OUTPUT CONTRACT

### 4.1 Risk Score

**Platinum Resistance Risk:** 0-1 (probability)
- Interpretation: Probability of PFI < 6 months
- Calibration: Expected Calibration Error (ECE) < 0.10

**Risk Category:**
- LOW: Risk < 0.33
- MODERATE: Risk 0.33-0.67
- HIGH: Risk > 0.67

**Confidence:** 0-1 (based on input completeness)
- L0 (no NGS): Cap at 0.4
- L1 (partial): Cap at 0.6
- L2 (full): Cap at 0.8

### 4.2 Mechanisms

**MAPK Status:**
- Mutated: Any MAPK pathway mutation (BRAF, KRAS, NRAS, NF1)
- Wild-type: No MAPK pathway mutations

**KELIM Class:**
- Favorable: K ≥ 0.05/day
- Unfavorable: K < 0.05/day

**Combined Risk:**
- Multi-modal score: Logistic regression (MAPK + KELIM + interaction)

### 4.3 Actions

**Monitoring Plan:**
- CA-125 frequency: q3weeks (if baseline available)
- Imaging trigger: Week 9 (if KELIM unfavorable + MAPK+)

**Treatment Considerations:**
- Continue platinum: If MAPK WT + KELIM favorable
- Switch therapy: If MAPK+ OR KELIM unfavorable

**Data Gaps:**
- Missing inputs flagged (e.g., "CA-125 baseline missing")

---

## 5. VALIDATION METRICS

### 5.1 Primary Metrics

**AUROC (Area Under ROC Curve):**
- Target: 0.65-0.75 (multi-modal)
- Comparison: vs. MAPK only (0.60) and KELIM only (~0.62)
- 95% Confidence Intervals: Bootstrap method (n=1000 iterations)

**Sensitivity / Specificity:**
- Target: ≥80% sensitivity (detect most resistant patients)
- Target: ≥70% specificity (minimize false positives)
- Threshold: Optimize for clinical decision-making

**Calibration:**
- Expected Calibration Error (ECE): < 0.10
- Brier Score: < 0.20
- Calibration plot: Predicted vs. observed risk

### 5.2 Secondary Metrics

**Lead Time Analysis:**
- Average weeks earlier: KELIM at week 6-9 vs. imaging at week 12-18
- Target: 3-6 weeks advantage
- Distribution: Histogram of lead time across patients

**Risk Stratification:**
- 2×2 Matrix: MAPK (WT/Mut) × KELIM (Fav/Unfav)
- Resistance rates: Per quadrant
- Clinical decision thresholds: Optimize for ≥80% sensitivity

**Cost-Effectiveness:**
- Cost savings: $10K-$40K per patient (2-4 fewer cycles)
- Payer perspective: ROI calculation

---

## 6. STATISTICAL ANALYSIS PLAN

### 6.1 Model Comparison

**Models to Test:**
1. **MAPK only:** Logistic regression (resistance ~ MAPK)
2. **KELIM only:** Logistic regression (resistance ~ KELIM)
3. **MAPK + KELIM:** Logistic regression (resistance ~ MAPK + KELIM + MAPK×KELIM)

**Comparison Method:**
- DeLong test: Compare AUROC between models
- Target: Multi-modal significantly better (p < 0.05)
- Sample size: n≥50 per site (ideally n≥100)

### 6.2 Validation Strategy

**External Validation:**
- Train on: TCGA-OV (MAPK) + published KELIM cohorts
- Validate on: External collaborator cohorts (n≥50 per site)
- Multi-site: Meta-analysis of combined results

**Cross-Validation:**
- 5-fold cross-validation: Within each site
- Stratified: Ensure balanced resistant/sensitive distribution

### 6.3 Confound Checks

**Coverage/Variant Count:**
- Ensure MAPK mutations not confounded by sequencing depth
- Check: Variant count vs. MAPK status (should be independent)

**CA-125 Timing:**
- Ensure KELIM not confounded by measurement timing
- Check: Measurement frequency vs. KELIM score (should be independent)

**Patient Characteristics:**
- Stratify by: Age, stage, histology
- Check: Model performance consistent across subgroups

---

## 7. TIMELINE

### 7.1 Per Site

**Phase 1: Data Acquisition (2-4 weeks)**
- Week 1-2: IRB approval (if required)
- Week 2-3: Data extraction (mutations, CA-125, outcomes)
- Week 3-4: Data quality checks, cleaning

**Phase 2: Analysis (2-4 weeks)**
- Week 4-5: KELIM calculation, MAPK status determination
- Week 5-6: Model training, validation
- Week 6-7: Statistical analysis, metrics calculation

**Phase 3: Paper Writing (4-6 weeks)**
- Week 7-9: Results section, figures, tables
- Week 9-11: Methods, introduction, discussion
- Week 11-12: Review, revision, submission

**Total: 8-14 weeks per site**

### 7.2 Multi-Site

**Parallel Execution:**
- Sites run in parallel (not sequential)
- Meta-analysis: Combine results after individual site completion
- Timeline: 12-18 weeks to publication-ready

---

## 8. IRB CONSIDERATIONS

### 8.1 Data Requirements

**De-Identified Data Only:**
- No patient identifiers (name, DOB, MRN)
- No dates that could identify patients (use relative dates)
- Secure transfer: Encrypted, HIPAA-compliant (if US data)

**Data Use Agreement:**
- Academic research only
- No commercial use without consent
- Data destruction: After analysis complete (or as specified)

### 8.2 IRB Status

**Retrospective Analysis:**
- Existing data (no new patient contact)
- Minimal risk (no intervention)
- May qualify for IRB exemption (site-dependent)

**Site-Specific:**
- Each site handles their own IRB
- We provide protocol template (this document)
- Site adapts as needed for local requirements

---

## 9. DATA SHARING AGREEMENT

### 9.1 What We Receive

**De-Identified Patient Data:**
- Mutations (MAPK pathway status)
- Serial CA-125 (≥3 timepoints)
- Outcomes (PFI, resistance labels)

**Format:**
- CSV or JSON (preferred)
- Secure transfer: Encrypted email or secure portal

### 9.2 What We Provide

**Analysis Results:**
- Risk scores per patient
- Model performance metrics
- Statistical analysis results

**Code & Methods:**
- All code open-source (GitHub)
- All methods documented
- Reproducible analysis pipeline

### 9.3 Co-Authorship

**Guaranteed Co-Authorship:**
- Even if multi-modal fails (negative results published)
- Authorship order: Negotiable (likely: Fahad first, site contributors)
- Publication: Open-access (we cover costs)

---

## 10. SUCCESS CRITERIA

### 10.1 Primary Success

**Multi-Modal AUROC:**
- Target: ≥0.65 (vs. 0.60 baseline)
- Success: ≥0.70 (vs. 0.60 baseline)
- Stretch: ≥0.75 (vs. 0.60 baseline)

**Statistical Significance:**
- p < 0.05 (multi-modal vs. single modality)
- 95% CI: Non-overlapping with baseline

### 10.2 Secondary Success

**Lead Time:**
- Target: ≥3 weeks earlier than imaging
- Success: ≥4 weeks earlier
- Stretch: ≥6 weeks earlier

**Clinical Utility:**
- Risk stratification: Clear separation (2×2 matrix)
- Sensitivity: ≥80% (detect most resistant patients)
- Specificity: ≥70% (minimize false positives)

---

## 11. RISK MITIGATION

### 11.1 If Multi-Modal Fails

**Negative Results Published:**
- Co-authorship still guaranteed
- Learnings documented
- Future directions identified

### 11.2 If Data Quality Issues

**Data Cleaning:**
- Missing data: Imputation or exclusion (documented)
- Outliers: Robust methods or exclusion (documented)
- Quality thresholds: ≥80% completeness required

### 11.3 If Sample Size Insufficient

**Multi-Site Collaboration:**
- Combine cohorts across sites
- Meta-analysis: Pooled results
- Minimum: n≥50 per site, n≥200 total

---

## 12. CONTACT & NEXT STEPS

### 12.1 Contact Information

**Principal Investigator:**
- Fahad Kiani
- CrisPRO.ai
- 📧 Fahad@CrisPRO.ai
- 📱 [PHONE NUMBER]

### 12.2 Next Steps

1. **Review this protocol** (IRB-ready template)
2. **Contact:** Fahad@CrisPRO.ai to discuss collaboration
3. **Schedule brief call** to discuss:
   - Data availability
   - IRB requirements
   - Timeline
   - Co-authorship terms
4. **Begin data sharing** (4-6 weeks per site)

---

## APPENDIX: KELIM CALCULATION METHOD

### A.1 Formula

**KELIM Score Calculation:**
- Input: ≥3 CA-125 measurements within 100 days of chemotherapy start
- Method: Exponential fit to log(CA125) ~ -K × time_days + baseline
- Extract: K value per patient → KELIM score
- Threshold: K ≥ 0.05/day = favorable, < 0.05/day = unfavorable

### A.2 Implementation

**Code:**
- Python implementation available (open-source)
- R implementation available (Colomban group)
- Excel calculator available (Colomban group website)

**Validation:**
- Matches published KELIM calculations (ICON-7, GOG-0218, etc.)
- Cross-validated with Colomban group (if collaboration established)

---

**END OF VALIDATION PROTOCOL**

**Version:** 1.0  
**Date:** December 26, 2024  
**Status:** IRB-ready template for external collaborators































