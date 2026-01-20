"""
Universal Biomarker Intelligence Router

Provides biomarker monitoring endpoints for any cancer type.

Author: Zo
Date: January 2025
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, Optional
import logging

from api.services.biomarker_intelligence_universal import get_biomarker_intelligence_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/biomarker", tags=["biomarker"])


class BiomarkerAnalysisRequest(BaseModel):
    """Request for biomarker analysis"""
    disease_type: str = Field(..., description="Disease type (e.g., 'ovarian_cancer_hgs', 'prostate_cancer')")
    biomarker_type: Optional[str] = Field(None, description="Biomarker type (e.g., 'ca125', 'psa', 'cea'). If None, uses primary biomarker for disease.")
    current_value: float = Field(..., description="Current biomarker value")
    baseline_value: Optional[float] = Field(None, description="Baseline biomarker value before treatment")
    cycle: Optional[int] = Field(None, description="Treatment cycle number")
    treatment_ongoing: bool = Field(default=False, description="Whether patient is currently on treatment")


@router.post("/intelligence")
async def analyze_biomarker(request: BiomarkerAnalysisRequest):
    """
    Analyze biomarker value and provide clinical intelligence.
    
    Supports multiple biomarkers:
    - CA-125 (ovarian cancer)
    - PSA (prostate cancer)
    - CEA (colorectal cancer)
    
    Returns burden classification, response forecast, resistance signals, and monitoring strategy.
    """
    try:
        service = get_biomarker_intelligence_service()
        
        result = service.analyze_biomarker(
            disease_type=request.disease_type,
            biomarker_type=request.biomarker_type,
            current_value=request.current_value,
            baseline_value=request.baseline_value,
            cycle=request.cycle,
            treatment_ongoing=request.treatment_ongoing
        )
        
        if "error" in result:
            raise HTTPException(status_code=400, detail=result.get("message", "Biomarker analysis failed"))
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Biomarker analysis failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Biomarker analysis failed: {str(e)}")


@router.get("/intelligence/health")
async def health_check():
    """Health check for biomarker intelligence service"""
    return {
        "status": "operational",
        "service": "biomarker_intelligence_universal",
        "supported_biomarkers": ["ca125", "psa", "cea"],
        "supported_diseases": ["ovarian_cancer_hgs", "prostate_cancer", "colorectal_cancer"]
    }
















