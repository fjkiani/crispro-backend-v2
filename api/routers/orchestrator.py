"""
Orchestrator API Router - REST endpoints for patient care pipeline orchestration.

Provides endpoints for:
- Running full pipeline
- Checking pipeline status
- Getting patient state
- Processing events
"""
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from ..services.orchestrator import Orchestrator
from ..services.orchestrator.state import PatientState, StatePhase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/orchestrate", tags=["orchestrator"])

# Global orchestrator instance
_orchestrator: Optional[Orchestrator] = None


def get_orchestrator() -> Orchestrator:
    """Get or create orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = Orchestrator()
    return _orchestrator


# Request/Response Models

class PipelineRequest(BaseModel):
    """Request to run full pipeline."""
    patient_profile: Optional[Dict[str, Any]] = None
    patient_id: Optional[str] = None
    options: Optional[Dict[str, Any]] = None


class PipelineResponse(BaseModel):
    """Response from pipeline execution."""
    job_id: str
    patient_id: str
    status: str
    phase: str
    progress: float
    estimated_time_seconds: Optional[int] = None
    alerts: List[Dict[str, Any]] = []


class StatusResponse(BaseModel):
    """Pipeline status response."""
    patient_id: str
    phase: str
    progress: float
    updated_at: str
    alerts: List[Dict[str, Any]] = []
    care_plan: Optional[Dict[str, Any]] = None


class EventRequest(BaseModel):
    """Request to process an event."""
    event_type: str
    data: Dict[str, Any]
    patient_id: str


# Endpoints

@router.post("/full", response_model=PipelineResponse)
async def run_full_pipeline(
    request: PipelineRequest,
    file: Optional[UploadFile] = File(None),
    file_type: Optional[str] = Form(None)
):
    """
    Run the complete end-to-end patient care pipeline.
    
    This endpoint orchestrates all agents:
    1. Data Extraction (if file provided)
    2. Biomarker Analysis
    3. Resistance Prediction
    4. Drug Efficacy Ranking
    5. Trial Matching
    6. Nutrition Planning
    7. Care Plan Generation
    8. Monitoring Configuration
    
    Args:
        request: Pipeline request with patient profile
        file: Optional uploaded file (NGS PDF, VCF, etc.)
        file_type: Type of file (pdf, vcf, maf, etc.)
    
    Returns:
        Pipeline response with job ID and status
    """
    try:
        orchestrator = get_orchestrator()
        
        # Run pipeline
        state = await orchestrator.run_full_pipeline(
            file=file.file if file else None,
            file_type=file_type,
            patient_profile=request.patient_profile,
            patient_id=request.patient_id,
            options=request.options or {}
        )
        
        return PipelineResponse(
            job_id=state.patient_id,
            patient_id=state.patient_id,
            status=state.phase.value,
            phase=state.phase.value,
            progress=state.get_progress(),
            estimated_time_seconds=None,  # TODO: Calculate based on phase
            alerts=state.alerts[-10:] if state.alerts else []
        )
        
    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status/{patient_id}", response_model=StatusResponse)
async def get_pipeline_status(patient_id: str):
    """
    Get current pipeline status for a patient.
    
    Args:
        patient_id: Patient ID
    
    Returns:
        Current pipeline status
    """
    try:
        orchestrator = get_orchestrator()
        state = await orchestrator.get_state(patient_id)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        
        return StatusResponse(
            patient_id=state.patient_id,
            phase=state.phase.value,
            progress=state.get_progress(),
            updated_at=state.updated_at.isoformat(),
            alerts=state.alerts[-10:] if state.alerts else [],
            care_plan=state.care_plan if state.care_plan else None
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Status check failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/state/{patient_id}")
async def get_patient_state(patient_id: str):
    """
    Get full patient state (for debugging/admin).
    
    Args:
        patient_id: Patient ID
    
    Returns:
        Complete patient state
    """
    try:
        orchestrator = get_orchestrator()
        state = await orchestrator.get_state(patient_id)
        
        if not state:
            raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
        
        return state.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"State retrieval failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/event")
async def process_event(request: EventRequest):
    """
    Process an incoming event (e.g., new lab result, progression).
    
    This will trigger the trigger system (Module 09) to evaluate
    conditions and execute automated responses.
    
    Args:
        request: Event request
    
    Returns:
        Event processing result
    """
    try:
        orchestrator = get_orchestrator()
        result = await orchestrator.process_event(
            event_type=request.event_type,
            data=request.data,
            patient_id=request.patient_id
        )
        
        return {
            'status': 'processed',
            'event_type': request.event_type,
            'patient_id': request.patient_id,
            'result': result
        }
        
    except Exception as e:
        logger.error(f"Event processing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check():
    """
    Health check endpoint for orchestrator service.
    
    Returns:
        Health status with service availability
    """
    try:
        orchestrator = get_orchestrator()
        # Check if orchestrator is initialized
        is_healthy = orchestrator is not None
        
        return {
            "status": "healthy" if is_healthy else "degraded",
            "service": "orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
            "version": "2.0.0",
            "components": {
                "orchestrator": is_healthy,
                "state_store": orchestrator.state_store is not None if orchestrator else False,
                "message_bus": orchestrator.message_bus is not None if orchestrator else False
            }
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "orchestrator",
            "timestamp": datetime.utcnow().isoformat(),
            "error": str(e)
        }


@router.get("/states")
async def list_all_states():
    """
    List all patient states (for admin/debugging).
    
    Returns:
        List of patient state summaries
    """
    try:
        orchestrator = get_orchestrator()
        states = await orchestrator.get_all_states()
        
        return {
            'count': len(states),
            'states': [state.to_summary() for state in states]
        }
        
    except Exception as e:
        logger.error(f"State listing failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


