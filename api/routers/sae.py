"""
SAE (Sparse Autoencoder) endpoints for Evo2 mechanistic interpretability
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import httpx
import os

from ..config import get_feature_flags

SAE_SERVICE_URL = os.getenv("SAE_SERVICE_URL", "https://your-modal-url-here.modal.run")

router = APIRouter(prefix="/api/sae", tags=["sae"])

@router.post("/extract_features")
async def extract_features(request: Dict[str, Any]):
    """
    Extract SAE features from Evo2 layer 26 activations.
    Gated by ENABLE_TRUE_SAE flag.
    
    Input:
        - activations: Optional[List[List[List[float]]]] - Layer 26 activations [batch, seq_len, 4096]
        - OR (chrom, pos, ref, alt) for variant scoring
        - model_id: str (default: "evo2_7b")
        - assembly: str (default: "GRCh38")
        - window: int (default: 8192)
    
    Output:
        {
            "features": List[...],  # 32K-dim feature vector
            "top_features": List[{"index": int, "value": float}],  # Top k=64 features
            "layer": "blocks.26",
            "stats": {
                "sparsity": float,
                "mean_activation": float,
                "num_active_features": int,
                "shape": List[int]
            },
            "provenance": {
                "method": "batch_topk_tied_sae",
                "d_in": 4096,
                "d_hidden": 32768,
                "k": 64,
                "model": "Goodfire/Evo-2-Layer-26-Mixed",
                "sae_version": "v1"
            }
        }
    """
    try:
        # Feature flag gate
        try:
            flags = get_feature_flags()
            if not flags.get("enable_true_sae", False):
                raise HTTPException(
                    status_code=403,
                    detail="True SAE features endpoint disabled. Set ENABLE_TRUE_SAE=1 to enable."
                )
        except Exception as e:
            if "403" in str(e):
                raise
            # If flags can't be loaded, default to disabled for safety
            raise HTTPException(
                status_code=403,
                detail="True SAE features endpoint disabled (feature flags unavailable)"
            )
        
        # Validate SAE service URL is configured
        if not SAE_SERVICE_URL or SAE_SERVICE_URL == "https://your-modal-url-here.modal.run":
            raise HTTPException(
                status_code=503,
                detail="SAE service URL not configured. Set SAE_SERVICE_URL environment variable."
            )
        
        # Call SAE service
        async with httpx.AsyncClient(timeout=120.0) as client:
            try:
                r = await client.post(
                    f"{SAE_SERVICE_URL}/extract_features",
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                r.raise_for_status()
                result = r.json()
                
                # Add version to provenance
                if "provenance" not in result:
                    result["provenance"] = {}
                result["provenance"]["sae_version"] = "v1"
                result["provenance"]["source"] = "modal_sae_service"
                
                return result
            
            except httpx.HTTPStatusError as e:
                raise HTTPException(
                    status_code=e.response.status_code,
                    detail=f"SAE service error: {e.response.text}"
                )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=503,
                    detail=f"Failed to connect to SAE service: {str(e)}"
                )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAE extraction failed: {str(e)}")

@router.post("/biomarker_summary")
async def get_biomarker_summary():
    """
    Returns biomarker correlation summary from TCGA-OV platinum cohort analysis.
    
    ⚠️ RUO/VALIDATION-ONLY: This endpoint is for internal research and validation.
    NOT for production clinical decision-making.
    
    Gated by ENABLE_TRUE_SAE feature flag.
    
    Output:
        {
            "top_features": List[{
                "feature_index": int,
                "pearson_r": float,
                "pearson_p": float,
                "spearman_r": float,
                "cohen_d": float,
                "cv_stability": float,
                "bootstrap_ci_lower": float,
                "bootstrap_ci_upper": float,
                "rank": int
            }],
            "total_features_analyzed": int,
            "significant_features_count": int,
            "p_value_threshold": float,
            "cohort_size": int,
            "outcome_distribution": {...},
            "provenance": {...},
            "ruo_disclaimer": str
        }
    """
    try:
        flags = get_feature_flags()
        if not flags.get("enable_true_sae", False):
            raise HTTPException(
                status_code=403,
                detail="SAE biomarker endpoint disabled (RUO only). Set ENABLE_TRUE_SAE=1."
            )
    except Exception as e:
        if "403" in str(e):
            raise
        raise HTTPException(
            status_code=403,
            detail="SAE biomarker endpoint disabled (feature flags unavailable)"
        )
    
    biomarker_file = "/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/validation/sae_cohort/sae_tcga_ov_platinum_biomarkers.json"
    
    try:
        import json
        from pathlib import Path
        
        biomarker_path = Path(biomarker_file)
        
        if not biomarker_path.exists():
            raise HTTPException(
                status_code=404, 
                detail="Biomarker analysis not yet computed. Run: python api/services/biomarker_correlation_service.py"
            )
        
        with open(biomarker_path, 'r') as f:
            summary = json.load(f)
        
        # Add RUO disclaimer
        summary["ruo_disclaimer"] = (
            "⚠️ RESEARCH USE ONLY - This biomarker analysis is for validation and research purposes. "
            "NOT approved for clinical decision-making. Manager approval required before integration."
        )
        
        return summary
    
    except HTTPException:
        raise
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="Biomarker analysis file not found.")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to load biomarker summary: {str(e)}")

@router.get("/health")
async def sae_health():
    """Check health of SAE service."""
    try:
        # Check if SAE service is configured
        if not SAE_SERVICE_URL or SAE_SERVICE_URL == "https://your-modal-url-here.modal.run":
            return {
                "service": "sae",
                "status": "not_configured",
                "message": "SAE_SERVICE_URL not set"
            }
        
        # Check if SAE service is reachable
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{SAE_SERVICE_URL}/health")
                return {
                    "service": "sae",
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": SAE_SERVICE_URL,
                    "response": response.json() if response.status_code == 200 else response.text
                }
            except Exception as e:
                return {
                    "service": "sae",
                    "status": "error",
                    "url": SAE_SERVICE_URL,
                    "error": str(e)
                }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"SAE health check failed: {str(e)}")

