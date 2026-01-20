"""
Patient Schemas - Core data models for patient data.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum


class ZygosityType(str, Enum):
    HETEROZYGOUS = "heterozygous"
    HOMOZYGOUS = "homozygous"
    HEMIZYGOUS = "hemizygous"
    UNKNOWN = "unknown"


class MutationSource(str, Enum):
    NGS = "ngs"
    IHC = "ihc"
    FISH = "fish"
    PCR = "pcr"
    INFERRED = "inferred"


class MutationInput(BaseModel):
    """Single mutation input for API requests."""
    gene: str = Field(..., description="Gene symbol (e.g., 'BRAF', 'TP53')")
    variant: Optional[str] = Field(None, description="Variant description")
    hgvs_c: Optional[str] = Field(None, description="Coding change (e.g., 'c.1799T>A')")
    hgvs_p: Optional[str] = Field(None, description="Protein change (e.g., 'p.V600E')")
    chromosome: Optional[str] = Field(None, description="Chromosome")
    position: Optional[int] = Field(None, description="Genomic position")
    ref: Optional[str] = Field(None, description="Reference allele")
    alt: Optional[str] = Field(None, description="Alternate allele")
    vaf: Optional[float] = Field(None, ge=0, le=1, description="Variant allele frequency")
    coverage: Optional[int] = Field(None, ge=0, description="Read coverage")
    zygosity: Optional[ZygosityType] = Field(ZygosityType.UNKNOWN, description="Zygosity")
    source: Optional[MutationSource] = Field(MutationSource.NGS, description="Source of mutation")
    classification: Optional[str] = Field(None, description="Pathogenicity classification")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "gene": "BRAF",
                "hgvs_p": "p.V600E",
                "hgvs_c": "c.1799T>A",
                "vaf": 0.45,
                "classification": "Pathogenic"
            }
        }
    }


class CytogeneticsInput(BaseModel):
    """MM-specific cytogenetics input."""
    del_17p: Optional[bool] = Field(False, description="del(17p) detected")
    t_4_14: Optional[bool] = Field(False, description="t(4;14) detected")
    t_11_14: Optional[bool] = Field(False, description="t(11;14) detected")
    gain_1q: Optional[bool] = Field(False, description="1q gain detected")
    t_14_16: Optional[bool] = Field(False, description="t(14;16) detected")
    
    def to_dict(self) -> Dict[str, bool]:
        return {
            'del_17p': self.del_17p,
            't_4_14': self.t_4_14,
            't_11_14': self.t_11_14,
            '1q_gain': self.gain_1q,
            't_14_16': self.t_14_16
        }


class ClinicalDataInput(BaseModel):
    """Clinical data for patient context."""
    stage: Optional[str] = Field(None, description="Cancer stage (e.g., 'IVB')")
    histology: Optional[str] = Field(None, description="Histology type")
    grade: Optional[str] = Field(None, description="Tumor grade")
    ecog_ps: Optional[int] = Field(None, ge=0, le=5, description="ECOG performance status")
    biomarkers: Optional[Dict[str, Any]] = Field(None, description="Additional biomarkers")
    prior_treatments: Optional[List[str]] = Field(None, description="Prior treatment list")
    current_treatment: Optional[str] = Field(None, description="Current treatment")


class PatientProfileInput(BaseModel):
    """Full patient profile for API requests."""
    patient_id: Optional[str] = Field(None, description="Patient ID (auto-generated if not provided)")
    disease: str = Field(..., description="Disease type (ovarian, myeloma, etc.)")
    mutations: List[MutationInput] = Field(default=[], description="List of mutations")
    cytogenetics: Optional[CytogeneticsInput] = Field(None, description="Cytogenetics data (MM)")
    clinical_data: Optional[ClinicalDataInput] = Field(None, description="Clinical data")
    treatment_line: int = Field(1, ge=1, description="Current treatment line")
    prior_therapies: Optional[List[str]] = Field(None, description="Prior drug classes")
    current_regimen: Optional[str] = Field(None, description="Current regimen")
    
    model_config = {
        "json_schema_extra": {
            "example": {
                "disease": "myeloma",
                "mutations": [
                    {"gene": "DIS3", "hgvs_p": "p.C562Y"},
                    {"gene": "TP53", "hgvs_p": "p.R175H"}
                ],
                "cytogenetics": {"del_17p": True},
                "treatment_line": 2,
                "prior_therapies": ["proteasome_inhibitor"],
                "current_regimen": "VRd"
            }
        }
    }


class MutationResponse(BaseModel):
    """Mutation in API responses."""
    gene: str
    variant: Optional[str] = None
    hgvs_p: Optional[str] = None
    hgvs_c: Optional[str] = None
    vaf: Optional[float] = None
    classification: Optional[str] = None


class PatientProfileResponse(BaseModel):
    """Patient profile in API responses."""
    patient_id: str
    disease: str
    mutations: List[MutationResponse]
    mutation_count: int
    extraction_method: Optional[str] = None
    data_quality_flags: List[str] = []
    created_at: Optional[str] = None

