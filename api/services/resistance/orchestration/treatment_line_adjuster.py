"""
Treatment Line Adjuster.

Adjusts resistance probability based on treatment line context and cross-resistance patterns.
Implements expert opinion multipliers for clone evolution and cross-resistance.
"""

from typing import Dict, List, Optional, Tuple

from ..config import (
    TREATMENT_LINE_MULTIPLIERS,
    CROSS_RESISTANCE_MULTIPLIER,
    MAX_PROBABILITY_CAP,
)


class TreatmentLineAdjuster:
    """
    Adjust resistance probability based on treatment line context.
    
    Expert Opinion - Task 3:
    - 1st line: base probability
    - 2nd line: probability × 1.2 (clone evolution)
    - 3rd+ line: probability × 1.4 (heavily pre-treated)
    - Same-class prior: probability × 1.3 (cross-resistance)
    """
    
    @classmethod
    def adjust(
        cls,
        base_probability: float,
        treatment_line: int,
        prior_therapies: Optional[List[str]] = None,
        current_drug_class: Optional[str] = None
    ) -> Tuple[float, Dict]:
        """
        Adjust resistance probability based on treatment line context.
        
        Args:
            base_probability: Base resistance probability (0.0-1.0)
            treatment_line: Treatment line (1, 2, 3+)
            prior_therapies: List of prior drug classes
            current_drug_class: Current drug class being assessed
            
        Returns:
            Tuple of (adjusted_probability, adjustment_details)
        """
        # Get line multiplier (cap at line 3+)
        line_multiplier = TREATMENT_LINE_MULTIPLIERS.get(
            min(treatment_line, 3),
            TREATMENT_LINE_MULTIPLIERS[3]
        )
        
        # Check for cross-resistance (same-class prior exposure)
        cross_resistance_applied = False
        if prior_therapies and current_drug_class:
            prior_classes = [p.lower().replace(" ", "_").replace("-", "_") for p in prior_therapies]
            current_class = current_drug_class.lower().replace(" ", "_").replace("-", "_")
            if current_class in prior_classes:
                line_multiplier *= CROSS_RESISTANCE_MULTIPLIER
                cross_resistance_applied = True
        
        # Apply multiplier but cap at MAX_PROBABILITY_CAP
        adjusted_probability = min(MAX_PROBABILITY_CAP, base_probability * line_multiplier)
        
        adjustment_details = {
            "treatment_line": treatment_line,
            "line_multiplier": TREATMENT_LINE_MULTIPLIERS.get(min(treatment_line, 3), 1.0),
            "cross_resistance_applied": cross_resistance_applied,
            "cross_resistance_multiplier": CROSS_RESISTANCE_MULTIPLIER if cross_resistance_applied else 1.0,
            "final_multiplier": line_multiplier,
            "evidence_level": "EXPERT_OPINION",
            "prior_therapies": prior_therapies,
            "current_drug_class": current_drug_class
        }
        
        return adjusted_probability, adjustment_details
