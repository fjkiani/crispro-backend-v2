# Ayesha Care Plan - Modular Architecture

## Overview

This module replaces the monolithic 1700+ line `ayesha_orchestrator_v2.py` with a modular, service-based architecture. Each component has a single responsibility and can be tested, maintained, and extended independently.

## Architecture

```
api/services/ayesha_care_plan/
├── __init__.py              # Module exports
├── schemas.py               # Request/Response models
├── orchestrator.py          # Thin coordinator (~400 lines)
├── trial_service.py         # Trial fetching/ranking
├── soc_service.py           # SOC recommendations
├── ca125_service.py         # CA-125 intelligence
├── drug_efficacy_service.py # WIWFM (drug efficacy)
├── food_service.py          # Food validator + supplements
├── resistance_service.py    # Resistance playbook + prophet
├── io_service.py            # IO selection
├── sae_service.py           # SAE Phase 1 and 2
└── utils.py                 # Shared utilities
```

## Components

### 1. Schemas (`schemas.py`)
- `CompleteCareV2Request`: Request model with all patient data and flags
- `CompleteCareV2Response`: Response model with all care plan components

### 2. Orchestrator (`orchestrator.py`)
- **Thin coordinator** (~400 lines vs 1700+)
- Coordinates service calls in the correct order
- Handles error propagation
- Generates summary and provenance

### 3. Service Modules

#### Trial Service (`trial_service.py`)
- Uses intent-gated ranking (`rank_trials_for_ayesha`)
- Fallback to mechanism-fit ranking if needed
- Returns ranked trials with scores and reasoning

#### SOC Service (`soc_service.py`)
- NCCN-aligned SOC recommendations
- Handles ascites/peritoneal disease add-ons
- Returns regimen with evidence

#### CA-125 Service (`ca125_service.py`)
- Wraps existing `ca125_intelligence` service
- Analyzes CA-125 trends and resistance signals

#### Drug Efficacy Service (`drug_efficacy_service.py`)
- Calls WIWFM endpoint
- Handles "awaiting NGS" case
- Returns drug rankings with confidence

#### Food Service (`food_service.py`)
- Food/supplement validation
- Supplement recommendations based on SOC drugs
- Extracts drugs from regimen strings

#### Resistance Service (`resistance_service.py`)
- Resistance playbook (next-line planning)
- Resistance Prophet (early warning 3-6 months)
- Manager Q7: Opt-in via `include_resistance_prediction`

#### IO Service (`io_service.py`)
- Safest IO regimen selection
- irAE risk stratification
- Eligibility signals

#### SAE Service (`sae_service.py`)
- **Phase 1**: Next-test recommender, hint tiles, mechanism map
- **Phase 2**: SAE features computation, resistance detection
- Extracts mechanism vector from WIWFM response
- Extracts insights bundle from insights endpoints

### 4. Utils (`utils.py`)
- `extract_insights_bundle()`: Calls insights endpoints (functionality, chromatin, essentiality, regulatory)
- `extract_drugs_from_regimen()`: Parses SOC regimen strings to extract drug names/classes

## Usage

### Router (Simplified)
```python
from api.services.ayesha_care_plan.schemas import CompleteCareV2Request, CompleteCareV2Response
from api.services.ayesha_care_plan.orchestrator import get_ayesha_care_plan_orchestrator

@router.post("/complete_care_v2", response_model=CompleteCareV2Response)
async def get_complete_care_v2(request: CompleteCareV2Request):
    orchestrator = get_ayesha_care_plan_orchestrator()
    return await orchestrator.get_complete_care_plan(request)
```

### Direct Service Usage
```python
from api.services.ayesha_care_plan.trial_service import get_ayesha_trial_service
from api.services.ayesha_care_plan.soc_service import get_ayesha_soc_service

trial_service = get_ayesha_trial_service()
soc_service = get_ayesha_soc_service()

# Use services independently
trials = await trial_service.get_trials(request)
soc = soc_service.get_soc_recommendation(has_ascites=True)
```

## Benefits

1. **Maintainability**: Each service is <200 lines, focused on one responsibility
2. **Testability**: Services can be unit tested independently
3. **Reusability**: Services can be used outside the orchestrator
4. **Extensibility**: New services can be added without touching existing code
5. **No Hard-coding**: Configuration-driven, follows DRY principles
6. **Scalability**: Easy to add new care plan components

## Migration Notes

- **Router**: Reduced from 1700+ lines to ~100 lines
- **Orchestrator**: Reduced from 1700+ lines to ~400 lines
- **Services**: Each service is focused and reusable
- **Backward Compatible**: Same API, same response format

## Next Steps

1. Add unit tests for each service
2. Add integration tests for orchestrator
3. Consider adding service-level caching
4. Add service-level error handling/retries
5. Consider adding service-level metrics/logging
