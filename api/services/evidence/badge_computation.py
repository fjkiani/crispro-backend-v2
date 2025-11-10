"""
Evidence Badge Computation: Badge determination logic.
"""
from typing import Dict, Any, List

from .models import EvidenceHit, ClinvarPrior


def _safe_lower(x: Any) -> str:
    """Safely convert to lowercase string."""
    try:
        return str(x or "").lower()
    except Exception:
        return ""


def compute_evidence_badges(evidence_hit: EvidenceHit, clinvar_prior: ClinvarPrior) -> List[str]:
    """
    Compute evidence badges based on literature and ClinVar results.
    
    Args:
        evidence_hit: Literature evidence result
        clinvar_prior: ClinVar prior result
        
    Returns:
        List of badge strings
    """
    badges = []
    
    # Literature badges
    if evidence_hit.strength >= 0.7:
        badges.append("StrongLiterature")
    elif evidence_hit.strength >= 0.4:
        badges.append("ModerateLiterature")
    
    # MoA alignment badge
    if evidence_hit.moa_hits > 0:
        badges.append("MoAAligned")
    
    # ClinVar badges
    if clinvar_prior.deep_analysis:
        clinvar_data = clinvar_prior.deep_analysis.get("clinvar", {})
        classification = str(clinvar_data.get("classification", "")).lower()
        review_status = str(clinvar_data.get("review_status", "")).lower()
        
        if classification in ("pathogenic", "likely_pathogenic"):
            if "expert" in review_status or "practice" in review_status:
                badges.append("ClinVarStrong")
            else:
                badges.append("ClinVarModerate")
        elif classification in ("benign", "likely_benign"):
            badges.append("ClinVarBenign")
    
    # Publication type badges
    for result in evidence_hit.top_results[:3]:
        pub_types = " ".join([_safe_lower(t) for t in (result.get("publication_types") or [])])
        title = _safe_lower(result.get("title"))
        
        if "randomized" in pub_types or "randomized" in title:
            badges.append("RCT")
        elif "guideline" in pub_types or "practice" in title:
            badges.append("Guideline")
    
    return badges


