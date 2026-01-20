"""
Orchestration Schemas - Request/response models for the orchestration API.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .patient import MutationInput, CytogeneticsInput, ClinicalDataInput


class DiseaseType(str, Enum):
    OVARIAN = "ovarian"
    MYELOMA = "myeloma"
    LUNG = "lung"
    BREAST = "breast"
    COLORECTAL = "colorectal"
    OTHER = "other"


class PipelinePhase(str, Enum):
    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    RANKING = "ranking"
    MATCHING = "matching"
    PLANNING = "planning"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    ERROR = "error"


class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


class AlertResponse(BaseModel):
    """Alert in API responses."""
    id: str
    alert_type: str
    message: str
    severity: AlertSeverity
    timestamp: str
    source_agent: str
    acknowledged: bool = False


class OrchestratePipelineRequest(BaseModel):
    """
    Request to run the full orchestration pipeline.
    
    Three modes:
    1. Provide mutations directly
    2. Provide patient profile
    3. Provide file (requires multipart)
    """
    # Patient identity
    patient_id: Optional[str] = Field(None, description="Patient ID (auto-generated if not provided)")
    disease: str = Field(..., description="Disease type")
    
    # Mutation data (primary mode)
    mutations: List[MutationInput] = Field(default=[], description="List of mutations")
    
    # MM-specific
    cytogenetics: Optional[CytogeneticsInput] = Field(None, description="Cytogenetics (MM)")
    
    # Treatment context
    treatment_line: int = Field(1, ge=1, description="Current treatment line")
    prior_therapies: Optional[List[str]] = Field(None, description="Prior drug classes")
    current_regimen: Optional[str] = Field(None, description="Current regimen")
    current_drug_class: Optional[str] = Field(None, description="Current drug class")
    
    # Clinical data
    clinical_data: Optional[ClinicalDataInput] = Field(None, description="Clinical data")
    
    # Options
    run_async: bool = Field(False, description="Return immediately with job ID")
    skip_agents: Optional[List[str]] = Field(None, description="Agents to skip")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "disease": "myeloma",
                "mutations": [
                    {"gene": "DIS3", "hgvs_p": "p.C562Y"}
                ],
                "cytogenetics": {"del_17p": True},
                "treatment_line": 2,
                "current_regimen": "VRd"
            }
        }
    }


class DrugRankingResponse(BaseModel):
    """Drug ranking in responses."""
    drug_name: str
    drug_class: str
    efficacy_score: float
    tier: Optional[str] = None
    confidence: Optional[str] = None
    mechanism: Optional[str] = None
    rationale: Optional[List[str]] = None


class TrialMatchResponse(BaseModel):
    """Trial match in responses."""
    nct_id: str
    title: str
    phase: Optional[str] = None
    status: Optional[str] = None
    mechanism_fit_score: Optional[float] = None
    eligibility_score: Optional[float] = None
    combined_score: Optional[float] = None
    why_matched: Optional[str] = None
    url: Optional[str] = None


class ResistancePredictionResponse(BaseModel):
    """Resistance prediction in responses."""
    risk_level: str
    probability: float
    confidence: float
    detected_genes: List[Dict[str, Any]]
    alternatives: Optional[List[Dict[str, Any]]] = None
    regimen_changes: Optional[List[Dict[str, Any]]] = None
    monitoring_changes: Optional[Dict[str, Any]] = None


class BiomarkerProfileResponse(BaseModel):
    """Biomarker profile in responses."""
    tmb: Optional[Dict[str, Any]] = None
    msi: Optional[Dict[str, Any]] = None
    hrd: Optional[Dict[str, Any]] = None
    io_eligible: bool = False
    parp_eligible: bool = False


class CarePlanSection(BaseModel):
    """Section of a care plan."""
    title: str
    content: Any


class CarePlanResponse(BaseModel):
    """Care plan in responses."""
    patient_id: str
    disease: str
    generated_at: str
    sections: List[CarePlanSection]
    alerts: List[AlertResponse]


class NutritionPlanResponse(BaseModel):
    """Nutrition plan in responses."""
    patient_id: str
    treatment: str
    supplements: List[Dict[str, Any]]
    foods_to_prioritize: List[Dict[str, Any]]
    foods_to_avoid: List[Dict[str, Any]]
    drug_food_interactions: List[Dict[str, Any]]
    timing_rules: Dict[str, str]
    provenance: Dict[str, Any]


class SyntheticLethalityResponse(BaseModel):
    """Synthetic lethality result in responses."""
    patient_id: Optional[str] = None
    disease: str
    synthetic_lethality_detected: bool
    double_hit_description: Optional[str] = None
    essentiality_scores: List[Dict[str, Any]]
    broken_pathways: List[Dict[str, Any]]
    essential_pathways: List[Dict[str, Any]]
    recommended_drugs: List[Dict[str, Any]]
    suggested_therapy: str
    explanation: Optional[Dict[str, Any]] = None


class OrchestratePipelineResponse(BaseModel):
    """
    Response from the orchestration pipeline.
    
    Includes all agent outputs and state.
    """
    # Identity
    patient_id: str
    disease: str
    
    # Status
    phase: PipelinePhase
    progress_percent: int
    completed_agents: List[str]
    
    # Timing
    created_at: str
    updated_at: str
    duration_ms: Optional[float] = None
    
    # Agent outputs
    mutation_count: int
    mechanism_vector: List[float]
    
    biomarker_profile: Optional[BiomarkerProfileResponse] = None
    resistance_prediction: Optional[ResistancePredictionResponse] = None
    drug_ranking: Optional[List[DrugRankingResponse]] = None
    trial_matches: Optional[List[TrialMatchResponse]] = None
    care_plan: Optional[CarePlanResponse] = None
    nutrition_plan: Optional[NutritionPlanResponse] = None
    synthetic_lethality_result: Optional[SyntheticLethalityResponse] = None
    
    # Quality
    data_quality_flags: List[str]
    alerts: List[AlertResponse]
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "patient_id": "PT-ABC12345",
                "disease": "myeloma",
                "phase": "complete",
                "progress_percent": 100,
                "completed_agents": ["biomarker", "resistance", "drug_efficacy", "trial_matching", "care_plan"],
                "created_at": "2025-01-28T10:00:00Z",
                "updated_at": "2025-01-28T10:01:30Z",
                "duration_ms": 90000,
                "mutation_count": 2,
                "mechanism_vector": [0.8, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0],
                "data_quality_flags": [],
                "alerts": []
            }
        }
    }


class PipelineStatusResponse(BaseModel):
    """Status response for async pipeline execution."""
    patient_id: str
    phase: PipelinePhase
    progress_percent: int
    current_agent: Optional[str] = None
    completed_agents: List[str]
    alerts: List[AlertResponse]
    errors: List[str]
    
    # Links
    status_url: str
    care_plan_url: Optional[str] = None

