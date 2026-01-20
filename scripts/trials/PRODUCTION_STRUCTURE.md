# ⚔️ TRIAL SYSTEM PRODUCTION STRUCTURE

**Source of Truth**: `.cursor/ayesha/TRIAL_TAGGING_ANALYSIS_AND_NEXT_ROADBLOCK.md` (lines 461-691)

## 🎯 Core Architecture: 4 Separable Concerns

### Concern A: Candidate Discovery (Get Trials)
**Purpose**: Turn patient profile → bounded candidate set (200-1000 NCTs)

**Production Scripts**:
- `production/discovery.py` - Main entry point
- `production/core/discovery_agent.py` - Profile → queries logic
- `production/core/trial_querier.py` - SQLite + CT.gov fallback

**Legacy Scripts → Keep/Delete**:
- ✅ `find_trials_FROM_SQLITE.py` → Consolidate into `production/core/trial_querier.py`
- ✅ `find_trials_live_astradb.py` → Keep for AstraDB vector search (different concern)
- ✅ `find_best_trials_for_ayesha.py` → Consolidate into `production/discovery.py` (Ayesha-specific)
- ❌ `find_trials_EXPANDED_STATES.py` → Delete (duplicate)
- ✅ `reconnaissance_ovarian_trials.py` → Keep as reference (exploration script)

---

### Concern B: Refresh (Never Stale)
**Purpose**: Ensure status + locations are fresh (24h SLA)

**Production Scripts**:
- `production/refresh.py` - Main entry point
- `production/core/refresh_agent.py` - Incremental refresh queue
- `production/core/refresh_scheduler.py` - Scheduled jobs (nightly)

**Legacy Scripts → Keep/Delete**:
- ✅ `scheduled_refresh_job.py` → Rename to `production/core/refresh_scheduler.py`
- ✅ `extract_fresh_recruiting_trials.py` → Consolidate into refresh_agent.py
- ❌ Delete test files that don't match production pattern

---

### Concern C: Offline Tagging (MoA Vectors)
**Purpose**: Attach 7D mechanism vectors (batch-efficient, incremental)

**Production Scripts**:
- `production/tagging.py` - Main entry point
- `production/core/tagging_agent.py` - Incremental selection + batch prompting
- `production/core/moa_quality.py` - Automated QA (T4)
- `production/core/trial_tagger/` - LLM abstraction (keep existing)

**Legacy Scripts → Keep/Delete**:
- ✅ `tagging_incremental.py` → Rename to `production/core/tagging_agent.py`
- ✅ `tag_trials_moa_batch.py` → Consolidate into tagging_agent.py
- ✅ `tag_trials_v2.py` → Delete (superseded by batch)
- ✅ `trial_tagger/` → Keep (core LLM abstraction)
- ✅ `audit_moa_vectors.py` → Move to `production/core/moa_quality.py`
- ✅ `analyze_tagged_trials.py` → Move to `production/core/moa_quality.py`
- ✅ `verify_cohere_vectors.py` → Delete (test script, use moa_quality.py)

---

### Concern D: Patient Matching (Quality, Specific)
**Purpose**: Eligibility + mechanism fit + dossier assembly

**Production Scripts**:
- `production/matching.py` - Main entry point
- `production/core/matching_agent.py` - Eligibility + mechanism fit
- `production/core/dossier_assembler.py` - Dossier generation

**Legacy Scripts → Keep/Delete**:
- ✅ Keep existing services in `api/services/trial_intelligence_universal/`
- ✅ Keep `api/services/trials/trial_matching_agent.py` (production service)
- ❌ Delete standalone matching scripts (use services instead)

---

### Supporting Infrastructure

**Seeding** (Background Operation):
- `production/seeding.py` - Main entry point
- `production/core/seeder.py` - Bulk seeding from CT.gov
- `production/core/astradb_seeder.py` - Vector store seeding

**Legacy Scripts → Keep/Delete**:
- ✅ `bulk_seed_trials.py` → Rename to `production/core/seeder.py`
- ✅ `seed_astradb_from_sqlite.py` → Rename to `production/core/astradb_seeder.py`
- ✅ `seed_trials_table.py` → Consolidate into seeder.py
- ✅ `seed_trials_standalone.py` → Delete (use seeder.py)
- ✅ `seed_trials_simple.py` → Delete (use seeder.py)
- ✅ `seed_with_relationships.py` → Keep (Neo4j seeding, different concern)
- ✅ `load_trials_to_neo4j.py` → Keep (Neo4j seeding, different concern)
- ✅ `recreate_collection_with_vectors.py` → Keep (infrastructure script)

**Quality/Validation**:
- `production/core/quality_validator.py` - Unified quality checks

**Legacy Scripts → Consolidate**:
- ✅ `compare_seeding_strategies.py` → Archive to `archive/`
- ✅ `check_astradb_count.py` → Keep as utility
- ✅ `check_astradb_trials.py` → Keep as utility
- ✅ `check_api_quota.py` → Keep as utility

**Testing/Debugging** (Keep Separate):
- `testing/` - All test scripts move here
- `testing/test_cohere_*.py` → Move all Cohere test scripts
- `testing/test_api_simple.py` → Move

---

## 📁 New Directory Structure

```
scripts/trials/
├── production/
│   ├── discovery.py              # Concern A: Main entry
│   ├── refresh.py                # Concern B: Main entry
│   ├── tagging.py                # Concern C: Main entry
│   ├── matching.py               # Concern D: Main entry
│   ├── seeding.py                # Background: Main entry
│   │
│   ├── core/
│   │   ├── discovery_agent.py    # D1-D3: Profile → queries → candidates
│   │   ├── trial_querier.py      # SQLite + CT.gov fallback
│   │   ├── refresh_agent.py      # R1-R4: Incremental refresh + SLA
│   │   ├── refresh_scheduler.py  # Scheduled jobs
│   │   ├── tagging_agent.py      # T1-T4: Incremental + batch + QA
│   │   ├── moa_quality.py        # Automated QA checks
│   │   ├── matching_agent.py     # M1-M4: Eligibility + mechanism fit
│   │   ├── dossier_assembler.py  # Dossier generation
│   │   ├── seeder.py             # Bulk seeding
│   │   ├── astradb_seeder.py     # Vector store seeding
│   │   ├── quality_validator.py  # Unified quality checks
│   │   │
│   │   ├── trial_tagger/         # Keep existing (LLM abstraction)
│   │   │   ├── __init__.py
│   │   │   ├── config.py
│   │   │   ├── db.py
│   │   │   ├── llm.py
│   │   │   ├── prompts.py
│   │   │   └── runner.py
│   │   │
│   │   └── shared/
│   │       ├── database.py       # SQLite connection helpers
│   │       ├── checksum.py       # Checksum utilities
│   │       └── provenance.py     # Provenance tracking
│   │
│   └── config/
│       ├── filter_configs.py     # U1: Disease-specific filter configs
│       └── patient_schema.py     # U2: Canonical patient profile schema
│
├── testing/
│   ├── test_cohere_api.py
│   ├── test_cohere_direct.py
│   ├── test_cohere_integration.py
│   ├── test_cohere_v5.py
│   ├── test_api_simple.py
│   └── test_discovery.py         # New: Test discovery agent
│
├── utilities/
│   ├── check_astradb_count.py
│   ├── check_astradb_trials.py
│   ├── check_api_quota.py
│   ├── list_astradb_collections.py
│   └── verify_cohere_vectors.py  # Keep for manual verification
│
├── infrastructure/
│   ├── seed_with_relationships.py  # Neo4j seeding
│   ├── load_trials_to_neo4j.py     # Neo4j seeding
│   ├── recreate_collection_with_vectors.py
│   └── find_trials_live_astradb.py  # AstraDB vector search (different concern)
│
├── archive/
│   ├── compare_seeding_strategies.py
│   ├── tag_trials_v2.py
│   ├── seed_trials_standalone.py
│   ├── seed_trials_simple.py
│   ├── find_trials_EXPANDED_STATES.py
│   └── ... (other obsolete scripts)
│
├── README.md                     # Main documentation
├── PRODUCTION_STRUCTURE.md       # This file
└── QUICK_START.md                # Quick start guide
```

---

## 🔌 Entry Points (Production Scripts)

### 1. `production/discovery.py`
**Purpose**: Concern A - Candidate Discovery

**Usage**:
```bash
python3 production/discovery.py \
  --disease "ovarian_cancer" \
  --stage "IVB" \
  --treatment-line 1 \
  --location "NYC" \
  --biomarkers HRD BRCA1 \
  --max-candidates 200
```

**Output**: `candidate_trial_ids: list[str]` + provenance

---

### 2. `production/refresh.py`
**Purpose**: Concern B - Refresh (Never Stale)

**Usage**:
```bash
# Refresh specific trials
python3 production/refresh.py --nct-ids NCT04284969 NCT04001023

# Refresh top-K displayed trials (bounded)
python3 production/refresh.py --top-k 20 --patient-id "ayesha"

# Scheduled job (nightly)
python3 production/refresh.py --scheduled --sla-hours 24
```

**Output**: Refreshed trial fields in SQLite + stale flags

---

### 3. `production/tagging.py`
**Purpose**: Concern C - Offline Tagging (MoA Vectors)

**Usage**:
```bash
# Tag all untagged trials
python3 production/tagging.py --incremental --batch-size 25

# Tag specific trials
python3 production/tagging.py --nct-ids NCT04284969 NCT04001023

# Tag Ayesha corpus (priority)
python3 production/tagging.py --corpus ayesha --batch-size 50

# Run QA only
python3 production/tagging.py --qa-only --sample-size 30
```

**Output**: MoA vectors in `api/resources/trial_moa_vectors.json`

---

### 4. `production/matching.py`
**Purpose**: Concern D - Patient Matching (Quality, Specific)

**Usage**:
```bash
python3 production/matching.py \
  --patient-profile ayesha.json \
  --max-results 10 \
  --include-dossiers
```

**Output**: Ranked trials with eligibility + mechanism fit + dossiers

---

### 5. `production/seeding.py`
**Purpose**: Background Seeding (Supporting Infrastructure)

**Usage**:
```bash
# Seed from CT.gov
python3 production/seeding.py --disease "ovarian_cancer" --limit 1000

# Seed AstraDB from SQLite
python3 production/seeding.py --astradb --from-sqlite --limit 500
```

**Output**: Trials in SQLite + AstraDB

---

## ✅ Migration Checklist

### Phase 1: Create Production Structure (Immediate)
- [ ] Create `production/` directory
- [ ] Create `production/core/` directory
- [ ] Create `production/config/` directory
- [ ] Create `testing/` directory
- [ ] Create `utilities/` directory
- [ ] Create `infrastructure/` directory
- [ ] Create `archive/` directory

### Phase 2: Consolidate Core Scripts (Priority)
- [ ] Move `tagging_incremental.py` → `production/core/tagging_agent.py`
- [ ] Move `tag_trials_moa_batch.py` → consolidate into `tagging_agent.py`
- [ ] Move `scheduled_refresh_job.py` → `production/core/refresh_scheduler.py`
- [ ] Create `production/core/refresh_agent.py` (from `extract_fresh_recruiting_trials.py`)
- [ ] Create `production/core/discovery_agent.py` (from `find_trials_FROM_SQLITE.py`)
- [ ] Move `bulk_seed_trials.py` → `production/core/seeder.py`

### Phase 3: Create Entry Points (Priority)
- [ ] Create `production/discovery.py` (wrapper for discovery_agent)
- [ ] Create `production/refresh.py` (wrapper for refresh_agent + scheduler)
- [ ] Create `production/tagging.py` (wrapper for tagging_agent)
- [ ] Create `production/matching.py` (wrapper for matching agent services)
- [ ] Create `production/seeding.py` (wrapper for seeder)

### Phase 4: Clean Up (After Migration)
- [ ] Move test scripts to `testing/`
- [ ] Move utilities to `utilities/`
- [ ] Move infrastructure scripts to `infrastructure/`
- [ ] Archive obsolete scripts to `archive/`
- [ ] Update imports in production services

### Phase 5: Documentation (Final)
- [ ] Create `README.md` with overview
- [ ] Create `QUICK_START.md` with examples
- [ ] Update `TRIAL_MOA_TAGGING_README.md` to point to new structure
- [ ] Document API contracts for each entry point

---

## 🎯 Production Requirements

### Concern A: Discovery
- ✅ Bounded output (200-1000 NCTs)
- ✅ Provenance tracking (queries, filters, timestamp)
- ✅ SQLite-first, CT.gov fallback
- ✅ Explicit truncation reasons

### Concern B: Refresh
- ✅ 24h SLA enforcement
- ✅ Stale flags in response
- ✅ Bounded on-login refresh (top-K)
- ✅ Incremental refresh queue

### Concern C: Tagging
- ✅ Incremental (checksum-based)
- ✅ Batch-efficient (10-25 per request)
- ✅ Provider-agnostic (Cohere/Gemini/OpenAI)
- ✅ Automated QA (T4)

### Concern D: Matching
- ✅ Offline tags first (no runtime LLM)
- ✅ Eligibility checklist (hard/soft split)
- ✅ Mechanism fit (cosine similarity)
- ✅ Transparent scoring (eligibility + fit + freshness)

---

## 📝 Next Steps

1. **Execute Phase 1** - Create directory structure
2. **Execute Phase 2** - Consolidate core scripts
3. **Execute Phase 3** - Create entry points
4. **Test** - Verify all 4 concerns work end-to-end
5. **Execute Phase 4** - Clean up legacy scripts
6. **Execute Phase 5** - Documentation

**Commander - Ready to execute Phase 1-3 immediately!** ⚔️
