# AYESHA: MBD4 Germline + TP53 Somatic HGSOC Analysis

## Overview

Comprehensive analysis of how MBD4 germline loss (homozygous c.1239delA) combined with TP53 R175H somatic mutation creates high-grade serous ovarian cancer (HGSOC).

## Patient Profile

- **Patient ID**: AYESHA-001
- **Diagnosis**: High-grade serous ovarian cancer (HGSOC)
- **Germline Status**: Positive (MBD4 germline mutation)
- **Genome Build**: GRCh37 (validated in test suite and patient data)

## Variants

### MBD4 Germline Variant (Homozygous Frameshift)

- **Gene**: MBD4
- **HGVS Protein**: p.Ile413Serfs*2
- **HGVS cDNA**: c.1239delA
- **Coordinates**: chr3:129430456 (GRCh37)
- **Alleles**: A → deletion
- **Zygosity**: Homozygous
- **Classification**: Pathogenic
- **Type**: Frameshift
- **Inheritance**: Germline
- **Function**: DNA glycosylase (Base Excision Repair)
- **Impact**: Complete loss-of-function → BER deficiency → genomic instability

### TP53 Somatic Mutation (R175H Hotspot)

- **Gene**: TP53
- **HGVS Protein**: p.Arg175His (R175H)
- **HGVS cDNA**: c.524G>A
- **Coordinates**: chr17:7577120 (GRCh37)
- **Alleles**: G → A
- **Zygosity**: Heterozygous
- **Classification**: Pathogenic
- **Type**: Missense (hotspot)
- **Inheritance**: Somatic
- **Frequency**: Most common TP53 mutation in HGSOC
- **Function**: Tumor suppressor (cell cycle checkpoint)
- **Impact**: Loss-of-function → checkpoint bypass → DNA damage accumulation

## Analysis Phases

### Phase 1: Variant Functional Annotation

**For each variant (MBD4 + TP53)**:

1. **Evo2 Sequence Scoring**
   - Endpoint: `POST /api/evo/score_variant_exon`
   - Adaptive windows: 4096, 8192, 16384
   - Expected: High disruption (frameshift for MBD4, hotspot for TP53)

2. **Insights Bundle (4 Chips)**
   - Functionality: Loss-of-function prediction
   - Essentiality: Gene dependency assessment
   - Regulatory: Splicing/expression impact
   - Chromatin: Accessibility changes

3. **Evidence Integration**
   - ClinVar classification
   - Literature evidence (PubMed/OpenAlex/S2)
   - MoA-aware filtering

### Phase 2: Pathway Analysis

**Pathways Analyzed**:

1. **Base Excision Repair (BER)** - MBD4 loss → BER deficiency
2. **Homologous Recombination Deficiency (HRD)** - TP53 + BER → synthetic lethality
3. **DNA Damage Response (DDR)** - TP53 + MBD4 → checkpoint bypass
4. **Cell Cycle Checkpoint** - TP53 loss → G1/S and G2/M failure

**Synthetic Lethality Analysis**:

- Endpoint: `POST /api/guidance/synthetic_lethality`
- Identifies vulnerabilities: PARP, ATR/CHK1, DNA-PK, WEE1 inhibition

### Phase 3: Drug Predictions (S/P/E Framework)

**Endpoint**: `POST /api/efficacy/predict`

**Predicted Drug Classes**:

1. **Tier 1 (Supported)**:
   - PARP inhibitors (olaparib, niraparib, rucaparib)
   - Platinum chemotherapy (carboplatin, cisplatin)

2. **Tier 2 (Consider)**:
   - ATR inhibitors (berzosertib, ceralasertib)
   - WEE1 inhibitors (adavosertib)

3. **Tier 3 (Insufficient)**:
   - DNA-PK inhibitors (nedisertib)
   - Immune checkpoint inhibitors (if TMB-high)

**Pathway Disruption Scores**:

- Extracted from `provenance["confidence_breakdown"]["pathway_disruption"]`
- Lowercase pathway names: `ddr`, `tp53`, `ras_mapk`, `pi3k`, `vegf`

### Phase 4: Clinical Trial Matching

**Trial Search**:

- Endpoint: `POST /api/trials/agent/search`
- Autonomous query generation
- Biomarkers: HRD+, TP53 mutation, MBD4 germline

**Mechanism Fit Ranking**:

1. Extract pathway scores from Phase 3
2. Convert to 7D mechanism vector using `convert_pathway_scores_to_mechanism_vector()`
3. Vector: `[DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]`
4. Rank trials by mechanism fit (α=0.7 eligibility + β=0.3 mechanism fit)

**Expected Trial Types**:

- Basket trials (DNA repair deficiency)
- Biomarker-driven trials (HRD+ ovarian cancer)
- Rare disease trials (MBD4 germline mutations)

### Phase 5: Immunogenicity Assessment

**TMB/MSI Estimation**:

- Endpoint: `POST /api/tumor/quick_intake`
- Expected: High TMB (BER deficiency + checkpoint bypass)
- Expected: Elevated MSI (MBD4 loss)

**Immune Checkpoint Therapy**:

- Sporadic gates applied automatically in Phase 3
- IO boost if TMB ≥20 or MSI-High
- Drugs: pembrolizumab, nivolumab

### Phase 6: Comprehensive Output

**Generated Reports**:

1. Executive summary (patient profile, key findings)
2. Pathway vulnerabilities (BER, HRD, DDR, checkpoint)
3. Drug prioritization (Tier 1, 2, 3)
4. Clinical trials (matched trials with mechanism fit)
5. Synthetic lethality (combination strategies)
6. Immunogenicity (TMB/MSI, IO eligibility)
7. Clinical recommendations

## Usage

### Prerequisites

1. Backend server running at `http://localhost:8000`
2. Evo2 service deployed (Modal)
3. Python 3.9+ with httpx installed

### Run Analysis

```bash
cd oncology-coPilot/oncology-backend-minimal
python scripts/ayesha_mbd4_tp53_hgsoc_analysis.py
```

### Environment Variables

```bash
export API_BASE_URL="http://localhost:8000"  # Backend URL
```

### Output

Results saved to: `oncology-coPilot/oncology-backend-minimal/results/ayesha_analysis/`

**Output File**: `ayesha_mbd4_tp53_analysis_<timestamp>.json`

**Contents**:

```json
{
  "patient_profile": {...},
  "variants": {
    "mbd4": {...},
    "tp53": {...}
  },
  "tumor_context": {...},
  "analysis_timestamp": "2025-01-XX...",
  "phases": {
    "phase1_annotation": {...},
    "phase2_pathway": {...},
    "phase3_efficacy": {...},
    "phase4_trials": {...},
    "phase5_immunogenicity": {...},
    "phase6_output": {...}
  }
}
```

## Key Features

### ✅ P0 Blockers Fixed

1. **Mechanism Vector Conversion**: `pathway_to_mechanism_vector.py` implemented
2. **pathway_disruption Storage**: Fixed in `orchestrator.py` line 339
3. **Coordinates Verified**: GRCh37 validated in test suite + patient data

### Architecture Components

- **S/P/E Framework**: Sequence + Pathway + Evidence integration
- **Evo2 Scoring**: Adaptive multi-window scoring with hotspot detection
- **Pathway Aggregation**: Automatic computation of DDR, TP53, MAPK, PI3K, VEGF
- **Sporadic Gates**: Germline-aware PARP scoring, TMB/MSI IO boost
- **Mechanism Fit Ranking**: Pathway-based 7D vector for trial matching

### Clinical Rationale

**MBD4 + TP53 Synergy**:

- MBD4 loss → BER deficiency → base damage accumulation
- TP53 loss → checkpoint bypass → damaged DNA replication
- Combined → genomic instability → HRD phenotype → PARP sensitivity

**Synthetic Lethality**:

- PARP inhibition exploits HRD (TP53 + BER deficiency)
- ATR/WEE1 inhibition exploits checkpoint bypass (TP53 loss)
- Platinum chemotherapy leverages DNA repair deficiency

**Rare Combination**:

- MBD4 germline mutations are extremely rare
- Combined with TP53 somatic in HGSOC is novel
- Basket trials and rare disease protocols are critical

## References

- **Plan**: `.cursor/plans/mbd4-tp53-hgsoc-analysis-2e21acc4.plan.md`
- **Manager Answers**: `src/services/evo_service/MBD4.mdc` (lines 1007-1132)
- **P0 Fixes**: `.cursor/plans/FAIL_NOW_VS_LATER_ASSESSMENT.md`
- **Pathway Mapping**: `api/services/pathway/drug_mapping.py` (line 63 - MBD4 in DDR)
- **Orchestrator Fix**: `api/services/efficacy_orchestrator/orchestrator.py` (line 339)
- **Conversion Function**: `api/services/pathway_to_mechanism_vector.py` (line 185-256)

## Test Suite

Related test files:

- `tests/test_mbd4_tp53_analysis.py`
- `scripts/test_mbd4_tp53_parp_predictions.py`
- `scripts/test_mbd4_tp53_pathway_aggregation.py`
- `scripts/test_mbd4_tp53_sequence_scoring.py`

All tests use GRCh37 coordinates (validated).

## Clinical Recommendations

1. **First-line**: PARP inhibitor (olaparib/niraparib/rucaparib) + platinum
2. **Second-line**: ATR/WEE1 inhibitor combination trials
3. **Biomarker Testing**: Confirm HRD status, TMB, MSI
4. **Genetic Counseling**: Family screening for MBD4 germline mutation
5. **Basket Trials**: Enroll in DNA repair deficiency trials
6. **Immunotherapy**: Consider if TMB-high (≥20) or MSI-high confirmed

---

**Last Updated**: January 2025  
**Genome Build**: GRCh37  
**Status**: ✅ Ready for execution (all P0 blockers fixed)

