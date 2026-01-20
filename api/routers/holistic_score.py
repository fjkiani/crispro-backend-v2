"""
Unified Patient-Trial-Dose Feasibility Score Router

THE MOAT: First end-to-end patient-trial-dose optimization.

API endpoints for computing the Holistic Score:
- POST /api/holistic-score/compute - Single patient-trial
- POST /api/holistic-score/batch - Multiple trials  
- GET /api/holistic-score/health

Research Use Only - Not for Clinical Decision Making

Owner: Zo (Lead Agent)
Created: January 2026
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any
import logging

from api.services.holistic_score_service import get_holistic_score_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/holistic-score", tags=["holistic-score"])


class PatientProfile(BaseModel):
    """Patient profile for holistic scoring."""
    mechanism_vector: Optional[List[float]] = Field(
        None, 
        description="7D mechanism vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]"
    )
    disease: Optional[str] = Field(None, description="Cancer type")
    age: Optional[int] = Field(None, description="Patient age")
    mutations: Optional[List[Dict[str, Any]]] = Field(
        None, 
        description="List of mutations [{gene, variant}]"
    )
    germline_variants: Optional[List[Dict[str, str]]] = Field(
        None,
        description="List of germline variants for PGx screening [{gene, variant}]"
    )
    location: Optional[Dict[str, str]] = Field(
        None,
        description="Patient location {state, city}"
    )


class TrialData(BaseModel):
    """Trial data for holistic scoring."""
    nct_id: Optional[str] = Field(None, alias="nctId")
    title: Optional[str] = None
    brief_title: Optional[str] = None
    moa_vector: Optional[List[float]] = Field(
        None,
        description="7D mechanism of action vector"
    )
    conditions: Optional[List[str]] = Field(None, description="Trial conditions")
    overall_status: Optional[str] = Field(None, description="Recruiting status")
    minimum_age: Optional[str] = None
    maximum_age: Optional[str] = None
    locations: Optional[List[Dict[str, Any]]] = None
    biomarker_requirements: Optional[List[str]] = None
    interventions: Optional[List[Dict[str, Any]]] = None
    
    class Config:
        populate_by_name = True


class HolisticScoreRequest(BaseModel):
    """Request for holistic score computation."""
    patient_profile: Dict[str, Any] = Field(
        ...,
        description="Patient profile including mechanism_vector, disease, age, mutations"
    )
    trial: Dict[str, Any] = Field(
        ...,
        description="Trial data including nct_id, moa_vector, conditions, status"
    )
    pharmacogenes: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Pharmacogene variants [{gene, variant}] for PGx screening"
    )
    drug: Optional[str] = Field(
        None,
        description="Drug name for dosing guidance (extracted from trial if not provided)"
    )


class HolisticScoreResponse(BaseModel):
    """Response with holistic score and breakdown."""
    holistic_score: float = Field(..., description="Unified score 0.0-1.0")
    mechanism_fit_score: float = Field(..., description="Mechanism alignment 0.0-1.0")
    eligibility_score: float = Field(..., description="Eligibility probability 0.0-1.0")
    pgx_safety_score: float = Field(..., description="PGx safety 0.0-1.0 (1.0=safe)")
    weights: Dict[str, float] = Field(..., description="Component weights")
    interpretation: str = Field(..., description="HIGH/MEDIUM/LOW/CONTRAINDICATED")
    recommendation: str = Field(..., description="Human-readable recommendation")
    caveats: List[str] = Field(..., description="Warnings and caveats")
    mechanism_alignment: Dict[str, float] = Field(..., description="Per-pathway alignment")
    eligibility_breakdown: List[str] = Field(..., description="Eligibility criteria breakdown")
    pgx_details: Dict[str, Any] = Field(..., description="PGx screening details")
    provenance: Dict[str, Any] = Field(..., description="Service provenance")


class BatchScoreRequest(BaseModel):
    """Request for batch holistic scoring."""
    patient_profile: Dict[str, Any] = Field(
        ...,
        description="Patient profile"
    )
    trials: List[Dict[str, Any]] = Field(
        ...,
        description="List of trials to score"
    )
    pharmacogenes: Optional[List[Dict[str, str]]] = Field(
        None,
        description="Pharmacogene variants for PGx screening"
    )


class BatchScoreResponse(BaseModel):
    """Response with ranked trial scores."""
    patient_id: Optional[str] = None
    trials_scored: int
    results: List[Dict[str, Any]]


@router.post("/compute", response_model=HolisticScoreResponse)
async def compute_holistic_score(request: HolisticScoreRequest):
    """
    Compute Unified Patient-Trial-Dose Feasibility Score.
    
    **Research Use Only - Not for Clinical Decision Making**
    
    Formula: Holistic Score = (0.5 × Mechanism Fit) + (0.3 × Eligibility) + (0.2 × PGx Safety)
    
    Example Request:
    ```json
    {
        "patient_profile": {
            "disease": "ovarian cancer",
            "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.0, 0.0],
            "mutations": [{"gene": "BRCA1"}, {"gene": "TP53"}],
            "germline_variants": [{"gene": "DPYD", "variant": "*1/*1"}]
        },
        "trial": {
            "nct_id": "NCT12345678",
            "moa_vector": [0.85, 0.10, 0.20, 0.15, 0.05, 0.0, 0.0],
            "conditions": ["Ovarian Cancer"],
            "overall_status": "RECRUITING"
        },
        "drug": "5-fluorouracil"
    }
    ```
    
    Returns:
        Unified score with interpretation, breakdown, and recommendations
    """
    logger.info(f"Holistic score request for trial: {request.trial.get('nct_id')}")
    
    try:
        service = get_holistic_score_service()
        result = await service.compute_holistic_score(
            patient_profile=request.patient_profile,
            trial=request.trial,
            pharmacogenes=request.pharmacogenes,
            drug=request.drug
        )
        
        logger.info(
            f"Holistic score: {result.holistic_score:.2f} "
            f"(mechanism={result.mechanism_fit_score:.2f}, "
            f"eligibility={result.eligibility_score:.2f}, "
            f"pgx={result.pgx_safety_score:.2f}) - {result.interpretation}"
        )
        
        return HolisticScoreResponse(
            holistic_score=result.holistic_score,
            mechanism_fit_score=result.mechanism_fit_score,
            eligibility_score=result.eligibility_score,
            pgx_safety_score=result.pgx_safety_score,
            weights=result.weights,
            interpretation=result.interpretation,
            recommendation=result.recommendation,
            caveats=result.caveats,
            mechanism_alignment=result.mechanism_alignment,
            eligibility_breakdown=result.eligibility_breakdown,
            pgx_details=result.pgx_details,
            provenance=result.provenance
        )
        
    except Exception as e:
        logger.error(f"Holistic score failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500, 
            detail=f"Holistic score computation failed: {str(e)}"
        )


@router.post("/batch", response_model=BatchScoreResponse)
async def compute_holistic_scores_batch(request: BatchScoreRequest):
    """
    Compute holistic scores for multiple trials.
    
    **Research Use Only - Not for Clinical Decision Making**
    
    Returns ranked list of trials by holistic score (descending).
    
    Example Request:
    ```json
    {
        "patient_profile": {
            "disease": "ovarian cancer",
            "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.0, 0.0]
        },
        "trials": [
            {"nct_id": "NCT111", "moa_vector": [0.85, 0.1, 0.2, 0.1, 0.0, 0.0, 0.0]},
            {"nct_id": "NCT222", "moa_vector": [0.2, 0.8, 0.1, 0.0, 0.0, 0.0, 0.0]}
        ],
        "pharmacogenes": [{"gene": "DPYD", "variant": "*2A"}]
    }
    ```
    """
    logger.info(f"Batch holistic score request for {len(request.trials)} trials")
    
    try:
        service = get_holistic_score_service()
        results = await service.compute_batch(
            patient_profile=request.patient_profile,
            trials=request.trials,
            pharmacogenes=request.pharmacogenes
        )
        
        logger.info(f"Batch scoring complete: {len(results)} trials scored")
        
        return BatchScoreResponse(
            patient_id=request.patient_profile.get("patient_id"),
            trials_scored=len(results),
            results=results
        )
        
    except Exception as e:
        logger.error(f"Batch holistic score failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Batch holistic score computation failed: {str(e)}"
        )


@router.get("/health")
async def health():
    """Health check for holistic score router."""
    return {
        "status": "healthy", 
        "service": "holistic-score",
        "formula": "0.5×mechanism + 0.3×eligibility + 0.2×pgx_safety",
        "ruo": "Research Use Only"
    }
