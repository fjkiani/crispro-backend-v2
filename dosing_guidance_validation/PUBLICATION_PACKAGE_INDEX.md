# PGx Dosing Guidance Publication Package

**Status:** 85% Ready for Submission  
**Last Updated:** January 3, 2026  
**Target Journal:** Clinical Pharmacology & Therapeutics

---

## Package Contents

### Core Manuscript

| Document | Description | Status |
|----------|-------------|--------|
| `docs/PUBLICATION_MANUSCRIPT_DRAFT.md` | Full manuscript draft (IMRaD format) | Ready for co-author review |
| `docs/VALIDATION_SUMMARY_FIGURES.md` | Figures 1-4, Tables 1-4, Supplementary | Publication-ready |

### Validation Evidence

| Document | Description | Status |
|----------|-------------|--------|
| `reports/CPIC_CONCORDANCE_REPORT.md` | CPIC concordance results (honest claims) | Audited |
| `reports/cpic_concordance_report.json` | Raw concordance data (machine-readable) | Complete |
| `scripts/validate_against_cpic.py` | Validation script (reproducible) | Functional |

### SME Review Materials

| Document | Description | Status |
|----------|-------------|--------|
| `docs/SME_REVIEW_PACKAGE.md` | Complete review package for pharmacologist | Ready |
| `docs/SME_EXECUTIVE_SUMMARY.md` | 1-page overview for busy reviewers | Updated |
| `docs/CONCORDANCE_REVIEW_FORM.md` | Case-by-case review form | Ready |
| `docs/CPIC_ALIGNMENT_SUMMARY.md` | Quick reference: CPIC vs Our System | Ready |

---

## Key Claims (Audited & Honest)

### Validated Claims (Can publish)

1. **CPIC Concordance: 100% (10/10 cases with CPIC data)**
   - Receipt: reports/cpic_concordance_report.json
   - Note: 49 cases had variants without CPIC coverage

2. **Sensitivity: 100% (6/6 toxicity cases flagged)**
   - All documented toxicity cases were correctly identified

3. **Specificity: 100% (0 false positives)**
   - No non-toxicity cases were falsely flagged

### Literature-Backed Claims (Cite sources)

| Gene-Drug | Prevention Rate | Source |
|-----------|-----------------|--------|
| DPYD - Fluoropyrimidines | 70-85% in carriers | PMID: 29152729 |
| TPMT - Thiopurines | 80-85% in carriers | PMID: 30447069 |
| UGT1A1 - Irinotecan | 40-50% in carriers | PMID: 26417955 |

---

## Key Metrics Summary

```
+-------------------------------------------------------------+
|                    VALIDATION SUMMARY                       |
+-------------------------------------------------------------+
|   CPIC Concordance:     100.0%  (10/10 with CPIC data)     |
|   95% CI:               72.2% - 100.0%                      |
|   Sensitivity:          100.0%  (6/6 toxicity caught)       |
|   Specificity:          100.0%  (0/53 false positives)      |
|   Cohort Size:          N=59 (multi-source)                 |
|   Genes Covered:        DPYD, TPMT, UGT1A1                  |
|   Variants without CPIC: 49 (83%) - correctly flagged       |
+-------------------------------------------------------------+
```

---

## Next Steps

- [ ] Obtain SME sign-off
- [ ] Co-author review
- [ ] Prepare cover letter
- [ ] Submit to journal

---

**Package Version:** 1.1
