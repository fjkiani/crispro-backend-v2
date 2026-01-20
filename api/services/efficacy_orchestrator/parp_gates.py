"""
PARP Inhibitor Gates (Germline + HRD Rescue)

Applies PARP penalty/rescue logic based on germline status and HRD score.
Critical for sporadic ovarian cancer patients (85-90% of cases).

Logic:
- Germline positive → Full PARP effect (1.0x)
- Germline negative + HRD ≥42 → Rescue PARP! (1.0x) ⚔️
- Germline negative + HRD <42 → Reduced effect (0.6x)
- Unknown germline + unknown HRD → Conservative penalty (0.8x)
"""
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)


def apply_parp_gates(
    drug_class: str,
    moa: str,
    germline_status: str,
    tumor_context: Optional[Dict[str, Any]] = None,
    expression_data: Optional[Any] = None,  # For future pathway-based PARP prediction
    cancer_type: Optional[str] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply PARP inhibitor penalty/rescue gates.
    
    Args:
        drug_class: Drug class (e.g., "PARP inhibitor")
        moa: Mechanism of action
        germline_status: "positive", "negative", "unknown"
        tumor_context: TumorContext dict with HRD score
        expression_data: Optional expression data (for future pathway-based prediction)
        cancer_type: Cancer type (for future pathway-based prediction)
    
    Returns:
        Tuple of (parp_penalty_factor, rationale_dict)
        - parp_penalty_factor: Multiplier for efficacy score (1.0 = no penalty)
        - rationale_dict: Contains penalty value, gate name, reason, HRD score if applicable
    """
    # Check if this is a PARP inhibitor
    if "parp" not in drug_class.lower() and "parp" not in moa.lower():
        return 1.0, {
            "gate": None,
            "verdict": "NOT_PARP",
            "penalty": 1.0,
            "reason": "Not a PARP inhibitor - no PARP gates applied"
        }
    
    parp_penalty = 1.0  # Default: no penalty
    rationale_dict = {
        "gate": None,
        "verdict": "NO_PENALTY",
        "penalty": 1.0,
        "reason": "PARP gates not applied"
    }
    
    if germline_status == "positive":
        # Germline BRCA1/2 positive → full PARP effect
        parp_penalty = 1.0
        rationale_dict = {
            "gate": "PARP_GERMLINE",
            "verdict": "FULL_EFFECT",
            "penalty": 1.0,
            "reason": "Germline BRCA1/2 positive → PARP inhibitor appropriate"
        }
    
    elif germline_status == "negative":
        # Germline negative → check tumor HRD
        if tumor_context and tumor_context.get("hrd_score") is not None:
            hrd_score = tumor_context["hrd_score"]
            
            if hrd_score >= 42:
                # HRD-high rescue! ⚔️
                parp_penalty = 1.0
                rationale_dict = {
                    "gate": "PARP_HRD_RESCUE",
                    "verdict": "RESCUED",
                    "penalty": 1.0,
                    "hrd_score": hrd_score,
                    "reason": f"Germline negative BUT HRD-high (≥42): score={hrd_score:.1f} → PARP rescued! ⚔️"
                }
            else:
                # HRD present but <42
                parp_penalty = 0.6
                rationale_dict = {
                    "gate": "PARP_HRD_LOW",
                    "verdict": "REDUCED",
                    "penalty": 0.6,
                    "hrd_score": hrd_score,
                    "reason": f"Germline negative, HRD<42 (score={hrd_score:.1f}) → PARP reduced to 0.6x"
                }
        else:
            # Unknown HRD, germline negative
            parp_penalty = 0.8
            rationale_dict = {
                "gate": "PARP_UNKNOWN_HRD",
                "verdict": "CONSERVATIVE",
                "penalty": 0.8,
                "reason": "Germline negative, HRD unknown → PARP conservative penalty 0.8x"
            }
    
    elif germline_status == "unknown":
        # Unknown germline, unknown HRD
        parp_penalty = 0.8
        rationale_dict = {
            "gate": "PARP_UNKNOWN_GERMLINE",
            "verdict": "CONSERVATIVE",
            "penalty": 0.8,
            "reason": "Germline status unknown → PARP conservative penalty 0.8x"
        }
    
    return parp_penalty, rationale_dict
