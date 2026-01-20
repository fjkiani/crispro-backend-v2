"""
Safety endpoints for toxicity risk and off-target preview.

Research Use Only (RUO) - Not for clinical decision-making.
"""

from fastapi import APIRouter, HTTPException
from api.schemas.safety import (
    ToxicityRiskRequest, ToxicityRiskResponse,
    OffTargetPreviewRequest, OffTargetPreviewResponse
)
from api.services.safety_service import get_safety_service

router = APIRouter(prefix="/api/safety", tags=["safety"])


@router.get("/health")
async def health_check():
    """Health check for safety service."""
    return {
        "status": "healthy",
        "service": "safety",
        "endpoints": ["/toxicity_risk", "/off_target_preview"],
        "ruo": True,
        "note": "Research Use Only - Not for clinical decision-making"
    }


@router.post("/toxicity_risk", response_model=ToxicityRiskResponse)
async def assess_toxicity_risk(request: ToxicityRiskRequest):
    """
    Assess toxicity risk based on germline variants, drug MoA, and clinical context.
    
    **Conservative RUO Assessment:**
    - Pharmacogene variants (affects drug metabolism)
    - MoA to toxicity pathway overlap (DNA repair, inflammation, cardiometabolic)
    - Tissue-specific risk (preliminary)
    
    **Returns:**
    - risk_score (0-1, higher = more risk)
    - confidence (0-1)
    - factors (list of individual risk contributors)
    - provenance (audit trail)
    
    **RUO DISCLAIMER:** This is a research tool. All results must be validated
    by qualified healthcare professionals before any clinical use.
    """
    try:
        safety_service = get_safety_service()
        response = await safety_service.compute_toxicity_risk(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Toxicity risk assessment failed: {str(e)}"
        )


@router.post("/off_target_preview", response_model=OffTargetPreviewResponse)
async def preview_off_targets(request: OffTargetPreviewRequest):
    """
    Heuristic off-target preview for CRISPR guide RNAs.
    
    **P1 Implementation (Heuristics Only):**
    - GC content scoring (optimal 40-60%)
    - Homopolymer detection (runs greater than 4 base pairs flagged)
    - Seed region quality (12 base pair PAM-proximal)
    - Combined heuristic safety score
    
    **P2 Roadmap:**
    - Genome-wide alignment (BLAST/minimap2)
    - Mismatch tolerance analysis
    - Chromatin accessibility context
    
    **Returns:**
    - guides (list of scored guides with risk levels)
    - summary (aggregate statistics)
    - provenance (audit trail)
    
    **RUO DISCLAIMER:** Heuristic preview only. Genome alignment validation
    required before experimental use.
    """
    try:
        safety_service = get_safety_service()
        response = await safety_service.preview_off_targets(request)
        return response
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Off-target preview failed: {str(e)}"
        )
