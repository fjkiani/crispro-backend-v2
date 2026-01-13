"""
Ayesha Complete Care v2 Router

CLINICAL PURPOSE: Unified care plan orchestration for AK
For use by Co-Pilot conversational interface

This router uses the modular AyeshaCarePlanOrchestrator service
to coordinate all care plan components.

NOT a demo. Real decision support for Ayesha's Stage IVB ovarian cancer.

Author: Zo (Refactored to modular architecture Jan 2026)
Date: January 13-14, 2025 (Resistance Prophet integrated Jan 14, 2025)
For: AK - Stage IVB HGSOC
Manager Policy: MANAGER_ANSWERS_TO_RESISTANCE_PROPHET_QUESTIONS.md (Jan 14, 2025)
"""

from fastapi import APIRouter, HTTPException
import logging

from api.services.ayesha_care_plan.schemas import CompleteCareV2Request, CompleteCareV2Response
from api.services.ayesha_care_plan.orchestrator import get_ayesha_care_plan_orchestrator

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/ayesha", tags=["ayesha"])


@router.post("/complete_care_v2", response_model=CompleteCareV2Response)
async def get_complete_care_v2(request: CompleteCareV2Request):
    """
    Get complete care plan v2 for AK.
    
    Orchestrates all care plan components:
    - Clinical trials (frontline, NYC metro, transparent reasoning)
    - SOC recommendation (NCCN-aligned)
    - CA-125 monitoring (burden, forecast, resistance)
    - Drug efficacy (WIWFM - awaiting NGS if no tumor data)
    - Food validator (optional)
    - Resistance playbook (optional)
    - RESISTANCE PROPHET (NEW - predicts resistance 3-6 months early)
    
    This is for Co-Pilot conversational interface.
    NOT a demo. Real clinical decision support.
    
    Args:
        request: Complete care request with Ayesha's profile
    
    Returns:
        Complete care plan with all components
    """
    try:
        orchestrator = get_ayesha_care_plan_orchestrator()
        return await orchestrator.get_complete_care_plan(request)
        
    except Exception as e:
        logger.error(f"Complete care v2 failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Complete care orchestration failed: {str(e)}")


@router.get("/complete_care_v2/health")
async def health_check_v2():
    """Health check for complete care v2 orchestrator"""
    return {
        "status": "operational",
        "service": "complete_care_v2_modular",
        "for_patient": "AK (Stage IVB ovarian cancer)",
        "sae_phase1_enabled": True,
        "sae_phase2_enabled": True,
        "resistance_prophet_enabled": True,
        "sae_policy": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (Jan 13, 2025)",
        "prophet_policy": "MANAGER_ANSWERS_TO_RESISTANCE_PROPHET_QUESTIONS.md (Jan 14, 2025)",
        "architecture": "modular_service_based",
        "capabilities": [
            "clinical_trials_frontline",
            "soc_recommendation_nccn",
            "ca125_intelligence",
            "wiwfm_evo2_powered",
            "food_validation",
            "resistance_playbook",
            # Phase 1 SAE Services
            "next_test_recommender_priority_hrd_ctdna_slfn11_abcb1",
            "hint_tiles_max4_suggestive_tone",
            "mechanism_map_6chips_color_coded",
            # Phase 2 SAE Services
            "sae_features_dna_repair_mechanism_vector",
            "resistance_alert_2of3_triggers",
            # Resistance Prophet (NEW)
            "resistance_prediction_3to6_months_early",
            "signal_fusion_dna_repair_pathway_escape",
            "risk_stratification_high_medium_low"
        ],
        "note": "Unified orchestrator for Co-Pilot conversational interface + RESISTANCE PROPHET (Modular Architecture)"
    }
