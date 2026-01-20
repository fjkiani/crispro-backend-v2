"""
Care Planning Router - Resistance Playbook, Monitoring, PGx

Endpoints for durable control strategy (Section 17 of ayesha_plan.mdc):
1. /api/care/resistance_playbook - Predict resistance and recommend strategies
2. /api/care/monitoring_plan - Generate MRD/imaging cadence (future)
3. /api/care/pharmacogene_detect - Detect PGx flags (future)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
import logging

from api.services.disease_normalization import validate_disease_type as validate_and_normalize_disease

from api.services.resistance_playbook_service import get_resistance_playbook_service

router = APIRouter(prefix="/api/care", tags=["care"])
logger = logging.getLogger(__name__)


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class ResistancePlaybookRequest(BaseModel):
    """Request for resistance playbook generation."""
    tumor_context: Dict[str, Any] = Field(
        ...,
        description="Tumor genomic context (somatic_mutations, CNAs, HRD, TMB, MSI)"
    )
    treatment_history: Dict[str, Any] = Field(
        ...,
        description="Treatment history (prior_therapies, platinum_response, current_line)"
    )
    pathway_disruption: Optional[Dict[str, Any]] = Field(
        None,
        description="Pathway burden scores (optional)"
    )
    sae_features: Optional[List[Dict[str, Any]]] = Field(
        None,
        description="SAE feature bundle (optional)"
    )
    insights: Optional[Dict[str, Any]] = Field(
        None,
        description="Insights bundle (Functionality, Chromatin, Essentiality, Regulatory)"
    )




class ResistancePlaybookRequestV2(ResistancePlaybookRequest):
    """V2 request: includes explicit disease for validation (no risky defaults)."""
    disease: str = Field(..., description="Canonical disease id (e.g., ovarian_cancer_hgs, multiple_myeloma)")
class ResistanceRiskResponse(BaseModel):
    """A detected resistance mechanism."""
    type: str
    confidence: float
    evidence: str
    triggers: List[str]
    source: str


class ComboStrategyResponse(BaseModel):
    """A recommended combination therapy."""
    drugs: List[str]
    moa: str
    indication: str
    evidence_tier: str
    trials: List[str]
    rank_score: float
    triggers: List[str]
    rationale: str


class NextLineSwitchResponse(BaseModel):
    """A recommended next-line switch."""
    drug: str
    drug_class: str
    indication: str
    evidence_tier: str
    trials: List[str]
    rank_score: float
    rationale: str


class ResistancePlaybookResponse(BaseModel):
    """Complete resistance playbook output."""
    risks: List[ResistanceRiskResponse]
    combo_strategies: List[ComboStrategyResponse]
    next_line_switches: List[NextLineSwitchResponse]
    trial_keywords: List[str]
    provenance: Dict[str, Any]




class ResistancePlaybookResponseV2(ResistancePlaybookResponse):
    """V2 response: adds disease + normalization metadata."""
    disease: str
    disease_is_valid: bool
    disease_original: str
# ============================================================================
# ENDPOINTS
# ============================================================================

@router.post("/resistance_playbook_v2", response_model=ResistancePlaybookResponseV2)
async def create_resistance_playbook_v2(request: ResistancePlaybookRequestV2):
    """
    V2: Generate resistance playbook with explicit disease validation.

    - If disease is unknown/unsupported: return 422 (no risky defaults).
    - Otherwise behaves like v1.
    """
    is_valid, normalized = validate_and_normalize_disease(request.disease)
    if not is_valid:
        raise HTTPException(status_code=422, detail=f"Unsupported disease: {request.disease}")
    # delegate to v1 logic (keep single implementation)
    payload = request.model_dump()
    payload.pop("disease", None)
    result = await create_resistance_playbook(ResistancePlaybookRequest(**payload))
    return ResistancePlaybookResponseV2(**result.model_dump(), disease=normalized, disease_is_valid=True, disease_original=request.disease)


@router.post("/resistance_playbook", response_model=ResistancePlaybookResponse)
async def create_resistance_playbook(request: ResistancePlaybookRequest):
    """
    Legacy endpoint (kept for compatibility).

    NOTE: This endpoint previously referenced non-existent symbols. It is now implemented
    as a thin wrapper around `ResistancePlaybookService.get_next_line_options()`.
    """
    try:
        tumor_context = request.tumor_context or {}
        mutations = tumor_context.get('somatic_mutations') or []
        detected_genes = sorted({(m.get('gene') or '').upper() for m in mutations if m.get('gene')})

        # Default disease routing for legacy endpoint: ovarian (caller should use v2 with explicit disease)
        svc = get_resistance_playbook_service()
        result = await svc.get_next_line_options(
            disease='ovarian',
            detected_resistance=detected_genes,
            current_regimen=None,
            current_drug_class=None,
            treatment_line=1,
            prior_therapies=None,
            cytogenetics=None,
            patient_id=None
        )

        # Return a compatible response shape (risks/combos not available in this service-backed implementation)
        return ResistancePlaybookResponse(
            risks=[],
            combo_strategies=[],
            next_line_switches=[],
            trial_keywords=[],
            provenance={
                **(result.provenance or {}),
                'status': 'service_backed_legacy',
                'detected_genes': detected_genes
            }
        )

    except Exception as e:
        logger.error(f"Resistance playbook generation failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Resistance playbook generation failed: {str(e)}")


@router.get("/health")
async def health_check():
    """Health check for care planning endpoints."""
    return {
        "status": "healthy",
        "service": "care_planning",
        "endpoints": {
            "resistance_playbook": "operational",
            "monitoring_plan": "not_implemented",
            "pharmacogene_detect": "not_implemented"
        },
        "version": "1.0"
    }



