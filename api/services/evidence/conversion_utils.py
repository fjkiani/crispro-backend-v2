"""
Evidence Conversion Utils: Data conversion utilities.
"""
from typing import Dict, Any

from .models import EvidenceHit, ClinvarPrior


def evidence_to_dict(evidence_hit: EvidenceHit) -> Dict[str, Any]:
    """
    Convert EvidenceHit to dictionary format.
    
    Args:
        evidence_hit: EvidenceHit object
        
    Returns:
        Dict representation
    """
    return {
        "top_results": evidence_hit.top_results,
        "filtered": evidence_hit.filtered,
        "strength": evidence_hit.strength,
        "pubmed_query": evidence_hit.pubmed_query,
        "moa_hits": evidence_hit.moa_hits,
        "provenance": evidence_hit.provenance
    }


def clinvar_to_dict(clinvar_prior: ClinvarPrior) -> Dict[str, Any]:
    """
    Convert ClinvarPrior to dictionary format.
    
    Args:
        clinvar_prior: ClinvarPrior object
        
    Returns:
        Dict representation
    """
    return {
        "deep_analysis": clinvar_prior.deep_analysis,
        "prior": clinvar_prior.prior,
        "provenance": clinvar_prior.provenance
    }


