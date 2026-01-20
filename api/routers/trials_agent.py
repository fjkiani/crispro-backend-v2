"""
Autonomous Trial Agent Router - Component 5
Endpoint: /api/trials/agent/search
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
from api.services.autonomous_trial_agent import AutonomousTrialAgent

router = APIRouter()


class PatientDataRequest(BaseModel):
    """Patient data for autonomous trial search with sporadic cancer support."""
    patient_summary: Optional[str] = None  # ⚔️ NEW: From Q2C Router
    mutations: Optional[List[Dict[str, Any]]] = []
    disease: Optional[str] = None
    location: Optional[Dict[str, str]] = None
    biomarkers: Optional[List[str]] = None
    state: Optional[str] = None
    germline_status: Optional[str] = None  # NEW: Sporadic cancer filtering
    tumor_context: Optional[Dict[str, Any]] = None  # NEW: TMB/MSI/HRD context
    mechanism_vector: Optional[List[float]] = None  # NEW: 7D mechanism vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux] for mechanism fit ranking


@router.post("/api/trials/agent/search")
async def autonomous_trial_search(request: PatientDataRequest):
    """
    Autonomous trial search agent with mechanism-based ranking.
    Automatically generates queries and finds matching trials.
    If mechanism_vector provided, applies mechanism fit ranking (Manager P4).
    
    **Research Use Only**
    """
    try:
        # ⚔️ FIX: Extract disease from patient_summary if provided
        disease = request.disease
        if request.patient_summary and not disease:
            # Try to extract disease from summary
            summary_lower = request.patient_summary.lower()
            if "ovarian" in summary_lower:
                disease = "ovarian_cancer"
            elif "breast" in summary_lower:
                disease = "breast_cancer"
            elif "lung" in summary_lower:
                disease = "lung_cancer"
        
        patient_data = {
            "mutations": request.mutations or [],
            "disease": disease or "cancer",  # ⚔️ FIX: Provide default
            "location": request.location or {},
            "biomarkers": request.biomarkers or [],
            "state": request.state,
            "germline_status": request.germline_status,
            "tumor_context": request.tumor_context
        }
        
        # NEW: Use TrialMatchingAgent if mechanism_vector provided (mechanism fit ranking)
        if request.mechanism_vector and len(request.mechanism_vector) == 7:
            from api.services.trials.trial_matching_agent import TrialMatchingAgent
            
            trial_agent = TrialMatchingAgent()
            biomarker_profile = None
            if request.tumor_context:
                biomarker_profile = {
                    "tmb": request.tumor_context.get("tmb"),
                    "msi": request.tumor_context.get("msi_status"),
                    "hrd": request.tumor_context.get("hrd_score")
                }
            
            # Use TrialMatchingAgent with mechanism fit ranking
            result = await trial_agent.match(
                patient_profile=patient_data,
                biomarker_profile=biomarker_profile,
                mechanism_vector=request.mechanism_vector,
                max_results=10
            )
            
            # Convert TrialMatchingResult to response format
            trials = []
            for match in result.matches:
                trials.append({
                    "nct_id": match.nct_id,
                    "title": match.title,
                    "phase": match.phase,
                    "status": match.status,
                    "mechanism_fit_score": match.mechanism_fit_score,
                    "combined_score": match.combined_score,
                    "mechanism_alignment": match.mechanism_alignment,
                    "eligibility_score": match.eligibility_score,
                    "boost_applied": match.boost_applied,
                    "location": match.location,
                    "enrollment_criteria": match.enrollment_criteria,
                    "genetic_requirements": match.genetic_requirements,
                    "principal_investigator": match.principal_investigator,
                    "site_contact": match.site_contact,
                    "source_url": match.source_url
                })
            
            return {
                "success": True,
                "data": {
                    "matched_trials": trials,
                    "total_found": len(trials),
                    "queries_used": result.provenance.get("queries_used", []),
                    "mechanism_fit_applied": True,
                    "mechanism_vector_used": request.mechanism_vector
                },
                "trials": trials,
                "total_found": len(trials),
                "excluded_count": 0,
                "mechanism_fit_applied": True
            }
        else:
            # Fallback: Use AutonomousTrialAgent (basic search, no mechanism fit)
            agent = AutonomousTrialAgent()
            
            results = await agent.search_for_patient(
                patient_data=patient_data,
                germline_status=request.germline_status,
                tumor_context=request.tumor_context,
                top_k=10
            )
            
            return {
                "success": True,
                "data": results,  # Return full results including metadata
                "trials": results.get("matched_trials", []),
                "total_found": results.get("total_found", 0),
                "excluded_count": results.get("excluded_count", 0),
                "mechanism_fit_applied": False,
                "note": "Mechanism fit not applied - provide mechanism_vector (7D) for mechanism-based ranking"
            }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class GenerateDossiersRequest(BaseModel):
    """Request to generate dossiers for a patient."""
    patient_profile: Dict[str, Any]  # Full or simple patient profile
    nct_ids: Optional[List[str]] = None  # Optional: specific NCT IDs, otherwise searches first
    use_llm: bool = True
    max_dossiers: int = 10


@router.post("/api/trials/agent/generate-dossiers")
async def generate_dossiers(request: GenerateDossiersRequest):
    """
    Autonomous end-to-end flow: Search → Filter → Generate Dossiers.
    
    If nct_ids provided, generates dossiers for those trials.
    Otherwise, searches for trials first, then generates dossiers.
    """
    try:
        agent = AutonomousTrialAgent()
        
        results = await agent.generate_dossiers_for_patient(
            patient_profile=request.patient_profile,
            nct_ids=request.nct_ids,
            use_llm=request.use_llm,
            max_dossiers=request.max_dossiers
        )
        
        return {
            "success": True,
            "data": results
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))



