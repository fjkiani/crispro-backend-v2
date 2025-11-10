"""
Config Factory: Confidence configuration creation utilities.
"""
from .models import ConfidenceConfig


def get_default_confidence_config() -> ConfidenceConfig:
    """
    Get default confidence configuration.
    
    Returns:
        Default ConfidenceConfig
    """
    return ConfidenceConfig()


def create_confidence_config(evidence_gate_threshold: float = 0.7,
                           pathway_alignment_threshold: float = 0.2,
                           insufficient_signal_threshold: float = 0.02,
                           fusion_active: bool = False) -> ConfidenceConfig:
    """
    Create custom confidence configuration.
    
    Args:
        evidence_gate_threshold: Evidence gate threshold
        pathway_alignment_threshold: Pathway alignment threshold
        insufficient_signal_threshold: Insufficient signal threshold
        fusion_active: Whether fusion engine is active
        
    Returns:
        Custom ConfidenceConfig
    """
    return ConfidenceConfig(
        evidence_gate_threshold=evidence_gate_threshold,
        pathway_alignment_threshold=pathway_alignment_threshold,
        insufficient_signal_threshold=insufficient_signal_threshold,
        fusion_active=fusion_active
    )


