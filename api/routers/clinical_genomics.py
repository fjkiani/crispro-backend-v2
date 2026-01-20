"""
Clinical Genomics Command Center Router
Unified endpoint for comprehensive variant analysis.
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import uuid
from datetime import datetime
from pydantic import BaseModel
from api.services.efficacy_orchestrator import (
    create_efficacy_orchestrator,
    EfficacyRequest,
)

router = APIRouter(prefix="/api/clinical_genomics", tags=["clinical_genomics"])


class AnalyzeVariantRequest(BaseModel):
    """Request model for unified variant analysis."""
    mutations: List[Dict[str, Any]]
    disease: Optional[str] = None
    profile: str = "baseline"  # baseline | richer | fusion
    include: List[str] = []  # optional: ["acmg", "pgx"]
    germline_variants: Optional[List[Dict[str, Any]]] = None
    guides: Optional[List[str]] = None


@router.post("/analyze_variant")
async def analyze_variant(request: AnalyzeVariantRequest):
    """
    Unified Clinical Genomics analysis endpoint.
    
    SLICE 1: Wraps /api/efficacy/predict for mechanistic S/P/E analysis.
    Future: Will integrate toxicity, off-target, and KG context.
    
    Args:
        request: AnalyzeVariantRequest with mutations, disease, profile
        
    Returns:
        Nested response with efficacy, toxicity, off_target, kg_context, provenance
    """
    if not request.mutations:
        raise HTTPException(status_code=400, detail="mutations required")
    
    # Generate unified run_id
    run_id = str(uuid.uuid4())
    
    # Call efficacy orchestrator (S/P/E) directly to avoid nested HTTP and reduce latency
    try:
        orchestrator = create_efficacy_orchestrator(api_base="http://127.0.0.1:8000")
        # Call efficacy orchestrator directly (profile-aware)
        # Profile determines fast/richer/fusion behavior
        is_baseline = (request.profile == "baseline")
        is_richer = (request.profile == "richer")
        is_fusion = (request.profile == "fusion")
        is_full = (request.profile == "full")  # Full-mode: SPE with evidence enabled
        
        # Determine ablation mode and fast flag
        if is_full:
            ablation_mode = "SPE"  # Full S/P/E with evidence
            fast_mode = False  # Enable evidence gathering
        elif is_baseline:
            ablation_mode = "SP"  # S+P only for baseline
            fast_mode = True  # Skip evidence for speed
        else:
            ablation_mode = "SPE"  # Full S/P/E for richer/fusion
            fast_mode = False  # Enable evidence
        
        efficacy_request = EfficacyRequest(
            mutations=request.mutations,
            model_id="evo2_1b",
            ablation_mode=ablation_mode,
            options={
                "adaptive": True,
                "profile": request.profile,
                # Fast path to prevent timeouts:
                "fast": fast_mode,           # skip evidence/insights/calibration for baseline only
                "limit_panel": 12 if is_baseline else 0,  # bound work for baseline, unlimited for full-mode
                "ensemble": False, # Force single model
                "force_exon_scan": is_richer or is_fusion or is_full, # Multi-window for richer/fusion/full
                "include_sae_features": True,  # Enable SAE feature extraction (P2)
            },
            api_base="http://127.0.0.1:8000",
            disease=request.disease,
            include_trials_stub=False,
            include_fda_badges=False,
            include_cohort_overlays=False,
            include_calibration_snapshot=False,
        )
        efficacy_response = await orchestrator.predict(efficacy_request)
        efficacy_data = {
            "drugs": efficacy_response.drugs,
            "run_signature": efficacy_response.run_signature,
            "scoring_strategy": efficacy_response.scoring_strategy,
            "evidence_tier": efficacy_response.evidence_tier,
            "provenance": efficacy_response.provenance,
        }
        # Include SAE features when available
        if getattr(efficacy_response, "sae_features", None):
            efficacy_data["sae_features"] = efficacy_response.sae_features
        if efficacy_response.cohort_signals:
            efficacy_data["cohort_signals"] = efficacy_response.cohort_signals
        if efficacy_response.calibration_snapshot:
            efficacy_data["calibration_snapshot"] = efficacy_response.calibration_snapshot
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Efficacy orchestrator failed: {e}")
    
    # Build nested response (SLICE 1: efficacy only)
    response = {
        "efficacy": efficacy_data,
        "toxicity": None,  # SLICE 3
        "off_target": None,  # SLICE 3
        "kg_context": None,  # SLICE 4
        "provenance": {
            "run_id": run_id,
            "efficacy_run": efficacy_data.get("provenance", {}).get("run_id"),
            "profile": request.profile,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "methods": {
                "efficacy": "S/P/E orchestrator (Evo2 + Pathway + Evidence)",
                "toxicity": "pending (SLICE 3)",
                "off_target": "pending (SLICE 3)",
                "kg": "pending (SLICE 4)"
            }
        }
    }
    
    # Optional includes (SLICE 2+)
    if "acmg" in request.include:
        response["acmg"] = None  # TODO: call /api/acmg/classify_variant
    if "pgx" in request.include:
        response["pharmgkb"] = None  # TODO: call /api/pharmgkb/metabolizer_status
    
    return response


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "clinical_genomics"}

