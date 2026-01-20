"""
SPE Scoring Step

Computes Sequence, Pathway, Evidence scores.
Extracts SAE features from SPE result.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def compute_spe_score(
    compound: str,
    targets: List[str],
    pathways: List[str],
    disease_context: Dict[str, Any],
    evidence_grade: str,
    treatment_history: Optional[Dict[str, Any]] = None,
    evo2_enabled: bool = False
) -> Dict[str, Any]:
    """
    Compute SPE (Sequence, Pathway, Evidence) score.
    
    Args:
        compound: Compound name
        targets: List of targets
        pathways: List of pathways
        disease_context: Disease context
        evidence_grade: Evidence grade from evidence mining
        treatment_history: Treatment history (optional)
        evo2_enabled: Whether Evo2 is enabled
    
    Returns:
        {
            "overall_score": 0.0-1.0,
            "spe_breakdown": {
                "sequence": 0.0-1.0,
                "pathway": 0.0-1.0,
                "evidence": 0.0-1.0
            },
            "confidence": 0.0-1.0,
            "verdict": "NOT_SUPPORTED" | "WEAK_SUPPORT" | "MODERATE_SUPPORT" | "STRONG_SUPPORT",
            "sae_features": {
                "line_appropriateness": 0.0-1.0,
                "cross_resistance": 0.0-1.0,
                "sequencing_fitness": 0.0-1.0
            },
            "provenance": {...}
        }
    """
    from api.services.food_spe_integration import FoodSPEIntegrationService
    
    spe_service = FoodSPEIntegrationService()
    
    spe_result = await spe_service.compute_spe_score(
        compound=compound,
        targets=targets,
        pathways=pathways,
        disease_context=disease_context,
        evidence_grade=evidence_grade,
        treatment_history=treatment_history,
        evo2_enabled=evo2_enabled
    )
    
    return spe_result

