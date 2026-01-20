# Tests Directory Organization

This directory contains test files organized by test type and purpose.

## Directory Structure

### `integration/`
End-to-end integration tests that test multiple components together.
- `test_*_integration.py` - Integration test suites
- `test_*_e2e.py` - End-to-end tests
- `test_orchestrator_e2e_pipeline.py` - Orchestrator pipeline tests
- `test_agents_e2e.py` - Agent integration tests
- `test_complete_care_universal_integration.py` - Complete care flow tests
- `test_research_intelligence_e2e.py` - Research intelligence E2E tests

### `unit/`
Unit tests for individual components (most test files remain here).
- `test_*.py` - Unit test files
- Organized by component/service being tested

### `smoke/`
Smoke tests for quick validation of critical paths.
- `smoke_*.py` - Smoke test scripts
- `test_*_smoke.py` - Smoke test suites
- `test_ayesha_e2e_smoke.py` - Ayesha smoke tests

### `runners/`
Test runner scripts and utilities.
- `run_integration_tests.py` - Integration test runner
- `run_universal_tests.py` - Universal test runner
- `show_results.py` - Test result display utility

### `archive/`
Deprecated or moved test files from root directory.
- `test_*.py` - Old test files moved from root
- `test_*.sh` - Old test scripts
- `TEST_*.md` - Old test result documentation

### Existing Subdirectories
- `agent_2_refresh/` - Agent 2 refresh tests
- `clinical_genomics/` - Clinical genomics endpoint tests
- `design/` - Design service tests
- `metastasis/` - Metastasis-related tests
- `metastasis_interception/` - Metastasis interception tests
- `safety/` - Safety and off-target tests

## Test Categories

### By Component
- **Ayesha**: `test_ayesha_*.py`
- **Efficacy**: `test_efficacy_*.py`
- **Evidence**: `test_evidence_*.py`
- **Food Validator**: `test_food_*.py`, `test_compound_*.py`
- **Orchestrator**: `test_orchestrator_*.py`
- **Resistance**: `test_resistance_*.py`
- **SAE**: `test_sae_*.py`
- **Sporadic**: `test_sporadic_*.py`
- **Safety**: `test_safety_*.py`
- **Toxicity**: `test_toxicity_*.py`
- **Trials**: `test_trial_*.py`, `test_advanced_trial_*.py`
- **Universal**: `test_universal_*.py`
- **VUS**: `test_vus_*.py`

### By Test Type
- **E2E**: End-to-end integration tests
- **Integration**: Multi-component integration tests
- **Unit**: Individual component tests
- **Smoke**: Quick validation tests
- **Performance**: Performance and load tests
- **Validation**: Data validation tests

## Running Tests

### Integration Tests
```bash
python tests/runners/run_integration_tests.py
```

### Universal Tests
```bash
python tests/runners/run_universal_tests.py
```

### Smoke Tests
```bash
python tests/smoke/smoke_mdt_live.py
```

### Individual Test Suites
```bash
pytest tests/unit/test_ayesha_trials.py
pytest tests/integration/test_orchestrator_e2e_pipeline.py
```




















