# Scripts Directory Organization

This directory contains utility scripts organized by purpose.

## Directory Structure

### `benchmark/`
Benchmarking and validation scripts for accuracy, SOTA comparisons, and clinical validation.
- `benchmark_*.py` - Benchmark scripts
- `benchmark_moat_vs_gpt.py`, `benchmark_vus_vs_gpt.py` - GPT comparison benchmarks
- `run_hrd_baseline.py`, `run_mm_*.py` - Benchmark runners
- `benchmark_sl/` - Synthetic lethality benchmarks
- `benchmark_common/` - Shared benchmark utilities
- `results/` - Benchmark result files (JSON outputs)

### `trials/`
Clinical trial seeding, management, and quality validation scripts.
- `seed_*.py` - Trial seeding scripts
- `bulk_seed_trials.py` - Bulk seeding operations
- `load_trials_to_neo4j.py` - Neo4j graph database loading
- `tag_trials_moa_batch.py` - MOA tagging
- `check_astradb_trials.py`, `check_astradb_count.py`, `list_astradb_collections.py` - Database utilities
- `find_best_trials_for_ayesha.py` - Ayesha-specific trial finding
- `find_trials_*.py` - Trial search and discovery scripts
- `BULK_SEEDING_INSTRUCTIONS.md`, `TRIAL_MOA_TAGGING_README.md` - Documentation

### `validation/`
Data validation and quality checking scripts.
- `validate_*.py` - Validation scripts
- Large validation dataset (10,000+ files)

### `analysis/`
Data analysis and research scripts.
- `analyze_*.py` - Analysis scripts
- `ayesha_*.py` - Ayesha-specific analysis

### `data_extraction/`
Data extraction and acquisition scripts.
- `extract_*.py` - Extraction scripts
- `reconnaissance_*.py` - Reconnaissance scripts
- `export_*.py` - Export utilities

### `setup/`
Setup, configuration, and utility scripts.
- `create_*.py`, `create_*.sh` - Setup scripts
- `setup_*.sh` - Configuration scripts
- `warm_*.py` - Cache warming
- `bootstrap_*.py` - Bootstrap scripts
- `generate_*.py` - Code generation
- `migrate_*.py` - Migration scripts
- `verify_*.py` - Verification scripts

### `testing/`
Test scripts and validation utilities.
- `test_*.py` - Test scripts
- `validate_*.py` - Validation scripts
- `quick_test.py`, `run_llm_test.py`, `simple_llm_test.py` - Quick test utilities
- `verify_setup.py` - Setup verification

### `dossiers/`
Dossier generation and intelligence scripts.
- `generate_dossiers_from_test_trials.py` - Generate dossiers from test trials
- `generate_enhanced_dossier.py` - Enhanced dossier generation
- `generate_zo_intelligence_dossiers.py` - ZO-style intelligence dossiers
- `generate_zo_intelligence_dossiers_v2.py` - ZO-style intelligence dossiers (v2)
- `generate_zo_style_dossiers.py` - ZO-style dossier generation

### `data/`
Data files and patient profiles.
- `ayesha_patient_profile.py` - Ayesha patient profile data

### Other Directories
- `cohorts/` - Cohort analysis scripts
- `figures/` - Figure generation scripts
- `publication/` - Publication-related scripts
- `tcga_extraction/` - TCGA data extraction
- `yale_tdzd/` - Yale TDZD project scripts

## Documentation
- `README_AYESHA.md` - Ayesha project documentation
- `README_BENCHMARKING.md` - Benchmarking framework documentation

