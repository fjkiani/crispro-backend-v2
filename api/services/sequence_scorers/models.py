"""
Sequence Scorers Models: Data classes for sequence scoring results.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class SeqScore:
    """Normalized sequence score result."""
    variant: Dict[str, Any]
    sequence_disruption: float
    min_delta: Optional[float] = None
    exon_delta: Optional[float] = None
    calibrated_seq_percentile: Optional[float] = None
    impact_level: str = "no_impact"
    scoring_mode: str = "unknown"
    best_model: Optional[str] = None
    best_window_bp: Optional[int] = None
    scoring_strategy: Dict[str, Any] = None
    forward_reverse_meta: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.scoring_strategy is None:
            self.scoring_strategy = {}


