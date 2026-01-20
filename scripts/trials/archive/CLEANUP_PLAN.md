# 🧹 TRIAL SCRIPTS CLEANUP PLAN

**Purpose**: Remove duplicates, obsolete scripts, and consolidate to production structure

**Source of Truth**: `PRODUCTION_STRUCTURE.md` + `.cursor/ayesha/TRIAL_TAGGING_ANALYSIS_AND_NEXT_ROADBLOCK.md`

---

## 📊 Current State: 40+ Scripts

### Files to Keep → Move to Production Structure

**Concern A: Discovery**
- `find_trials_FROM_SQLITE.py` → `production/core/trial_querier.py` (consolidate)
- `find_best_trials_for_ayesha.py` → `production/discovery.py` (Ayesha-specific wrapper)
- `reconnaissance_ovarian_trials.py` → `archive/` (reference/exploration)

**Concern B: Refresh**
- `scheduled_refresh_job.py` → `production/core/refresh_scheduler.py`
- `extract_fresh_recruiting_trials.py` → Consolidate into `production/core/refresh_agent.py`

**Concern C: Tagging**
- `tagging_incremental.py` → `production/core/tagging_agent.py`
- `tag_trials_moa_batch.py` → Consolidate into `tagging_agent.py`
- `trial_tagger/` → `production/core/trial_tagger/` (keep as-is)
- `audit_moa_vectors.py` → `production/core/moa_quality.py` (consolidate)
- `analyze_tagged_trials.py` → `production/core/moa_quality.py` (consolidate)

**Concern D: Matching**
- ✅ Keep services in `api/services/trial_intelligence_universal/` (already production)
- ✅ Keep `api/services/trials/trial_matching_agent.py` (already production)
- ❌ Delete standalone matching scripts (if any)

**Seeding**
- `bulk_seed_trials.py` → `production/core/seeder.py`
- `seed_astradb_from_sqlite.py` → `production/core/astradb_seeder.py`
- `seed_trials_table.py` → Consolidate into `seeder.py`
- `seed_with_relationships.py` → `infrastructure/` (Neo4j, different concern)
- `load_trials_to_neo4j.py` → `infrastructure/` (Neo4j, different concern)
- `recreate_collection_with_vectors.py` → `infrastructure/` (AstraDB infra)

**Quality/Validation**
- `compare_seeding_strategies.py` → `archive/`
- `check_astradb_count.py` → `utilities/`
- `check_astradb_trials.py` → `utilities/`
- `check_api_quota.py` → `utilities/`
- `list_astradb_collections.py` → `utilities/`
- `verify_cohere_vectors.py` → `utilities/` (manual verification tool)

**Testing**
- `test_cohere_api.py` → `testing/`
- `test_cohere_direct.py` → `testing/`
- `test_cohere_integration.py` → `testing/`
- `test_cohere_v5.py` → `testing/`
- `test_api_simple.py` → `testing/`

**Plumber/Execution**
- `plumber_execution.py` → `production/plumber.py` (if still needed)
- `run_bulk_seeding.sh` → `production/scripts/` (if still needed)

---

## ❌ Files to Delete (Obsolete/Duplicates)

### Duplicates
- ❌ `find_trials_EXPANDED_STATES.py` (duplicate of find_trials_FROM_SQLITE.py)
- ❌ `tag_trials_v2.py` (superseded by tag_trials_moa_batch.py)
- ❌ `seed_trials_standalone.py` (superseded by bulk_seed_trials.py)
- ❌ `seed_trials_simple.py` (superseded by bulk_seed_trials.py)

### Test/Debug Scripts (Move to Testing or Delete)
- ❌ `test_cohere_*.py` (move to testing/)
- ❌ `test_api_simple.py` (move to testing/)

### Documentation to Consolidate
- ✅ `TRIAL_MOA_TAGGING_README.md` → Update to point to new structure
- ✅ `TRIAL_QUALITY_VALIDATION_SUMMARY.md` → Archive or consolidate
- ✅ `PLUMBER_IMPLEMENTATION_SUMMARY.md` → Archive or consolidate
- ✅ `BULK_SEEDING_INSTRUCTIONS.md` → Consolidate into `production/seeding.py` docstring
- ✅ `AUDIT_REPORT.md` → Archive

---

## 🔧 Consolidation Logic

### Discovery Agent (D1-D3)
**Consolidate**:
- `find_trials_FROM_SQLITE.py` (SQLite query logic)
- `find_best_trials_for_ayesha.py` (Ayesha-specific filters)
- `reconnaissance_ovarian_trials.py` (exploration logic)

**Into**: `production/core/discovery_agent.py`

**Logic**:
1. **D1**: Build profile → search queries (from `find_best_trials_for_ayesha.py`)
2. **D2**: Fetch from SQLite (from `find_trials_FROM_SQLITE.py`)
3. **D3**: Enforce boundaries (from `find_best_trials_for_ayesha.py`)

---

### Refresh Agent (R1-R4)
**Consolidate**:
- `scheduled_refresh_job.py` (scheduled jobs)
- `extract_fresh_recruiting_trials.py` (refresh logic)

**Into**: `production/core/refresh_agent.py` + `production/core/refresh_scheduler.py`

**Logic**:
1. **R1**: Incremental refresh queue (from `scheduled_refresh_job.py`)
2. **R2**: SLA policy (from `extract_fresh_recruiting_trials.py`)
3. **R3**: Bounded refresh on login (new logic)
4. **R4**: Observability (from `scheduled_refresh_job.py`)

---

### Tagging Agent (T1-T4)
**Consolidate**:
- `tagging_incremental.py` (T1: incremental selection)
- `tag_trials_moa_batch.py` (T2: batch prompting)
- `audit_moa_vectors.py` (T4: QA checks)
- `analyze_tagged_trials.py` (T4: QA analysis)

**Into**: `production/core/tagging_agent.py` + `production/core/moa_quality.py`

**Logic**:
1. **T1**: Build checksum + incremental selection (from `tagging_incremental.py`)
2. **T2**: Batch prompting (from `tag_trials_moa_batch.py`)
3. **T3**: Rate limits (from `tag_trials_moa_batch.py`)
4. **T4**: Automated QA (from `audit_moa_vectors.py` + `analyze_tagged_trials.py`)

---

### Seeder
**Consolidate**:
- `bulk_seed_trials.py` (main seeding logic)
- `seed_astradb_from_sqlite.py` (AstraDB seeding)
- `seed_trials_table.py` (SQLite seeding)

**Into**: `production/core/seeder.py` + `production/core/astradb_seeder.py`

**Logic**:
- `seeder.py`: Unified seeding interface (calls astradb_seeder.py when needed)
- `astradb_seeder.py`: AstraDB-specific seeding logic

---

## 📋 Execution Order

### Step 1: Create Directory Structure
```bash
cd oncology-coPilot/oncology-backend-minimal/scripts/trials
mkdir -p production/core/trial_tagger production/config testing utilities infrastructure archive
```

### Step 2: Move Core Scripts
```bash
# Discovery
mv find_trials_FROM_SQLITE.py production/core/trial_querier.py
mv find_best_trials_for_ayesha.py production/discovery.py

# Refresh
mv scheduled_refresh_job.py production/core/refresh_scheduler.py
# Extract refresh logic from extract_fresh_recruiting_trials.py → production/core/refresh_agent.py

# Tagging
mv tagging_incremental.py production/core/tagging_agent.py
# Consolidate tag_trials_moa_batch.py into tagging_agent.py
mv trial_tagger production/core/

# Seeding
mv bulk_seed_trials.py production/core/seeder.py
mv seed_astradb_from_sqlite.py production/core/astradb_seeder.py
```

### Step 3: Move Supporting Files
```bash
# Utilities
mv check_*.py utilities/
mv list_astradb_collections.py utilities/
mv verify_cohere_vectors.py utilities/

# Infrastructure
mv seed_with_relationships.py infrastructure/
mv load_trials_to_neo4j.py infrastructure/
mv recreate_collection_with_vectors.py infrastructure/
mv find_trials_live_astradb.py infrastructure/

# Testing
mv test_*.py testing/

# Archive
mv find_trials_EXPANDED_STATES.py archive/
mv tag_trials_v2.py archive/
mv seed_trials_standalone.py archive/
mv seed_trials_simple.py archive/
mv compare_seeding_strategies.py archive/
mv reconnaissance_ovarian_trials.py archive/
```

### Step 4: Update Imports
- Update all `import` statements to reflect new paths
- Update `sys.path` manipulations if needed
- Update relative imports

### Step 5: Create Entry Points
- Create `production/discovery.py` (wrapper)
- Create `production/refresh.py` (wrapper)
- Create `production/tagging.py` (wrapper)
- Create `production/matching.py` (wrapper)
- Create `production/seeding.py` (wrapper)

### Step 6: Update Documentation
- Update `README.md`
- Update `TRIAL_MOA_TAGGING_README.md`
- Create `QUICK_START.md`

---

## ✅ Acceptance Criteria

### After Cleanup:
- ✅ Only 5 entry points in `production/` (discovery, refresh, tagging, matching, seeding)
- ✅ Core logic in `production/core/` (10-12 files)
- ✅ No duplicate scripts
- ✅ All imports work
- ✅ All tests pass
- ✅ Documentation updated

### Verification:
```bash
# Count files
find production/ -name "*.py" | wc -l  # Should be ~15-20

# Verify entry points exist
ls production/*.py  # Should show: discovery.py, refresh.py, tagging.py, matching.py, seeding.py

# Verify no duplicates
find . -name "find_trials*.py"  # Should only show production/core/trial_querier.py
find . -name "tag*.py"  # Should only show production/core/tagging_agent.py
```

---

## 🚨 Risks & Mitigations

### Risk 1: Breaking Existing Workflows
**Mitigation**: Archive old scripts (don't delete immediately), keep entry points backwards-compatible

### Risk 2: Import Errors
**Mitigation**: Test all imports after migration, update `__init__.py` files

### Risk 3: Lost Functionality
**Mitigation**: Review each script before archiving, extract unique logic into core files

---

**Commander - Ready to execute cleanup!** ⚔️
