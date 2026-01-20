"""
Efficacy Router: Thin FastAPI endpoints delegating to orchestrator.
"""
import os
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional

from api.services.efficacy_orchestrator import create_efficacy_orchestrator, EfficacyRequest
from api.services.pathway import get_default_panel
from api.config import get_feature_flags, DEFAULT_EVO_MODEL
from api.middleware.auth_middleware import get_optional_user

router = APIRouter(prefix="/api/efficacy", tags=["efficacy"])

# Create orchestrator instance
orchestrator = create_efficacy_orchestrator()


@router.get("/config")
async def get_efficacy_config():
    """Get efficacy configuration and available options."""
    try:
        feature_flags = get_feature_flags()
        panel = get_default_panel()
        
        return {
            "panel": panel,
            "feature_flags": {
                "enable_massive_modes": feature_flags.get("enable_massive_modes", False),
                "disable_fusion": feature_flags.get("disable_fusion", False),
                "disable_evo2": feature_flags.get("disable_evo2", False),
                "evo_use_delta_only": feature_flags.get("evo_use_delta_only", False),
                "evo_disable_symmetry": feature_flags.get("evo_disable_symmetry", True),
                "evo_max_flanks": feature_flags.get("evo_max_flanks", 1),
                "evo_max_models": feature_flags.get("evo_max_models", 1),
            },
            "scoring_modes": {
                "fusion_am": bool(os.getenv("FUSION_AM_URL")),
                "evo2": True,
                "massive_oracle": feature_flags.get("enable_massive_modes", False)
            },
            "default_options": {
                "adaptive": True,
                "ensemble": True,
                "massive_impact": False,
                "massive_real_context": False,
                "include_fda_badges": False,
                "include_trials_stub": False,
                "include_cohort_overlays": False,
                "include_calibration_snapshot": False
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"config failed: {e}")


@router.post("/predict")
async def predict_efficacy(
    request: Dict[str, Any],
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
):
    """Predict drug efficacy for given mutations."""
    try:
        # Check quota if authenticated
        if user and user.get("user_id"):
            from ..middleware.quota_middleware import check_quota
            quota_check = check_quota("drug_queries")
            await quota_check(user)
        
        # Check feature flag if authenticated (SAE features require Pro+)
        if user and user.get("user_id"):
            from ..middleware.feature_flag_middleware import require_feature
            feature_check = require_feature("sae_features")
            await feature_check(user)
        
        # Log user_id if authenticated (for usage tracking)
        if user:
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Efficacy prediction requested by user {user.get('user_id')[:8]}...")
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        
        # Extract request parameters
        model_id = request.get("model_id", DEFAULT_EVO_MODEL)
        mutations = request.get("mutations") or []
        options = request.get("options") or {}
        # Enforce single-model 1B unless explicitly overridden via env
        options["ensemble"] = False
        api_base = request.get("api_base", "http://127.0.0.1:8000")
        disease = request.get("disease")
        moa_terms = request.get("moa_terms")
        
        # Extract sporadic cancer fields (Agent Jr Mission 4)
        germline_status = request.get("germline_status", "unknown")
        tumor_context = request.get("tumor_context")
        
        if not mutations:
            raise HTTPException(status_code=400, detail="mutations required")
        
        # Create efficacy request
        efficacy_request = EfficacyRequest(
            mutations=mutations,
            model_id=model_id,
            options=options,
            api_base=api_base,
            disease=disease,
            moa_terms=moa_terms,
            include_trials_stub=options.get("include_trials_stub", False),
            include_fda_badges=options.get("include_fda_badges", False),
            include_cohort_overlays=options.get("include_cohort_overlays", False),
            include_calibration_snapshot=options.get("include_calibration_snapshot", False),
            ablation_mode=options.get("ablation_mode"),
            # Sporadic cancer fields (Agent Jr Mission 4)
            germline_status=germline_status,
            tumor_context=tumor_context
        )
        
        # Predict efficacy
        response = await orchestrator.predict(efficacy_request)
        
        # Convert to expected response format
        result = {
            "drugs": response.drugs,
            "run_signature": response.run_signature,
            "scoring_strategy": response.scoring_strategy,
            "evidence_tier": response.evidence_tier,
            "provenance": response.provenance
        }
        
        # Add optional enrichment fields
        if response.cohort_signals:
            result["cohort_signals"] = response.cohort_signals
        if response.calibration_snapshot:
            result["calibration_snapshot"] = response.calibration_snapshot
            
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy prediction failed: {e}")


@router.post("/explain")
async def explain_efficacy(request: Dict[str, Any]):
    """Explain efficacy prediction methodology."""
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        
        # Extract request parameters
        model_id = request.get("model_id", DEFAULT_EVO_MODEL)
        mutations = request.get("mutations") or []
        options = request.get("options") or {}
        api_base = request.get("api_base", "http://127.0.0.1:8000")
        disease = request.get("disease")
        moa_terms = request.get("moa_terms")
        
        if not mutations:
            raise HTTPException(status_code=400, detail="mutations required")
        
        # Create efficacy request
        efficacy_request = EfficacyRequest(
            mutations=mutations,
            model_id=model_id,
            options=options,
            api_base=api_base,
            disease=disease,
            moa_terms=moa_terms
        )
        
        # Explain efficacy
        explanation = await orchestrator.explain(efficacy_request)
        
        return explanation
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy explanation failed: {e}")


@router.get("/run/{run_signature}")
async def get_efficacy_run(run_signature: str):
    """Get efficacy prediction results by run signature."""
    try:
        # For now, return a placeholder response
        # In a full implementation, this would retrieve cached results
        return {
            "run_signature": run_signature,
            "status": "completed",
            "message": "Run results not cached - please re-run prediction",
            "provenance": {
                "run_id": run_signature,
                "cache": "miss"
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run retrieval failed: {e}")


@router.get("/calibration/status")
async def get_calibration_status():
    """Get gene calibration service status."""
    try:
        # Check if calibration service is available
        from api.services.gene_calibration import get_calibration_service
        
        calibration_service = get_calibration_service()
        
        return {
            "status": "available",
            "service": "gene_calibration",
            "preloaded_genes": getattr(calibration_service, 'preloaded_count', 0),
            "provenance": {
                "source": "gene_calibration_service"
            }
        }
    except Exception as e:
        return {
            "status": "unavailable",
            "error": str(e),
            "provenance": {
                "source": "gene_calibration_service",
                "error": str(e)
            }
        }



