"""
Ayesha Care Plan Service Module

Modular service-based architecture for Ayesha's complete care plan orchestration.
Replaces the monolithic 1700+ line orchestrator with focused, reusable components.

Components:
- schemas: Request/Response models
- orchestrator: Thin coordinator that calls services
- trial_service: Trial fetching/ranking
- soc_service: SOC recommendations
- ca125_service: CA-125 intelligence
- drug_efficacy_service: WIWFM
- food_service: Food validator + supplements
- resistance_service: Resistance playbook + prophet
- sae_service: SAE Phase 1 and 2
- io_service: IO selection
- utils: Shared utilities (insights extraction, etc.)
"""

from .schemas import CompleteCareV2Request, CompleteCareV2Response
from .orchestrator import AyeshaCarePlanOrchestrator

__all__ = [
    "CompleteCareV2Request",
    "CompleteCareV2Response",
    "AyeshaCarePlanOrchestrator",
]
