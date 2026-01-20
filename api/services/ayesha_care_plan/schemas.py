"""
Ayesha Care Plan Schemas

Request and Response models for Ayesha's complete care plan v2.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional, Union

# Pydantic v1/v2 compatibility
try:
    from pydantic import field_validator as _field_validator  # type: ignore
    def compat_field_validator(*fields: str, mode: str = "before"):
        return _field_validator(*fields, mode=mode)
except Exception:  # pragma: no cover
    from pydantic import validator as _validator  # type: ignore
    def compat_field_validator(*fields: str, mode: str = "before"):
        return _validator(*fields, pre=(mode == "before"))


class CompleteCareV2Request(BaseModel):
    """Request schema for complete care plan v2"""
    
    # Patient profile
    ca125_value: Optional[float] = Field(
        None,
        description="Current CA-125 value in U/mL (optional; omit if not available)",
        example=2842.0
    )
    
    @compat_field_validator('ca125_value', mode='before')
    @classmethod
    def parse_ca125_value(cls, v: Union[str, float, int, None]) -> Optional[float]:
        """Convert string 'No', 'None', etc. to None, otherwise convert to float"""
        if v is None:
            return None
        if isinstance(v, str):
            v_lower = v.lower().strip()
            if v_lower in ['no', 'none', 'null', 'n/a', 'na', '']:
                return None
            try:
                return float(v)
            except ValueError:
                return None
        if isinstance(v, (int, float)):
            return float(v)
        return None
    
    stage: str = Field(..., description="Cancer stage", example="IVB")
    treatment_line: str = Field(default="either", description="Treatment line preference: first-line | recurrent | either")
    germline_status: str = Field(default="negative", description="Germline mutation status")
    treatment_history: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Prior treatment history (optional)")
    germline_variants: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Germline variants (optional)")

    # IO selection inputs (optional; RUO)
    patient_age: Optional[int] = Field(None, description="Patient age (optional; used for IO irAE risk adjustment)")
    autoimmune_history: Optional[List[str]] = Field(default_factory=list, description="Autoimmune history (optional; increases IO irAE risk)")

    # Clinical details
    has_ascites: bool = Field(default=False, description="Presence of ascites")
    has_peritoneal_disease: bool = Field(default=False, description="Presence of peritoneal disease")
    ecog_status: Optional[int] = Field(None, description="ECOG performance status (0-4)")
    location_state: str = Field(default="NY", description="State for location filtering")
    
    # Optional NGS data (when available)
    tumor_context: Optional[Dict[str, Any]] = Field(None, description="Tumor NGS data (somatic mutations, HRD, TMB, MSI)")
    
    # Optional drug query (for WIWFM)
    drug_query: Optional[str] = Field(None, description="Specific drug to evaluate (e.g., 'Olaparib')")
    
    # Optional food query
    food_query: Optional[str] = Field(None, description="Food/supplement to validate (e.g., 'curcumin')")
    
    # Flags
    include_trials: bool = Field(default=True, description="Include clinical trials")
    include_soc: bool = Field(default=True, description="Include SOC recommendation")
    include_ca125: bool = Field(default=True, description="Include CA-125 intelligence")
    include_wiwfm: bool = Field(default=True, description="Include drug efficacy (WIWFM)")
    include_io_selection: bool = Field(default=True, description="Include safest IO selection (irAE + eligibility) (RUO)")
    include_food: bool = Field(default=False, description="Include food validator")
    include_resistance: bool = Field(default=False, description="Include resistance playbook")
    include_resistance_prediction: bool = Field(default=False, description="Include Resistance Prophet prediction (Manager Q7: opt-in)")
    
    max_trials: int = Field(default=10, description="Maximum number of trials to return")


class CompleteCareV2Response(BaseModel):
    """Response schema for complete care plan v2"""
    trials: Optional[Dict[str, Any]] = Field(None, description="Clinical trials results")
    soc_recommendation: Optional[Dict[str, Any]] = Field(None, description="Standard of care recommendation")
    ca125_intelligence: Optional[Dict[str, Any]] = Field(None, description="CA-125 analysis and monitoring")
    wiwfm: Optional[Dict[str, Any]] = Field(None, description="Drug efficacy predictions (WIWFM)")
    io_selection: Optional[Dict[str, Any]] = Field(None, description="Safest IO regimen selection (RUO)")
    food_validation: Optional[Dict[str, Any]] = Field(None, description="Food/supplement validation")
    supplement_recommendations: Optional[Dict[str, Any]] = Field(None, description="Supplement recommendations based on drugs + treatment line")
    resistance_playbook: Optional[Dict[str, Any]] = Field(None, description="Resistance planning")
    
    # Phase 1 SAE Services (Manager-approved)
    next_test_recommender: Optional[Dict[str, Any]] = Field(None, description="Prioritized next-test recommendations (HRD→ctDNA→SLFN11→ABCB1)")
    hint_tiles: Optional[Dict[str, Any]] = Field(None, description="Clinician action hints (max 4 tiles)")
    mechanism_map: Optional[Dict[str, Any]] = Field(None, description="Pathway burden visualization (6 chips)")
    
    # Phase 2 SAE Services (Manager-approved, integrated Jan 13, 2025)
    sae_features: Optional[Dict[str, Any]] = Field(None, description="SAE feature bundle (post-NGS): DNA repair capacity, mechanism vector, resistance signals")
    resistance_alert: Optional[Dict[str, Any]] = Field(None, description="Resistance detection (2-of-3 triggers, HR restoration, immediate alerts)")
    
    # Resistance Prophet (Manager-approved, integrated Jan 14, 2025)
    resistance_prediction: Optional[Dict[str, Any]] = Field(None, description="Resistance Prophet early warning (predicts treatment failure 3-6 months early)")
    
    summary: Dict[str, Any] = Field(..., description="Summary of care plan components")
    provenance: Dict[str, Any] = Field(..., description="Data sources and orchestration metadata")
