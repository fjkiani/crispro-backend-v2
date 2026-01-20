"""
Pydantic Models for Personalized Outreach System
"""
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


class TrialSearchRequest(BaseModel):
    """Request for searching clinical trials."""
    conditions: List[str] = Field(default_factory=list, description="Disease conditions")
    interventions: List[str] = Field(default_factory=list, description="Interventions/drugs")
    keywords: List[str] = Field(default_factory=list, description="Keywords (e.g., CA-125, biomarker)")
    phases: List[str] = Field(default_factory=list, description="Trial phases")
    status: List[str] = Field(default_factory=list, description="Trial status")
    max_results: int = Field(default=100, description="Maximum trials to return")


class IntelligenceExtractionRequest(BaseModel):
    """Request for extracting intelligence from a trial."""
    nct_id: str = Field(..., description="ClinicalTrials.gov identifier")
    pi_name: Optional[str] = Field(None, description="PI name (optional, extracted if not provided)")
    institution: Optional[str] = Field(None, description="Institution name (optional)")


class EmailGenerationRequest(BaseModel):
    """Request for generating personalized email."""
    intelligence_profile: Dict[str, Any] = Field(..., description="Complete intelligence profile")
    outreach_config: Optional[Dict[str, Any]] = Field(None, description="Outreach configuration")


class IntelligenceProfileResponse(BaseModel):
    """Response containing complete intelligence profile."""
    nct_id: str
    trial_intelligence: Dict[str, Any]
    research_intelligence: Dict[str, Any]
    biomarker_intelligence: Dict[str, Any]
    goals: List[str]
    value_proposition: List[str]
    personalization_quality: float
    status: str


class EmailResponse(BaseModel):
    """Response containing generated email."""
    subject: str
    body: str
    personalization_quality: float
    key_points: List[str]
    pi_name: str
    pi_email: str
    institution: str
