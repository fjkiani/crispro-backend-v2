"""
Ovarian Cancer Pathway-Based PARP/Platinum Gates

Applies pathway-based resistance prediction for PARP inhibitors and platinum agents
in ovarian cancer, based on GSE165897 validation (n=11, AUC=0.750).

Key Findings:
- post_ddr: ρ = -0.711, p = 0.014 (strongest correlation)
- post_pi3k: AUC = 0.750 (best predictor)
- Composite (weighted): ρ = -0.674, p = 0.023

Higher composite score → higher resistance risk → lower PARP/platinum efficacy
"""
import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd

from .ovarian_pathway_model import (
    compute_ovarian_pathway_scores,
    compute_ovarian_resistance_composite,
    classify_resistance_risk
)
from .ovarian_pathway_safety import (
    validate_expression_data_quality as validate_ovarian_expression_quality,
    should_use_pathway_prediction as should_use_ovarian_pathway_prediction,
    compute_ovarian_pathway_confidence,
    get_ruo_disclaimer as get_ovarian_ruo_disclaimer
)

logger = logging.getLogger(__name__)


def apply_ovarian_pathway_gates(
    drug_class: str,
    moa: str,
    tumor_context: Optional[Dict[str, Any]] = None,
    expression_data: Optional[pd.DataFrame] = None,
    cancer_type: Optional[str] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply ovarian cancer pathway-based gates for PARP/platinum drugs.
    
    Priority order:
    1. Pathway-based resistance prediction (GSE165897, AUC=0.750) - if expression available
    2. Fallback to HRD-based logic (if no expression)
    
    Args:
        drug_class: Drug class (e.g., "PARP inhibitor", "platinum")
        moa: Mechanism of action
        tumor_context: TumorContext dict with HRD score
        expression_data: Optional RNA-seq expression DataFrame
        cancer_type: Cancer type (e.g., "ovarian", "hgsoc")
    
    Returns:
        Tuple of (efficacy_multiplier, rationale_dict)
        - efficacy_multiplier: Multiplier for efficacy score (1.0 = no change)
        - rationale_dict: Contains gate name, verdict, composite score, resistance risk, safety metadata
    """
    # Check if this is a PARP or platinum drug
    is_parp = "parp" in drug_class.lower() or "parp" in moa.lower()
    is_platinum = (
        "platinum" in drug_class.lower() or
        "platinum" in moa.lower() or
        "carboplatin" in drug_class.lower() or
        "cisplatin" in drug_class.lower()
    )
    
    if not (is_parp or is_platinum):
        return 1.0, {
            "gate": None,
            "verdict": "NOT_OVARIAN_DRUG",
            "multiplier": 1.0,
            "reason": "Not a PARP or platinum drug - no ovarian pathway gates applied"
        }
    
    # Default: no change
    efficacy_multiplier = 1.0
    rationale_dict = {
        "gate": "OVARIAN_PATHWAY_GATES",
        "verdict": "NO_CHANGE",
        "multiplier": 1.0,
        "reason": "Ovarian pathway gates not applied"
    }
    
    # ====================================================================
    # PRIORITY 1: PATHWAY-BASED RESISTANCE PREDICTION (GSE165897)
    # ====================================================================
    if expression_data is not None:
        try:
            # Convert to DataFrame if needed
            if isinstance(expression_data, dict):
                expr_df = pd.DataFrame([expression_data]).T
                expr_df.columns = ['sample']
            elif isinstance(expression_data, pd.DataFrame):
                expr_df = expression_data
            else:
                logger.warning(f"Unsupported expression data type: {type(expression_data)}")
                expr_df = None
            
            if expr_df is not None and not expr_df.empty:
                # ============================================================
                # SAFETY LAYER 1: Validate Expression Data Quality
                # ============================================================
                expression_quality = validate_ovarian_expression_quality(expr_df)
                
                # Compute pathway scores
                pathway_scores = compute_ovarian_pathway_scores(expr_df)
                composite_score = compute_ovarian_resistance_composite(pathway_scores)
                
                # ============================================================
                # SAFETY LAYER 2: Check if pathway prediction should be used
                # ============================================================
                hrd_score = tumor_context.get("hrd_score") if tumor_context else None
                should_use_pathway, fallback_reason = should_use_ovarian_pathway_prediction(
                    composite_score,
                    cancer_type=cancer_type,
                    expression_quality=expression_quality,
                    hrd_score=hrd_score
                )
                
                if should_use_pathway:
                    # ============================================================
                    # SAFETY LAYER 3: Confidence-Adjusted Prediction
                    # ============================================================
                    confidence_adjusted_composite, safety_metadata = compute_ovarian_pathway_confidence(
                        composite_score,
                        cancer_type=cancer_type,
                        expression_quality=expression_quality,
                        pathway_coverage=expression_quality.get("avg_pathway_coverage", 0.0)
                    )
                    
                    # Classify resistance risk
                    resistance_risk = classify_resistance_risk(confidence_adjusted_composite)
                    
                    # Map resistance risk to efficacy multiplier
                    # Higher composite → higher resistance → lower efficacy
                    if resistance_risk == "HIGH":
                        # High resistance → reduce efficacy by 30%
                        efficacy_multiplier = 0.7
                        verdict = "REDUCED"
                    elif resistance_risk == "MODERATE":
                        # Moderate resistance → reduce efficacy by 15%
                        efficacy_multiplier = 0.85
                        verdict = "MODERATELY_REDUCED"
                    else:
                        # Low resistance → no change (or slight boost if very low)
                        if confidence_adjusted_composite < 0.10:
                            efficacy_multiplier = 1.05  # Slight boost for very sensitive
                            verdict = "SLIGHTLY_BOOSTED"
                        else:
                            efficacy_multiplier = 1.0
                            verdict = "NO_CHANGE"
                    
                    rationale_dict = {
                        "gate": "OVARIAN_PATHWAY_GATES",
                        "verdict": verdict,
                        "multiplier": efficacy_multiplier,
                        "composite_raw": composite_score,
                        "composite_adjusted": confidence_adjusted_composite,
                        "resistance_risk": resistance_risk,
                        "safety_metadata": safety_metadata,
                        "ruo_disclaimer": get_ovarian_ruo_disclaimer(cancer_type),
                        "reason": (
                            f"Pathway-based resistance prediction (GSE165897, AUC=0.750): "
                            f"composite={confidence_adjusted_composite:.3f}, "
                            f"risk={resistance_risk} → "
                            f"Efficacy multiplier {efficacy_multiplier:.2f}x"
                        )
                    }
                    
                    if safety_metadata.get("warnings"):
                        rationale_dict["warnings"] = safety_metadata["warnings"]
                        logger.warning(f"Ovarian pathway prediction warnings: {safety_metadata['warnings']}")
                else:
                    # Fallback to HRD-based logic
                    logger.info(f"OVARIAN PATHWAY PREDICTION: {fallback_reason}")
                    rationale_dict = {
                        "gate": "OVARIAN_PATHWAY_GATES",
                        "verdict": "FALLBACK",
                        "multiplier": 1.0,
                        "composite_raw": composite_score,
                        "fallback_reason": fallback_reason,
                        "ruo_disclaimer": get_ovarian_ruo_disclaimer(cancer_type),
                        "reason": (
                            f"Pathway prediction computed but not used: {fallback_reason}. "
                            f"Falling back to HRD-based logic."
                        )
                    }
        except Exception as e:
            logger.warning(f"Failed to compute ovarian pathway-based prediction: {e}")
            # Fall through to HRD-based logic (no change)
    
    # ====================================================================
    # PRIORITY 2: FALLBACK TO HRD-BASED LOGIC (if no expression)
    # ====================================================================
    # If no expression data or pathway prediction failed, rely on HRD score
    # This is handled by PARP gates in parp_gates.py
    # Here we just return no change if pathway prediction wasn't used
    if rationale_dict["verdict"] == "NO_CHANGE" and expression_data is None:
        rationale_dict["reason"] = (
            "No expression data available for pathway-based prediction. "
            "Relying on HRD-based PARP gates (see PARP_GERMLINE/PARP_HRD_RESCUE gates)."
        )
    
    return efficacy_multiplier, rationale_dict
