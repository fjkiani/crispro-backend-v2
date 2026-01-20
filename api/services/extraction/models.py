"""
Data models for data extraction service.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum


class Zygosity(str, Enum):
    """Mutation zygosity."""
    HETEROZYGOUS = "heterozygous"
    HOMOZYGOUS = "homozygous"
    HEMIZYGOUS = "hemizygous"
    UNKNOWN = "unknown"


class MutationSource(str, Enum):
    """Source of mutation data."""
    NGS = "ngs"
    IHC = "ihc"
    FISH = "fish"
    PCR = "pcr"
    INFERRED = "inferred"


@dataclass
class Mutation:
    """Mutation data model."""
    gene: str
    variant: str  # e.g., "c.1239delA" or "p.V600E"
    hgvs_c: Optional[str] = None  # Coding change
    hgvs_p: Optional[str] = None  # Protein change
    chromosome: Optional[str] = None
    position: Optional[int] = None
    ref: Optional[str] = None
    alt: Optional[str] = None
    vaf: Optional[float] = None  # Variant allele frequency
    coverage: Optional[int] = None
    zygosity: Zygosity = Zygosity.UNKNOWN
    source: MutationSource = MutationSource.NGS
    classification: Optional[str] = None  # Pathogenic, VUS, Benign
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'gene': self.gene,
            'variant': self.variant,
            'hgvs_c': self.hgvs_c,
            'hgvs_p': self.hgvs_p,
            'chromosome': self.chromosome,
            'position': self.position,
            'ref': self.ref,
            'alt': self.alt,
            'vaf': self.vaf,
            'coverage': self.coverage,
            'zygosity': self.zygosity.value,
            'source': self.source.value,
            'classification': self.classification
        }


@dataclass
class GermlinePanel:
    """Germline panel results."""
    genes_tested: List[str] = field(default_factory=list)
    pathogenic: Dict[str, str] = field(default_factory=dict)  # gene -> variant
    vus: Dict[str, str] = field(default_factory=dict)
    negative: List[str] = field(default_factory=list)
    panel_name: Optional[str] = None
    test_date: Optional[datetime] = None


@dataclass
class ClinicalData:
    """Clinical data extracted from reports."""
    stage: Optional[str] = None  # e.g., "IVB"
    histology: Optional[str] = None  # e.g., "high_grade_serous"
    grade: Optional[str] = None
    ecog_ps: Optional[int] = None  # Performance status
    biomarkers: Dict[str, Any] = field(default_factory=dict)  # CA-125, HER2, etc.
    prior_treatments: List[str] = field(default_factory=list)
    current_treatment: Optional[str] = None


@dataclass
class Demographics:
    """Patient demographics."""
    age: Optional[int] = None
    sex: Optional[str] = None
    ethnicity: Optional[str] = None


@dataclass
class PatientProfile:
    """Complete patient profile extracted from files."""
    patient_id: str
    disease: str  # e.g., "ovarian_cancer"
    mutations: List[Mutation] = field(default_factory=list)
    germline_panel: Optional[GermlinePanel] = None
    clinical_data: Optional[ClinicalData] = None
    demographics: Optional[Demographics] = None
    data_quality_flags: List[str] = field(default_factory=list)
    extraction_provenance: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        return {
            'patient_id': self.patient_id,
            'disease': self.disease,
            'mutations': [m.to_dict() for m in self.mutations],
            'germline_panel': {
                'genes_tested': self.germline_panel.genes_tested if self.germline_panel else [],
                'pathogenic': self.germline_panel.pathogenic if self.germline_panel else {},
                'vus': self.germline_panel.vus if self.germline_panel else {},
                'negative': self.germline_panel.negative if self.germline_panel else [],
                'panel_name': self.germline_panel.panel_name if self.germline_panel else None,
                'test_date': self.germline_panel.test_date.isoformat() if self.germline_panel and self.germline_panel.test_date else None
            } if self.germline_panel else None,
            'clinical_data': {
                'stage': self.clinical_data.stage if self.clinical_data else None,
                'histology': self.clinical_data.histology if self.clinical_data else None,
                'grade': self.clinical_data.grade if self.clinical_data else None,
                'ecog_ps': self.clinical_data.ecog_ps if self.clinical_data else None,
                'biomarkers': self.clinical_data.biomarkers if self.clinical_data else {},
                'prior_treatments': self.clinical_data.prior_treatments if self.clinical_data else [],
                'current_treatment': self.clinical_data.current_treatment if self.clinical_data else None
            } if self.clinical_data else None,
            'demographics': {
                'age': self.demographics.age if self.demographics else None,
                'sex': self.demographics.sex if self.demographics else None,
                'ethnicity': self.demographics.ethnicity if self.demographics else None
            } if self.demographics else None,
            'data_quality_flags': self.data_quality_flags,
            'extraction_provenance': self.extraction_provenance,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }


