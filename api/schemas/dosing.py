"""
Dosing Guidance Schemas

Pydantic models for pharmacogenomics-based dosing recommendations.
Integrates PharmGKB metabolizer status, toxicity risk, and treatment line context.

Research Use Only - Not for Clinical Decision Making
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum


class CPICLevel(str, Enum):
    """CPIC Evidence Levels"""
    A = "A"       # Strong evidence, actionable
    A_B = "A/B"   # Strong-moderate evidence
    B = "B"       # Moderate evidence
    C = "C"       # Weak evidence
    D = "D"       # Insufficient evidence


class DosingAdjustmentType(str, Enum):
    """Types of dosing adjustments"""
    AVOID = "avoid"
    REDUCE_SIGNIFICANT = "reduce_50_percent_or_more"
    REDUCE_MODERATE = "reduce_25_to_50_percent"
    REDUCE_MILD = "reduce_less_than_25_percent"
    STANDARD = "standard_dose"
    INCREASE = "increase_dose"  # For ultrarapid metabolizers


class DosingGuidanceRequest(BaseModel):
    """Request for dosing guidance"""
    gene: str = Field(..., description="Gene symbol (e.g., 'DPYD', 'TPMT', 'UGT1A1')")
    variant: Optional[str] = Field(None, description="Specific variant/diplotype (e.g., '*2A', '*28/*28', 'D949V')")
    drug: str = Field(..., description="Drug name (e.g., '5-fluorouracil', 'irinotecan')")
    standard_dose: Optional[str] = Field(None, description="Standard dose if known (e.g., '1000 mg/m²')")
    treatment_line: Optional[int] = Field(None, description="Current treatment line")
    prior_therapies: Optional[List[str]] = Field(None, description="List of prior drugs")
    disease: Optional[str] = Field(None, description="Disease context")


class DosingRecommendation(BaseModel):
    """Individual dosing recommendation"""
    gene: str
    drug: str
    phenotype: Optional[str] = Field(None, description="Metabolizer phenotype (PM, IM, NM, UM)")
    adjustment_type: DosingAdjustmentType
    adjustment_factor: Optional[float] = Field(None, description="Multiply standard dose by this (0.5 = 50%)")
    recommendation: str = Field(..., description="Plain English recommendation")
    rationale: str = Field(..., description="Clinical rationale")
    cpic_level: Optional[CPICLevel] = Field(None, description="CPIC evidence level")
    monitoring: List[str] = Field(default_factory=list, description="Recommended monitoring")
    alternatives: List[str] = Field(default_factory=list, description="Alternative drugs")


class DosingGuidanceResponse(BaseModel):
    """Response with dosing guidance"""
    recommendations: List[DosingRecommendation] = Field(default_factory=list)
    cumulative_toxicity_alert: Optional[str] = Field(None, description="Alert for cumulative toxicity")
    contraindicated: bool = Field(default=False, description="Whether drug should be avoided")
    confidence: float = Field(..., description="Overall confidence (0-1)")
    provenance: Dict[str, Any] = Field(default_factory=dict)

