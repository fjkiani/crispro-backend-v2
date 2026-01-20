"""
Pydantic schemas for design endpoints (spacer efficacy, guide generation, etc.)
"""
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List


class SpacerEfficacyRequest(BaseModel):
    """Request for predicting CRISPR spacer efficacy using Evo2 delta scoring"""
    guide_sequence: str = Field(..., description="20bp guide RNA sequence (spacer)")
    target_sequence: Optional[str] = Field(None, description="Target genomic context (guide + ±window_size bp flanks)")
    window_size: Optional[int] = Field(150, description="Flank size in bp (default: 150bp = 300bp total context)")
    chrom: Optional[str] = Field(None, description="Chromosome (for Ensembl fetch if target_sequence not provided)")
    pos: Optional[int] = Field(None, description="Position (for Ensembl fetch)")
    ref: Optional[str] = Field(None, description="Reference allele")
    alt: Optional[str] = Field(None, description="Alternate allele")
    model_id: Optional[str] = Field("evo2_1b", description="Evo2 model to use (evo2_1b/evo2_7b/evo2_40b)")
    assembly: Optional[str] = Field("GRCh38", description="Genome assembly (GRCh38 or GRCh37)")


class SpacerEfficacyProvenance(BaseModel):
    """Provenance metadata for spacer efficacy predictions"""
    method: str = Field(..., description="Method used (e.g., 'evo2_delta_sigmoid_v1')")
    model_id: str = Field(..., description="Evo2 model used")
    context_length: int = Field(..., description="Total context length used (bp)")
    scale_factor: float = Field(..., description="Sigmoid scale factor")
    evo_url: Optional[str] = Field(None, description="Evo2 endpoint URL used")
    cached: bool = Field(False, description="Whether result was cached")


class SpacerEfficacyResponse(BaseModel):
    """Response from spacer efficacy prediction"""
    guide_sequence: str = Field(..., description="20bp guide RNA sequence")
    efficacy_score: float = Field(..., description="On-target efficacy score [0,1], higher=better")
    evo2_delta: Optional[float] = Field(None, description="Raw Evo2 delta log-likelihood")
    confidence: float = Field(..., description="Prediction confidence [0,1]")
    rationale: List[str] = Field(default_factory=list, description="Human-readable explanations")
    provenance: SpacerEfficacyProvenance = Field(..., description="Provenance metadata")
