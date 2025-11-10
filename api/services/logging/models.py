"""
Logging Models: Data classes for logging efficacy runs and evidence items.
"""
from dataclasses import dataclass
from typing import Dict, Any, List, Optional


@dataclass
class EfficacyRunData:
    """Efficacy run logging data."""
    run_signature: str
    request: Dict[str, Any]
    sequence_details: List[Dict[str, Any]]
    pathway_scores: Dict[str, float]
    scoring_strategy: Dict[str, Any]
    weights_snapshot: Dict[str, Any]
    gates_snapshot: Dict[str, Any]
    feature_flags_snapshot: Dict[str, Any]
    operational_mode: str
    confidence_tier: str
    drug_count: int
    insights: Dict[str, Any]


@dataclass
class EvidenceItem:
    """Evidence item logging data."""
    run_signature: str
    drug_name: str
    evidence_type: str
    content: Dict[str, Any]
    strength_score: float
    pubmed_id: Optional[str] = None



