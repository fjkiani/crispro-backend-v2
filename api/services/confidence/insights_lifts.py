"""
Insights Lifts: Confidence lift computation from insights.
"""
from typing import Dict


def compute_insights_lifts(insights: Dict[str, float]) -> Dict[str, float]:
    """
    Compute confidence lifts from insights scores.
    
    Args:
        insights: Insights scores dictionary
        
    Returns:
        Dict mapping insight names to lift values
    """
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


