"""
Confidence Computation: Core confidence calculation logic.
"""
import os
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
    # Feature flag for new confidence calculation
    if os.getenv("CONFIDENCE_V2", "0") == "1":
        return compute_confidence_v2(tier, seq_pct, path_pct, insights, config)
    
    # LEGACY: Original tier-based approach (commented out for safety)
    # func = insights.get("functionality", 0.0)
    # chrom = insights.get("chromatin", 0.0)
    # ess = insights.get("essentiality", 0.0)
    # reg = insights.get("regulatory", 0.0)
    # 
    # # Base confidence by tier
    # if tier == "supported":
    #     confidence = 0.6 + 0.2 * max(seq_pct, path_pct)
    # elif tier == "consider":
    #     # Under fusion and strong S/P, raise base confidence conservatively (research-mode)
    #     if config.fusion_active and max(seq_pct, path_pct) >= 0.7:
    #         confidence = 0.5 + 0.2 * max(seq_pct, path_pct)
    #     else:
    #         confidence = 0.3 + 0.1 * seq_pct + 0.1 * path_pct
    # else:  # insufficient
    #     # Research-mode: raise base confidence using S/P strength, with higher floor under Fusion
    #     max_sp = max(seq_pct, path_pct)
    #     min_sp = min(seq_pct, path_pct)
    #     base = 0.20 + 0.35 * max_sp + 0.15 * min_sp
    #     if config.fusion_active:
    #         confidence = max(0.25, base)
    #     else:
    #         confidence = base
    # 
    # # Insights modulation (small, transparent lifts)
    # confidence += 0.05 if func >= 0.6 else 0.0
    # confidence += 0.04 if chrom >= 0.5 else 0.0
    # confidence += 0.07 if ess >= 0.7 else 0.0
    # confidence += 0.02 if reg >= 0.6 else 0.0
    # 
    # # Alignment margin boost: if top pathway signal is clearly higher than others
    # try:
    #     margin = abs(seq_pct - path_pct)
    #     if margin >= 0.2:
    #         confidence += 0.05
    # except Exception:
    #     pass
    # 
    # return float(min(1.0, max(0.0, confidence)))
    
    # LEGACY: Keep original implementation as fallback
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


def compute_confidence_v2(tier: str, seq_pct: float, path_pct: float, 
                         insights: Dict[str, float], config: ConfidenceConfig) -> float:
    """
    Compute confidence score using linear S/P/E formula (CONFIDENCE_V2=1).
    
    Formula: confidence = clamp01(0.5·S + 0.2·P + 0.3·E + lifts)
    Lifts: +0.04 if functionality≥0.6; +0.02 if chromatin≥0.5; +0.02 if essentiality≥0.7; +0.02 if regulatory≥0.6
    Cap total lifts at +0.08; round to 2 decimals
    
    Args:
        tier: Evidence tier (used for E component)
        seq_pct: Sequence percentile (S component)
        path_pct: Pathway percentile (P component)
        insights: Insights scores (functionality, chromatin, essentiality, regulatory)
        config: Confidence configuration
        
    Returns:
        Confidence score [0, 1] rounded to 2 decimals
    """
    # Extract insights scores
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    # Convert tier to evidence score (E component)
    # Tier I (supported): +0.05, Tier II (consider): +0.02, Tier III (insufficient): +0.00
    if tier == "supported":
        e_score = 0.05
    elif tier == "consider":
        e_score = 0.02
    else:  # insufficient
        e_score = 0.00
    
    # Calculate lifts with exact specifications
    lifts = 0.0
    lifts += 0.04 if func >= 0.6 else 0.0      # Functionality
    lifts += 0.02 if chrom >= 0.5 else 0.0     # Chromatin
    lifts += 0.02 if ess >= 0.7 else 0.0       # Essentiality
    lifts += 0.02 if reg >= 0.6 else 0.0       # Regulatory
    
    # Cap total lifts at +0.08
    lifts = min(lifts, 0.08)
    
    # Linear S/P/E formula: confidence = clamp01(0.5·S + 0.2·P + 0.3·E + lifts)
    confidence = 0.5 * seq_pct + 0.2 * path_pct + 0.3 * e_score + lifts
    
    # Clamp to [0, 1] and round to 2 decimals
    confidence = clamp01(confidence)
    return round(confidence, 2)


def clamp01(x: float) -> float:
    """
    Clamp value to [0, 1] range.
    
    Args:
        x: Input value
        
    Returns:
        Clamped value in [0, 1]
    """
    return min(1.0, max(0.0, x))


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

