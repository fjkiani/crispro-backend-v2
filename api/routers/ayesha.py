"""
Ayesha Complete Care Router

Unified endpoint for complete care planning (drugs + foods)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging

from api.services.ayesha_orchestrator import build_complete_care_plan

router = APIRouter(prefix="/api/ayesha", tags=["ayesha"])
logger = logging.getLogger(__name__)


@router.post("/complete_care_plan")
async def complete_care_plan(request: Dict[str, Any]):
    """
    Unified Complete Care Plan Endpoint
    
    Orchestrates both drug efficacy and food validation to provide
    holistic care recommendations.
    
    Request Body:
    {
        "patient_context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_history": [
                {"line": 1, "drugs": ["Carboplatin", "Paclitaxel"], "outcome": "partial_response"},
                {"line": 2, "drugs": ["Olaparib"], "outcome": "progression"}
            ],
            "biomarkers": {
                "brca1_mutant": true,
                "hrd_positive": true,
                "tp53_mutant": false
            },
            "germline_status": "negative"
        },
        "mutations": [  // Optional - if not provided, uses disease defaults
            {"gene": "TP53", "hgvs_p": "R273H", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A"}
        ]
    }
    
    Response:
    {
        "run_id": "uuid",
        "timestamp": "ISO format",
        "patient_context": {...},
        "drug_recommendations": [
            {
                "drug": "PARP Inhibitor",
                "efficacy_score": 0.82,
                "confidence": 0.85,
                "tier": "supported",
                "sae_features": {...},
                "rationale": "...",
                "citations": ["pmid1", "pmid2"],
                "badges": ["RCT", "Guideline"],
                "insights": {...}
            }
        ],
        "food_recommendations": [
            {
                "compound": "Vitamin D",
                "targets": ["VDR", "CASR"],
                "pathways": ["immune_modulation", "dna_repair"],
                "efficacy_score": 0.75,
                "confidence": 0.78,
                "sae_features": {...},
                "dosage": "4000-5000 IU daily",
                "rationale": "...",
                "citations": ["pmid1"]
            }
        ],
        "integrated_confidence": 0.78,
        "confidence_breakdown": {
            "drug_component": 0.80,
            "food_component": 0.76,
            "integration_method": "weighted_average"
        },
        "provenance": {
            "drug_analysis": {...},
            "food_analysis": {...}
        },
        "errors": []  // Optional - only present if partial failure
    }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="Invalid payload - expected JSON object")
        
        patient_context = request.get("patient_context")
        if not patient_context:
            raise HTTPException(status_code=400, detail="patient_context is required")
        
        mutations = request.get("mutations")
        
        # Validate patient context structure
        if not isinstance(patient_context, dict):
            raise HTTPException(status_code=400, detail="patient_context must be an object")
        
        if "disease" not in patient_context:
            raise HTTPException(status_code=400, detail="patient_context.disease is required")
        
        # Normalize treatment_history format
        treatment_history = patient_context.get("treatment_history", [])
        if not isinstance(treatment_history, list):
            treatment_history = []
        
        # Normalize biomarkers
        biomarkers = patient_context.get("biomarkers", {})
        if not isinstance(biomarkers, dict):
            biomarkers = {}
        
        normalized_context = {
            "disease": patient_context["disease"],
            "treatment_history": treatment_history,
            "biomarkers": biomarkers,
            "germline_status": patient_context.get("germline_status", "unknown"),
            "tumor_context": patient_context.get("tumor_context")  # Sporadic Cancer Support
        }
        
        # Build complete care plan
        result = await build_complete_care_plan(
            patient_context=normalized_context,
            mutations=mutations
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete care plan orchestration failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )


