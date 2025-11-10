"""
Evidence Package: Literature search and ClinVar prior analysis.
"""
from .models import EvidenceHit, ClinvarPrior
from .literature_client import literature
from .clinvar_client import clinvar_prior
from .badge_computation import compute_evidence_badges
from .conversion_utils import evidence_to_dict, clinvar_to_dict

__all__ = [
    "EvidenceHit",
    "ClinvarPrior", 
    "literature",
    "clinvar_prior",
    "compute_evidence_badges",
    "evidence_to_dict",
    "clinvar_to_dict"
]


