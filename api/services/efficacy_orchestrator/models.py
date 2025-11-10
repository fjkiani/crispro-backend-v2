"""
Efficacy Orchestrator Models: Data classes for efficacy prediction.
"""
import uuid
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class EfficacyRequest:
    """Efficacy prediction request."""
    mutations: List[Dict[str, Any]]
    model_id: str = "evo2_7b"
    options: Dict[str, Any] = None
    api_base: str = "http://127.0.0.1:8000"
    disease: Optional[str] = None
    moa_terms: Optional[List[str]] = None
    include_trials_stub: bool = False
    include_fda_badges: bool = False
    include_cohort_overlays: bool = False
    include_calibration_snapshot: bool = False
    ablation_mode: Optional[str] = None  # One of: S_only, P_only, E_only, SP, SE, PE, SPE
    treatment_history: Optional[Dict[str, Any]] = None  # Phase 3: Treatment line integration
    
    # NEW: Sporadic Cancer Strategy (Day 2)
    germline_status: Optional[str] = "unknown"  # "positive", "negative", "unknown"
    tumor_context: Optional[Dict[str, Any]] = None  # TumorContext dict from /api/tumor/quick_intake
    
    def __post_init__(self):
        if self.options is None:
            self.options = {"adaptive": True, "ensemble": True}


@dataclass
class EfficacyResponse:
    """Efficacy prediction response."""
    drugs: List[Dict[str, Any]]
    run_signature: str
    scoring_strategy: Dict[str, Any]
    evidence_tier: str
    provenance: Dict[str, Any]
    cohort_signals: Optional[Dict[str, Any]] = None
    calibration_snapshot: Optional[Dict[str, Any]] = None
    sae_features: Optional[Dict[str, Any]] = None  # P2: SAE interpretable features
    schema_version: str = "v1"
    
    def __post_init__(self):
        if self.provenance is None:
            self.provenance = {}


@dataclass
class DrugScoreResult:
    """Individual drug scoring result."""
    name: str
    moa: str
    efficacy_score: float
    confidence: float
    evidence_tier: str
    badges: List[str]
    evidence_strength: float
    citations: List[str]
    citations_count: int
    clinvar: Dict[str, Any]
    evidence_manifest: Dict[str, Any]
    insights: Dict[str, float]
    rationale: List[Dict[str, Any]]
    meets_evidence_gate: bool
    insufficient_signal: bool


