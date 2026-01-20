"""
Safety schemas for toxicity risk and off-target preview.

Following the doctrine from toxicity_risk_plan.mdc with conservative, RUO-focused design.
"""

from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


# ============================================================================
# TOXICITY RISK SCHEMAS
# ============================================================================

class GermlineVariant(BaseModel):
    """Germline variant (from patient constitutional DNA)."""
    chrom: str = Field(..., description="Chromosome (e.g., '7', 'X')")
    pos: int = Field(..., description="Position (GRCh38)")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    gene: Optional[str] = Field(None, description="Gene symbol if known")
    hgvs_p: Optional[str] = Field(None, description="Protein change (e.g., 'V600E')")


class PatientContext(BaseModel):
    """Patient germline context."""
    germlineVariants: List[GermlineVariant] = Field(default_factory=list)


class TumorContext(BaseModel):
    """Tumor somatic variants (for future use)."""
    somaticVariants: List[Dict[str, Any]] = Field(default_factory=list)


class TherapeuticCandidate(BaseModel):
    """Drug or CRISPR candidate being evaluated."""
    type: str = Field(..., description="'drug' or 'crispr'")
    moa: Optional[str] = Field(None, description="Mechanism of action (e.g., 'BRAF_inhibitor')")
    guides: Optional[List[Dict[str, str]]] = Field(None, description="CRISPR guides for off-target preview")


class ClinicalContext(BaseModel):
    """Clinical setting."""
    disease: Optional[str] = Field(None, description="Disease (e.g., 'MM', 'melanoma')")
    tissue: Optional[str] = Field(None, description="Tissue type")
    regimen: Optional[str] = Field(None, description="Current regimen")


class ToxicityRiskRequest(BaseModel):
    """Request for toxicity risk assessment."""
    patient: PatientContext = Field(..., description="Patient germline variants")
    tumor: Optional[TumorContext] = Field(None, description="Tumor somatic variants (optional)")
    candidate: TherapeuticCandidate = Field(..., description="Drug or CRISPR candidate")
    context: ClinicalContext = Field(..., description="Clinical context")
    options: Dict[str, Any] = Field(default_factory=lambda: {"evidence": True, "profile": "baseline"})


class ToxicityFactor(BaseModel):
    """Individual toxicity risk factor."""
    type: str = Field(..., description="Factor type: 'germline', 'pathway', 'evidence', 'tissue'")
    detail: str = Field(..., description="Human-readable explanation")
    weight: float = Field(..., description="Contribution to risk score (0-1)")
    confidence: float = Field(..., description="Confidence in this factor (0-1)")


class ToxicityRiskResponse(BaseModel):
    """Response from toxicity risk assessment."""
    risk_score: float = Field(..., description="Overall toxicity risk (0-1, higher = more risk)")
    confidence: float = Field(..., description="Confidence in assessment (0-1)")
    reason: str = Field(..., description="Plain-English summary of risk")
    factors: List[ToxicityFactor] = Field(default_factory=list, description="Individual risk factors")
    mitigating_foods: List[Dict[str, Any]] = Field(
        default_factory=list, 
        description="Foods that mitigate detected toxicity pathways (THE MOAT)"
    )
    evidence: Dict[str, Any] = Field(default_factory=dict, description="Citations and badges")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Run ID, profile, methods, cache")


# ============================================================================
# OFF-TARGET PREVIEW SCHEMAS
# ============================================================================

class GuideRNA(BaseModel):
    """CRISPR guide RNA."""
    seq: str = Field(..., description="Guide sequence (20bp standard)")
    pam: str = Field(default="NGG", description="PAM sequence")
    target_gene: Optional[str] = Field(None, description="Target gene symbol")
    target_pos: Optional[str] = Field(None, description="Target position (chr:pos)")


class GuideRNAScore(BaseModel):
    """Heuristic off-target score for a guide."""
    seq: str = Field(..., description="Guide sequence")
    pam: str = Field(..., description="PAM sequence")
    gc_content: float = Field(..., description="GC content (0-1)")
    gc_score: float = Field(..., description="GC quality score (0-1, optimal 0.4-0.6)")
    homopolymer: bool = Field(..., description="Has long homopolymer run (>4bp)")
    homopolymer_penalty: float = Field(..., description="Penalty for homopolymers (0-1)")
    seed_quality: float = Field(..., description="12bp seed region quality (0-1)")
    heuristic_score: float = Field(..., description="Overall heuristic safety score (0-1)")
    risk_level: str = Field(..., description="'low', 'medium', 'high'")
    warnings: List[str] = Field(default_factory=list, description="Human-readable warnings")


class OffTargetPreviewRequest(BaseModel):
    """Request for off-target preview (heuristics only for P1)."""
    guides: List[GuideRNA] = Field(..., description="Guide RNAs to evaluate")
    options: Dict[str, Any] = Field(default_factory=lambda: {"maxMismatches": 3, "profile": "baseline"})


class OffTargetPreviewResponse(BaseModel):
    """Response from off-target preview."""
    guides: List[GuideRNAScore] = Field(..., description="Scored guides")
    summary: Dict[str, Any] = Field(default_factory=dict, description="Overall summary stats")
    provenance: Dict[str, Any] = Field(default_factory=dict, description="Run ID, methods, cache")
    note: str = Field(
        default="Heuristic preview only (RUO). Genome-wide alignment in development.",
        description="Disclaimer about heuristic nature"
    )
