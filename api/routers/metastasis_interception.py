"""
Metastasis Interception Router - Weapon design endpoints (RUO).

Exposes:
- POST /api/metastasis/intercept
- GET  /api/metastasis/intercept/health
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from ..schemas.metastasis_interception import (
    MetastasisInterceptRequest,
    MetastasisInterceptResponse,
)
from ..services import metastasis_interception_service

router = APIRouter(prefix="/api/metastasis", tags=["metastasis_interception"])


@router.post("/intercept", response_model=MetastasisInterceptResponse)
async def intercept_metastatic_step(request: MetastasisInterceptRequest):
    """
    Design CRISPR interception weapons for a metastatic cascade step.

    RUO - Research Use Only. Not for clinical decision-making.

    Workflow:
    1) Target Lock
    2) Design
    3) Safety preview
    4) Assassin scoring
    """
    try:
        return await metastasis_interception_service.intercept_metastatic_step(
            request.model_dump(),
            api_base="http://127.0.0.1:8000",
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Interception failed: {str(e)}")


@router.get("/intercept/health")
async def health_check():
    ruleset = metastasis_interception_service.load_ruleset()
    return {
        "status": "healthy",
        "ruleset_version": ruleset.get("version"),
        "mission_steps_configured": len(ruleset.get("mission_to_gene_sets", {})),
        "gene_sets": list(ruleset.get("gene_sets", {}).keys()),
    }
