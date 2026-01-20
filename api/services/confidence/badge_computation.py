"""
Badge computation for evidence quality indicators
"""

from typing import List, Dict, Any


def compute_evidence_badges(
    evidence_tier: str,
    literature_strength: float = 0.0,
    clinvar_review: str = "",
    pathway_aligned: bool = False,
    **kwargs
) -> List[str]:
    """
    Compute evidence quality badges based on multiple signals
    
    Args:
        evidence_tier: Evidence tier (supported/consider/insufficient)
        literature_strength: Literature strength score [0,1]
        clinvar_review: ClinVar review status
        pathway_aligned: Whether variant aligns with pathway expectations
        **kwargs: Additional signals
        
    Returns:
        List of badge strings (e.g., ["RCT", "Guideline", "ClinVar-Strong"])
    """
    badges = []
    
    # Evidence tier badge
    if evidence_tier == "supported":
        badges.append("Evidence-Supported")
    elif evidence_tier == "consider":
        badges.append("Consider")
    
    # Literature badges
    if literature_strength >= 0.8:
        badges.append("RCT")
    elif literature_strength >= 0.6:
        badges.append("Guideline")
    elif literature_strength >= 0.4:
        badges.append("Case-Series")
    
    # ClinVar badges
    if "expert" in clinvar_review.lower() or "practice" in clinvar_review.lower():
        badges.append("ClinVar-Strong")
    elif clinvar_review:
        badges.append("ClinVar")
    
    # Pathway alignment
    if pathway_aligned:
        badges.append("PathwayAligned")
    
    return badges