# 🎯 Yale T-DXd Resistance Project - Data Pipeline

**Mission:** Predict post-T-DXd therapy response for Dr. Maryam Lustberg's Yale Cancer Center cohort

**Timeline:** Week 1 (Oct 18-25, 2024) - Data Extraction & Labeling

---

## 📊 Pipeline Overview

```
1. extract_tcga_brca.py   → Extract TCGA/METABRIC breast cancer data
2. label_adc_resistance.py → Generate resistance labels (auto, no curation)
3. train_adc_models.py     → Train therapy-specific prediction models
4. validate_on_yale.py     → External validation (requires Yale data)
```

---

## 🚀 Quick Start

### Step 1: Extract Public Data (30 min)

```bash
cd /Users/fahadkiani/Desktop/development/crispr-assistant-main
source venv/bin/activate
python oncology-coPilot/oncology-backend-minimal/scripts/yale_tdzd/extract_tcga_brca.py
```

**Output:**
- `data/yale_tdzd_project/raw/brca_tcga_pan_can_atlas_2018_mutations.csv`
- `data/yale_tdzd_project/raw/brca_tcga_pan_can_atlas_2018_clinical.csv`
- `data/yale_tdzd_project/raw/brca_metabric_mutations.csv`
- `data/yale_tdzd_project/raw/brca_metabric_clinical.csv`

### Step 2: Generate Resistance Labels (15 min)

```bash
python oncology-coPilot/oncology-backend-minimal/scripts/yale_tdzd/label_adc_resistance.py
```

**Output:**
- `data/yale_tdzd_project/processed/brca_adc_resistance_cohort.csv`

Labels generated:
- `adc_resistance_risk`: HIGH / MEDIUM / LOW
- `sg_cross_resistance_risk`: HIGH / MEDIUM / LOW (sacituzumab govitecan)
- `endocrine_sensitivity`: HIGH / MEDIUM / LOW
- `eribulin_sensitivity`: HIGH / MEDIUM / LOW

### Step 3: Train Models (coming next)

```bash
python oncology-coPilot/oncology-backend-minimal/scripts/yale_tdzd/train_adc_models.py
```

---

## 🧬 Target Genes (38 genes)

### HER2 Pathway
- ERBB2, ERBB3, EGFR

### PI3K/AKT Pathway
- PIK3CA, AKT1, PTEN, PIK3R1

### DNA Damage Response (DDR)
- TP53, BRCA1, BRCA2, ATM, CHEK2, RAD51, SLFN11

### ADC Targets
- TACSTD2 (TROP2 - SG target)
- TOP1, TOP2A (topoisomerase)

### Drug Efflux
- ABCB1 (MDR1), ABCG2 (BCRP)

### Hormone Receptors
- ESR1, PGR

### Cell Cycle
- CCND1, CDK4, CDK6, RB1

### Other Drivers
- MYC, GATA3, MAP3K1, TBX3

---

## 🏷️ Labeling Logic

### ADC Resistance Risk

**Scoring:**
- TP53 mutation: +3 points
- HER2-low expression: +3 points
- PIK3CA mutation: +2 points
- SLFN11-low: +2 points (DDR deficiency)
- ABCB1/ABCG2 high: +2 points (drug efflux)

**Classification:**
- HIGH_RISK: ≥7 points (expected rwPFS <3 months)
- MEDIUM_RISK: 4-6 points
- LOW_RISK: 0-3 points

### SG Cross-Resistance Risk

**Scoring:**
- TROP2-low: +3 points
- SLFN11-low: +2 points
- TOP1 mutation: +2 points

**Classification:**
- HIGH_RISK: ≥5 points (avoid SG after T-DXd)
- MEDIUM_RISK: 3-4 points
- LOW_RISK: 0-2 points

---

## 📈 Expected Outputs

### Cohort Sizes
- TCGA PanCancer Atlas: ~1,000 patients
- METABRIC: ~2,500 patients
- **Total: ~3,500 patients for training**

### Label Distribution (expected)
- HIGH_RISK: 20-30%
- MEDIUM_RISK: 40-50%
- LOW_RISK: 20-30%

---

## 🎯 Success Criteria

**Week 1 Complete:**
- [X] Scripts created
- [ ] TCGA data extracted
- [ ] Labels generated
- [ ] Initial data quality checks

**Week 2 Complete:**
- [ ] Models trained (AUROC ≥0.70)
- [ ] Internal validation complete
- [ ] Benchmark vs clinical variables

---

## 📧 Partnership Status

**Partner:** Dr. Maryam Lustberg, Yale Cancer Center  
**Email Sent:** Oct 18, 2024  
**Attachment:** METASTASIS_INTERCEPTION_ONE_PAGER.pdf  
**Status:** Awaiting response

**Next Steps:**
1. Complete public data extraction (no Yale data needed yet)
2. Train and validate models on TCGA/METABRIC
3. If Dr. Lustberg responds → validate on Yale cohort (793 patients)
4. Co-author publication + partnership

---

**EXECUTION STATUS:** INITIATED (Oct 18, 2024)

