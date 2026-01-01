# Dosing Guidance Validation - Complete Workflow

**Status:** ✅ Production-Ready  
**Created:** January 2025  
**Purpose:** Clinical validation of dosing guidance system for publication

---

## 🎯 Overview

This validation workflow extracts pharmacogenomics cases from multiple data sources, runs them through the dosing guidance API, and generates comprehensive validation metrics for publication.

### Data Sources

1. **PubMed** - Literature case reports (DPYD/5-FU, UGT1A1/irinotecan, TPMT/thiopurine)
2. **cBioPortal** - Public dataset pharmacogene variants (MSK-IMPACT, colorectal studies)
3. **GDC/TCGA** - Germline variant data (TCGA-COAD, TCGA-READ)

### Validation Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│  STEP 1: Extract Cases                                      │
│  - PubMed: Literature case reports                          │
│  - cBioPortal: Pharmacogene variants                        │
│  - GDC: TCGA germline variants                              │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 2: Run Through Dosing Guidance API                   │
│  - Map variants to diplotypes                               │
│  - Call /api/dosing/guidance                                │
│  - Extract predictions (dose, adjustment, risk level)      │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 3: Assess Concordance                                 │
│  - Compare predictions vs clinical decisions                 │
│  - Identify cases where we could prevent toxicity           │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 4: Calculate Metrics                                  │
│  - Concordance rate                                          │
│  - Sensitivity/Specificity                                   │
│  - PPV/NPV                                                   │
└─────────────────────────────────────────────────────────────┘
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  STEP 5: Generate Report                                    │
│  - JSON results                                              │
│  - Markdown validation report                                │
└─────────────────────────────────────────────────────────────┘
```

---

## 📁 Scripts

### 1. `unified_extraction_pipeline.py`

Extracts cases from all three data sources.

**Usage:**
```bash
# Extract all pharmacogenes
python unified_extraction_pipeline.py --genes DPYD UGT1A1 TPMT

# Extract from specific studies
python unified_extraction_pipeline.py --genes DPYD --cbioportal-studies msk_impact_2017

# Extract from multiple GDC projects
python unified_extraction_pipeline.py --genes DPYD --gdc-projects TCGA-COAD TCGA-READ
```

**Output:** `unified_validation_cases.json`

---

### 2. `run_validation_workflow.py`

Complete validation workflow (extraction → API → metrics → report).

**Usage:**
```bash
# Full workflow (extract + validate)
python run_validation_workflow.py --genes DPYD UGT1A1 TPMT

# Use existing extraction results
python run_validation_workflow.py \
    --skip-extraction \
    --extraction-file unified_validation_cases.json

# Custom API endpoint
python run_validation_workflow.py \
    --api-base http://localhost:8000 \
    --genes DPYD
```

**Outputs:**
- `validation_report.json` - Complete results with all cases
- `validation_report.md` - Markdown report with metrics

---

### 3. `calculate_validation_metrics.py`

Standalone metrics calculator (if you already have curated cases).

**Usage:**
```bash
python calculate_validation_metrics.py \
    --input curated_cases.json \
    --output metrics_report.md
```

---

## 🔧 Setup

### Prerequisites

1. **Dosing Guidance API Running**
   ```bash
   # Start the API server
   cd oncology-coPilot/oncology-backend-minimal
   uvicorn api.main:app --reload
   ```

2. **Environment Variables** (for PubMed)
   ```bash
   export NCBI_USER_EMAIL="your-email@example.com"
   export NCBI_USER_API_KEY="your-api-key"  # Optional but recommended
   ```

3. **Dependencies**
   ```bash
   pip install requests httpx
   ```

---

## 📊 Expected Results

### Target Metrics (Publication-Ready)

| Metric | Target | Minimum |
|--------|--------|---------|
| Total cases | N≥50 | N≥30 |
| Concordance rate | ≥75% | ≥70% |
| Sensitivity | ≥85% | ≥75% |
| Specificity | ≥65% | ≥60% |

### Sample Output

```
================================================================================
VALIDATION COMPLETE
================================================================================
Total cases: 44
Cases with predictions: 42
Concordance rate: 78.6%
Sensitivity: 88.2%
Specificity: 68.4%
================================================================================
```

---

## 🚀 Quick Start

### Option 1: Full Automated Workflow

```bash
# 1. Run complete validation
python run_validation_workflow.py --genes DPYD UGT1A1 TPMT

# 2. Review results
cat validation_report.md
```

### Option 2: Step-by-Step

```bash
# 1. Extract cases
python unified_extraction_pipeline.py --genes DPYD

# 2. Manually curate cases (add treatment/outcome data)
# Edit unified_validation_cases.json

# 3. Run through API and calculate metrics
python run_validation_workflow.py \
    --skip-extraction \
    --extraction-file unified_validation_cases.json
```

---

## 📋 Next Steps for Agent Jr

1. **Run full extraction** for all 3 pharmacogenes
2. **Manually curate** extracted cases:
   - Add treatment doses from abstracts/clinical data
   - Add toxicity outcomes (grade, type, hospitalization)
   - Verify variant nomenclature (PharmVar)
3. **Run validation workflow** to get final metrics
4. **Review report** and identify gaps
5. **Iterate** until N≥50 with target metrics

---

## 🔍 Troubleshooting

### API Connection Issues

```bash
# Check if API is running
curl http://localhost:8000/api/dosing/health

# Test with sample request
curl -X POST http://localhost:8000/api/dosing/guidance \
  -H "Content-Type: application/json" \
  -d '{"gene": "DPYD", "variant": "*2A/*2A", "drug": "5-fluorouracil"}'
```

### cBioPortal Empty Responses

- Some studies may not have mutation data
- Try different studies: `--cbioportal-studies msk_impact_2017`
- The pipeline automatically falls back to sample list method

### PubMed Rate Limiting

- Add delays between requests
- Use NCBI API key to increase rate limits
- Reduce `--max-pubmed` if needed

---

## 📚 Related Documentation

- **Validation Plan:** `.cursor/plans/DOSING_GUIDANCE_VALIDATION_PLAN.md`
- **Cohort Framework:** `.cursor/rules/research/cohort_context_concept.mdc`
- **Dosing Guidance API:** `api/routers/dosing.py`
- **Contribution MDC:** `.cursor/lectures/drugDevelopment/dosing_guidance_contribution.mdc`

---

**Status:** ✅ Ready for Agent Jr to execute  
**Last Updated:** January 2025

