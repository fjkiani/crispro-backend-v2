"""
Tier Computation: Evidence tier determination logic.
"""
from typing import List
from .models import ConfidenceConfig


def compute_evidence_tier(s_seq: float, s_path: float, s_evd: float, 
                         badges: List[str], config: ConfidenceConfig) -> str:
    """
    Compute evidence tier based on sequence, pathway, and evidence scores.
    
    Args:
        s_seq: Sequence score
        s_path: Pathway score
        s_evd: Evidence score
        badges: List of evidence badges
        config: Confidence configuration
        
    Returns:
        Evidence tier: "supported", "consider", or "insufficient"
    """
    # Evidence gate: strong evidence OR ClinVar-Strong + pathway alignment
    evidence_gate = (
        s_evd >= config.evidence_gate_threshold or 
        ("ClinVar-Strong" in badges and s_path >= config.pathway_alignment_threshold)
    )
    
    # Insufficient signal: low sequence, pathway, and evidence
    insufficient = (
        s_seq < config.insufficient_signal_threshold and 
        s_path < 0.05 and 
        s_evd < 0.2
    )
    
    if evidence_gate:
        return "supported"
    elif insufficient:
        return "insufficient"
    else:
        return "consider"

