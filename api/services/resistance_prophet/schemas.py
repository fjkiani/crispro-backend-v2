"""
Resistance Prophet Schemas
Pure data transfer objects and enums for the Resistance Prophet service.
Moved from monolithic resistance_prophet_service.py.
"""

from typing import Dict, List, Optional
from enum import Enum
from dataclasses import dataclass, field

class ResistanceRiskLevel(str, Enum):
    """Resistance risk stratification levels"""
    HIGH = "HIGH"      # >=0.70 probability + >=2 signals
    MEDIUM = "MEDIUM"  # 0.50-0.69 or exactly 1 signal
    LOW = "LOW"        # <0.50 probability
    NOT_APPLICABLE = "NOT_APPLICABLE" # Treatment Naive

@dataclass
class DNARepairMetrics:
    """
    Canonical DNA repair representation (Version 2.0).
    Resolves 'Capacity vs Deficiency' ambiguity.
    """
    dna_repair_deficiency: float # Primary: 1.0 = Highly Deficient (Sensitive), 0.0 = Proficient (Resistant)
    metric_version: str = "v2.0_deficiency_canonical"
    
    @property
    def dna_repair_capacity(self) -> float:
        """Deprecated alias (Legacy SAE polarity). 1.0 = Proficient."""
        return 1.0 - self.dna_repair_deficiency


class ResistanceSignal(str, Enum):
    """Individual resistance signals"""
    # Phenotypic Signals (Phase 1)
    DNA_REPAIR_RESTORATION = "DNA_REPAIR_RESTORATION"  # Signal 1
    PATHWAY_ESCAPE = "PATHWAY_ESCAPE"                  # Signal 2
    CA125_KINETICS = "CA125_KINETICS"                  # Signal 3 (Phase 1b+)
    
    # Cross-Disease Signals (Gene/Cyto/Drug)
    GENE_LEVEL_RESISTANCE = "GENE_LEVEL_RESISTANCE"      # Signal 4 (e.g., TP53, MBD4)
    CYTOGENETIC_ABNORMALITY = "CYTOGENETIC_ABNORMALITY"  # Signal 5 (e.g., del(17p))
    DRUG_CLASS_RESISTANCE = "DRUG_CLASS_RESISTANCE"      # Signal 6 (e.g., PSMB5, CRBN)

class UrgencyLevel(str, Enum):
    """Action urgency levels"""
    CRITICAL = "CRITICAL"  # HIGH risk
    ELEVATED = "ELEVATED"  # MEDIUM risk
    ROUTINE = "ROUTINE"    # LOW risk

@dataclass
class MechanismBreakdown:
    """Mechanism-level breakdown for DNA repair restoration signal"""
    ddr_pathway_change: float  # Change in DDR pathway burden
    hrr_essentiality_change: float  # Change in HRR essentiality
    exon_disruption_change: float  # Change in exon disruption score
    pathway_contributions: Dict[str, float]

@dataclass
class ResistanceSignalData:
    """Data for a single resistance signal"""
    signal_type: ResistanceSignal
    detected: bool
    probability: float  # 0.0-1.0
    confidence: float   # 0.0-1.0
    rationale: str
    provenance: Dict
    # Mechanism details
    mechanism_breakdown: Optional[MechanismBreakdown] = None
    escaped_pathways: Optional[List[str]] = None
    mechanism_alignment: Optional[Dict[str, float]] = None
    # Missing Data Policy
    baseline_reliability: float = 1.0  # 1.0 = Patient Baseline, 0.2 = Population

@dataclass
class ResistancePrediction:
    """Complete resistance prediction output"""
    risk_level: ResistanceRiskLevel
    probability: float  # Overall resistance probability
    confidence: float   # Prediction confidence
    signals_detected: List[ResistanceSignalData]
    signal_count: int
    urgency: UrgencyLevel
    recommended_actions: List[Dict]
    next_line_options: List[Dict]
    rationale: List[str]
    provenance: Dict
    warnings: List[str]
    baseline_source: str
    baseline_penalty_applied: bool
    confidence_cap: Optional[str] = None
    
    # NEW: HRD decomposition for Gap 3 (Phase 4)
    hrd_components: Optional['HRDComponentScores'] = None
    
    # NEW: Driver Alerts (Split Output Strategy)
    driver_alerts: List['DriverAlert'] = field(default_factory=list)
    genomic_alert_context: Optional[Dict] = None


@dataclass
class DriverAlert:
    """Genomic driver alert (Biology), distinct from Clinical Risk."""
    gene: str
    variant: str
    mechanism: str
    clinical_implication: str
    evidence_tier: str = "Tier 1"



@dataclass
class HRDComponentScores:
    """Decomposed HRD-like score for probabilistic interpretation."""
    
    # Component scores (0-1)
    ddr_component: float          # DNA Damage Response pathway score
    hrr_component: float          # Homologous Recombination Repair score
    exon_disruption: float        # Exon-level damage score
    
    # Aggregated
    raw_hrd_score: float          # Weighted sum
    calibrated_hrd_probability: float  # 0-100%, outcome-calibrated
    
    # Confidence
    confidence_interval: tuple    # (low, high)
    calibration_source: str       # "TCGA-OV" or "population"

@dataclass
class NextTestAction:
    """A deterministic test recommendation from the TestRouter."""
    test_id: str
    priority: str  # IMMEDIATE, HIGH, ROUTINE
    
    # Timing / Interval Logic
    frequency: str  # "ONCE", "WEEKLY", "MONTHLY"
    duration: str   # "x1", "x3", "UNTIL_RESOLUTION"
    
    # Rationale
    why: str
    enables_signals: List[str]
    triggered_by: List[str]
    expected_effect: Optional[Dict[str, str]] = None

@dataclass
class LogicStep:
    """A single step in the logic stream audit log."""
    ts: str
    severity: str  # INFO, WARNING, CRITICAL
    event: str
    because: str
    provenance: Dict

