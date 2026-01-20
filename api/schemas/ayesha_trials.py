"""
Ayesha Trial Matching Schemas

Pydantic models for precision trial matching for Ayesha's Stage IVB ovarian cancer.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import date


class AyeshaTrialProfile(BaseModel):
    """
    Ayesha's clinical profile for trial matching.
    
    Combines:
    - Known data (germline, CA-125, stage, mets)
    - Unknown data (tumor biomarkers awaiting NGS)
    """
    
    # Disease characteristics
    disease: str = Field(
        default="ovarian_cancer_high_grade_serous",
        description="Disease type for matching"
    )
    stage: str = Field(
        default="IVB",
        description="Cancer stage"
    )
    histology: str = Field(
        default="suspected_HGS",
        description="Histological subtype"
    )
    
    # Known biomarkers
    ca125: float = Field(
        default=2842.0,
        ge=0.0,
        description="Current CA-125 level (U/mL)"
    )
    germline_status: str = Field(
        default="NEGATIVE",
        description="Germline mutation status (NEGATIVE/POSITIVE/UNKNOWN)"
    )
    germline_brca: str = Field(
        default="negative",
        description="Germline BRCA status"
    )
    
    # Unknown biomarkers (awaiting NGS)
    somatic_brca: Optional[str] = Field(
        default=None,
        description="Somatic BRCA status (awaiting NGS)"
    )
    tumor_hrd_score: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=100.0,
        description="Tumor HRD score (awaiting NGS)"
    )
    tmb: Optional[float] = Field(
        default=None,
        ge=0.0,
        description="Tumor mutational burden (awaiting NGS)"
    )
    msi_status: Optional[str] = Field(
        default=None,
        description="MSI status (awaiting NGS)"
    )
    tp53_status: Optional[str] = Field(
        default="likely_mutated",
        description="TP53 mutation status"
    )
    
    # Metastatic burden
    peritoneal_carcinomatosis: str = Field(
        default="extensive",
        description="Peritoneal disease extent"
    )
    ascites: str = Field(
        default="moderate",
        description="Ascites presence/severity"
    )
    pleural_effusions: str = Field(
        default="bilateral_large",
        description="Pleural effusion status"
    )
    suv_max: float = Field(
        default=15.0,
        ge=0.0,
        description="Maximum SUV on PET scan"
    )
    
    # Treatment status
    treatment_line: int = Field(
        default=0,
        ge=0,
        description="Treatment line (0 = treatment-naive)"
    )
    prior_therapies: List[str] = Field(
        default_factory=list,
        description="List of prior therapies"
    )
    platinum_exposure: bool = Field(
        default=False,
        description="Prior platinum exposure"
    )
    
    # Clinical context
    age: int = Field(
        default=40,
        ge=0,
        le=120,
        description="Patient age"
    )
    location: str = Field(
        default="NYC",
        description="Patient location for proximity matching"
    )
    urgent: bool = Field(
        default=True,
        description="Urgent case flag"
    )


class TrialMatchReasoning(BaseModel):
    """Transparent reasoning for why a trial matches."""
    
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Match score (0-1)"
    )
    
    why_eligible: List[str] = Field(
        default_factory=list,
        description="Reasons why patient meets hard eligibility criteria"
    )
    why_good_fit: List[str] = Field(
        default_factory=list,
        description="Reasons why trial is a good fit (soft boosts)"
    )
    conditional_requirements: List[str] = Field(
        default_factory=list,
        description="Conditional requirements (NGS-gated, etc.)"
    )
    red_flags: List[str] = Field(
        default_factory=list,
        description="Warnings or concerns about this trial"
    )
    
    evidence_tier: str = Field(
        ...,
        description="Evidence tier: STANDARD, SUPPORTED, or INVESTIGATIONAL"
    )
    enrollment_likelihood: str = Field(
        ...,
        description="Enrollment likelihood: HIGH, MEDIUM, or LOW"
    )
    
    ca125_intelligence: Optional[Dict[str, Any]] = Field(
        default=None,
        description="CA-125 intelligence context"
    )
    germline_context: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Germline status context"
    )


class AyeshaTrialMatch(BaseModel):
    """Complete trial match with reasoning."""
    
    # Trial data
    nct_id: str = Field(
        ...,
        description="ClinicalTrials.gov identifier"
    )
    title: str = Field(
        ...,
        description="Trial title"
    )
    phase: str = Field(
        ...,
        description="Trial phase (Phase 1, Phase 2, Phase 3)"
    )
    status: str = Field(
        ...,
        description="Trial status (Recruiting, Active, etc.)"
    )
    interventions: List[str] = Field(
        default_factory=list,
        description="List of interventions/drugs"
    )
    locations: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Trial locations (sites)"
    )
    
    # Match data
    match_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Overall match score"
    )
    reasoning: TrialMatchReasoning = Field(
        ...,
        description="Transparent reasoning for match"
    )
    
    # Contact (optional - may be blank, use ClinicalTrials.gov link)
    contact_name: Optional[str] = Field(
        default=None,
        description="Contact name (if available)"
    )
    contact_phone: Optional[str] = Field(
        default=None,
        description="Contact phone (if available)"
    )
    contact_email: Optional[str] = Field(
        default=None,
        description="Contact email (if available)"
    )
    
    # Additional metadata
    source_url: Optional[str] = Field(
        default=None,
        description="ClinicalTrials.gov URL"
    )
    optimization_score: Optional[float] = Field(
        default=None,
        description="Graph optimization score (if available)"
    )


class AyeshaTrialSearchResponse(BaseModel):
    """Response from Ayesha trial search endpoint."""
    
    trials: List[AyeshaTrialMatch] = Field(
        ...,
        description="Top 10 ranked trial matches"
    )
    total_screened: int = Field(
        ...,
        ge=0,
        description="Total number of trials screened"
    )
    ca125_intelligence: Dict[str, Any] = Field(
        ...,
        description="CA-125 intelligence analysis"
    )
    provenance: Dict[str, Any] = Field(
        ...,
        description="Provenance and metadata"
    )


