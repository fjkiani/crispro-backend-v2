"""
PGx Safety Calculator

Computes PGx safety score from pharmacogene variants using PGx screening service.
"""

from typing import Dict, List, Any, Optional, Tuple
import logging

from .models import CONTRAINDICATION_THRESHOLD

logger = logging.getLogger(__name__)


async def compute_pgx_safety(
    pharmacogenes: Optional[List[Dict[str, str]]],
    drug: Optional[str],
    trial: Dict[str, Any],
    pgx_service
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute PGx safety score from pharmacogene variants.
    
    Returns inverted adjustment factor:
    - 1.0 = no variants (fully safe)
    - 0.5 = 50% dose reduction needed
    - 0.0 = contraindicated
    
    Args:
        pharmacogenes: List of {gene, variant} for PGx screening
        drug: Drug name for dosing guidance (optional, extracted from trial if not provided)
        trial: Trial data with interventions
        pgx_service: PGx screening service instance
    
    Returns:
        Tuple of (pgx_safety_score, pgx_details_dict)
    """
    # Try to get drug from trial interventions if not provided
    if not drug:
        interventions = trial.get("interventions", [])
        for intervention in interventions:
            if isinstance(intervention, dict):
                drug_names = intervention.get("drug_names", []) or intervention.get("drugs", [])
                if drug_names:
                    drug = drug_names[0] if isinstance(drug_names, list) else drug_names
                    break
    
    if not pharmacogenes:
        return 1.0, {
            "status": "not_screened", 
            "reason": "No germline variants provided",
            "contraindicated": False
        }
    
    if not drug:
        return 1.0, {
            "status": "not_screened",
            "reason": "No drug specified for PGx screening",
            "contraindicated": False
        }
    
    details = {
        "drug": drug,
        "variants_screened": [],
        "contraindicated": False,
        "dose_adjustments": []
    }
    
    min_adjustment = 1.0
    
    try:
        # Screen each pharmacogene
        for pgx in pharmacogenes:
            gene = pgx.get("gene", "")
            variant = pgx.get("variant", "")
            
            if not gene:
                continue
            
            # Use PGx screening service
            screening_result = await pgx_service.screen_drugs(
                drugs=[{"name": drug}],
                germline_variants=[pgx],
                treatment_line=None,
                prior_therapies=None,
                disease=None
            )
            
            drug_result = screening_result.get(drug, {})
            adjustment = drug_result.get("adjustment_factor", 1.0)
            tier = drug_result.get("toxicity_tier", "LOW")
            
            details["variants_screened"].append({
                "gene": gene,
                "variant": variant,
                "toxicity_tier": tier,
                "adjustment_factor": adjustment
            })
            
            if adjustment <= CONTRAINDICATION_THRESHOLD:
                details["contraindicated"] = True
                details["reason"] = f"{gene} {variant}: Contraindicated for {drug}"
                min_adjustment = 0.0
            elif adjustment < min_adjustment:
                min_adjustment = adjustment
                reduction_pct = int((1 - adjustment) * 100)
                details["dose_adjustments"].append(
                    f"{gene} {variant}: {reduction_pct}% dose reduction for {drug}"
                )
    
    except Exception as e:
        logger.error(f"PGx screening failed: {e}")
        return 1.0, {
            "status": "error",
            "reason": f"PGx screening failed: {str(e)}",
            "contraindicated": False
        }
    
    details["pgx_safety_score"] = min_adjustment
    return min_adjustment, details
