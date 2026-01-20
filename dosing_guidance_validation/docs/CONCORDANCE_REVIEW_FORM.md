# Clinical Concordance Review Form

**Purpose:** Compare AI Dosing Guidance recommendations against expert clinical decisions  
**Reviewer:** ________________________________ (Oncologist/Pharmacologist)  
**Date:** ________________________________  
**Review Time:** Approximately 30-45 minutes

---

## Instructions

For each case below, please:
1. Review the patient scenario and variant information
2. Review our system's recommendation
3. Indicate what YOU would recommend in clinical practice
4. Mark whether our recommendation matches, is more conservative, or less conservative

**Concordance Legend:**
- ✅ **MATCH** - Our recommendation aligns with your clinical judgment
- 🔼 **MORE CONSERVATIVE** - Our system is more cautious (acceptable)
- 🔽 **LESS CONSERVATIVE** - Our system is less cautious (CONCERNING)
- ❌ **DISAGREE** - Recommendation is clinically inappropriate

---

## Case Reviews

### Case 1: DPYD c.2846A>T + Capecitabine

| Field | Value |
|-------|-------|
| **Patient** | 58F, Colorectal Adenocarcinoma, Stage III |
| **Gene/Variant** | DPYD c.2846A>T (heterozygous) |
| **Drug** | Capecitabine |
| **Standard Dose** | 1250 mg/m² BID, days 1-14 q21d |
| **Documented Outcome** | Grade 4 neutropenia, hospitalization required |

**Our System Recommendation:**
```
Phenotype: Intermediate Metabolizer
Risk Level: HIGH
Dose Adjustment: 50% reduction
Specific Dose: 625 mg/m² BID
Alternative: Consider tegafur-gimeracil-oteracil or raltitrexed
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Would you dose reduce? | □ Yes □ No |
| If yes, by how much? | ___% reduction |
| Specific dose you'd use: | ___ mg/m² |
| Would you use alternative drug? | □ Yes □ No → Which? _______ |

**Concordance Assessment:**
```
□ ✅ MATCH - 50% reduction appropriate
□ 🔼 MORE CONSERVATIVE - 50% is cautious but acceptable
□ 🔽 LESS CONSERVATIVE - Should be higher reduction
□ ❌ DISAGREE - Explain: ________________________________
```

---

### Case 2: DPYD *2A Homozygous + 5-FU

| Field | Value |
|-------|-------|
| **Patient** | 62M, Gastric Cancer, Stage IV |
| **Gene/Variant** | DPYD c.1905+1G>A (*2A/*2A) - Homozygous |
| **Drug** | 5-Fluorouracil (FOLFOX regimen) |
| **Standard Dose** | 400 mg/m² bolus + 2400 mg/m² CI |
| **Documented Outcome** | Fatal toxicity (case report from literature) |

**Our System Recommendation:**
```
Phenotype: Poor Metabolizer (Complete DPD Deficiency)
Risk Level: CRITICAL
Dose Adjustment: AVOID - Contraindicated
Alternative: Raltitrexed, oxaliplatin + irinotecan (with UGT1A1 testing)
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Would you give 5-FU? | □ Yes (with modification) □ Absolute No |
| If giving, what dose? | ___% of standard |
| Alternative regimen: | ________________________________ |

**Concordance Assessment:**
```
□ ✅ MATCH - AVOID is correct
□ 🔼 MORE CONSERVATIVE - Unnecessary, could try reduced dose
□ ❌ DISAGREE - Explain: ________________________________
```

---

### Case 3: DPYD Heterozygous *2A + Capecitabine

| Field | Value |
|-------|-------|
| **Patient** | 55F, Breast Cancer, Stage II (adjuvant) |
| **Gene/Variant** | DPYD c.1905+1G>A (*1/*2A) - Heterozygous |
| **Drug** | Capecitabine (Xeloda) |
| **Standard Dose** | 1000 mg/m² BID |
| **Documented Outcome** | Grade 3 diarrhea, mucositis (hospitalized) |

**Our System Recommendation:**
```
Phenotype: Intermediate Metabolizer
Risk Level: HIGH
Dose Adjustment: 50% reduction
Specific Dose: 500 mg/m² BID
Alternative: None required if dose-reduced
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Would you dose reduce? | □ Yes □ No |
| Reduction percentage: | ___% |
| Would you start with test dose? | □ Yes □ No |

**Concordance Assessment:**
```
□ ✅ MATCH
□ 🔼 MORE CONSERVATIVE
□ 🔽 LESS CONSERVATIVE
□ ❌ DISAGREE - Explain: ________________________________
```

---

### Case 4: TPMT *3A Heterozygous + 6-MP

| Field | Value |
|-------|-------|
| **Patient** | 12M, Acute Lymphoblastic Leukemia (ALL) |
| **Gene/Variant** | TPMT *1/*3A (Heterozygous) |
| **Drug** | 6-Mercaptopurine (Maintenance) |
| **Standard Dose** | 75 mg/m²/day |
| **Documented Outcome** | Severe myelosuppression at standard dose |

**Our System Recommendation:**
```
Phenotype: Intermediate Metabolizer
Risk Level: MODERATE
Dose Adjustment: 50% reduction
Specific Dose: 37.5 mg/m²/day
Alternative: Consider therapeutic drug monitoring (TDM)
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Starting dose: | ___% of standard |
| Would you use TDM? | □ Yes □ No |
| Escalation strategy: | ________________________________ |

**Concordance Assessment:**
```
□ ✅ MATCH - 50% starting dose appropriate
□ 🔼 MORE CONSERVATIVE - Could start at 30%
□ 🔽 LESS CONSERVATIVE - Should start lower
□ ❌ DISAGREE - Explain: ________________________________
```

---

### Case 5: UGT1A1 *28/*28 + Irinotecan

| Field | Value |
|-------|-------|
| **Patient** | 67M, Colorectal Cancer, Stage IV |
| **Gene/Variant** | UGT1A1 *28/*28 (Homozygous) |
| **Drug** | Irinotecan (FOLFIRI regimen) |
| **Standard Dose** | 180 mg/m² q2w |
| **Documented Outcome** | Grade 3-4 diarrhea and neutropenia |

**Our System Recommendation:**
```
Phenotype: Poor Metabolizer
Risk Level: HIGH
Dose Adjustment: 50% reduction (first cycle)
Specific Dose: 90 mg/m²
Alternative: Escalate based on tolerance
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Starting dose: | ___ mg/m² |
| Escalation plan: | ________________________________ |
| Would you use prophylactic G-CSF? | □ Yes □ No |

**Concordance Assessment:**
```
□ ✅ MATCH
□ 🔼 MORE CONSERVATIVE
□ 🔽 LESS CONSERVATIVE
□ ❌ DISAGREE - Explain: ________________________________
```

---

### Case 6: No Variants Detected

| Field | Value |
|-------|-------|
| **Patient** | 45F, Colorectal Cancer, Stage III |
| **Gene/Variant** | DPYD: No variants detected (*1/*1 assumed) |
| **Drug** | FOLFOX (5-FU component) |
| **Standard Dose** | Full standard dose |
| **Documented Outcome** | Tolerated well, no significant toxicity |

**Our System Recommendation:**
```
Phenotype: Normal Metabolizer
Risk Level: LOW
Dose Adjustment: None (100% standard dose)
Note: Standard monitoring recommended
```

**Your Clinical Recommendation:**

| Question | Your Response |
|----------|---------------|
| Agree with full dose? | □ Yes □ No |
| Would you add any precautions? | ________________________________ |

**Concordance Assessment:**
```
□ ✅ MATCH
□ ❌ DISAGREE - Explain: ________________________________
```

---

## Summary Scoring

### Concordance Tally

| Rating | Count | Percentage |
|--------|-------|------------|
| ✅ MATCH | ___ / 6 | ___% |
| 🔼 MORE CONSERVATIVE | ___ / 6 | ___% |
| 🔽 LESS CONSERVATIVE | ___ / 6 | ___% |
| ❌ DISAGREE | ___ / 6 | ___% |

### Overall Assessment

**Total Concordance Rate:** ___% (MATCH + MORE CONSERVATIVE)

**Acceptability Threshold:**
- ≥75% Concordance → **ACCEPTABLE for clinical use**
- 50-74% Concordance → **MODIFICATIONS REQUIRED**
- <50% Concordance → **MAJOR REVISION NEEDED**

---

## Reviewer Comments

### What we did well:
```
[Reviewer comments here]
```

### What needs improvement:
```
[Reviewer comments here]
```

### Specific recommendations:
```
[Reviewer comments here]
```

---

## Reviewer Attestation

I have reviewed the AI Dosing Guidance system recommendations for the cases presented and provided my clinical assessment.

**Signature:** ________________________________

**Name:** ________________________________

**Credentials:** ________________________________

**Institution:** ________________________________

**Date:** ________________________________

---

*Thank you for your expert review. Your input is critical to ensuring patient safety.*

