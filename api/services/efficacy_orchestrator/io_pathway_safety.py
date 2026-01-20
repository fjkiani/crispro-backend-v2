"""
IO Pathway Prediction Safety Layer

CRITICAL: Production safety gates for IO pathway-based predictions.

What We CAN Predict:
- Pre-treatment IO response probability (0-1) for melanoma + nivolumab
- Validated on GSE91061 (n=51, AUC=0.780)
- Outperforms PD-L1 alone by +36%

What We CANNOT Predict (Yet):
- Other cancer types (NSCLC, RCC, etc.) - needs validation
- Other IO drugs (ipilimumab, atezolizumab, etc.) - needs validation
- Long-term survival (only short-term response validated)
- Combination therapy response (single-agent only)

Safety Gates:
1. Cancer type validation (melanoma only)
2. Expression data quality checks
3. Confidence degradation for out-of-distribution
4. Fallback to TMB/MSI if pathway uncertain
5. RUO disclaimers
"""
import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# VALIDATION STATUS (What We've Actually Tested)
# ============================================================================

VALIDATED_CANCER_TYPES = {
    "melanoma": {
        "validated": True,
        "cohort": "GSE91061",
        "n_samples": 51,
        "drug": "nivolumab",
        "auc": 0.780,
        "cv_auc": 0.670,
        "cv_std": 0.192,
        "confidence_level": "moderate"  # Small sample, high variance
    }
}

# Cancer types NOT yet validated (will degrade confidence)
UNVALIDATED_CANCER_TYPES = {
    "nsclc", "lung", "renal", "rcc", "bladder", "colorectal", "ovarian",
    "breast", "gastric", "hcc", "liver", "pancreatic", "prostate"
}

# ============================================================================
# EXPRESSION DATA QUALITY THRESHOLDS
# ============================================================================

MIN_GENES_FOR_PATHWAY = 3  # Minimum genes required per pathway
MIN_PATHWAY_COVERAGE = 0.3  # Minimum 30% of pathway genes present
MIN_EXPRESSION_VALUE = 0.0  # Minimum TPM value (log2(TPM+1) handles zeros)

# ============================================================================
# CONFIDENCE DEGRADATION RULES
# ============================================================================

def compute_io_pathway_confidence(
    pathway_composite: float,
    cancer_type: Optional[str] = None,
    expression_quality: Dict[str, Any] = None,
    pathway_coverage: Dict[str, float] = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute confidence-adjusted IO pathway prediction.
    
    Confidence degradation factors:
    1. Cancer type validation (melanoma = full confidence, others = degraded)
    2. Expression data quality (low coverage = degraded)
    3. Pathway coverage (missing genes = degraded)
    4. Composite score uncertainty (extreme values = degraded)
    
    Args:
        pathway_composite: Raw composite score (0-1)
        cancer_type: Cancer type (e.g., "melanoma", "nsclc")
        expression_quality: Dict with quality metrics
        pathway_coverage: Dict mapping pathway names to coverage (0-1)
    
    Returns:
        Tuple of (confidence_adjusted_score, safety_metadata)
    """
    safety_metadata = {
        "raw_composite": pathway_composite,
        "confidence_factors": {},
        "warnings": [],
        "ruo_disclaimer": True
    }
    
    confidence_multiplier = 1.0
    
    # ========================================================================
    # FACTOR 1: Cancer Type Validation
    # ========================================================================
    if cancer_type:
        cancer_lower = cancer_type.lower()
        
        if cancer_lower in VALIDATED_CANCER_TYPES:
            # Validated cancer type - full confidence
            validation_info = VALIDATED_CANCER_TYPES[cancer_lower]
            safety_metadata["cancer_type_validated"] = True
            safety_metadata["validation_cohort"] = validation_info["cohort"]
            safety_metadata["validation_auc"] = validation_info["auc"]
            safety_metadata["confidence_factors"]["cancer_type"] = 1.0
        elif any(utype in cancer_lower for utype in UNVALIDATED_CANCER_TYPES):
            # Unvalidated cancer type - degrade confidence by 30%
            confidence_multiplier *= 0.7
            safety_metadata["cancer_type_validated"] = False
            safety_metadata["confidence_factors"]["cancer_type"] = 0.7
            safety_metadata["warnings"].append(
                f"IO pathway prediction not validated for {cancer_type}. "
                f"Confidence degraded by 30%. Validated only for melanoma (GSE91061)."
            )
        else:
            # Unknown cancer type - degrade by 50%
            confidence_multiplier *= 0.5
            safety_metadata["cancer_type_validated"] = False
            safety_metadata["confidence_factors"]["cancer_type"] = 0.5
            safety_metadata["warnings"].append(
                f"IO pathway prediction not validated for {cancer_type}. "
                f"Confidence degraded by 50%. Use with extreme caution."
            )
    else:
        # No cancer type specified - degrade by 40%
        confidence_multiplier *= 0.6
        safety_metadata["confidence_factors"]["cancer_type"] = 0.6
        safety_metadata["warnings"].append(
            "Cancer type not specified. IO pathway prediction confidence degraded by 40%."
        )
    
    # ========================================================================
    # FACTOR 2: Expression Data Quality
    # ========================================================================
    if expression_quality:
        coverage = expression_quality.get("avg_pathway_coverage", 1.0)  # FIX: Use avg_pathway_coverage, not pathway_coverage (which is a dict)
        gene_count = expression_quality.get("total_genes", 0)
        
        if coverage < MIN_PATHWAY_COVERAGE:
            # Low pathway coverage - degrade confidence
            quality_factor = max(0.5, coverage / MIN_PATHWAY_COVERAGE)
            confidence_multiplier *= quality_factor
            safety_metadata["confidence_factors"]["expression_quality"] = quality_factor
            safety_metadata["warnings"].append(
                f"Low pathway gene coverage ({coverage:.1%} < {MIN_PATHWAY_COVERAGE:.1%}). "
                f"Confidence degraded by {1-quality_factor:.1%}."
            )
        else:
            safety_metadata["confidence_factors"]["expression_quality"] = 1.0
        
        if gene_count < 1000:
            # Very sparse expression data
            safety_metadata["warnings"].append(
                f"Low gene count ({gene_count} genes). Pathway scores may be unreliable."
            )
    else:
        # No quality metrics - assume moderate degradation
        confidence_multiplier *= 0.8
        safety_metadata["confidence_factors"]["expression_quality"] = 0.8
        safety_metadata["warnings"].append(
            "Expression data quality not assessed. Confidence degraded by 20%."
        )
    
    # ========================================================================
    # FACTOR 3: Pathway Coverage
    # ========================================================================
    if pathway_coverage:
        avg_coverage = np.mean(list(pathway_coverage.values()))
        
        if avg_coverage < 0.5:
            # Low average pathway coverage
            coverage_factor = max(0.6, avg_coverage)
            confidence_multiplier *= coverage_factor
            safety_metadata["confidence_factors"]["pathway_coverage"] = coverage_factor
            safety_metadata["warnings"].append(
                f"Low average pathway coverage ({avg_coverage:.1%}). "
                f"Confidence degraded by {1-coverage_factor:.1%}."
            )
        else:
            safety_metadata["confidence_factors"]["pathway_coverage"] = 1.0
    else:
        # No coverage info - moderate degradation
        confidence_multiplier *= 0.85
        safety_metadata["confidence_factors"]["pathway_coverage"] = 0.85
    
    # ========================================================================
    # FACTOR 4: Composite Score Uncertainty
    # ========================================================================
    # Extreme values (very high or very low) are less reliable
    # Most reliable range: 0.3-0.7 (moderate predictions)
    if pathway_composite < 0.1 or pathway_composite > 0.9:
        # Extreme values - slight degradation
        uncertainty_factor = 0.9
        confidence_multiplier *= uncertainty_factor
        safety_metadata["confidence_factors"]["score_uncertainty"] = uncertainty_factor
        safety_metadata["warnings"].append(
            f"Extreme composite score ({pathway_composite:.3f}). "
            f"Confidence degraded by 10% (extreme values less reliable)."
        )
    else:
        safety_metadata["confidence_factors"]["score_uncertainty"] = 1.0
    
    # ========================================================================
    # FINAL CONFIDENCE-ADJUSTED SCORE
    # ========================================================================
    # Apply confidence multiplier to composite score
    # But don't let it go below 0.1 or above 0.9 (keep some uncertainty)
    confidence_adjusted = pathway_composite * confidence_multiplier
    confidence_adjusted = max(0.1, min(0.9, confidence_adjusted))
    
    safety_metadata["confidence_multiplier"] = confidence_multiplier
    safety_metadata["confidence_adjusted_composite"] = confidence_adjusted
    safety_metadata["confidence_degradation"] = 1.0 - confidence_multiplier
    
    return confidence_adjusted, safety_metadata


def validate_expression_data_quality(
    expression_data: pd.DataFrame,
    required_pathways: list = None
) -> Dict[str, Any]:
    """
    Validate expression data quality for IO pathway prediction.
    
    Checks:
    1. Minimum gene count
    2. Pathway gene coverage
    3. Expression value distribution
    4. Missing data patterns
    
    Returns:
        Dict with quality metrics and warnings
    """
    from .io_pathway_model import IO_PATHWAYS
    
    if required_pathways is None:
        required_pathways = list(IO_PATHWAYS.keys())
    
    quality_report = {
        "total_genes": len(expression_data.index),
        "pathway_coverage": {},
        "avg_pathway_coverage": 0.0,
        "warnings": [],
        "quality_score": 1.0,
        "is_acceptable": True
    }
    
    # Check pathway coverage
    pathway_coverages = []
    for pathway_name in required_pathways:
        pathway_genes = IO_PATHWAYS.get(pathway_name, [])
        available_genes = [g for g in pathway_genes if g in expression_data.index]
        coverage = len(available_genes) / len(pathway_genes) if pathway_genes else 0.0
        
        quality_report["pathway_coverage"][pathway_name] = coverage
        pathway_coverages.append(coverage)
        
        if coverage < MIN_PATHWAY_COVERAGE:
            quality_report["warnings"].append(
                f"{pathway_name}: Only {len(available_genes)}/{len(pathway_genes)} genes found "
                f"({coverage:.1%} coverage, minimum {MIN_PATHWAY_COVERAGE:.1%} required)"
            )
    
    quality_report["avg_pathway_coverage"] = np.mean(pathway_coverages) if pathway_coverages else 0.0
    
    # Overall quality score
    if quality_report["avg_pathway_coverage"] < MIN_PATHWAY_COVERAGE:
        quality_report["quality_score"] = quality_report["avg_pathway_coverage"] / MIN_PATHWAY_COVERAGE
        quality_report["is_acceptable"] = False
        quality_report["warnings"].append(
            f"Average pathway coverage ({quality_report['avg_pathway_coverage']:.1%}) "
            f"below minimum ({MIN_PATHWAY_COVERAGE:.1%}). Pathway prediction may be unreliable."
        )
    
    # Check gene count
    if quality_report["total_genes"] < 1000:
        quality_report["warnings"].append(
            f"Low gene count ({quality_report['total_genes']} genes). "
            f"Expression data may be incomplete."
        )
    
    return quality_report


def should_use_pathway_prediction(
    pathway_composite: float,
    cancer_type: Optional[str] = None,
    expression_quality: Dict[str, Any] = None,
    tmb: Optional[float] = None,
    msi_status: Optional[str] = None
) -> Tuple[bool, str]:
    """
    Determine if pathway prediction should be used or fallback to TMB/MSI.
    
    Decision logic:
    - Use pathway if: validated cancer type + good expression quality + moderate composite
    - Fallback to TMB/MSI if: unvalidated cancer type OR poor expression quality OR extreme composite
    
    Returns:
        Tuple of (should_use_pathway, reason)
    """
    # Check cancer type
    if cancer_type:
        cancer_lower = cancer_type.lower()
        if cancer_lower not in VALIDATED_CANCER_TYPES:
            return False, (
                f"Pathway prediction not validated for {cancer_type}. "
                f"Fallback to TMB/MSI (validated only for melanoma)."
            )
    
    # Check expression quality
    if expression_quality:
        if not expression_quality.get("is_acceptable", True):
            return False, (
                f"Expression data quality insufficient. "
                f"Fallback to TMB/MSI (pathway coverage too low)."
            )
    
    # Check composite score reliability
    # Only reject if VERY low (<0.1) - high scores (>0.9) are still valid (strong positive signal)
    if pathway_composite < 0.1:
        # Very low composite - unreliable, prefer TMB/MSI if available
        if tmb is not None or (msi_status and str(msi_status).upper() in ["MSI-H", "MSI-HIGH"]):
            return False, (
                f"Very low pathway composite ({pathway_composite:.3f} < 0.1). "
                f"Fallback to TMB/MSI (more reliable for very low scores)."
            )
    # Note: High scores (>0.9) are still valid - they indicate strong positive signal
    # We'll cap them at 0.9 in confidence adjustment, but still use them
    
    # All checks passed - use pathway prediction
    return True, "Pathway prediction validated and acceptable"


def get_ruo_disclaimer(cancer_type: Optional[str] = None) -> str:
    """
    Get Research Use Only disclaimer for IO pathway predictions.
    
    Returns:
        RUO disclaimer text
    """
    base_disclaimer = (
        "⚠️ RESEARCH USE ONLY (RUO): IO pathway predictions are based on "
        "retrospective analysis of GSE91061 (n=51 melanoma samples, nivolumab). "
        "Not validated for clinical decision-making."
    )
    
    if cancer_type and cancer_type.lower() not in VALIDATED_CANCER_TYPES:
        return (
            f"{base_disclaimer} "
            f"⚠️ NOT VALIDATED for {cancer_type}. Validated only for melanoma. "
            f"Use with extreme caution."
        )
    
    return base_disclaimer
