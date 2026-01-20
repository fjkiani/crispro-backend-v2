"""
Data models for Synthetic Lethality & Essentiality Agent.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from enum import Enum
from datetime import datetime


class EssentialityLevel(str, Enum):
    """Gene essentiality level."""
    HIGH = "high"           # Score >= 0.7
    MODERATE = "moderate"   # Score 0.5-0.7
    LOW = "low"             # Score < 0.5
    UNKNOWN = "unknown"


class PathwayStatus(str, Enum):
    """Pathway functional status."""
    FUNCTIONAL = "functional"
    COMPROMISED = "compromised"
    NON_FUNCTIONAL = "non_functional"
    UNKNOWN = "unknown"


@dataclass
class MutationInput:
    """Input mutation for analysis."""
    gene: str
    hgvs_p: Optional[str] = None
    hgvs_c: Optional[str] = None
    consequence: Optional[str] = None
    chrom: Optional[str] = None
    pos: Optional[int] = None
    ref: Optional[str] = None
    alt: Optional[str] = None


@dataclass
class SLOptions:
    """Options for synthetic lethality analysis."""
    model_id: str = "evo2_7b"
    include_explanations: bool = True
    explanation_audience: str = "clinician"  # clinician/patient/researcher


@dataclass
class SyntheticLethalityRequest:
    """Request for synthetic lethality analysis."""
    disease: str
    mutations: List[MutationInput]
    options: Optional[SLOptions] = None


@dataclass
class GeneEssentialityScore:
    """Essentiality score for a single gene."""
    gene: str
    essentiality_score: float              # 0.0 - 1.0
    essentiality_level: EssentialityLevel
    
    # Breakdown
    sequence_disruption: float             # Evo2 delta score (normalized)
    pathway_impact: str                    # e.g., "BER pathway NON-FUNCTIONAL"
    functional_consequence: str            # e.g., "frameshift → loss of function"
    
    # Flags
    flags: Dict[str, bool] = field(default_factory=dict)  # truncation, frameshift, hotspot, etc.
    
    # Provenance
    evo2_raw_delta: float = 0.0           # Raw Evo2 score
    evo2_window_used: int = 0              # Context window size
    confidence: float = 0.0                 # 0.0 - 1.0


@dataclass
class PathwayAnalysis:
    """Analysis of a biological pathway."""
    pathway_name: str                      # e.g., "Base Excision Repair"
    pathway_id: str                        # e.g., "BER"
    status: PathwayStatus
    genes_affected: List[str]              # Genes in this pathway that are mutated
    disruption_score: float                # 0.0 - 1.0
    description: str                       # Human-readable explanation


@dataclass
class DrugRecommendation:
    """Drug recommendation based on synthetic lethality."""
    drug_name: str
    drug_class: str                        # e.g., "PARP_inhibitor"
    target_pathway: str                    # e.g., "HR"
    confidence: float                      # 0.0 - 1.0
    mechanism: str                         # Why this drug works
    fda_approved: bool = False
    evidence_tier: str = "Research"        # I, II, III, Research
    rationale: List[str] = field(default_factory=list)  # Supporting reasons


@dataclass
class AIExplanation:
    """AI-generated explanation of results."""
    audience: str                          # clinician/patient/researcher
    summary: str                           # Brief summary
    full_explanation: str                  # Detailed explanation
    key_points: List[str] = field(default_factory=list)  # Bullet points
    generated_at: datetime = field(default_factory=datetime.utcnow)
    provider: str = "gemini"               # e.g., "gemini"


@dataclass
class SyntheticLethalityResult:
    """Complete synthetic lethality analysis result."""
    patient_id: Optional[str] = None
    disease: str = ""
    
    # Core Results
    synthetic_lethality_detected: bool = False
    double_hit_description: Optional[str] = None  # e.g., "BER + checkpoint loss"
    
    # Gene Essentiality
    essentiality_scores: List[GeneEssentialityScore] = field(default_factory=list)
    
    # Pathway Analysis
    broken_pathways: List[PathwayAnalysis] = field(default_factory=list)
    essential_pathways: List[PathwayAnalysis] = field(default_factory=list)  # Backups cancer depends on
    
    # Drug Recommendations
    recommended_drugs: List[DrugRecommendation] = field(default_factory=list)
    suggested_therapy: str = "platinum"    # Top recommendation
    
    # AI Explanation
    explanation: Optional[AIExplanation] = None
    
    # Metadata
    calculation_time_ms: int = 0
    evo2_used: bool = True
    provenance: Dict[str, Any] = field(default_factory=dict)


