"""
Confidence Capping by Completeness Level

Caps confidence based on tumor context completeness (L0/L1/L2).
Ensures we don't overstate confidence when data is incomplete.

Logic:
- Level 0 (completeness <0.3): Cap confidence at 0.4 (low quality data)
- Level 1 (0.3 ≤ completeness <0.7): Cap confidence at 0.6 (moderate quality)
- Level 2 (completeness ≥0.7): No cap (high quality data)
"""
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def apply_confidence_capping(
    confidence: float,
    tumor_context: Optional[Dict[str, Any]] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply confidence capping based on tumor context completeness.
    
    Args:
        confidence: Base confidence score (0-1)
        tumor_context: TumorContext dict with completeness_score
    
    Returns:
        Tuple of (capped_confidence, rationale_dict)
        - capped_confidence: Confidence after capping (0-1)
        - rationale_dict: Contains cap value, level, completeness, reason
    """
    original_confidence = confidence
    rationale_dict = {
        "gate": None,
        "verdict": "NO_CAP",
        "cap": None,
        "level": None,
        "completeness": None,
        "reason": "No confidence capping applied"
    }
    
    # Extract completeness level (L0, L1, L2)
    completeness_score = 0.0
    level = "L0"  # Default to Level 0
    
    if tumor_context:
        completeness_score = tumor_context.get("completeness_score", 0.0)
        if completeness_score >= 0.7:
            level = "L2"  # Full report
        elif completeness_score >= 0.3:
            level = "L1"  # Partial data
        else:
            level = "L0"  # Minimal data
    
    # Apply capping based on level
    if level == "L0":
        # Cap at 0.4 for minimal data
        if confidence > 0.4:
            confidence = 0.4
            rationale_dict = {
                "gate": "CONFIDENCE_CAP_L0",
                "verdict": "CAPPED",
                "cap": 0.4,
                "level": "L0",
                "completeness": completeness_score,
                "original_confidence": original_confidence,
                "capped_confidence": confidence,
                "reason": f"Level 0 data (completeness={completeness_score:.2f}) → confidence capped at 0.4"
            }
    
    elif level == "L1":
        # Cap at 0.6 for partial data
        if confidence > 0.6:
            confidence = 0.6
            rationale_dict = {
                "gate": "CONFIDENCE_CAP_L1",
                "verdict": "CAPPED",
                "cap": 0.6,
                "level": "L1",
                "completeness": completeness_score,
                "original_confidence": original_confidence,
                "capped_confidence": confidence,
                "reason": f"Level 1 data (completeness={completeness_score:.2f}) → confidence capped at 0.6"
            }
    
    # Level 2: No cap (full report, high quality)
    # If no cap was applied, update rationale to reflect that
    if rationale_dict["gate"] is None:
        rationale_dict = {
            "gate": "CONFIDENCE_CAP_L2",
            "verdict": "NO_CAP",
            "cap": None,
            "level": level,
            "completeness": completeness_score,
            "original_confidence": original_confidence,
            "capped_confidence": confidence,
            "reason": f"Level {level[-1]} data (completeness={completeness_score:.2f}) → no confidence cap applied"
        }
    
    return confidence, rationale_dict
