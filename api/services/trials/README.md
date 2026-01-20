# 🔬 Trial Matching Agent - Module 05

**Status:** ✅ **COMPLETE**  
**Owner:** JR Agent D  
**Priority:** 🟡 HIGH | **Dependencies:** 01, 02, 04 | **Consumers:** 07, 08

---

## 📋 Overview

The Trial Matching Agent wires existing services to provide mechanism-based trial matching for the MOAT orchestration pipeline. It integrates:

- **AutonomousTrialAgent**: Query generation and ClinicalTrials.gov search
- **MechanismFitRanker**: Mechanism-based ranking (Manager P4 compliance)
- **TrialDataEnricher**: MoA extraction and eligibility scoring

---

## 🏗️ Architecture

```
TrialMatchingAgent
    │
    ├── AutonomousTrialAgent
    │   ├── Query Generation (5-10 queries)
    │   └── HybridTrialSearchService (AstraDB + Neo4j)
    │
    ├── MechanismFitRanker
    │   ├── Cosine Similarity (7D vectors)
    │   └── Combined Scoring (0.7×eligibility + 0.3×mechanism)
    │
    └── TrialDataEnricher
        ├── MoA Vector Extraction (Gemini tags preferred)
        ├── Eligibility Scoring
        └── PI Contact Extraction
```

---

## 📁 File Structure

```
api/services/trials/
├── __init__.py                    # Package exports
├── trial_matching_agent.py        # Main agent class
└── README.md                      # This file
```

---

## 🚀 Core Components

### **TrialMatchingAgent** (`trial_matching_agent.py`)

Main agent class that orchestrates trial matching:

**Key Methods:**
- `match(patient_profile, biomarker_profile, mechanism_vector, max_results)` - Main matching method
- `_estimate_eligibility_score()` - Simplified eligibility scoring
- `_build_trial_match()` - Convert trial data to TrialMatch object
- `_build_eligibility_criteria()` - Build eligibility breakdown
- `_explain_match()` - Generate human-readable explanation

**Process:**
1. Generate queries using `AutonomousTrialAgent.generate_search_queries()`
2. Search trials using `AutonomousTrialAgent.search_for_patient()`
3. Extract MoA vectors using `TrialDataEnricher.extract_moa_vector_for_trial()`
4. Rank by mechanism fit using `MechanismFitRanker.rank_trials()`
5. Build TrialMatch objects with scores and rationale
6. Return TrialMatchingResult

---

## 📊 Data Models

### **TrialMatch**

```python
@dataclass
class TrialMatch:
    nct_id: str
    title: str
    brief_summary: str
    phase: TrialPhase
    status: TrialStatus
    mechanism_fit_score: float      # Cosine similarity (0-1)
    eligibility_score: float        # Eligibility match (0-1)
    combined_score: float           # 0.7×eligibility + 0.3×mechanism
    trial_moa: TrialMoA             # 7D mechanism vector
    eligibility: EligibilityCriteria
    mechanism_alignment: Dict[str, float]  # Per-pathway alignment
    why_matched: str                # Human-readable explanation
    query_matched: str              # Which query found it
    locations: List[Dict]
    contact: Optional[Dict]
    url: str
    last_updated: str
    sponsor: str
```

### **TrialMatchingResult**

```python
@dataclass
class TrialMatchingResult:
    patient_id: str
    queries_used: List[str]
    trials_found: int
    trials_ranked: int
    matches: List[TrialMatch]
    top_match: Optional[TrialMatch]
    search_time_ms: int
    provenance: Dict[str, Any]
```

---

## 🔗 Integration

### **Orchestrator Integration**

The agent is wired to the orchestrator in `orchestrator.py`:

```python
async def _run_trial_matching_agent(self, state: PatientState) -> Dict:
    from ..trials import TrialMatchingAgent
    
    agent = TrialMatchingAgent()
    result = await agent.match(
        patient_profile=patient_profile,
        biomarker_profile=biomarker_profile,
        mechanism_vector=state.mechanism_vector,
        max_results=10
    )
    
    state.update('trial_matches', result.matches, agent='trial_matching', reason='Trial matching complete')
```

### **Pipeline Flow**

```
Phase 4: MATCHING
├── Extract patient profile from state
├── Extract biomarker profile from state
├── Extract mechanism vector from drug ranking
├── Call TrialMatchingAgent.match()
└── Store results in state.trial_matches
```

---

## ✅ Manager Policy Compliance

### **Manager P4: Mechanism Fit Ranking**

- ✅ Formula: `combined_score = 0.7×eligibility + 0.3×mechanism_fit`
- ✅ Thresholds: `min_eligibility=0.60`, `min_mechanism_fit=0.50`
- ✅ Uses `MechanismFitRanker` with Manager's approved weights

### **Manager P3: Gemini Trial Tagging**

- ✅ Priority 1: Pre-tagged Gemini vectors (offline)
- ✅ Priority 2: Runtime keyword matching (fallback only)
- ✅ Uses `TrialDataEnricher.extract_moa_vector_for_trial()` with `use_gemini_tag=True`

### **Manager C7: SAE-Aligned Trial Ranking**

- ✅ Supports 7D mechanism vectors: `[DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]`
- ✅ Fallback: If mechanism vector all zeros, ranks by eligibility only
- ✅ Provides per-pathway alignment breakdown

---

## 🧪 Testing

**Unit Tests Needed:**
- Query generation
- MoA vector extraction
- Mechanism fit ranking
- Eligibility scoring
- TrialMatch object building

**Integration Tests Needed:**
- Full pipeline with real patient data
- Mechanism vector integration
- Error handling

**Target Coverage:** >80%

---

## 📝 Usage Example

```python
from api.services.trials import TrialMatchingAgent

agent = TrialMatchingAgent()

result = await agent.match(
    patient_profile={
        'patient_id': 'PT-12345',
        'disease': 'ovarian_cancer_hgs',
        'mutations': [{'gene': 'MBD4', 'hgvs_p': 'p.R345*'}]
    },
    biomarker_profile={
        'tmb': {'value': 12.5, 'classification': 'TMB-H'},
        'msi': {'status': 'MSS'}
    },
    mechanism_vector=[0.88, 0.20, 0.10, 0.05, 0.0, 0.0, 0.0],  # 7D
    max_results=10
)

print(f"Found {result.trials_found} trials")
print(f"Top match: {result.top_match.title} (score: {result.top_match.combined_score:.2f})")
```

---

## 🔗 Related Services

- **AutonomousTrialAgent**: `api/services/autonomous_trial_agent.py`
- **MechanismFitRanker**: `api/services/mechanism_fit_ranker.py`
- **TrialDataEnricher**: `api/services/trial_data_enricher.py`
- **HybridTrialSearchService**: `api/services/hybrid_trial_search.py`
- **PathwayToMechanismVector**: `api/services/pathway_to_mechanism_vector.py`

---

**Module Status:** ✅ **COMPLETE**  
**Last Updated:** January 2025  
**Owner:** JR Agent D


