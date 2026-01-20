"""
SAE Features Step

Computes SAE (Sequencing, Appropriateness, Efficacy) features.
Wraps food_treatment_line_service.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


def compute_sae_features(
    compound: str,
    disease_context: Dict[str, Any],
    treatment_history: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Compute SAE features (treatment line intelligence).
    
    Note: This is a wrapper around food_treatment_line_service.
    The actual computation happens in FoodSPEIntegrationService.
    This function exists for consistency with the modular pipeline.
    
    Args:
        compound: Compound name
        disease_context: Disease context
        treatment_history: Treatment history (optional)
    
    Returns:
        {
            "line_appropriateness": 0.0-1.0,
            "cross_resistance": 0.0-1.0,
            "sequencing_fitness": 0.0-1.0
        }
    """
    try:
        from api.services.food_treatment_line_service import compute_food_treatment_line_features
        
        sae_scores = compute_food_treatment_line_features(
            compound=compound,
            disease_context=disease_context,
            treatment_history=treatment_history
        )
        
        return {
            "line_appropriateness": sae_scores.get("line_appropriateness", 0.6),
            "cross_resistance": sae_scores.get("cross_resistance", 0.0),
            "sequencing_fitness": sae_scores.get("sequencing_fitness", 0.6)
        }
    except Exception as e:
        logger.warning(f"SAE features computation failed: {e}")
        # Return defaults
        return {
            "line_appropriateness": 0.6,
            "cross_resistance": 0.0,
            "sequencing_fitness": 0.6
        }

