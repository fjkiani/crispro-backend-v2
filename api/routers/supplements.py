"""
Supplement Recommendations Router

FastAPI router for supplement recommendations based on drugs + treatment line.

Research Use Only - Not for Clinical Decision Making
"""

from fastapi import APIRouter, HTTPException
from typing import List, Dict, Any, Optional
import logging

from api.schemas.supplements import (
    SupplementRecommendationRequest,
    SupplementRecommendationResponse
)
from api.services.supplement_recommendation_service import get_supplement_recommendation_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/supplements", tags=["supplements"])


@router.post("/recommendations", response_model=SupplementRecommendationResponse)
async def get_supplement_recommendations(request: SupplementRecommendationRequest):
    """
    Get supplement recommendations based on drugs + treatment line.
    
    **Research Use Only - Not for Clinical Decision Making**
    
    Generates recommendations based on:
    - Drug classes and mechanisms
    - Treatment line (first-line, maintenance, etc.)
    - Drug-supplement interactions
    - Disease-specific needs
    
    Example:
    ```json
    {
      "drugs": [
        {"name": "Carboplatin", "class": "platinum", "moa": "DNA crosslinking"},
        {"name": "Paclitaxel", "class": "taxane", "moa": "microtubule stabilization"},
        {"name": "Bevacizumab", "class": "anti-VEGF", "moa": "angiogenesis inhibition"}
      ],
      "treatment_line": "first-line",
      "disease": "ovarian_cancer_hgs",
      "treatment_history": [],
      "germline_variants": []
    }
    ```
    
    Returns supplement recommendations with rationale, dosage, interactions, and evidence.
    """
    logger.info(
        f"Supplement recommendations request: {len(request.drugs)} drugs, "
        f"treatment_line={request.treatment_line}, disease={request.disease}"
    )
    
    try:
        service = get_supplement_recommendation_service()
        response = await service.generate_recommendations(request)
        
        logger.info(
            f"Supplement recommendations: {len(response.recommendations)} recommended, "
            f"{len(response.avoid)} to avoid"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Supplement recommendations failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Supplement recommendations failed: {str(e)}"
        )


@router.get("/health")
async def health():
    """Health check for supplement recommendations router"""
    return {"status": "healthy", "service": "supplement_recommendations"}
