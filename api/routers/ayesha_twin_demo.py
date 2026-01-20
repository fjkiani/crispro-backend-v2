"""
Ayesha Twin Demo - Public TCGA Case Study

Demonstrates the complete A→B Food Validator + Drug Efficacy workflow
using PUBLIC TCGA-OV data (no PHI, ethical demo).

This is NOT Ayesha's data - it's a public case study that mirrors her profile:
- Ovarian high-grade serous
- TP53 mutation (likely)
- HRD+ (homologous recombination deficiency)
- Stage III
- Post-platinum progression

Perfect for showing Ayesha the platform capabilities without using her private data.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import httpx

from api.routers.hypothesis_validator import validate_food_ab_enhanced

router = APIRouter()


class TwinDemoRequest(BaseModel):
    use_llm: bool = True

# Public TCGA case study profile (mirrors Ayesha's situation)
PUBLIC_CASE_PROFILE = {
    "patient_id": "TCGA-13-1481 (PUBLIC CASE STUDY)",
    "disease": "Ovarian High-Grade Serous Carcinoma",
    "stage": "III",
    "mutations": [
        {
            "gene": "TP53",
            "hgvs_p": "R248Q",
            "vaf": 0.45,
            "chrom": "17",
            "pos": 7577539,
            "ref": "G",
            "alt": "A",
            "build": "GRCh38",
            "consequence": "missense_variant"
        }
    ],
    "biomarkers": {
        "hrd": "POSITIVE",
        "tmb": 8.2,
        "msi": "MSS",
        "hrd_score": 42  # High HRD score (>42 = HRD+)
    },
    "treatment_history": {
        "line_1": "carboplatin_paclitaxel",
        "line_2": "bevacizumab",
        "current_line": 3,
        "prior_therapies": ["carboplatin", "paclitaxel", "bevacizumab"]
    },
    "disclaimer": "This is a PUBLIC TCGA case study - NOT a real patient's private data"
}


@router.post("/api/demo/ayesha_twin")
async def ayesha_twin_demo(request: Optional[TwinDemoRequest] = None) -> Dict[str, Any]:
    """
    Complete analysis workflow using public TCGA case that mirrors Ayesha's profile.
    
    Returns:
    - Food/Supplement recommendations (A→B validated)
    - Drug efficacy rankings (WIWFM)
    - Complete analysis provenance
    
    This demonstrates the platform WITHOUT using Ayesha's private data.
    """
    
    use_llm = request.use_llm if request else True
    
    try:
        # Step 1: Run Food Validator for key compounds
        food_compounds = ["Vitamin D", "Omega-3", "Curcumin", "NAC", "Green Tea"]
        food_results = []
        
        for compound in food_compounds:
            try:
                food_result = await validate_food_ab_enhanced(
                    compound=compound,
                    disease="ovarian_cancer_hgs",
                    germline_status="negative",
                    treatment_line=3,
                    prior_therapies=PUBLIC_CASE_PROFILE["treatment_history"]["prior_therapies"],
                    use_llm=use_llm
                )
                food_results.append(food_result)
            except Exception as e:
                # Continue with other compounds if one fails
                food_results.append({
                    "compound": compound,
                    "status": "ERROR",
                    "error": str(e)
                })
        
        # Step 2: Run Drug Efficacy (WIWFM) - using public mutation profile
        drug_results = None
        try:
            # Import efficacy endpoint
            from api.services.efficacy_orchestrator.orchestrator import predict_drug_efficacy
            from api.services.efficacy_orchestrator.models import EfficacyRequest
            
            efficacy_request = EfficacyRequest(
                mutations=PUBLIC_CASE_PROFILE["mutations"],
                disease="ovarian",
                model_id="evo2_1b",
                options={
                    "adaptive": True,
                    "ensemble": False,
                    "profile": "baseline",
                    "fast": False
                }
            )
            
            drug_results = await predict_drug_efficacy(efficacy_request)
        except Exception as e:
            # Graceful degradation if efficacy fails
            drug_results = {
                "error": str(e),
                "message": "Drug efficacy analysis unavailable - using food recommendations only"
            }
        
        # Step 3: Assemble complete response
        return {
            "case_data": PUBLIC_CASE_PROFILE,
            "food_recommendations": food_results,
            "drug_recommendations": drug_results,
            "analysis_summary": {
                "total_foods_analyzed": len(food_results),
                "supported_foods": len([f for f in food_results if f.get("verdict") == "SUPPORTED"]),
                "weak_support_foods": len([f for f in food_results if f.get("verdict") == "WEAK_SUPPORT"]),
                "llm_enabled": use_llm,
                "drug_analysis_available": drug_results is not None and "error" not in str(drug_results)
            },
            "provenance": {
                "method": "ayesha_twin_demo_v1",
                "data_source": "TCGA-OV (Public)",
                "case_id": PUBLIC_CASE_PROFILE["patient_id"],
                "ruo_disclaimer": "PUBLIC CASE STUDY - NOT A REAL PATIENT'S DATA"
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Demo analysis failed: {str(e)}"
        )


@router.get("/api/demo/ayesha_twin/profile")
async def get_twin_profile() -> Dict[str, Any]:
    """Get the public case profile used in the demo."""
    return PUBLIC_CASE_PROFILE

