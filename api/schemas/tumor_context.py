"""
Tumor Context Schema for Sporadic Cancer Strategy

Supports Level 0 (no report), Level 1 (partial data), Level 2 (full NGS report)
for germline-negative patients requiring tumor-centric analysis.
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, List, Dict, Any, Literal
from datetime import datetime


class SomaticMutation(BaseModel):
    """Individual somatic mutation from tumor NGS"""
    gene: str
    hgvs_p: Optional[str] = None
    hgvs_c: Optional[str] = None
    variant_class: Optional[Literal["missense", "nonsense", "frameshift", "splice", "inframe_indel"]] = None
    vaf: Optional[float] = Field(None, ge=0.0, le=1.0, description="Variant allele frequency")
    zygosity: Optional[Literal["heterozygous", "homozygous", "hemizygous"]] = None
    pathogenicity: Optional[Literal["pathogenic", "likely_pathogenic", "VUS", "likely_benign", "benign"]] = None
    hotspot: Optional[bool] = None
    domain: Optional[str] = None


class CopyNumberAlteration(BaseModel):
    """Copy number alteration (amplification/deletion)"""
    gene: str
    type: Literal["amplification", "deletion"]
    copy_number_estimate: Optional[int] = Field(None, ge=0)
    log2_ratio: Optional[float] = None
    focality: Optional[Literal["focal", "broad"]] = None


class GeneFusion(BaseModel):
    """Gene fusion/structural variant"""
    gene_5p: str
    gene_3p: str
    breakpoints: Optional[str] = None
    exon_junctions: Optional[str] = None
    inframe: Optional[bool] = None
    read_support: Optional[int] = Field(None, ge=0)


class TMBMetrics(BaseModel):
    """Tumor mutational burden metrics"""
    value: float = Field(..., ge=0.0, description="TMB in mutations/Mb")
    panel_size_mb: Optional[float] = Field(None, gt=0.0)
    method: Optional[Literal["DNA", "RNA", "WES", "WGS"]] = None
    category: Optional[Literal["low", "intermediate", "high"]] = None


class MSIMetrics(BaseModel):
    """Microsatellite instability metrics"""
    status: Literal["MSI-H", "MSS", "indeterminate"]
    method: Optional[Literal["PCR", "IHC", "NGS"]] = None
    instability_fraction: Optional[float] = Field(None, ge=0.0, le=1.0)


class HRDMetrics(BaseModel):
    """Homologous recombination deficiency metrics"""
    score: float = Field(..., ge=0.0, le=100.0, description="HRD score (GIS)")
    loh_score: Optional[float] = Field(None, ge=0.0)
    lst_score: Optional[float] = Field(None, ge=0.0)
    tai_score: Optional[float] = Field(None, ge=0.0)
    category: Optional[Literal["high", "low", "unknown"]] = None
    brca_biallelic_loss: Optional[bool] = Field(None, description="Biallelic BRCA1/2 inactivation")


class QCMetrics(BaseModel):
    """Sample quality control metrics"""
    tumor_purity: Optional[float] = Field(None, ge=0.0, le=1.0, description="Tumor purity fraction")
    ploidy: Optional[float] = Field(None, gt=0.0)
    mean_coverage: Optional[int] = Field(None, ge=0)
    uniformity: Optional[float] = Field(None, ge=0.0, le=1.0)


class IHCMetrics(BaseModel):
    """Immunohistochemistry metrics"""
    pdl1_assay: Optional[str] = None
    pdl1_score_type: Optional[Literal["TPS", "CPS", "IC"]] = None
    pdl1_score_value: Optional[float] = Field(None, ge=0.0, le=100.0)
    mmr_mlh1: Optional[Literal["intact", "lost"]] = None
    mmr_msh2: Optional[Literal["intact", "lost"]] = None
    mmr_msh6: Optional[Literal["intact", "lost"]] = None
    mmr_pms2: Optional[Literal["intact", "lost"]] = None


class TumorContext(BaseModel):
    """
    Tumor genomic context for sporadic cancer analysis.
    
    Supports three intake levels:
    - Level 0 (L0): Disease priors + platinum proxy (no report)
    - Level 1 (L1): Manually entered metrics (partial data)
    - Level 2 (L2): Full NGS report parsing (Foundation/Tempus)
    """
    
    # Core biomarkers
    somatic_mutations: List[SomaticMutation] = Field(default_factory=list)
    copy_number_alterations: List[CopyNumberAlteration] = Field(default_factory=list)
    fusions: List[GeneFusion] = Field(default_factory=list)
    
    # Simplified biomarker fields (for Level 0/1)
    tmb: Optional[float] = Field(None, ge=0.0, description="TMB value (mutations/Mb)")
    msi_status: Optional[Literal["MSI-H", "MSS"]] = Field(None, description="MSI status (null = unknown)")
    hrd_score: Optional[float] = Field(None, ge=0.0, le=100.0, description="HRD score (GIS)")
    
    # Detailed metrics (for Level 2)
    tmb_metrics: Optional[TMBMetrics] = None
    msi_metrics: Optional[MSIMetrics] = None
    hrd_metrics: Optional[HRDMetrics] = None
    qc: Optional[QCMetrics] = None
    ihc: Optional[IHCMetrics] = None
    
    # Mutational signatures
    signatures: Optional[Dict[str, float]] = Field(None, description="SBS signature weights (e.g., SBS3 for HRD)")
    
    # Metadata
    level: Literal["L0", "L1", "L2"] = Field(..., description="Data completeness level")
    priors_used: bool = Field(default=False, description="Whether disease priors were used")
    completeness_score: float = Field(..., ge=0.0, le=1.0, description="Fraction of tracked fields populated")
    
    # Provenance
    tumor_context_source: Optional[Literal["Foundation", "Tempus", "Manual", "Quick Intake"]] = None
    specimen_type: Optional[Literal["primary", "metastasis", "ascites", "biopsy"]] = None
    report_date: Optional[str] = None
    panel_name: Optional[str] = None
    panel_version: Optional[str] = None
    
    @field_validator('tmb')
    @classmethod
    def validate_tmb(cls, v):
        """Ensure TMB is non-negative"""
        if v is not None and v < 0:
            raise ValueError("TMB must be >= 0")
        return v
    
    @field_validator('hrd_score')
    @classmethod
    def validate_hrd(cls, v):
        """Ensure HRD score is within 0-100 range"""
        if v is not None and (v < 0 or v > 100):
            raise ValueError("HRD score must be between 0 and 100")
        return v
    
    @classmethod
    def calculate_completeness(cls, data: Dict[str, Any]) -> float:
        """
        Calculate completeness score based on tracked fields.
        
        Tracked fields: tmb, msi_status, hrd_score, somatic_mutations
        """
        tracked_fields = ["tmb", "msi_status", "hrd_score", "somatic_mutations"]
        non_null_count = sum(1 for field in tracked_fields if data.get(field) is not None and data.get(field) != [])
        return non_null_count / len(tracked_fields)


class QuickIntakeRequest(BaseModel):
    """
    Request for Level 0 Quick Intake (no NGS report).
    
    Uses disease priors + platinum response proxy to estimate
    tumor biomarkers for sporadic cancer analysis.
    """
    cancer_type: str = Field(..., description="Disease key (e.g., 'ovarian_hgs')")
    stage: Optional[str] = None
    line: Optional[int] = Field(None, ge=1, description="Treatment line")
    platinum_response: Optional[Literal["sensitive", "resistant", "unknown"]] = None
    
    # Optional manually entered fields (elevates to Level 1)
    tmb: Optional[float] = Field(None, ge=0.0)
    msi_status: Optional[Literal["MSI-H", "MSS"]] = None
    hrd_score: Optional[float] = Field(None, ge=0.0, le=100.0)
    somatic_mutations: List[SomaticMutation] = Field(default_factory=list)


class QuickIntakeResponse(BaseModel):
    """Response from Quick Intake with estimated TumorContext"""
    tumor_context: TumorContext
    provenance: Dict[str, Any] = Field(
        default_factory=lambda: {
            "no_report_mode": True,
            "disease_priors_used": False,
            "disease_priors_version": None,
            "priors_refresh_date": None,
            "platinum_proxy_used": False,
            "confidence_version": "v1.0"
        }
    )
    confidence_cap: float = Field(..., ge=0.0, le=1.0, description="Confidence ceiling for Level 0/1")
    recommendations: Optional[List[str]] = Field(
        default_factory=lambda: ["Tumor NGS recommended for refined analysis"]
    )


class IngestNGSRequest(BaseModel):
    """
    Request for Level 2 NGS report ingestion.
    
    Supports both PDF upload and direct JSON (JSON preferred for speed).
    """
    report_file: Optional[str] = Field(None, description="Base64-encoded PDF")
    report_json: Optional[Dict[str, Any]] = Field(None, description="Pre-parsed JSON (preferred)")
    report_source: Literal["Foundation", "Tempus"] = Field(..., description="NGS platform")


class IngestNGSResponse(BaseModel):
    """Response from NGS report ingestion"""
    tumor_context: TumorContext
    provenance: Dict[str, Any] = Field(
        default_factory=lambda: {
            "source": None,
            "report_hash": None,
            "parsed_at": None,
            "parser_version": "v1.0",
            "confidence_version": "v1.0"
        }
    )



