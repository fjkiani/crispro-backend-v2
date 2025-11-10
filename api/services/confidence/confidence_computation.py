"""
Confidence Computation: Core confidence calculation logic.
"""
from typing import Dict
from .models import ConfidenceConfig


def compute_confidence(tier: str, seq_pct: float, path_pct: float, 
                      insights: Dict[str, float], config: ConfidenceConfig) -> float:
    """
    Compute confidence score based on tier and supporting signals.
    
    Args:
        tier: Evidence tier
        seq_pct: Sequence percentile
        path_pct: Pathway percentile
        insights: Insights scores (functionality, chromatin, essentiality, regulatory)
        config: Confidence configuration
        
    Returns:
        Confidence score [0, 1]
    """
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    # Base confidence by tier
    if tier == "supported":
        confidence = 0.6 + 0.2 * max(seq_pct, path_pct)
    elif tier == "consider":
        # Under fusion and strong S/P, raise base confidence conservatively (research-mode)
        if config.fusion_active and max(seq_pct, path_pct) >= 0.7:
            confidence = 0.5 + 0.2 * max(seq_pct, path_pct)
        else:
            confidence = 0.3 + 0.1 * seq_pct + 0.1 * path_pct
    else:  # insufficient
        # Research-mode: raise base confidence using S/P strength, with higher floor under Fusion
        max_sp = max(seq_pct, path_pct)
        min_sp = min(seq_pct, path_pct)
        base = 0.20 + 0.35 * max_sp + 0.15 * min_sp
        if config.fusion_active:
            confidence = max(0.25, base)
        else:
            confidence = base
    
    # Insights modulation (small, transparent lifts)
    confidence += 0.05 if func >= 0.6 else 0.0
    confidence += 0.04 if chrom >= 0.5 else 0.0
    confidence += 0.07 if ess >= 0.7 else 0.0
    confidence += 0.02 if reg >= 0.6 else 0.0

    # Alignment margin boost: if top pathway signal is clearly higher than others
    try:
        margin = abs(seq_pct - path_pct)
        if margin >= 0.2:
            confidence += 0.05
    except Exception:
        pass
    
    return float(min(1.0, max(0.0, confidence)))


def apply_confidence_modulation(base_confidence: float, tier: str, 
                               insights_lifts: Dict[str, float], 
                               config: ConfidenceConfig) -> float:
    """
    Apply insights-based confidence modulation.
    
    Args:
        base_confidence: Base confidence score
        tier: Evidence tier
        insights_lifts: Insights-based lifts
        config: Confidence configuration
        
    Returns:
        Modulated confidence score
    """
    confidence = base_confidence
    
    # Apply insights lifts
    for insight, lift in insights_lifts.items():
        confidence += lift
    
    # Tier-specific adjustments
    if tier == "insufficient" and config.fusion_active:
        # Under fusion, cap the penalty for insufficient evidence
        confidence = max(0.1, confidence)
    
    return float(min(1.0, max(0.0, confidence)))

