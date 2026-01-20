"""
Tier Computation: Evidence tier determination logic.
"""
import os
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
    # Feature flag for new tier classification
    if os.getenv("CONFIDENCE_V2", "0") == "1":
        return compute_evidence_tier_v2(s_seq, s_path, s_evd, badges, config)
    
    # LEGACY: Original tier computation (commented out for safety)
    # # Evidence gate: strong evidence OR ClinVar-Strong + pathway alignment
    # evidence_gate = (
    #     s_evd >= config.evidence_gate_threshold or 
    #     ("ClinVar-Strong" in badges and s_path >= config.pathway_alignment_threshold)
    # )
    # 
    # # Insufficient signal: low sequence, pathway, and evidence
    # insufficient = (
    #     s_seq < config.insufficient_signal_threshold and 
    #     s_path < 0.05 and 
    #     s_evd < 0.2
    # )
    # 
    # if evidence_gate:
    #     return "supported"
    # elif insufficient:
    #     return "insufficient"
    # else:
    #     return "consider"
    
    # LEGACY: Keep original implementation as fallback
    # Evidence gate: strong evidence OR ClinVar-Strong + pathway alignment
    evidence_gate = (
        s_evd >= config.evidence_gate_threshold or 
        ("ClinVar-Strong" in badges and s_path >= config.pathway_alignment_threshold)
    )
    
    # Insufficient signal: low sequence, pathway, and evidence
    # NOTE: s_path threshold adjusted from 0.05 to 0.001 to match new pathway score range (0 to ~0.005)
    # Previous threshold (0.05) was for old normalization range (1e-6 to 1e-4)
    insufficient = (
        s_seq < config.insufficient_signal_threshold and 
        s_path < 0.001 and  # Adjusted for new pathway score range (max ~0.005)
        s_evd < 0.2
    )
    
    if evidence_gate:
        return "supported"
    elif insufficient:
        return "insufficient"
    else:
        return "consider"


def compute_evidence_tier_v2(s_seq: float, s_path: float, s_evd: float, 
                            badges: List[str], config: ConfidenceConfig) -> str:
    """
    Compute evidence tier with exact specifications (CONFIDENCE_V2=1).
    
    Tier I (supported): FDA on‑label OR ≥1 RCT OR (ClinVar‑Strong AND pathway_aligned). Confidence +0.05.
    Tier II (consider): ≥2 human studies MoA‑aligned OR 1 strong study + pathway_aligned. +0.02.
    Tier III (insufficient): else. +0.00.
    
    Args:
        s_seq: Sequence score
        s_path: Pathway score
        s_evd: Evidence score
        badges: List of evidence badges
        config: Confidence configuration
        
    Returns:
        Evidence tier: "supported", "consider", or "insufficient"
    """
    # Tier I (supported): FDA on‑label OR ≥1 RCT OR (ClinVar‑Strong AND pathway_aligned)
    if ("FDA-OnLabel" in badges or 
        "RCT" in badges or 
        ("ClinVar-Strong" in badges and s_path >= 0.2)):
        return "supported"
    
    # Tier II (consider): ≥2 human studies MoA‑aligned OR 1 strong study + pathway_aligned
    # For now, we'll use evidence strength as proxy for "strong study" and pathway alignment
    if (s_evd >= 0.6 or  # Strong evidence (proxy for strong study)
        (s_evd >= 0.4 and s_path >= 0.2)):  # Moderate evidence + pathway alignment
        return "consider"
    
    # Tier III (insufficient): else
    return "insufficient"

