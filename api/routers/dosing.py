"""
Dosing Guidance Router

FastAPI router for pharmacogenomics-based dosing recommendations.

Research Use Only - Not for Clinical Decision Making
"""

from fastapi import APIRouter, HTTPException
from typing import Optional
import logging

from api.schemas.dosing import DosingGuidanceRequest, DosingGuidanceResponse
from api.services.dosing_guidance_service import get_dosing_guidance_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/dosing", tags=["dosing"])


@router.post("/guidance", response_model=DosingGuidanceResponse)
async def get_dosing_guidance(request: DosingGuidanceRequest):
    """
    Get dosing guidance based on pharmacogenomics.
    
    **Research Use Only - Not for Clinical Decision Making**
    
    Example:
    ```json
    {
        "gene": "DPYD",
        "variant": "*2A",
        "drug": "5-fluorouracil",
        "treatment_line": 1,
        "prior_therapies": []
    }
    ```
    
    Returns dosing recommendations with adjustment factors, CPIC evidence levels,
    monitoring requirements, and alternatives.
    """
    logger.info(f"Dosing guidance request: {request.gene} + {request.drug} (variant: {request.variant})")
    
    try:
        service = get_dosing_guidance_service()
        response = await service.get_dosing_guidance(request)
        
        logger.info(
            f"Dosing guidance: {len(response.recommendations)} recommendation(s), "
            f"contraindicated={response.contraindicated}, confidence={response.confidence:.2f}"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Dosing guidance failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Dosing guidance failed: {str(e)}"
        )


@router.get("/health")
async def health():
    """Health check for dosing guidance router"""
    return {"status": "operational", "service": "dosing_guidance"}

