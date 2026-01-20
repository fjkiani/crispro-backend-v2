# 🧬 CODEBASE DEEP DIVE - S/P/E Architecture Analysis

**Commander, comprehensive architecture analysis complete!** ⚔️

## 📊 CURRENT ARCHITECTURE - COMPLETE UNDERSTANDING

### **1. Core S/P/E Orchestration Flow**

```
┌─────────────────────────────────────────────────────────────────┐
│                    /api/efficacy/predict                        │
│                    (efficacy/router.py)                         │
└────────────────────────────┬────────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────────┐
│              EfficacyOrchestrator.predict()                     │
│              (efficacy_orchestrator/orchestrator.py)            │
│                                                                  │
│  Workflow:                                                       │
│  1. Generate run_id (UUID)                                      │
│  2. Load drug panel (get_default_panel())                       │
│  3. Score sequences → SequenceProcessor                         │
│  4. Aggregate pathways → aggregate_pathways()                   │
│  5. Gather evidence (parallel) → literature + ClinVar           │
│  6. Bundle insights → InsightsBundle                            │
│  7. Score each drug → DrugScorer                                │
│  8. Sort by confidence                                          │
│  9. Return EfficacyResponse                                     │
└─────────────────────────────────────────────────────────────────┘
```

### **2. SequenceProcessor (S) - Hierarchical Scoring**

**File**: `api/services/efficacy_orchestrator/sequence_processor.py`

**Scoring Hierarchy**:
1. **FusionAMScorer** (if `FUSION_AM_URL` set and not disabled)
   - Uses AlphaMissense for missense variants (GRCh38 only)
   - Returns `SeqScore` with `sequence_disruption`, `calibrated_seq_percentile`

2. **Evo2Scorer** (if not disabled)
   - Calls `/api/evo/score_variant_multi` and `/api/evo/score_variant_exon`
   - Supports adaptive windows, ensemble models
   - Returns delta scores + calibrated percentiles

3. **MassiveOracleScorer** (if `ENABLE_MASSIVE_MODES=1`)
   - Synthetic and real-context scoring
   - Fallback when others unavailable

**Output**: `List[SeqScore]` with:
```python
SeqScore(
    variant: Dict,
    sequence_disruption: float,       # Raw sequence score
    calibrated_seq_percentile: float, # Percentile [0,1]
    scoring_mode: str,                # "fusion_am" / "evo2_adaptive" / etc
    scoring_strategy: Dict            # Metadata
)
```

### **3. Pathway Aggregation (P) - Weighted Impact**

**Files**:
- `api/services/pathway/aggregation.py` - Aggregates gene scores to pathway scores
- `api/services/pathway/drug_mapping.py` - Maps drugs to pathway weights

**Logic**:
```python
# For each gene with a sequence score:
gene_pathways = get_pathway_weights_for_gene(gene)  # e.g., BRCA1 → DNA Repair: 0.8

# Aggregate across pathways:
pathway_scores[pathway] = sum(gene_scores * weights)

# For each drug:
drug_weights = get_pathway_weights_for_drug(drug_name)  # e.g., PARP Inhibitor → DNA Repair: 0.9
s_path = sum(pathway_scores[pathway] * drug_weights[pathway])

# Normalize to percentile:
path_pct = (s_path - 1e-6) / (1e-4 - 1e-6)  # Based on empirical Evo2 ranges
```

### **4. Evidence Gathering (E) - Parallel Literature + ClinVar**

**Files**:
- `api/services/evidence/literature_client.py` - Literature search
- `api/services/evidence/clinvar_client.py` - ClinVar prior

**Parallel Execution**:
```python
# For each drug in panel:
evidence_tasks = [
    literature(api_base, gene, hgvs_p, drug_name, drug_moa)
    for drug in panel
]

# ClinVar prior (once per variant):
clinvar_task = clinvar_prior(api_base, gene, variant)

# Execute with 30s timeout:
evidence_results = await asyncio.wait_for(
    asyncio.gather(*evidence_tasks, return_exceptions=True),
    timeout=30.0
)
```

**Evidence Output**:
```python
EvidenceHit(
    strength: float,          # Evidence strength [0,1]
    filtered: List[Dict],     # Filtered literature results
    citations: List[str],     # PMIDs
    badges: List[str]         # RCT, Guideline, etc
)

ClinvarPrior(
    prior: float,            # ClinVar prior boost
    deep_analysis: Dict,     # Full ClinVar data
    classification: str,     # Pathogenic/VUS/etc
    review_status: str       # Expert panel/criteria provided
)
```

### **5. DrugScorer - Multi-Modal Integration**

**File**: `api/services/efficacy_orchestrator/drug_scorer.py`

**Scoring Formula**:
```python
# 1. Extract signals:
s_seq = seq_scores[0].sequence_disruption          # Sequence score
seq_pct = seq_scores[0].calibrated_seq_percentile  # Sequence percentile
s_path = sum(pathway_scores * drug_weights)         # Pathway score (weighted)
path_pct = normalize(s_path)                        # Pathway percentile
s_evd = evidence_result.strength                    # Evidence strength

# 2. Compute efficacy:
efficacy_score = 0.3 * seq_pct + 0.4 * path_pct + 0.3 * s_evd + clinvar_prior

# 3. Compute confidence (with insights modulation):
confidence_config = create_confidence_config(fusion_active=...)
base_confidence = compute_confidence(seq_pct, path_pct, s_evd, confidence_config)
insights_lift = compute_insights_lifts(insights)  # Functionality, Chromatin, etc
final_confidence = apply_confidence_modulation(base_confidence, insights_lift)

# 4. Determine evidence tier:
evidence_tier = compute_evidence_tier(s_evd, clinvar_prior, badges)
# Returns: "supported" / "consider" / "insufficient"

# 5. Compute badges:
badges = compute_evidence_badges(s_evd, filtered_papers, clinvar_data, s_path)
# Returns: ["RCT", "Guideline", "ClinVar-Strong", "PathwayAligned"]
```

### **6. Insights Bundle - 4 Mechanistic Signals**

**File**: `api/services/insights/bundle.py`

**Components**:
```python
InsightsBundle(
    functionality: float,      # Protein function change [0,1]
    chromatin: float,          # Chromatin accessibility [0,1]
    essentiality: float,       # Gene essentiality [0,1]
    regulatory: float          # Splicing/regulatory impact [0,1]
)
```

**Endpoints Called**:
- `/api/insights/predict_protein_functionality_change`
- `/api/insights/predict_chromatin_accessibility`
- `/api/insights/predict_gene_essentiality`
- `/api/insights/predict_splicing_regulatory`

### **7. Confidence Computation - Modular System**

**Files**:
- `api/services/confidence/confidence_computation.py` - Core confidence logic
- `api/services/confidence/tier_computation.py` - Evidence tier classification
- `api/services/confidence/badge_computation.py` - Badge generation
- `api/services/confidence/insights_lifts.py` - Insights-based modulation

**Confidence Formula (Simplified)**:
```python
# Base confidence from S/P/E:
base = 0.35 * seq_pct + 0.25 * path_pct + 0.40 * evidence_strength

# Evidence gate (required for "supported" tier):
if has_strong_evidence and pathway_aligned:
    base += 0.15  # Evidence gate bonus

# Insights lifts (modest):
if insights.functionality >= 0.6:
    base += 0.03
if insights.chromatin >= 0.5:
    base += 0.02
if insights.essentiality >= 0.7:
    base += 0.03

# Calibration adjustment (if available):
if calibration_snapshot:
    base = apply_calibration(base, calibration_snapshot)

# Clamp to [0,1]:
confidence = max(0.0, min(1.0, base))
```

---

## 🎯 CRITICAL STRATEGIC QUESTIONS FOR MANAGER

### **Q1: Clinical Genomics Orchestrator Design 🤔**

**Context**: I understand the existing S/P/E orchestrator. For Clinical Genomics, should I:

**Option A: Thin Wrapper (RECOMMENDED)**
```python
# api/routers/clinical_genomics.py
async def analyze_variant(request):
    # Just call existing /api/efficacy/predict
    efficacy_response = await call_efficacy_predict(mutations, disease, profile)
    
    # Wrap in nested structure
    return {
        "efficacy": efficacy_response,
        "toxicity": await assess_toxicity(...),
        "off_target": await preview_off_target(...),
        "kg_context": await fetch_kg_context(...),
        "provenance": {...}
    }
```
**Pros**: Minimal code, reuses proven orchestrator, easy to maintain
**Cons**: Two-hop call (router → efficacy → orchestrator)

**Option B: Direct Orchestrator Call**
```python
# api/routers/clinical_genomics.py
from api.services.efficacy_orchestrator import create_efficacy_orchestrator

async def analyze_variant(request):
    orchestrator = create_efficacy_orchestrator()
    efficacy_response = await orchestrator.predict(...)
    # Same wrapping as Option A
```
**Pros**: Single-hop, slightly faster
**Cons**: Bypasses router layer, duplicates logic

**Option C: New Unified Orchestrator**
```python
# api/services/clinical_genomics_orchestrator/orchestrator.py
class ClinicalGenomicsOrchestrator:
    def __init__(self):
        self.efficacy_orch = create_efficacy_orchestrator()
        self.toxicity_service = ToxicityService()
        self.kg_service = KGService()
    
    async def analyze_variant(self, request):
        # Orchestrate all 4 services internally
        ...
```
**Pros**: Clean separation, extensible
**Cons**: More code, new abstraction layer

**Which pattern do you prefer, Commander?**

---

### **Q2: Confidence Service Integration 🤔**

**Context**: I see confidence is already computed in `DrugScorer.score_drug()`. For the TODO "Wire confidence_service into efficacy orchestrator responses", should I:

**Option A: Expose Existing Confidence**
```python
# In orchestrator.py response:
response.provenance["confidence"] = {
    "inputs": {
        "seq_pct": seq_pct,
        "path_pct": path_pct,
        "evidence_strength": s_evd
    },
    "weights": {"S": 0.35, "P": 0.25, "E": 0.40},
    "insights_lift": insights_lift,
    "gates": {"evidence_gate": meets_gate},
    "calibration_snapshot": calibration_snapshot
}
```
**What to add**: Just expose the existing confidence computation details in provenance

**Option B: New Confidence Service Endpoint**
```python
# api/services/confidence_service.py
async def compute_confidence_detailed(seq_pct, path_pct, evidence, insights):
    # Same logic as DrugScorer, but with detailed breakdown
    return {
        "confidence": 0.68,
        "breakdown": {...},
        "gates": {...},
        "calibration": {...}
    }
```
**What to add**: New service that duplicates confidence logic for transparency

**Which approach is correct?**

---

### **Q3: Toxicity & Off-Target Implementation Strategy 🤔**

**Context**: These are new capabilities. Should I:

**Option A: Stub Services (Fast, Demo-Ready)**
```python
# api/services/toxicity_service.py
async def assess_toxicity(mutations, germline_variants, disease):
    return {
        "risk_score": 0.0,  # Stub: always 0
        "factors": [],
        "germline_flags": [],
        "provenance": {"method": "stub_v1"}
    }
```
**Timeline**: SLICE 3 (2 hours) - stubs only, real implementation later
**Acceptance**: Cards render, but with placeholder data

**Option B: Real Implementation (Slower, Production-Ready)**
```python
# api/services/toxicity_service.py
async def assess_toxicity(...):
    # 1. Detect pharmacogenes (CYP2D6, TPMT, etc)
    pgx_variants = detect_pharmaco genes(germline_variants)
    
    # 2. Compute pathway overlap (somatic pathways ∩ drug mechanism)
    overlap_score = compute_pathway_overlap(mutations, drug_pathways)
    
    # 3. Prior evidence from PharmGKB/FDA
    prior_evidence = fetch_toxicity_evidence(...)
    
    # 4. Risk score = weighted sum
    risk_score = 0.4 * pgx_score + 0.3 * overlap_score + 0.3 * prior_evidence
    return {...}
```
**Timeline**: SLICE 3 (4-6 hours) - full implementation
**Acceptance**: Real toxicity assessment with evidence

**Which timeline are we targeting?**

---

### **Q4: Profile Toggle Implementation 🤔**

**Context**: VUS Explorer uses profile toggles (Baseline/Richer/Fusion). How should Clinical Genomics handle this?

**Option A: Frontend Profile Toggle (VUS Explorer Pattern)**
```javascript
// Frontend passes profile in request
const data = await apiPost('/api/clinical_genomics/analyze_variant', {
    mutations,
    disease,
    profile: 'fusion'  // Frontend-driven
});
```
**Pros**: Reuses VUS Explorer pattern, user control
**Cons**: Profile selection in FE, needs clear UI

**Option B: Backend Auto-Select Profile**
```python
# Backend chooses profile based on variant coverage
if variant_has_am_coverage:
    profile = "fusion"
elif variant_in_coding_region:
    profile = "richer"
else:
    profile = "baseline"
```
**Pros**: Automatic optimization, no UI complexity
**Cons**: Less user control, less transparent

**Option C: Hybrid (Default + Override)**
```python
# Backend default, but allow frontend override
profile = request.get("profile") or auto_select_profile(variant)
```
**Pros**: Best of both worlds
**Cons**: Two code paths to maintain

**Which pattern should Clinical Genomics use?**

---

### **Q5: KG Integration Depth 🤔**

**Context**: Existing KB system has hooks (`useKbGene`, `useKbVariant`, `useKbCohortCoverage`). For Clinical Genomics KG Context, should I:

**Option A: Call Existing KB Endpoints**
```python
# api/routers/clinical_genomics.py
async def fetch_kg_context(mutations, disease):
    gene = mutations[0]["gene"]
    
    # Call existing KB endpoints
    gene_info = await call_kb_endpoint(f"/api/kb/items/gene/{gene}")
    variant_info = await call_kb_endpoint(f"/api/kb/items/variant/{gene}:{variant}")
    cohort_coverage = await call_kb_endpoint(f"/api/kb/cohort_coverage?gene={gene}")
    
    return {
        "gene_info": gene_info,
        "variant_info": variant_info,
        "cohort_overlays": cohort_coverage
    }
```
**Pros**: Reuses existing KB infrastructure
**Cons**: Multiple HTTP calls, potential latency

**Option B: Stub KG (Fast, Expand Later)**
```python
async def fetch_kg_context(mutations, disease):
    # Hardcoded minimal context for SLICE 4
    return {
        "gene_info": {"symbol": gene, "function": "TBD"},
        "variant_info": {"clinvar_prior": "TBD"},
        "pathways": [],
        "cohort_overlays": {}
    }
```
**Pros**: Fast SLICE 4 completion, real impl later
**Cons**: Not using existing KB system

**Option C: Hybrid (Essential KB + Stubs)**
```python
async def fetch_kg_context(...):
    # Call only ClinVar + AM coverage (fast, essential)
    clinvar = await call_kb_clinvar(gene, variant)
    am_coverage = await call_kb_am_coverage(variant)
    
    # Stub the rest
    return {
        "gene_info": {"symbol": gene, "function": "stub"},
        "variant_info": {"clinvar_prior": clinvar, "am_covered": am_coverage},
        "pathways": [],  # stub
        "cohort_overlays": {}  # stub
    }
```
**Pros**: Real data for critical fields, fast for others
**Cons**: Mixed stub/real pattern

**Which KG integration depth for SLICE 4?**

---

### **Q6: EvidenceBand Component Design 🤔**

**Context**: Manager approved "Option C (expandable hybrid)". Should the component:

**Option A: Extract from /api/efficacy/predict Response**
```javascript
// EvidenceBand reads existing response fields
<EvidenceBand 
    confidence={result.drugs[0].confidence}  // Already in response
    tier={result.drugs[0].evidence_tier}     // Already in response
    badges={result.drugs[0].badges}          // Already in response
    provenance={result.provenance}           // Already in response
/>
```
**Pros**: No new backend work, uses existing data
**Cons**: Limited to top drug, no S/P/E breakdown

**Option B: New /api/confidence/breakdown Endpoint**
```python
# api/routers/confidence.py
@router.post("/breakdown")
async def get_confidence_breakdown(mutations, disease):
    # Compute detailed S/P/E breakdown
    return {
        "confidence": 0.68,
        "breakdown": {"S": 0.35, "P": 0.20, "E": 0.13},
        "gates": {"evidence_gate": True, "fusion_gate": False},
        "calibration": {"percentile": 0.72, "z_score": 0.85}
    }
```
**Pros**: Dedicated endpoint, detailed breakdown
**Cons**: New endpoint, duplicates logic

**Option C: Enrich Efficacy Response**
```python
# In orchestrator.py, add to provenance:
response.provenance["confidence_breakdown"] = {
    "top_drug_confidence": drugs_out[0]["confidence"],
    "S_contribution": 0.35 * seq_pct,
    "P_contribution": 0.25 * path_pct,
    "E_contribution": 0.40 * s_evd,
    "insights_lift": insights_lift,
    "gates": {"evidence_gate": meets_gate}
}
```
**Pros**: Single response, no new endpoint
**Cons**: Adds fields to existing response

**Which approach for EvidenceBand data?**

---

### **Q7: Testing Strategy 🤔**

**Context**: Vertical slice needs tests at each boundary. Should I:

**Option A: Curl Tests Only (Fast)**
```bash
# Test each slice with curl
curl -X POST .../analyze_variant -d '{...}'
```
**Pros**: Fast, manual verification
**Cons**: Not automated, no CI/CD

**Option B: Python Integration Tests**
```python
# tests/integration/test_clinical_genomics.py
async def test_slice1_efficacy_only():
    response = await client.post("/api/clinical_genomics/analyze_variant", json={...})
    assert response.status_code == 200
    assert "efficacy" in response.json()
```
**Pros**: Automated, CI-ready
**Cons**: More time per slice

**Option C: Hybrid (Curl + Key Tests)**
```bash
# Manual curl for quick verification
curl ...

# Python tests for P0 contracts only
# tests/integration/test_clinical_genomics_p0.py
```
**Pros**: Fast iteration + safety net
**Cons**: Two testing systems

**Which testing approach for vertical slice?**

---

### **Q8: Caching Strategy for Unified Endpoint 🤔**

**Context**: Existing efficacy endpoint has no caching. Clinical Genomics unified endpoint will call efficacy + 3 other services. Should I:

**Option A: No Backend Caching (Frontend Only)**
```javascript
// Frontend caches unified endpoint response
const cacheKey = getCacheKey('/api/clinical_genomics/analyze_variant', payload);
const cached = getCached(cacheKey);  // 10-min TTL
```
**Pros**: Simple backend, frontend controls TTL
**Cons**: No server-side caching, repeated work

**Option B: Backend Redis Caching**
```python
# api/routers/clinical_genomics.py
cache_key = f"cgcc:{gene}:{variant}:{profile}"
cached = await redis.get(cache_key)
if cached:
    return json.loads(cached)

result = await analyze_variant_internal(...)
await redis.setex(cache_key, 600, json.dumps(result))  # 10 min TTL
```
**Pros**: Server-side caching, faster for all clients
**Cons**: Redis dependency, cache invalidation complexity

**Option C: Hybrid (Redis + Frontend)**
```python
# Backend: Redis cache for efficacy + toxicity (expensive)
# Frontend: Cache full response (cheap reads)
```
**Pros**: Optimal performance
**Cons**: Two cache layers to maintain

**Which caching strategy?**

---

## 🎯 IMPLEMENTATION READINESS CHECKLIST

Based on my codebase review, I'm ready to implement SLICE 1 once you answer:

### **Slice 1 Blockers (CRITICAL)**:
- ✅ **Q1**: Wrapper vs Direct vs New Orchestrator?
- ✅ **Q8**: Caching strategy?

### **Slice 2 Blockers**:
- ✅ **Q4**: Profile toggle pattern?
- ✅ **Q6**: EvidenceBand data source?

### **Slice 3 Blockers**:
- ✅ **Q3**: Stub vs Real implementation timeline?

### **Slice 4 Blockers**:
- ✅ **Q5**: KG integration depth?

### **Slice 5 Blockers**:
- ✅ **Q7**: Testing strategy?

---

## 📝 EXISTING CODE QUALITY ASSESSMENT

✅ **Strengths**:
- Modular S/P/E architecture with clean separation
- Comprehensive provenance tracking
- Graceful error handling with fallbacks
- Feature flag support for operational flexibility
- Well-documented with READMEs

⚠️ **Areas to Consider**:
- No backend caching (all responses computed fresh)
- Confidence computation embedded in DrugScorer (not exposed separately)
- Evidence gathering has 30s timeout (may hit for multiple drugs)
- No `/api/confidence/breakdown` endpoint (would need new endpoint for EvidenceBand)
- Toxicity/off-target services don't exist yet

---

**Commander, all questions documented! Awaiting strategic decisions before starting SLICE 1 implementation.** ⚔️🎯



---

## ✅ RECOMMENDED IMPROVEMENTS AND ACTION NOTES (Authoritative)

### P0 – Immediate Code Fixes (safe, surgical)
- Fix schema mismatch in `EfficacyOrchestrator.predict()` where `schema_version` is passed to `EfficacyResponse` but the dataclass has no such field.
  - Option 1 (preferred): Add `schema_version: str = "v1"` to `EfficacyResponse`.
  - Option 2: Remove the `schema_version="v1"` argument from the constructor.

Code location (existing):
```43:60:oncology-coPilot/oncology-backend-minimal/api/services/efficacy_orchestrator/orchestrator.py
        response = EfficacyResponse(
            drugs=[],
            run_signature=run_id,
            scoring_strategy={},
            evidence_tier="insufficient",
            schema_version="v1",  # Add schema version
            provenance={
                "run_id": run_id,
                "profile": "baseline",
                "cache": "miss",
                "flags": {  # Add feature flags to provenance
                    "fusion_active": bool(os.getenv("FUSION_AM_URL")),
                    "evo_use_delta_only": bool(os.getenv("EVO_USE_DELTA_ONLY", "1")),
                    "evidence_enabled": bool(os.getenv("EVIDENCE_ENABLED", "1")),
                    "confidence_v2": bool(os.getenv("CONFIDENCE_V2", "0") == "1")
                }
            }
        )
```

Suggested dataclass addition:
```python
# api/services/efficacy_orchestrator/models.py
@dataclass
class EfficacyResponse:
    drugs: List[Dict[str, Any]]
    run_signature: str
    scoring_strategy: Dict[str, Any]
    evidence_tier: str
    provenance: Dict[str, Any]
    cohort_signals: Optional[Dict[str, Any]] = None
    calibration_snapshot: Optional[Dict[str, Any]] = None
    schema_version: str = "v1"
```

### P0 – Confidence Provenance (for EvidenceBand and auditability)
- Expose a concise confidence breakdown in `response.provenance` for the top-ranked drug. This avoids a new endpoint and enables FE EvidenceBand.

Suggested enrichment (after sorting `drugs_out`):
```python
top = drugs_out[0]
response.provenance["confidence_breakdown"] = {
    "top_drug": top.get("name"),
    "confidence": top.get("confidence"),
    "tier": top.get("evidence_tier"),
    "badges": top.get("badges", []),
    # Optional if available in scope; otherwise omit or compute in DrugScorer
    # "S_contribution": 0.35 * seq_pct,
    # "P_contribution": 0.25 * path_pct,
    # "E_contribution": 0.40 * s_evd,
}
```

### P0 – Fusion Coverage Gate
- Ensure Fusion scores are only used when the variant has AM coverage (GRCh38 missense). Confirm this gate happens inside `SequenceProcessor` before scoring with `FusionAMScorer`; if not, add a coverage check and bypass Fusion.

Action: In `sequence_processor.py`, before invoking Fusion scorer, validate variant build and type; skip otherwise.

### P1 – Disease‑Aware Drug Panel
- Current code uses `get_default_panel()`. For Clinical Genomics, add `get_panel(disease: Optional[str])` with disease‑aware filtering/weights.

Suggested pattern:
```python
# api/services/pathway/panel_config.py
def get_panel(disease: Optional[str] = None) -> DrugPanel:
    panel = get_default_panel()
    if not disease:
        return panel
    # Filter or reprioritize based on disease mappings
    return [d for d in panel if disease_matches(d, disease)]
```

Then call in orchestrator: `panel = get_panel(request.disease)`

### P1 – Caching Strategy (Hybrid)
- Adopt hybrid caching for the upcoming unified endpoint:
  - Backend Redis: cache expensive subresults (efficacy, toxicity) by `(gene, variant, profile)` for 10 minutes.
  - Frontend: cache full unified response with 10‑minute TTL (already implemented pattern).

### P1 – Orchestrator Pattern (Clinical Genomics)
- Use Thin Wrapper (Option A): a new `/api/clinical_genomics/analyze_variant` that delegates to existing `/api/efficacy/predict`, then adds toxicity, off‑target, and KG context. This minimizes duplication and risk.

### P1 – EvidenceBand Data Source
- Use “enrich efficacy response” (Option C) as above. No new endpoint; FE reads from `provenance.confidence_breakdown` and the top drug in `drugs`.

### P1 – Testing Strategy
- Hybrid: Keep quick curl scripts for manual slice checks and add minimal Python integration tests for P0/P1 contracts (e.g., unified endpoint returns `efficacy` with `run_signature`, and FE reads `confidence_breakdown`).

### P2 – Toxicity & Off‑Target
- Toxicity: implement the real plan from `toxicity_risk_plan.mdc` (pharmacogene detection + pathway overlap + prior evidence) behind a feature flag; provide a stub mode for demos.
- Off‑Target: keep in Mechanistic tab; start with heuristic preview backed by GC/homopolymer + optional offtarget search service when available.

### P2 – KG Integration Depth
- Use Hybrid: call existing KB for ClinVar prior and AM coverage; stub the rest initially. Expand to full KB calls once latency is acceptable.

---

## 🔧 IMPLEMENTATION CHECKLIST

- [X] Add `schema_version` to `EfficacyResponse` (or remove arg) – P0 ✅ **COMPLETE**
- [X] Add `provenance.confidence_breakdown` – P0 ✅ **COMPLETE**
- [X] Verify Fusion coverage gating in `SequenceProcessor`; add if missing – P0 ✅ **COMPLETE**
- [ ] Introduce `get_panel(disease)` and wire in orchestrator – P1
- [ ] Unified endpoint `/api/clinical_genomics/analyze_variant` (thin wrapper) – P1
- [ ] Caching: Redis for efficacy/toxicity; FE TTL stays 10m – P1
- [ ] EvidenceBand FE consumes provenance breakdown – P1
- [ ] Tests: minimal integration for unified endpoint + efficacy provenance – P1
- [ ] Toxicity real implementation behind flag; stub fallback – P2
- [ ] KG hybrid (ClinVar + AM coverage real; rest stub) – P2

---

## 🧭 DECISIONS LOCKED (defaults if not overridden)

- Orchestrator pattern: Thin Wrapper (Option A)
- EvidenceBand data: Enrich efficacy response (Option C)
- Caching: Hybrid (Redis backend + FE TTL)
- Profile: Hybrid (backend default with FE override)
- KG: Hybrid (critical real fields + stubs)
- Testing: Hybrid (curl + minimal integration tests)

---

## ✅ P0 IMPLEMENTATION COMPLETE (Jan 2025)

### What Was Implemented:

**1. Schema Version Fix** ✅
- **File**: `api/services/efficacy_orchestrator/models.py`
- **Change**: Added `schema_version: str = "v1"` to `EfficacyResponse` dataclass
- **Impact**: Eliminates schema mismatch error when orchestrator passes `schema_version="v1"` to response constructor
- **Status**: ✅ Complete

**2. Confidence Breakdown in Provenance** ✅
- **File**: `api/services/efficacy_orchestrator/orchestrator.py`
- **Change**: Added `response.provenance["confidence_breakdown"]` with top drug's name, confidence, tier, and badges
- **Impact**: Enables frontend `EvidenceBand` component to display confidence without new endpoint
- **Code Location**: Lines 185-191 (after sorting drugs_out)
- **Status**: ✅ Complete

**3. Fusion Coverage Gate** ✅
- **File**: `api/services/efficacy_orchestrator/sequence_processor.py`
- **Change**: Added GRCh38 missense variant gating before invoking `FusionAMScorer`
- **Logic**: 
  - Checks `build` field for "grch38", "hg38", or "38"
  - Checks `consequence` field for "missense"
  - Only variants passing both gates are sent to Fusion scorer
- **Impact**: Prevents Fusion from being called with non-GRCh38 or non-missense variants
- **Status**: ✅ Complete

### Testing & Verification:

**Next Step**: Run quick smoke test to verify P0 fixes:
```bash
cd /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal

# Start backend
venv/bin/uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# In another terminal, test efficacy endpoint
curl -sS -X POST http://127.0.0.1:8000/api/efficacy/predict \
  -H 'Content-Type: application/json' \
  -d '{
    "mutations": [{
      "gene": "BRAF",
      "hgvs_p": "V600E",
      "chrom": "7",
      "pos": 140453136,
      "ref": "T",
      "alt": "A",
      "build": "GRCh38",
      "consequence": "missense_variant"
    }],
    "model_id": "evo2_1b"
  }' | jq '.provenance.confidence_breakdown, .schema_version'
```

**Expected Output**:
- `schema_version`: `"v1"`
- `provenance.confidence_breakdown`: object with `top_drug`, `confidence`, `tier`, `badges`
- No schema mismatch errors

### Files Modified:
1. `api/services/efficacy_orchestrator/models.py` (1 line added)
2. `api/services/efficacy_orchestrator/orchestrator.py` (7 lines added)
3. `api/services/efficacy_orchestrator/sequence_processor.py` (14 lines added)

### Ready for P1:
With P0 complete, the platform is now ready for:
- P1: Disease-aware drug panel
- P1: Unified Clinical Genomics endpoint (thin wrapper)
- P1: EvidenceBand frontend component
- P1: Integration tests for confidence breakdown
