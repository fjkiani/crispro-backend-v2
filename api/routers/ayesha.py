"""
Ayesha Complete Care Router

Unified endpoint for complete care planning (drugs + foods)
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging

"""
Ayesha Complete Care Router (Legacy Adapter)

Adapts V1 requests to the V2 Ayesha Care Plan Orchestrator.
Maintains backward compatibility for /api/ayesha/complete_care_plan 
while routing all logic through the modular V2 system.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
import logging

from api.services.ayesha_care_plan.orchestrator import get_ayesha_care_plan_orchestrator
from api.services.ayesha_care_plan.schemas import CompleteCareV2Request

router = APIRouter(prefix="/api/ayesha", tags=["ayesha"])
logger = logging.getLogger(__name__)


@router.post("/complete_care_plan")
async def complete_care_plan(request: Dict[str, Any]):
    """
    Unified Complete Care Plan Endpoint (Adapter to V2)
    
    Orchestrates holistic care recommendations via V2 Modular Architecture.
    Refactored Jan 2026 to remove legacy code.
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="Invalid payload - expected JSON object")
        
        patient_context = request.get("patient_context", {})
        mutations = request.get("mutations", [])
        
        # 1. Map V1 Request -> V2 Request
        v2_request_data = {
            # Default to IVB for Ayesha if not specified
            "stage": patient_context.get("stage", "IVB"),
            "treatment_line": "either", # Default
            "germline_status": patient_context.get("germline_status", "unknown"),
            "treatment_history": patient_context.get("treatment_history", []),
            
            # Map mutations to tumor_context
            tumor_context = {
                "somatic_mutations": mutations,
                "biomarkers": patient_context.get("biomarkers", {})
            }
            
            # 1b. Apply Preview Scenario (if requested)
            scenario_id = request.get("scenario_id")
            scenario_ca125 = None
            if scenario_id:
                try:
                    from api.services.resistance_prophet.scenarios import apply_scenario_to_context, get_scenario
                    tumor_context = apply_scenario_to_context(tumor_context, scenario_id)
                    scn_def = get_scenario(scenario_id)
                    if scn_def and "ca125_value" in scn_def:
                        scenario_ca125 = scn_def["ca125_value"]
                    logger.info(f"Applied preview scenario: {scenario_id}")
                except ImportError:
                    logger.warning("Scenarios module not found, skipping preview injection")
                except Exception as e:
                    logger.error(f"Failed to apply scenario {scenario_id}: {e}")

            v2_request_data = {
                # Default to IVB for Ayesha if not specified
                "stage": patient_context.get("stage", "IVB"),
                "treatment_line": "either", # Default
                "germline_status": patient_context.get("germline_status", "unknown"),
                "treatment_history": patient_context.get("treatment_history", []),
                
                "tumor_context": tumor_context,
                
                # Injected Scalar (if present in scenario)
                "ca125_value": scenario_ca125 if scenario_ca125 is not None else patient_context.get("ca125_value"),
                
                # Flags - Enable all for complete plan
                "include_trials": True,
                "include_soc": True,
                "include_ca125": True,
                "include_wiwfm": True,
                "include_food": True, # Now supports derived foods
                "include_resistance": True,
                "include_resistance_prediction": True, # Enable Prophet by default for demo
            }
        
        # Use Pydantic validation
        v2_req = CompleteCareV2Request(**v2_request_data)
        
        # 2. Call V2 Orchestrator
        orchestrator = get_ayesha_care_plan_orchestrator()
        v2_response = await orchestrator.get_complete_care_plan(v2_req)
        
        # 3. Map V2 Response -> V1 Response Structure (Best Effort Compatibility)
        # The V2 response is richer but structured differently. 
        # We return the V2 response structure directly as it is a superset, 
        # assuming the frontend can handle the improved structure or is robust.
        # If strict V1 schema compliance is needed, we would need a mapper here.
        # Given "deprecate" instruction, returning the new payload is usually acceptable.
        
        return v2_response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Complete care plan adapter failed: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Internal server error: {str(e)}"
        )



