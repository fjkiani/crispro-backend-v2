"""
Ayesha Complete Care Plan Schemas

Request/Response models for unified drug + food recommendations
"""

from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from datetime import datetime

# Import TumorContext for sporadic cancer support (Day 1)
try:
    from .tumor_context import TumorContext
except ImportError:
    TumorContext = None  # Graceful fallback if not yet available


class BiomarkerContext(BaseModel):
    """Biomarker context for patient"""
    brca1_mutant: bool = False
    brca2_mutant: bool = False
    hrd_positive: bool = False
    tp53_mutant: bool = False
    high_tmb: bool = False
    msi_status: Optional[str] = None
    pd_l1_status: Optional[str] = None


class TreatmentLine(BaseModel):
    """Single treatment line record"""
    line: int = Field(..., ge=1, le=10)
    drugs: List[str] = []
    outcome: Optional[str] = None  # "response", "progression", "stable", "partial_response"


class PatientContext(BaseModel):
    """Complete patient context for unified care plan"""
    disease: str = "ovarian_cancer_hgs"
    treatment_history: List[TreatmentLine] = []
    biomarkers: BiomarkerContext = Field(default_factory=BiomarkerContext)
    
    # Sporadic Cancer Strategy (Day 1) - NEW fields
    germline_status: Literal["positive", "negative", "unknown"] = "unknown"
    tumor_context: Optional["TumorContext"] = None  # From /api/tumor/quick_intake or /ingest_ngs
    
    class Config:
        # Allow forward references for TumorContext
        arbitrary_types_allowed = True


class CompleteCareRequest(BaseModel):
    """Request for unified complete care plan"""
    patient_context: PatientContext


class DrugRecommendation(BaseModel):
    """Individual drug recommendation"""
    drug: str
    efficacy_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    tier: str  # "supported", "consider", "insufficient"
    sae_features: Optional[Dict[str, Any]] = None
    rationale: Optional[str] = None
    citations: Optional[List[str]] = None
    badges: Optional[List[str]] = None
    insights: Optional[Dict[str, Any]] = None


class FoodRecommendation(BaseModel):
    """Individual food/supplement recommendation"""
    compound: str
    targets: List[str] = []
    pathways: List[str] = []
    efficacy_score: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    sae_features: Optional[Dict[str, Any]] = None
    dosage: Optional[str] = None
    rationale: Optional[str] = None
    citations: Optional[List[str]] = None


class ConfidenceBreakdown(BaseModel):
    """Integrated confidence breakdown"""
    drug_component: float = Field(..., ge=0.0, le=1.0)
    food_component: float = Field(..., ge=0.0, le=1.0)
    integration_method: str = "weighted_average"  # "weighted_average", "simple_average", "min", "max"


class AnalysisProvenance(BaseModel):
    """Provenance for drug or food analysis"""
    endpoint: str
    data_sources: List[str] = []
    papers_reviewed: int = 0
    run_id: Optional[str] = None
    timestamp: Optional[str] = None


class CompleteCareResponse(BaseModel):
    """Unified complete care plan response"""
    run_id: str
    timestamp: str
    patient_context: PatientContext
    
    drug_recommendations: List[DrugRecommendation] = []
    food_recommendations: List[FoodRecommendation] = []
    
    integrated_confidence: float = Field(..., ge=0.0, le=1.0)
    confidence_breakdown: ConfidenceBreakdown
    
    provenance: Dict[str, Any] = Field(default_factory=dict)
    
    # Error handling (partial results)
    errors: Optional[List[str]] = None


