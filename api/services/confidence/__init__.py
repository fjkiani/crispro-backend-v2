"""
Confidence Package: Evidence tier computation and confidence modulation.
"""
from .models import ConfidenceConfig
from .tier_computation import compute_evidence_tier
from .confidence_computation import compute_confidence, apply_confidence_modulation
from .badge_computation import compute_evidence_badges
from .insights_lifts import compute_insights_lifts
from .manifest_computation import compute_evidence_manifest
from .rationale_computation import compute_rationale_breakdown
from .config_factory import get_default_confidence_config, create_confidence_config

__all__ = [
    "ConfidenceConfig",
    "compute_evidence_tier",
    "compute_confidence", 
    "apply_confidence_modulation",
    "compute_evidence_badges",
    "compute_insights_lifts",
    "compute_evidence_manifest",
    "compute_rationale_breakdown",
    "get_default_confidence_config",
    "create_confidence_config"
]


