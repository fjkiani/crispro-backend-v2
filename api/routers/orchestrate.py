"""
Orchestration Router - Master API for the MOAT pipeline.

Endpoints:
- POST /api/orchestrate/full: Run complete pipeline
- GET /api/orchestrate/status/{patient_id}: Get pipeline status
- GET /api/patients/{patient_id}: Get full patient state
- GET /api/patients/{patient_id}/care-plan: Get care plan
- GET /api/patients: List all patients
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from typing import Optional, List
import logging
import json
from datetime import datetime

from ..schemas.orchestrate import (
    OrchestratePipelineRequest,
    OrchestratePipelineResponse,
    PipelineStatusResponse,
    PipelinePhase,
    AlertResponse,
    BiomarkerProfileResponse,
    ResistancePredictionResponse,
    DrugRankingResponse,
    TrialMatchResponse,
    CarePlanResponse,
    CarePlanSection,
    NutritionPlanResponse,
    SyntheticLethalityResponse
)
from ..services.orchestrator import get_orchestrator, PatientState

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["Orchestration"])


# ============================================================================
# MAIN ORCHESTRATION ENDPOINTS
# ============================================================================

@router.post("/orchestrate/full", response_model=OrchestratePipelineResponse)
async def run_full_pipeline(
    request: OrchestratePipelineRequest
):
    """
    Run the complete MOAT orchestration pipeline with JSON request.
    
    This is the main entry point for patient analysis. Provide:
    - Disease type (required)
    - Mutations (list of gene variants)
    - Cytogenetics (optional, for MM)
    - Treatment context (line, prior therapies)
    
    The pipeline runs through:
    1. Biomarker calculation (TMB, MSI, HRD)
    2. Resistance prediction (validated: DIS3 RR=2.08, TP53 RR=1.90)
    3. Drug efficacy ranking (S/P/E framework)
    4. Synthetic lethality analysis
    5. Clinical trial matching (mechanism vector)
    6. Nutrition planning
    7. Care plan generation
    8. Monitoring setup
    
    Returns complete analysis results.
    """
    orchestrator = get_orchestrator()
    
    try:
        # Convert mutations to dict format
        mutations = [m.dict() if hasattr(m, 'dict') else m for m in request.mutations]
        
        # Convert cytogenetics to dict if provided
        cytogenetics = request.cytogenetics.to_dict() if request.cytogenetics else None
        
        # Run pipeline
        state = await orchestrator.run_full_pipeline(
            mutations=mutations,
            disease=request.disease,
            patient_id=request.patient_id,
            cytogenetics=cytogenetics,
            treatment_line=request.treatment_line,
            prior_therapies=request.prior_therapies,
            current_regimen=request.current_regimen,
            skip_agents=request.skip_agents
        )
        
        return _state_to_response(state)
        
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/orchestrate/full/upload", response_model=OrchestratePipelineResponse)
async def run_full_pipeline_with_file(
    file: UploadFile = File(...),
    file_type: Optional[str] = Form(None),
    disease: str = Form("ovarian_cancer"),
    patient_id: Optional[str] = Form(None),
    treatment_line: int = Form(1),
    prior_therapies: Optional[str] = Form(None),
    current_regimen: Optional[str] = Form(None),
    skip_agents: Optional[str] = Form(None)
):
    """
    Run the complete MOAT orchestration pipeline with file upload.
    
    Accepts multipart/form-data with:
    - file: VCF, MAF, PDF, or JSON file
    - file_type: Optional file type override (auto-detected from filename if not provided)
    - disease: Disease type (default: ovarian_cancer)
    - patient_id: Optional patient ID
    - treatment_line: Current treatment line (default: 1)
    - prior_therapies: JSON array string of prior therapies
    - current_regimen: Current treatment regimen
    - skip_agents: JSON array string of agents to skip
    
    The pipeline will extract mutations from the file and run all analysis agents.
    """
    orchestrator = get_orchestrator()
    
    try:
        # Parse JSON string parameters
        prior_therapies_list = json.loads(prior_therapies) if prior_therapies else None
        skip_agents_list = json.loads(skip_agents) if skip_agents else None
        
        # Auto-detect file type from filename if not provided
        detected_file_type = file_type
        if not detected_file_type and file.filename:
            ext = file.filename.split('.')[-1].lower()
            detected_file_type = ext if ext in ['vcf', 'maf', 'pdf', 'json', 'txt', 'csv'] else 'json'
        
        # Run pipeline with file
        state = await orchestrator.run_full_pipeline(
            file=file.file,
            file_type=detected_file_type or 'json',
            disease=disease,
            patient_id=patient_id,
            treatment_line=treatment_line,
            prior_therapies=prior_therapies_list,
            current_regimen=current_regimen,
            skip_agents=skip_agents_list
        )
        
        return _state_to_response(state)
        
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON in form parameters: {e}")
        raise HTTPException(status_code=400, detail=f"Invalid JSON in form parameters: {str(e)}")
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/orchestrate/status/{patient_id}", response_model=PipelineStatusResponse)
async def get_pipeline_status(patient_id: str):
    """
    Get the current status of a pipeline execution.
    
    Use this to poll for status during async execution.
    """
    orchestrator = get_orchestrator()
    state = await orchestrator.get_state(patient_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    
    # Find current running agent
    current_agent = None
    for execution in state.agent_executions:
        if execution.status == "running":
            current_agent = execution.agent_id
            break
    
    # Get errors from failed agents
    errors = [e.error for e in state.agent_executions if e.error]
    
    return PipelineStatusResponse(
        patient_id=state.patient_id,
        phase=PipelinePhase(state.phase.value),
        progress_percent=state.get_progress_percent(),
        current_agent=current_agent,
        completed_agents=state.get_completed_agents(),
        alerts=[_alert_to_response(a) for a in state.alerts],
        errors=errors,
        status_url=f"/api/orchestrate/status/{patient_id}",
        care_plan_url=f"/api/patients/{patient_id}/care-plan" if state.care_plan else None
    )


# ============================================================================
# PATIENT ENDPOINTS
# ============================================================================

@router.get("/orchestrate/state/{patient_id}", response_model=OrchestratePipelineResponse)
@router.get("/patients/{patient_id}", response_model=OrchestratePipelineResponse)
async def get_patient(patient_id: str):
    """
    Get full patient state including all agent outputs.
    
    Available at both:
    - /api/orchestrate/state/{patient_id} (for frontend compatibility)
    - /api/patients/{patient_id} (alternative endpoint)
    """
    orchestrator = get_orchestrator()
    state = await orchestrator.get_state(patient_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    
    return _state_to_response(state)


@router.get("/patients/{patient_id}/care-plan")
async def get_care_plan(patient_id: str):
    """
    Get just the care plan for a patient.
    """
    orchestrator = get_orchestrator()
    care_plan = await orchestrator.get_care_plan(patient_id)
    
    if not care_plan:
        raise HTTPException(status_code=404, detail=f"Care plan not found for {patient_id}")
    
    return care_plan


@router.get("/orchestrate/states", response_model=List[dict])
@router.get("/patients", response_model=List[dict])
async def list_patients(
    limit: int = 50,
    phase: Optional[str] = None
):
    """
    List all patients with optional filtering.
    
    Available at both:
    - /api/orchestrate/states (for frontend compatibility)
    - /api/patients (alternative endpoint)
    """
    orchestrator = get_orchestrator()
    states = await orchestrator.get_all_states(limit=limit, phase=phase)
    
    return [s.to_dict() for s in states]


@router.get("/patients/{patient_id}/history")
async def get_patient_history(patient_id: str, limit: int = 50):
    """
    Get state change history for a patient.
    """
    orchestrator = get_orchestrator()
    state = await orchestrator.get_state(patient_id)
    
    if not state:
        raise HTTPException(status_code=404, detail=f"Patient {patient_id} not found")
    
    history = [h.to_dict() for h in state.history[-limit:]]
    
    return {
        'patient_id': patient_id,
        'total_changes': len(state.history),
        'history': history
    }


# ============================================================================
# HEALTH CHECK
# ============================================================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "moat-orchestrator",
        "timestamp": datetime.utcnow().isoformat()
    }


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def _state_to_response(state: PatientState) -> OrchestratePipelineResponse:
    """Convert PatientState to API response."""
    duration_ms = (datetime.utcnow() - state.created_at).total_seconds() * 1000
    
    return OrchestratePipelineResponse(
        patient_id=state.patient_id,
        disease=state.disease or "unknown",
        phase=PipelinePhase(state.phase.value),
        progress_percent=state.get_progress_percent(),
        completed_agents=state.get_completed_agents(),
        created_at=state.created_at.isoformat(),
        updated_at=state.updated_at.isoformat(),
        duration_ms=duration_ms,
        mutation_count=len(state.mutations),
        mechanism_vector=state.mechanism_vector,
        biomarker_profile=_biomarker_to_response(state.biomarker_profile),
        resistance_prediction=_resistance_to_response(state.resistance_prediction),
        drug_ranking=_drug_ranking_to_response(state.drug_ranking),
        trial_matches=_trials_to_response(state.trial_matches),
        care_plan=_care_plan_to_response(state),
        nutrition_plan=_nutrition_plan_to_response(state.nutrition_plan),
        synthetic_lethality_result=_synthetic_lethality_to_response(state.synthetic_lethality_result),
        data_quality_flags=state.data_quality_flags,
        alerts=[_alert_to_response(a) for a in state.alerts]
    )


def _alert_to_response(alert) -> AlertResponse:
    """Convert Alert to response."""
    from ..schemas.orchestrate import AlertSeverity as ResponseSeverity
    
    return AlertResponse(
        id=alert.id,
        alert_type=alert.alert_type,
        message=alert.message,
        severity=ResponseSeverity(alert.severity.value),
        timestamp=alert.timestamp.isoformat(),
        source_agent=alert.source_agent,
        acknowledged=alert.acknowledged
    )


def _biomarker_to_response(profile: dict) -> Optional[BiomarkerProfileResponse]:
    """Convert biomarker profile to response."""
    if not profile:
        return None
    
    return BiomarkerProfileResponse(
        tmb=profile.get('tmb'),
        msi=profile.get('msi'),
        hrd=profile.get('hrd'),
        io_eligible=profile.get('io_eligible', False),
        parp_eligible=profile.get('parp_eligible', False)
    )


def _resistance_to_response(prediction: dict) -> Optional[ResistancePredictionResponse]:
    """Convert resistance prediction to response."""
    if not prediction:
        return None
    
    return ResistancePredictionResponse(
        risk_level=prediction.get('risk_level', 'LOW'),
        probability=prediction.get('probability', 0.0),
        confidence=prediction.get('confidence', 0.0),
        detected_genes=prediction.get('detected_genes', []),
        alternatives=prediction.get('next_line_options', {}).get('alternatives'),
        regimen_changes=prediction.get('next_line_options', {}).get('regimen_changes'),
        monitoring_changes=prediction.get('next_line_options', {}).get('monitoring_changes')
    )


def _drug_ranking_to_response(ranking: list) -> Optional[List[DrugRankingResponse]]:
    """Convert drug ranking to response."""
    if not ranking:
        return None
    
    return [
        DrugRankingResponse(
            drug_name=d.get('drug_name', ''),
            drug_class=d.get('drug_class', ''),
            efficacy_score=d.get('efficacy_score', 0.0),
            tier=d.get('tier'),
            confidence=d.get('confidence'),
            mechanism=d.get('mechanism'),
            rationale=d.get('rationale')
        )
        for d in ranking
    ]


def _trials_to_response(matches: list) -> Optional[List[TrialMatchResponse]]:
    """Convert trial matches to response."""
    if not matches:
        return None
    
    return [
        TrialMatchResponse(
            nct_id=t.get('nct_id', ''),
            title=t.get('title', ''),
            phase=t.get('phase'),
            status=t.get('status'),
            mechanism_fit_score=t.get('mechanism_fit_score'),
            eligibility_score=t.get('eligibility_score'),
            combined_score=t.get('combined_score'),
            why_matched=t.get('why_matched'),
            url=t.get('url')
        )
        for t in matches
    ]


def _care_plan_to_response(state: PatientState) -> Optional[CarePlanResponse]:
    """Convert care plan to response."""
    if not state.care_plan:
        return None
    
    sections = [
        CarePlanSection(title=s['title'], content=s['content'])
        for s in state.care_plan.get('sections', [])
    ]
    
    return CarePlanResponse(
        patient_id=state.patient_id,
        disease=state.disease or "unknown",
        generated_at=state.care_plan.get('generated_at', datetime.utcnow().isoformat()),
        sections=sections,
        alerts=[_alert_to_response(a) for a in state.alerts]
    )


def _nutrition_plan_to_response(nutrition_plan) -> Optional[NutritionPlanResponse]:
    """Convert nutrition plan to response."""
    if not nutrition_plan:
        return None
    
    # If it's a NutritionPlan object, convert to dict
    if hasattr(nutrition_plan, 'to_dict'):
        plan_dict = nutrition_plan.to_dict()
    elif isinstance(nutrition_plan, dict):
        plan_dict = nutrition_plan
    else:
        return None
    
    return NutritionPlanResponse(
        patient_id=plan_dict.get('patient_id', ''),
        treatment=plan_dict.get('treatment', ''),
        supplements=plan_dict.get('supplements', []),
        foods_to_prioritize=plan_dict.get('foods_to_prioritize', []),
        foods_to_avoid=plan_dict.get('foods_to_avoid', []),
        drug_food_interactions=plan_dict.get('drug_food_interactions', []),
        timing_rules=plan_dict.get('timing_rules', {}),
        provenance=plan_dict.get('provenance', {})
    )


def _synthetic_lethality_to_response(sl_result) -> Optional[SyntheticLethalityResponse]:
    """Convert synthetic lethality result to response."""
    if not sl_result:
        return None
    
    # If it's a SyntheticLethalityResult dataclass, convert to dict
    from dataclasses import asdict
    if hasattr(sl_result, '__dict__') and not isinstance(sl_result, dict):
        result_dict = asdict(sl_result) if hasattr(sl_result, '__dataclass_fields__') else sl_result.__dict__
    elif isinstance(sl_result, dict):
        result_dict = sl_result
    else:
        return None
    
    return SyntheticLethalityResponse(
        patient_id=result_dict.get('patient_id'),
        disease=result_dict.get('disease', ''),
        synthetic_lethality_detected=result_dict.get('synthetic_lethality_detected', False),
        double_hit_description=result_dict.get('double_hit_description'),
        essentiality_scores=[
            asdict(score) if hasattr(score, '__dataclass_fields__') else score
            for score in result_dict.get('essentiality_scores', [])
        ] if isinstance(result_dict.get('essentiality_scores'), list) else [],
        broken_pathways=[
            asdict(pathway) if hasattr(pathway, '__dataclass_fields__') else pathway
            for pathway in result_dict.get('broken_pathways', [])
        ] if isinstance(result_dict.get('broken_pathways'), list) else [],
        essential_pathways=[
            asdict(pathway) if hasattr(pathway, '__dataclass_fields__') else pathway
            for pathway in result_dict.get('essential_pathways', [])
        ] if isinstance(result_dict.get('essential_pathways'), list) else [],
        recommended_drugs=[
            asdict(drug) if hasattr(drug, '__dataclass_fields__') else drug
            for drug in result_dict.get('recommended_drugs', [])
        ] if isinstance(result_dict.get('recommended_drugs'), list) else [],
        suggested_therapy=result_dict.get('suggested_therapy', ''),
        explanation=result_dict.get('explanation')
    )

