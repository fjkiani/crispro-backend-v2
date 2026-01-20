"""
Shared data models for resistance prediction modules.

Extracted from resistance_prophet_service.py for modularization.
Enhanced for extensibility - uses TypedDict for signal-specific data.
"""

from typing import Dict, List, Optional, TypedDict, Union, Any
from enum import Enum
from dataclasses import dataclass, field

# Import PATHWAY_CONTRIBUTIONS and PATHWAY_NAMES for backward compatibility
try:
    from .config import PATHWAY_CONTRIBUTIONS, PATHWAY_NAMES
except ImportError:
    # Fallback for backward compatibility
    PATHWAY_CONTRIBUTIONS = {
        "ddr": 0.60,
        "hrr": 0.20,
        "exon": 0.20
    }
    PATHWAY_NAMES = ["DDR", "MAPK", "PI3K", "VEGF", "HER2", "IO", "Efflux"]


class ResistanceRiskLevel(str, Enum):
    """Resistance risk stratification levels (Manager Q9)"""
    HIGH = "HIGH"      # >=0.70 probability + >=2 signals
    MEDIUM = "MEDIUM"  # 0.50-0.69 or exactly 1 signal
    LOW = "LOW"        # <0.50 probability


class ResistanceSignal(str, Enum):
    """Individual resistance signals"""
    DNA_REPAIR_RESTORATION = "DNA_REPAIR_RESTORATION"  # Signal 1
    PATHWAY_ESCAPE = "PATHWAY_ESCAPE"                  # Signal 2
    CA125_KINETICS = "CA125_KINETICS"                  # Signal 3 (Phase 1b+)
    # MM-specific signals (Gene-level / Proxy SAE)
    MM_HIGH_RISK_GENE = "MM_HIGH_RISK_GENE"           # Signal 4: DIS3, TP53 mutations
    MM_CYTOGENETICS = "MM_CYTOGENETICS"               # Signal 5: del(17p), t(4;14), 1q gain
    MM_DRUG_CLASS_RESISTANCE = "MM_DRUG_CLASS_RESISTANCE"  # Signal 6: PSMB5/CRBN mutations
    POST_TREATMENT_PATHWAY_PROFILING = "POST_TREATMENT_PATHWAY_PROFILING"  # Signal 7: Post-treatment pathway state


class UrgencyLevel(str, Enum):
    """Action urgency levels (Manager Q10)"""
    CRITICAL = "CRITICAL"  # HIGH risk - immediate escalation
    ELEVATED = "ELEVATED"  # MEDIUM risk - weekly monitoring
    ROUTINE = "ROUTINE"    # LOW risk - routine monitoring


# TypedDict definitions for signal-specific data (extensible)
class DNARepairSignalData(TypedDict, total=False):
    """Signal-specific data for DNA repair restoration."""
    mechanism_breakdown: "MechanismBreakdown"
    pathway_contributions: Dict[str, float]


class PathwayEscapeSignalData(TypedDict, total=False):
    """Signal-specific data for pathway escape."""
    escaped_pathways: List[str]
    mechanism_alignment: Dict[str, float]


class PostTreatmentSignalData(TypedDict, total=False):
    """Signal-specific data for post-treatment pathway profiling."""
    pathway_scores: Dict[str, float]
    composite_score: float
    predicted_pfi_category: str


class MMHighRiskSignalData(TypedDict, total=False):
    """Signal-specific data for MM high-risk genes."""
    detected_genes: List[Dict[str, Any]]
    max_relative_risk: float
    drug_relevant: bool


# Union type for all signal-specific data (extensible)
SignalSpecificData = Union[
    DNARepairSignalData,
    PathwayEscapeSignalData,
    PostTreatmentSignalData,
    MMHighRiskSignalData,
    Dict[str, Any],  # Fallback for unknown signal types
]


@dataclass
class MechanismBreakdown:
    """Mechanism-level breakdown for DNA repair restoration signal"""
    ddr_pathway_change: float  # Change in DDR pathway burden
    hrr_essentiality_change: float  # Change in HRR essentiality
    exon_disruption_change: float  # Change in exon disruption score
    pathway_contributions: Dict[str, float] = field(default_factory=lambda: PATHWAY_CONTRIBUTIONS.copy())


@dataclass
class ResistanceSignalData:
    """
    Data for a single resistance signal - extensible architecture.
    
    Uses signal_specific_data dict for signal-type-specific fields, making it
    easy to add new signal types without modifying this class.
    """
    signal_type: ResistanceSignal
    detected: bool
    probability: float  # 0.0-1.0
    confidence: float   # 0.0-1.0
    rationale: str
    provenance: Dict
    # Extensible signal-specific data (TypedDict for type safety)
    signal_specific_data: Optional[SignalSpecificData] = None
    
    # Backward compatibility: legacy fields (deprecated, use signal_specific_data)
    mechanism_breakdown: Optional[MechanismBreakdown] = None  # For DNA_REPAIR_RESTORATION (legacy)
    escaped_pathways: Optional[List[str]] = None  # For PATHWAY_ESCAPE (legacy)
    mechanism_alignment: Optional[Dict[str, float]] = None  # Per-pathway changes (legacy)
    pathway_scores: Optional[Dict[str, float]] = None  # For POST_TREATMENT_PATHWAY_PROFILING (legacy)
    composite_score: Optional[float] = None  # For POST_TREATMENT_PATHWAY_PROFILING (legacy)
    predicted_pfi_category: Optional[str] = None  # For POST_TREATMENT_PATHWAY_PROFILING (legacy)
    
    def __post_init__(self):
        """Migrate legacy fields to signal_specific_data for backward compatibility."""
        if self.signal_specific_data is None:
            self.signal_specific_data = {}
        
        # Migrate legacy fields to signal_specific_data
        if self.signal_type == ResistanceSignal.DNA_REPAIR_RESTORATION and self.mechanism_breakdown:
            if "mechanism_breakdown" not in self.signal_specific_data:
                self.signal_specific_data["mechanism_breakdown"] = self.mechanism_breakdown
            if "pathway_contributions" not in self.signal_specific_data:
                self.signal_specific_data["pathway_contributions"] = PATHWAY_CONTRIBUTIONS.copy()
        elif self.signal_type == ResistanceSignal.PATHWAY_ESCAPE:
            if self.escaped_pathways and "escaped_pathways" not in self.signal_specific_data:
                self.signal_specific_data["escaped_pathways"] = self.escaped_pathways
            if self.mechanism_alignment and "mechanism_alignment" not in self.signal_specific_data:
                self.signal_specific_data["mechanism_alignment"] = self.mechanism_alignment
        elif self.signal_type == ResistanceSignal.POST_TREATMENT_PATHWAY_PROFILING:
            if self.pathway_scores and "pathway_scores" not in self.signal_specific_data:
                self.signal_specific_data["pathway_scores"] = self.pathway_scores
            if self.composite_score is not None and "composite_score" not in self.signal_specific_data:
                self.signal_specific_data["composite_score"] = self.composite_score
            if self.predicted_pfi_category and "predicted_pfi_category" not in self.signal_specific_data:
                self.signal_specific_data["predicted_pfi_category"] = self.predicted_pfi_category


@dataclass
class ResistancePrediction:
    """Complete resistance prediction output"""
    risk_level: ResistanceRiskLevel
    probability: float  # Overall resistance probability (0.0-1.0)
    confidence: float   # Prediction confidence (0.0-1.0)
    signals_detected: List[ResistanceSignalData]
    signal_count: int
    urgency: UrgencyLevel
    recommended_actions: List[Dict]
    next_line_options: List[Dict]  # From ResistancePlaybookService
    rationale: List[str]
    provenance: Dict
    warnings: List[str]
    # Baseline handling documentation
    baseline_source: str = "patient_baseline"  # "patient_baseline" or "population_average"
    baseline_penalty_applied: bool = False
    confidence_cap: Optional[str] = None  # "MEDIUM" if capped
