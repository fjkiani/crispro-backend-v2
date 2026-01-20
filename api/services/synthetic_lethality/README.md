# Synthetic Lethality & Essentiality Agent - Module 14

**Status:** ✅ **IMPLEMENTATION COMPLETE**  
**Owner:** AI Agent (Synthetic Lethality Specialist)  
**Version:** 2.1

---

## Overview

The Synthetic Lethality & Essentiality Agent identifies double-hit vulnerabilities and scores gene essentiality for precision drug targeting. When cancer cells lose one pathway (e.g., HR), they become dependent on backup pathways (e.g., PARP) - we identify these dependencies and target them with precision drugs.

**Validated:**
- ✅ 7D Pathway Mapping: 62.2% accuracy (n=500), 7.4% PARP FPR (safety-compliant)
- ✅ Beats SPD-ML approach: 52.0% vs 40.0% accuracy (n=100 comparison)
- ⏸️ Evo2 integration: Deferred (broken, needs 1-2 days fix)

**See:** `VALIDATION_STATUS.md` for latest validation results and deployment guidance.

---

## Architecture

### Pipeline

1. **Score Gene Essentiality** (Evo2 + pathway impact)
2. **Map Broken Pathways** (identify disrupted pathways)
3. **Identify Essential Backups** (synthetic lethality relationships)
4. **Recommend Drugs** (targeting essential pathways)
5. **Generate AI Explanations** (3 audiences: clinician/patient/researcher)

### Components

```
api/services/synthetic_lethality/
├── __init__.py                    # Exports
├── models.py                      # Data models
├── constants.py                       # Pathways, genes, drugs, SL relationships
├── essentiality_scorer.py          # Evo2 integration
├── pathway_mapper.py              # Pathway disruption mapping
├── dependency_identifier.py       # Essential backup identification
├── drug_recommender.py            # Drug recommendation engine
├── explanation_generator.py       # AI explanation generation
├── sl_agent.py                    # Main orchestrating agent
└── tests/                        # Unit tests (pending)
```

---

## API Endpoints

### POST `/api/agents/synthetic_lethality`

**Input:**
```json
{
  "disease": "ovarian_cancer",
  "mutations": [
    {
      "gene": "BRCA1",
      "hgvs_p": "p.C61G",
      "consequence": "stop_gained",
      "chrom": "17",
      "pos": 43044295,
      "ref": "T",
      "alt": "G"
    }
  ],
  "options": {
    "model_id": "evo2_7b",
    "include_explanations": true,
    "explanation_audience": "clinician"
  }
}
```

**Output:**
```json
{
  "synthetic_lethality_detected": true,
  "double_hit_description": "HR pathway loss",
  "essentiality_scores": [...],
  "broken_pathways": [...],
  "essential_pathways": [...],
  "recommended_drugs": [...],
  "suggested_therapy": "Olaparib",
  "explanation": {...},
  "calculation_time_ms": 1234,
  "evo2_used": true
}
```

### GET `/api/agents/synthetic_lethality/health`

Health check endpoint.

---

## Integration

### Orchestrator Integration

The agent is wired to the MOAT orchestrator:

- **Phase:** 3.5 (after drug efficacy, before trial matching)
- **Method:** `_run_synthetic_lethality_phase()` in `orchestrator.py`
- **State Storage:** `state.synthetic_lethality_result`

### Usage in Orchestrator

```python
# Automatically runs in orchestrator flow
state = await orchestrator.process_patient(patient_data)

# Access results
sl_result = state.synthetic_lethality_result
```

---

## Key Features

### 1. Gene Essentiality Scoring

- **Evo2 Integration:** Uses Evo2 foundation model for sequence disruption scoring
- **Formula:** `essentiality = base_score + evo2_boost + variant_type_boost`
- **Flags:** Truncation, frameshift, hotspot detection
- **Confidence:** Based on Evo2 score quality and variant type

### 2. Pathway Mapping

- **Pathways Tracked:** BER, HR, MMR, Checkpoint, MAPK, PARP
- **Status:** Functional, Compromised, Non-Functional
- **Disruption Score:** Aggregated from gene essentiality scores

### 3. Synthetic Lethality Detection

- **Known Relationships:**
  - HR deficient → depends on PARP (targeted by PARP inhibitors)
  - BER deficient → depends on HR (targeted by PARP inhibitors)
  - Checkpoint bypass → depends on ATR/CHK1 (targeted by ATR inhibitors)
  - MMR deficient → depends on immune checkpoint (targeted by IO)

### 4. Drug Recommendations

- **Ranking:** By confidence (pathway alignment + FDA approval + disease match)
- **Evidence Tiers:** I (FDA approved), II (high confidence), III (moderate), Research
- **Rationale:** Pathway targeting, mechanism, gene-specific reasons

### 5. AI Explanations

- **Audiences:** Clinician, Patient, Researcher
- **Provider:** Gemini LLM
- **Content:** Summary, full explanation, key points

---

## Data Models

### GeneEssentialityScore

```python
@dataclass
class GeneEssentialityScore:
    gene: str
    essentiality_score: float              # 0.0 - 1.0
    essentiality_level: EssentialityLevel   # HIGH/MODERATE/LOW
    sequence_disruption: float             # Evo2 delta (normalized)
    pathway_impact: str                    # e.g., "BER NON-FUNCTIONAL"
    functional_consequence: str            # e.g., "frameshift → loss of function"
    flags: Dict[str, bool]                 # truncation, frameshift, hotspot
    confidence: float                      # 0.0 - 1.0
```

### PathwayAnalysis

```python
@dataclass
class PathwayAnalysis:
    pathway_name: str                      # e.g., "Base Excision Repair"
    pathway_id: str                        # e.g., "BER"
    status: PathwayStatus                  # FUNCTIONAL/COMPROMISED/NON_FUNCTIONAL
    genes_affected: List[str]
    disruption_score: float                # 0.0 - 1.0
    description: str
```

### DrugRecommendation

```python
@dataclass
class DrugRecommendation:
    drug_name: str
    drug_class: str                        # e.g., "PARP_inhibitor"
    target_pathway: str                    # e.g., "HR"
    confidence: float                      # 0.0 - 1.0
    mechanism: str
    fda_approved: bool
    evidence_tier: str                     # I, II, III, Research
    rationale: List[str]
```

---

## Testing

### Unit Tests (Pending)

- `test_essentiality.py` - Essentiality scoring
- `test_pathways.py` - Pathway mapping
- `test_recommendations.py` - Drug recommendations
- `test_integration.py` - End-to-end integration

### Validation Statusnn**Current Validation Framework:** 7D Pathway Mapping (deterministic, production-ready)nn- **n=500 Baseline (Mutation Counts):**n  - Accuracy: 62.2%n  - Macro-F1: 0.178n  - PARP FPR: 7.4% (safety-compliant)n  - Receipt: `publications/synthetic_lethality/results/gdsc2_7d_mutcounts_n500_safety.json`nn- **n=100 Comparison vs SPD-ML:**n  - 7D wins:s 40.0% accuracy, 0.172 vs 0.143 macro-F1n  - Receipt: `publications/synthetic_lethality/results/gdsc2_7d_validation.json`nn- **Evo2 Integration:** Deferred (broken, fix in progress)n  - Current: Worse accuracy (40%) + unsafe PARP FPR (51.3%)n  - Fix timeline: 1-2 days (see `VALIDATION_STATUS.md`)nn**See:** `VALIDATION_STATUS.md` for detailed validation results and deployment guidance.n
### Dependencies