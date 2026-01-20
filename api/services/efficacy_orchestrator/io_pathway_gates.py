"""
IO Pathway-Based Gates (GSE91061, AUC = 0.780)

Applies pathway-based IO boost prediction for checkpoint inhibitors.
Validated on GSE91061 (n=51 melanoma samples, nivolumab).

Priority order (mutually exclusive, highest priority wins):
1. Pathway-based LR composite (GSE91061, AUC=0.780) - if expression available + validated
2. Measured TMB ≥20 (1.35x) or TMB ≥10 (1.25x)
3. MSI-H (1.30x)
4. Hypermutator inference (flag only, no boost)
"""
import logging
from typing import Dict, Any, Optional, List, Tuple, Set
import pandas as pd

from .io_pathway_model import (
    compute_io_pathway_scores,
    logistic_regression_composite
)
from .io_pathway_safety import (
    compute_io_pathway_confidence,
    validate_expression_data_quality,
    should_use_pathway_prediction,
    get_ruo_disclaimer
)

logger = logging.getLogger(__name__)

# Hypermutator genes: mutations in these genes can be associated with hypermutation / high TMB.
# MBD4: BER pathway; loss can drive CpG hypermutation in some contexts.
# POLE/POLD1: polymerase proofreading; loss can drive ultrahypermutation.
HYPERMUTATOR_GENES: Set[str] = {"MBD4", "POLE", "POLD1"}


def apply_io_boost(
    tumor_context: Dict[str, Any],
    expression_data: Optional[pd.DataFrame] = None,
    germline_mutations: Optional[List[Dict[str, Any]]] = None,
    cancer_type: Optional[str] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Apply IO boost with multi-signal integration and safety gates.
    
    Priority order (mutually exclusive, highest priority wins):
    1. Pathway-based LR composite (GSE91061, AUC=0.780) - if expression available + validated
    2. Measured TMB ≥20 (1.35x) or TMB ≥10 (1.25x)
    3. MSI-H (1.30x)
    4. Hypermutator inference (flag only, no boost)
    
    SAFETY LAYERS:
    - Cancer type validation (melanoma only - validated)
    - Expression data quality checks
    - Confidence degradation for unvalidated cases
    - Fallback to TMB/MSI if pathway uncertain
    - RUO disclaimers
    
    Args:
        tumor_context: TumorContext dict with TMB, MSI, HRD, mutations, etc.
        expression_data: Optional RNA-seq expression DataFrame (genes as index, samples as columns)
        germline_mutations: Optional list of germline mutations for hypermutator inference
        cancer_type: Cancer type (e.g., "melanoma", "nsclc") - used for validation checks
    
    Returns:
        Tuple of (io_boost_factor, rationale_dict)
        - io_boost_factor: Multiplier for efficacy score (1.0 = no boost)
        - rationale_dict: Contains boost value, gate name, reason, safety metadata, RUO disclaimer
    """
    io_boost = 1.0
    rationale_dict = {
        "gate": None,
        "verdict": "NO_BOOST",
        "boost": 1.0,
        "reason": "No IO boost signals detected",
        "safety_metadata": {},
        "ruo_disclaimer": None
    }
    
    tmb = tumor_context.get("tmb")
    msi_status = tumor_context.get("msi_status")
    
    # ====================================================================
    # PRIORITY 1: PATHWAY-BASED IO PREDICTION (GSE91061, AUC = 0.780)
    # ====================================================================
    # If expression data is available, use pathway-based prediction
    # Validated on GSE91061 (n=51 melanoma, nivolumab)
    # Outperforms PD-L1 alone by +36% (0.572 → 0.780)
    # 
    # SAFETY: Only use if validated cancer type + good expression quality
    # ====================================================================
    if expression_data is not None:
        try:
            # Convert to DataFrame if needed
            if isinstance(expression_data, dict):
                # Assume dict with gene symbols as keys, expression as values
                expr_df = pd.DataFrame([expression_data]).T
                expr_df.columns = ['sample']
            elif isinstance(expression_data, pd.DataFrame):
                expr_df = expression_data
            else:
                logger.warning(f"Unsupported expression data type: {type(expression_data)}")
                expr_df = None
            
            if expr_df is not None:
                # ============================================================
                # SAFETY LAYER 1: Validate Expression Data Quality
                # ============================================================
                expression_quality = validate_expression_data_quality(expr_df)
                
                # ============================================================
                # SAFETY LAYER 2: Check if pathway prediction should be used
                # ============================================================
                # Compute pathway scores first (needed for decision)
                pathway_scores = compute_io_pathway_scores(expr_df)
                pathway_composite_score = logistic_regression_composite(pathway_scores)
                
                # Check if we should use pathway prediction or fallback
                should_use_pathway, fallback_reason = should_use_pathway_prediction(
                    pathway_composite_score,
                    cancer_type=cancer_type,
                    expression_quality=expression_quality,
                    tmb=tmb,
                    msi_status=msi_status
                )
                
                if should_use_pathway:
                    # ============================================================
                    # SAFETY LAYER 3: Confidence-Adjusted Prediction
                    # ============================================================
                    # Compute confidence-adjusted composite (degraded for unvalidated cases)
                    confidence_adjusted_composite, safety_metadata = compute_io_pathway_confidence(
                        pathway_composite_score,
                        cancer_type=cancer_type,
                        expression_quality=expression_quality,
                        pathway_coverage=expression_quality.get("pathway_coverage", {})
                    )
                    
                    # Use confidence-adjusted composite for boost decision
                    # But also report raw composite for transparency
                    composite_for_boost = confidence_adjusted_composite
                    
                    # Map composite score to boost factor (using confidence-adjusted score)
                    # Thresholds based on GSE91061 validation:
                    # - High (≥0.7): 1.40x boost (strong IO response predicted)
                    # - Medium (0.5-0.7): 1.30x boost (moderate IO response)
                    # - Low (0.3-0.5): 1.15x boost (weak IO response)
                    if composite_for_boost >= 0.7:
                        io_boost = 1.40
                        verdict = "BOOSTED"
                    elif composite_for_boost >= 0.5:
                        io_boost = 1.30
                        verdict = "BOOSTED"
                    elif composite_for_boost >= 0.3:
                        io_boost = 1.15
                        verdict = "BOOSTED"
                    else:
                        # Low composite score (<0.3) - no boost
                        io_boost = 1.0
                        verdict = "NO_BOOST"
                    
                    # Build rationale with safety metadata
                    rationale_dict = {
                        "gate": "IO_PATHWAY_BOOST",
                        "verdict": verdict,
                        "boost": io_boost,
                        "pathway_composite_raw": pathway_composite_score,
                        "pathway_composite_adjusted": confidence_adjusted_composite,
                        "safety_metadata": safety_metadata,
                        "ruo_disclaimer": get_ruo_disclaimer(cancer_type),
                        "reason": (
                            f"Pathway-based IO prediction (GSE91061, AUC=0.780): "
                            f"raw_composite={pathway_composite_score:.3f}, "
                            f"confidence_adjusted={confidence_adjusted_composite:.3f} → "
                            f"Checkpoint inhibitor boost {io_boost:.2f}x"
                        )
                    }
                    
                    # Add warnings if any
                    if safety_metadata.get("warnings"):
                        rationale_dict["warnings"] = safety_metadata["warnings"]
                        logger.warning(f"IO pathway prediction warnings: {safety_metadata['warnings']}")
                else:
                    # Fallback to TMB/MSI - pathway prediction not recommended
                    logger.info(f"IO PATHWAY PREDICTION: {fallback_reason}")
                    rationale_dict = {
                        "gate": "IO_PATHWAY_BOOST",
                        "verdict": "FALLBACK",
                        "boost": 1.0,
                        "pathway_composite_raw": pathway_composite_score,
                        "fallback_reason": fallback_reason,
                        "ruo_disclaimer": get_ruo_disclaimer(cancer_type),
                        "reason": (
                            f"Pathway prediction computed but not used: {fallback_reason}. "
                            f"Falling back to TMB/MSI logic."
                        )
                    }
                    # Continue to TMB/MSI logic below
        except Exception as e:
            logger.warning(f"Failed to compute pathway-based IO prediction: {e}")
            # Fall through to TMB/MSI logic
    
    # ====================================================================
    # PRIORITY 2: TMB BOOST (if pathway prediction not used)
    # ====================================================================
    if io_boost == 1.0 and tmb is not None:
        if tmb >= 20:
            io_boost = 1.35
            rationale_dict = {
                "gate": "IO_TMB_BOOST",
                "verdict": "BOOSTED",
                "boost": 1.35,
                "tmb": tmb,
                "reason": f"TMB-high (≥20): {tmb:.1f} mut/Mb → Checkpoint inhibitor boost 1.35x"
            }
        elif tmb >= 10:
            io_boost = 1.25
            rationale_dict = {
                "gate": "IO_TMB_BOOST",
                "verdict": "BOOSTED",
                "boost": 1.25,
                "tmb": tmb,
                "reason": f"TMB-intermediate (≥10): {tmb:.1f} mut/Mb → Checkpoint inhibitor boost 1.25x"
            }
    
    # ====================================================================
    # PRIORITY 3: MSI-H BOOST (if pathway/TMB not used)
    # ====================================================================
    if io_boost == 1.0 and msi_status and str(msi_status).upper() in ["MSI-H", "MSI-HIGH"]:
        io_boost = 1.30
        rationale_dict = {
            "gate": "IO_MSI_BOOST",
            "verdict": "BOOSTED",
            "boost": 1.30,
            "msi_status": msi_status,
            "reason": f"MSI-High ({msi_status}) → Checkpoint inhibitor boost 1.30x"
        }
    
    # ====================================================================
    # PRIORITY 4: HYPERMUTATOR GENE FLAG (if no measured data)
    # ====================================================================
    # If TMB is unknown, we may have a *biological reason* to suspect hypermutation.
    # Policy: **flag** suspected hypermutation and recommend measuring TMB/MSI;
    # do NOT boost IO efficacy as if TMB were measured.
    # ====================================================================
    if io_boost == 1.0 and tmb is None:
        mutated_genes: Set[str] = set()
        
        # Collect genes from tumor_context mutations
        if tumor_context.get("mutations"):
            for m in tumor_context["mutations"]:
                gene = (m.get("gene") or m.get("hugoGeneSymbol") or "").upper()
                if gene:
                    mutated_genes.add(gene)
        
        # Collect genes from germline mutations
        if germline_mutations:
            for m in germline_mutations:
                gene = (m.get("gene") or "").upper()
                if gene:
                    mutated_genes.add(gene)
        
        # Also check germline from tumor_context if nested
        if tumor_context.get("germline"):
            germline_obj = tumor_context["germline"]
            for m in germline_obj.get("mutations", []):
                gene = (m.get("gene") or "").upper()
                if gene:
                    mutated_genes.add(gene)
        
        # Check for hypermutator genes
        hypermutator_hits = mutated_genes.intersection(HYPERMUTATOR_GENES)
        if hypermutator_hits:
            rationale_dict = {
                "gate": "IO_HYPERMUTATOR_FLAG",
                "verdict": "SUSPECTED_HYPERMUTATION",
                "boost": 1.0,  # No boost, just flag
                "hypermutator_genes": list(hypermutator_hits),
                "reason": (
                    f"Hypermutator gene mutation ({', '.join(hypermutator_hits)}) with unknown TMB. "
                    "Suspect hypermutation; recommend measuring TMB/MSI before treating as IO-positive signal."
                ),
                "action": "MEASURE_TMB_MSI"
            }
            logger.info(
                f"HYPERMUTATOR FLAG: Hypermutator genes present with unknown TMB: {hypermutator_hits}"
            )
    
    return io_boost, rationale_dict
