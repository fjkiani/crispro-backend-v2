# 🔥 COMPREHENSIVE CLAIMS AUDIT REPORT

**Generated:** January 3, 2026  
**Purpose:** Verify all claims in pharma_integrated_development.mdc against actual receipts

---

## ✅ VALIDATED CLAIMS (5/6 checked)

| Claim | Document | Receipt | Status |
|-------|----------|---------|--------|
| Top-3 Accuracy | 100% | 1.0 | ✅ **VALIDATED** |
| MRR | 0.75 | 0.75 | ✅ **VALIDATED** |
| Toxicity Sensitivity | 100% (6/6) | 1.0 | ✅ **VALIDATED** |
| Toxicity Specificity | 100% (0 FP) | 1.0 | ✅ **VALIDATED** |
| Pathway Alignment | 100% (5/5 MAPK) | 1.0 | ✅ **VALIDATED** |
| Risk-Benefit Logic | 100% (15/15) | 100% | ✅ **VALIDATED** |

---

## ⚠️ HALLUCINATION FOUND (1/6)

### CPIC Concordance - **MISLEADING CLAIM**

**Document Claims:** "100% (N=59 cases)" (Line 134)

**Actual Receipt Data:**
- Total cases evaluated: **59 match: **10**
- Concordant cases: **10/10** (100%)
- Cases without CPIC data: **49**

**The Problem:**
The document claims "100% (N=59 cases)" which implies all 59 cases are 100% concordant. However:
- Only **10 cases** have CPIC guideline data available
- Those 10 cases are 100% concordant ✅
- But **49 cases** have no CPIC data (unknown variants or not in CPIC database)

**Correct Claim Should Be:**
"100% CPIC concordance (10/10 cases with CPIC data, out of 59 total cases)"

**Status:** ⚠️ **MISLEADING** - Not technically wrong, but implies 100% of 59 when it's actually 100% of 10

---

## 📋 RECOMMENDED FIXES

### Fix CPIC Concordance Claim

**Current (Line 134):**
```
| **Dosing Guidance** | CPIC concordance | **100%** (N=59 cases) | `cpic_concordance_report.json` |
```

**Should Be:**
```
| **Dosing Guidance** | CPIC concordance | **100%** (10/10 cases with CPIC data, 49 cases have no CPIC guideline) | `cpic_concordance_report.json` |
```

**Or More Honest:**
```
| **Dosing Guidance** | CPIC coe | **100%** (10/10 cases with CPIC data) | `cpic_concordance_report.json` |
| **Dosing Guidance** | CPIC coverage | **17%** (10/59 cases have CPIC guidelines) | `cpic_concordance_report.json` |
```

---

## 🎯 AUDIT SUMMARY

| Category | Count | Status |
|----------|-------|--------|
| ✅ Validated | 5 | All match receipts |
| ⚠️ Misleading | 1 | CPIC concordance claim |
| ❓ Not Checked | 3 | Mechanism fit DDR, Top-5 accuracy, Resistance prediction |

---

## ⚠️ NOTES

1. **CPIC Concordance:** The 100% is correct for cases with CPIC data, but the "N=59" is misleading
2. **Mechanism Fit DDR (0.983):** Need to check actual receipt structure
3. **Top-5 Accuracy (17/17):** Need to find benchmark receipt
4. **Resistance Prediction:** Need to check mapk_ov_platinum receipts

---

**Action Required:** Update CPIC concordance claim to be more accurate
