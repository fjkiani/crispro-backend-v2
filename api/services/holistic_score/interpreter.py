"""
Score Interpreter

Generates human-readable interpretation and recommendations from holistic scores.
"""

from typing import Dict, Any, Tuple


def interpret_score(
    holistic_score: float,
    mechanism_fit: float,
    eligibility: float,
    pgx_safety: float,
    pgx_details: Dict[str, Any],
    trial: Dict[str, Any]
) -> Tuple[str, str]:
    """
    Generate interpretation and recommendation from holistic score.
    
    Args:
        holistic_score: Combined holistic score (0.0-1.0)
        mechanism_fit: Mechanism fit score (0.0-1.0)
        eligibility: Eligibility score (0.0-1.0)
        pgx_safety: PGx safety score (0.0-1.0)
        pgx_details: PGx details dict
        trial: Trial data with nct_id
    
    Returns:
        Tuple of (interpretation_string, recommendation_string)
    """
    nct_id = trial.get("nct_id", trial.get("nctId", "this trial"))
    
    # Check for hard contraindication
    if pgx_details.get("contraindicated"):
        return "CONTRAINDICATED", (
            f"⛔ CONTRAINDICATED for {nct_id}: {pgx_details.get('reason')}. "
            f"Consider alternative trial without this drug class or enroll "
            f"with modified protocol (pre-approved dose adjustment)."
        )
    
    # Check for hard eligibility fail
    if eligibility <= 0.0:
        return "INELIGIBLE", (
            f"❌ INELIGIBLE for {nct_id}: Patient does not meet hard eligibility "
            f"criteria (recruiting status, age, or other requirements). "
            f"Consider alternative trials."
        )
    
    # Interpret holistic score
    if holistic_score >= 0.8:
        return "HIGH", (
            f"✅ HIGH PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
            f"Strong mechanism alignment ({mechanism_fit:.2f}), meets eligibility "
            f"({eligibility:.2f}), and no significant PGx concerns ({pgx_safety:.2f}). "
            f"Recommend proceeding with enrollment."
        )
    
    elif holistic_score >= 0.6:
        concerns = []
        if mechanism_fit < 0.6:
            concerns.append(f"moderate mechanism fit ({mechanism_fit:.2f})")
        if eligibility < 0.8:
            concerns.append(f"eligibility concerns ({eligibility:.2f})")
        if pgx_safety < 0.8:
            concerns.append(f"dose adjustment may be needed ({pgx_safety:.2f})")
        
        concern_str = ", ".join(concerns) if concerns else "borderline scores"
        return "MEDIUM", (
            f"⚠️ MODERATE PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
            f"Proceed with caution due to: {concern_str}. "
            f"Consider additional workup before enrollment."
        )
    
    elif holistic_score >= 0.4:
        return "LOW", (
            f"⚠️ LOW PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
            f"Significant concerns: mechanism fit={mechanism_fit:.2f}, "
            f"eligibility={eligibility:.2f}, PGx safety={pgx_safety:.2f}. "
            f"Consider alternative trials with better alignment."
        )
    
    else:
        return "VERY_LOW", (
            f"❌ VERY LOW PROBABILITY for {nct_id} (score: {holistic_score:.2f}). "
            f"Poor alignment across multiple dimensions. "
            f"Recommend alternative trial search."
        )
