"""
Supplement Recommendation Schemas

Pydantic models for supplement recommendations based on drugs + treatment line.
Generates recommendations considering drug-supplement interactions, disease needs, and treatment context.

Research Use Only - Not for Clinical Decision Making
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class SupplementPriority(str, Enum):
    """Priority levels for supplement recommendations"""
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class SupplementCategory(str, Enum):
    """Categories of supplements"""
    BONE_HEALTH = "bone_health"
    ANTI_INFLAMMATORY = "anti_inflammatory"
    NEUROPROTECTIVE = "neuroprotective"
    CARDIOPROTECTIVE = "cardioprotective"
    DRUG_INTERACTION = "drug_interaction"
    GENERAL_HEALTH = "general_health"
    NUTRITION_SUPPORT = "nutrition_support"


class SupplementRecommendationRequest(BaseModel):
    """Request for supplement recommendations"""
    drugs: List[Dict[str, Any]] = Field(..., description="List of recommended drugs with name, class, moa")
    treatment_line: Optional[str] = Field(None, description="Treatment line (e.g., 'first-line', 'maintenance', 'second-line')")
    disease: Optional[str] = Field(None, description="Disease context (e.g., 'ovarian_cancer_hgs')")
    treatment_history: Optional[List[str]] = Field(default_factory=list, description="Prior therapies")
    germline_variants: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Germline variants for PGx considerations")


class SupplementRecommendation(BaseModel):
    """Individual supplement recommendation"""
    supplement: str = Field(..., description="Supplement name (e.g., 'Calcium + Vitamin D')")
    category: SupplementCategory = Field(..., description="Category of supplement")
    priority: SupplementPriority = Field(..., description="Priority level")
    rationale: str = Field(..., description="Why this supplement is recommended")
    dosage: Optional[str] = Field(None, description="Recommended dosage (e.g., '1200mg Ca + 2000 IU D3 daily')")
    timing: Optional[str] = Field(None, description="When to take (e.g., 'During treatment and for 6 months post-treatment')")
    evidence: Optional[str] = Field(None, description="Evidence sources (e.g., 'NCCN Survivorship Guidelines')")
    drug_interactions: Optional[List[str]] = Field(default_factory=list, description="Drug-supplement interactions to monitor")
    confidence: float = Field(0.75, ge=0.0, le=1.0, description="Confidence in recommendation")


class SupplementToAvoid(BaseModel):
    """Supplement that should be avoided"""
    supplement: str = Field(..., description="Supplement name to avoid")
    category: SupplementCategory = Field(..., description="Category")
    rationale: str = Field(..., description="Why to avoid")
    applicable_drugs: Optional[List[str]] = Field(default_factory=list, description="Drugs where this applies")
    confidence: float = Field(0.75, ge=0.0, le=1.0, description="Confidence")


class SupplementRecommendationResponse(BaseModel):
    """Response with supplement recommendations"""
    recommendations: List[SupplementRecommendation] = Field(default_factory=list, description="Recommended supplements")
    avoid: List[SupplementToAvoid] = Field(default_factory=list, description="Supplements to avoid")
    treatment_line_specific: Optional[Dict[str, List[SupplementRecommendation]]] = Field(None, description="Treatment-line-specific recommendations")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Provenance information")
