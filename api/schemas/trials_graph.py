"""
Graph-Optimized Trial Search Schemas - Component 4
Updated with Sporadic Cancer Support
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal


class PatientContext(BaseModel):
    """Patient context for graph optimization."""
    condition: Optional[str] = None
    biomarkers: Optional[List[str]] = None
    location_state: Optional[str] = None
    disease_category: Optional[str] = None


class TumorContext(BaseModel):
    """Tumor genomic context for sporadic cancer filtering."""
    tmb: Optional[float] = Field(None, description="Tumor Mutational Burden (mutations/Mb)")
    msi_status: Optional[str] = Field(None, description="MSI status (MSI-High, MSI-Stable, MSI-Low)")
    hrd_score: Optional[float] = Field(None, description="Homologous Recombination Deficiency score (0-100)")
    somatic_mutations: Optional[List[str]] = Field(None, description="List of somatic mutation genes")


class OptimizedTrialSearchRequest(BaseModel):
    """Request for graph-optimized trial search with sporadic cancer support."""
    query: str
    patient_context: Optional[PatientContext] = None
    germline_status: Optional[Literal["positive", "negative", "unknown"]] = Field(
        None, 
        description="Germline status for sporadic filtering. If 'negative', excludes germline-required trials."
    )
    tumor_context: Optional[TumorContext] = Field(
        None,
        description="Tumor genomic context for biomarker boost (TMB/MSI/HRD matching)"
    )
    top_k: int = 10






