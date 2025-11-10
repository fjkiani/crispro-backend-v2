"""
Confidence Models: Data classes for confidence computation.
"""
from dataclasses import dataclass


@dataclass
class ConfidenceConfig:
    """Configuration for confidence computation."""
    evidence_gate_threshold: float = 0.7
    pathway_alignment_threshold: float = 0.2
    insufficient_signal_threshold: float = 0.02
    fusion_active: bool = False


