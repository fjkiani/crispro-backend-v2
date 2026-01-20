# Scripts and Tests Organization Summary

**Date**: January 2025  
**Status**: ✅ Complete

## Overview

Organized all scripts and test files into logical folder structures for better maintainability and discoverability.

---

## Scripts Directory (`scripts/`)

### New Organization Structure

```
scripts/
├── benchmark/          # Benchmarking scripts
│   ├── benchmark_*.py
│   ├── run_hrd_baseline.py
│   ├── run_mm_*.py
│   ├── benchmark_sl/   # Synthetic lethality benchmarks
│   └── benchmark_common/
│
├── trials/              # Trial seeding and management
│   ├── seed_*.py
│   ├── bulk_seed_trials.py
│   ├── load_trials_to_neo4j.py
│   ├── tag_trials_moa_batch.py
│   ├── check_astradb_trials.py
│   ├── run_bulk_seeding.sh
│   └── *.md (documentation)
│
├── validation/          # Data validation scripts
│   └── (10,000+ validation files)
│
├── analysis/            # Analysis scripts
│   ├── analyze_*.py
│   └── ayesha_*.py
│
├── data_extraction/     # Data extraction
│   ├── export_*.py
│   └── cache_warm_results.json
│
├── setup/               # Setup and utilities
│   ├── create_*.py
│   ├── setup_*.sh
│   ├── warm_*.py
│   ├── bootstrap_*.py
│   ├── generate_*.py
│   ├── migrate_*.py
│   └── verify_*.py
│
├── testing/             # Test scripts
│   ├── test_*.py
│   └── validate_*.py
│
└── (existing subdirs)   # cohorts/, figures/, publication/, etc.
```

### Files Moved

**To `trials/`**:
- All `seed_*.py` files
- `bulk_seed_trials.py`
- `load_trials_to_neo4j.py`
- `tag_trials_moa_batch.py`
- `check_astradb_trials.py`
- `list_astradb_collections.py`
- `recreate_collection_with_vectors.py`
- `compare_seeding_strategies.py`
- `extract_fresh_recruiting_trials.py`
- `reconnaissance_ovarian_trials.py`
- `run_bulk_seeding.sh`
- Trial-related documentation

**To `benchmark/`**:
- `benchmark_brca_tp53_proxy.py`
- `benchmark_clinical_validation.py`
- `benchmark_mbd4_tp53_accuracy.py`
- `benchmark_sota_melanoma.py`
- `benchmark_sota_mm.py`
- `benchmark_sota_ovarian.py`
- `run_hrd_baseline.py`
- `run_mm_ablations.py`
- `run_mm_baseline.py`

**To `validation/`**:
- `validate_*.py` files
- `validate_*.sh` files

**To `analysis/`**:
- `analyze_outcome_by_pathway.py`
- `ayesha_mbd4_tp53_hgsoc_analysis.py`

**To `data_extraction/`**:
- `export_50_candidates.py`
- `cache_warm_results.json`

**To `setup/`**:
- `create_*.py` and `create_*.sh`
- `setup_*.sh`
- `warm_compound_cache.py`
- `bootstrap_calibration.py`
- `generate_calibration_plots.py`
- `migrate_existing_data.py`
- `verify_supabase_auth.py`
- `test_auth_endpoints.sh`

**To `testing/`**:
- `test_*.py` files from scripts/
- `validate_*.py` files

---

## Tests Directory (`tests/`)

### New Organization Structure

```
tests/
├── integration/         # E2E and integration tests
│   ├── test_*_integration.py
│   ├── test_*_e2e.py
│   ├── test_orchestrator_e2e_pipeline.py
│   ├── test_agents_e2e.py
│   └── test_research_intelligence_e2e.py
│
├── smoke/               # Smoke tests
│   ├── smoke_*.py
│   └── test_*_smoke.py
│
├── runners/             # Test runners
│   ├── run_integration_tests.py
│   ├── run_universal_tests.py
│   └── show_results.py
│
├── archive/             # Moved from root
│   ├── test_*.py (from root)
│   ├── test_*.sh (from root)
│   └── TEST_*.md (from root)
│
├── unit/                # Unit tests (folder created, most tests remain in root)
│
└── (existing subdirs)   # agent_2_refresh/, clinical_genomics/, etc.
```

### Files Moved

**To `integration/`**:
- `test_*_integration.py`
- `test_*_e2e.py`
- `test_orchestrator_e2e_pipeline.py`
- `test_agents_e2e.py`
- `test_complete_care_universal_integration.py`
- `test_research_intelligence_e2e.py`

**To `smoke/`**:
- `smoke_mdt_live.py`
- `test_ayesha_e2e_smoke.py`

**To `runners/`**:
- `run_integration_tests.py`
- `run_universal_tests.py`
- `show_results.py`

**To `archive/`** (from root directory):
- All `test_*.py` files from root
- All `test_*.sh` files from root
- All `TEST_*.md` files from root

---

## Root Directory Cleanup

### Files Moved from Root

**Test Files → `tests/archive/`**:
- `test_after_restart.sh`
- `test_api_integration.py`
- `test_comprehensive_analysis.py`
- `test_e2e_toxicity_moat.sh`
- `test_end_to_end.sh`
- `test_food_validator_boosts.py`
- `test_jr2_pipeline.py`
- `test_llm_toxicity.py`
- `test_moat_integration.py`
- `test_modular_pipeline.py`
- `test_phase0_phase1.py`
- `test_research_intelligence.py`
- `test_sae_phase3_e2e.py`
- `test_toxicity_async.py`
- `test_toxicity_food_integration.py`
- `test_toxicity_validation.py`
- `test_universal_endpoint.py`
- `test_universal_orchestrator.py` → `tests/`
- `test_advanced_queries_standalone.py`
- `TEST_RESULTS_PHASE0_PHASE1.md`
- `TEST_RESULTS_SUMMARY.md`

**Benchmark Files → `scripts/benchmark/`**:
- `benchmark_moat_vs_gpt.py`
- `benchmark_vus_vs_gpt.py`
- `benchmark_metrics.json` → `scripts/benchmark/results/`
- `benchmark_output.json` → `scripts/benchmark/results/`
- `benchmark_raw.json` → `scripts/benchmark/results/`

**Trial Finding Scripts → `scripts/trials/`**:
- `find_best_trials_for_ayesha.py`
- `find_trials_EXPANDED_STATES.py`
- `find_trials_FROM_SQLITE.py`
- `find_trials_live_astradb.py`
- `check_astradb_count.py`

**Dossier Generation → `scripts/dossiers/`**:
- `generate_dossiers_from_test_trials.py`
- `generate_enhanced_dossier.py`
- `generate_zo_intelligence_dossiers.py`
- `generate_zo_intelligence_dossiers_v2.py`
- `generate_zo_style_dossiers.py`

**Test Utilities → `scripts/testing/`**:
- `quick_test.py`
- `run_llm_test.py`
- `simple_llm_test.py`
- `verify_setup.py`

**Data Files → `scripts/data/`**:
- `ayesha_patient_profile.py`

**Test Fixtures → `tests/fixtures/`**:
- `golden_snapshot_braf_v600e.json`

**Documentation → `docs/`**:
- `BACKEND_FIXES_SUMMARY.md`
- `ORGANIZATION_OPPORTUNITIES.md`
- `PAPER_DRAFT.md`
- `PATHWAY_NORMALIZATION_FIX_SUMMARY.md`
- `PHASE0_PHASE1_PHASE2_PROGRESS.md`
- `PRE_BENCHMARK_AUDIT.md`
- `PUBLICATION_STATUS.md`
- `REPRODUCIBILITY.md`
- `ROOT_CAUSE_ANALYSIS_COMPREHENSIVE.md`
- `SUBMISSION_CHECKLIST.md`
- `SUGGESTED_REVIEWERS.md`
- `VUS_EXPLORER_KG_INTEGRATION_README.md`
- `GITHUB_CODE_AUDIT_AND_STRATEGY.md`
- `GITHUB_PUBLICATION_STRATEGY.md`

**Benchmark Results → `docs/benchmarks/`**:
- `benchmark_metrics.json`
- `benchmark_output.json`
- `benchmark_raw.json`
- `guidance_tier_eval_results.json`
- `variant_auroc_results.json`

**Configuration → `config/`**:
- `cspell.json` - Spell checker configuration
- `clin_req.json` - Clinical requirements configuration

**Logs → `logs/`**:
- `backend.log` - Backend application logs

### Files Remaining in Root

The following files remain in root as they are application entry points or configuration:
- `main.py` - Application entry point
- `main_minimal.py` - Minimal application entry point
- `vercel.json` - Vercel deployment configuration
- `vercel.tmp.json` - Temporary Vercel configuration
- `ORGANIZATION_SUMMARY.md` - This file (organization documentation)

---

## Documentation Created

1. **`scripts/README.md`** - Complete documentation of scripts directory structure
2. **`tests/README.md`** - Complete documentation of tests directory structure
3. **`ORGANIZATION_SUMMARY.md`** (this file) - Summary of organization changes

---

## Benefits

1. **Better Discoverability**: Files organized by purpose, easier to find
2. **Reduced Clutter**: Root directory cleaned up
3. **Logical Grouping**: Related scripts grouped together
4. **Maintainability**: Clear structure for future additions
5. **Documentation**: README files explain organization

---

## Next Steps (Optional)

1. Review archived test files in `tests/archive/` - determine if any should be moved to active test directories
2. Consider creating subdirectories in `unit/` for component-specific unit tests
3. Review `scripts/testing/` - determine if these should be moved to `tests/` instead
4. Update any hardcoded paths in scripts that reference moved files

---

## Notes

- All file moves preserve original file names
- Existing subdirectories (benchmark/, cohorts/, etc.) were preserved
- README files in subdirectories were preserved
- No files were deleted, only reorganized

