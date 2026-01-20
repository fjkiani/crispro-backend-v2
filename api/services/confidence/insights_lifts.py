"""
Insights Lifts: Confidence lift computation from insights.
"""
import os
from typing import Dict


def compute_insights_lifts(insights: Dict[str, float]) -> Dict[str, float]:
    """
    Compute confidence lifts from insights scores.
    
    Args:
        insights: Insights scores dictionary
        
    Returns:
        Dict mapping insight names to lift values
    """
    # Feature flag for new lift values
    if os.getenv("CONFIDENCE_V2", "0") == "1":
        return compute_insights_lifts_v2(insights)
    
    # LEGACY: Original lift values (commented out for safety)
    # lifts = {}
    # 
    # func = insights.get("functionality", 0.0)
    # chrom = insights.get("chromatin", 0.0)
    # ess = insights.get("essentiality", 0.0)
    # reg = insights.get("regulatory", 0.0)
    # 
    # if func >= 0.6:
    #     lifts["functionality"] = 0.05
    # if chrom >= 0.5:
    #     lifts["chromatin"] = 0.03
    # if ess >= 0.7:
    #     lifts["essentiality"] = 0.07
    # if reg >= 0.6:
    #     lifts["regulatory"] = 0.02
    # 
    # return lifts
    
    # LEGACY: Keep original implementation as fallback
    lifts = {}
    
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    if func >= 0.6:
        lifts["functionality"] = 0.05
    if chrom >= 0.5:
        lifts["chromatin"] = 0.03
    if ess >= 0.7:
        lifts["essentiality"] = 0.07
    if reg >= 0.6:
        lifts["regulatory"] = 0.02
    
    return lifts


def compute_insights_lifts_v2(insights: Dict[str, float]) -> Dict[str, float]:
    """
    Compute confidence lifts with exact specifications (CONFIDENCE_V2=1).
    
    Lifts: +0.04 if functionality≥0.6; +0.02 if chromatin≥0.5; +0.02 if essentiality≥0.7; +0.02 if regulatory≥0.6
    Cap total lifts at +0.08
    
    Args:
        insights: Insights scores dictionary
        
    Returns:
        Dict mapping insight names to lift values with cap applied
    """
    lifts = {}
    
    func = insights.get("functionality", 0.0)
    chrom = insights.get("chromatin", 0.0)
    ess = insights.get("essentiality", 0.0)
    reg = insights.get("regulatory", 0.0)
    
    # Exact specifications
    if func >= 0.6:
        lifts["functionality"] = 0.04
    if chrom >= 0.5:
        lifts["chromatin"] = 0.02
    if ess >= 0.7:
        lifts["essentiality"] = 0.02
    if reg >= 0.6:
        lifts["regulatory"] = 0.02
    
    # Cap total lifts at +0.08
    total_lifts = sum(lifts.values())
    if total_lifts > 0.08:
        # Proportionally scale down all lifts to maintain relative importance
        scale_factor = 0.08 / total_lifts
        for key in lifts:
            lifts[key] = round(lifts[key] * scale_factor, 3)
    
    return lifts


