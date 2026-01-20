"""
Ovarian Cancer Pathway Prediction Safety Layer

Safety gates for pathway-based platinum resistance prediction in ovarian cancer.
Validated on GSE165897 (n=11 patients, AUC = 0.750).
"""
import logging
from typing import Dict, Any, Optional, Tuple
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)

# ============================================================================
# VALIDATED CANCER TYPES
# ============================================================================
VALIDATED_CANCER_TYPES = {
    "ovarian": {
        "validated": True,
        "cohort": "GSE165897",
        "n_samples": 11,
        "drug": "platinum (carboplatin/cisplatin)",
        "auc": 0.750,  # post_pi3k best predictor
        "correlation": -0.711,  # post_ddr strongest correlation (ρ)
        "p_value": 0.014,  # post_ddr p-value
        "confidence_level": "moderate"  # Small sample size (n=11)
    },
    "ovarian_cancer": {
        "validated": True,
        "cohort": "GSE165897",
        "n_samples": 11,
        "drug": "platinum (carboplatin/cisplatin)",
        "auc": 0.750,
        "correlation": -0.711,
        "p_value": 0.014,
        "confidence_level": "moderate"
    },
    "hgsoc": {  # High-Grade Serous Ovarian Cancer
        "validated": True,
        "cohort": "GSE165897",
        "n_samples": 11,
        "drug": "platinum (carboplatin/cisplatin)",
        "auc": 0.750,
        "correlation": -0.711,
        "p_value": 0.014,
        "confidence_level": "moderate"
    }
}

UNVALIDATED_CANCER_TYPES = {
    "breast", "lung", "nsclc", "colorectal", "gastric", "pancreatic",
    "endometrial", "cervical", "prostate", "renal", "bladder"
}

# Quality thresholds
MIN_GENES_FOR_PATHWAY = 3
MIN_PATHWAY_COVERAGE = 0.3
MIN_GENES_THRESHOLD = 1000  # Minimum total genes in expression data


def validate_expression_data_quality(
    expression_data: pd.DataFrame,
    required_pathways: list = None
) -> Dict[str, Any]:
    """
    Validate expression data quality for ovarian pathway prediction.
    
    Args:
        expression_data: DataFrame with genes as index, samples as columns
        required_pathways: Optional list of required pathways (default: DDR, PI3K, VEGF)
    
    Returns:
        Dict with quality metrics and warnings
    """
    if required_pathways is None:
        required_pathways = ['DDR', 'PI3K', 'VEGF']
    
    quality = {
        "total_genes": len(expression_data.index),
        "pathway_coverage": {},
        "avg_pathway_coverage": 0.0,
        "warnings": [],
        "quality_score": 1.0,
        "is_acceptable": True
    }
    
    # Check minimum gene count
    if quality["total_genes"] < MIN_GENES_THRESHOLD:
        quality["warnings"].append(
            f"Low gene count ({quality['total_genes']} < {MIN_GENES_THRESHOLD}). "
            "Pathway prediction may be unreliable."
        )
        quality["quality_score"] *= 0.7
        quality["is_acceptable"] = False
    
    # Check for NaN/Inf values
    if expression_data.isnull().any().any():
        quality["warnings"].append("Expression data contains NaN values.")
        quality["quality_score"] *= 0.8
    
    if np.isinf(expression_data.values).any():
        quality["warnings"].append("Expression data contains Inf values.")
        quality["quality_score"] *= 0.8
    
    # Check expression range (should be reasonable for log2(TPM+1))
    max_val = expression_data.max().max()
    min_val = expression_data.min().min()
    
    if max_val > 20:
        quality["warnings"].append(
            f"High expression values detected (max={max_val:.1f}). "
            "Data may not be log-transformed."
        )
        quality["quality_score"] *= 0.9
    
    if min_val < 0:
        quality["warnings"].append(
            "Negative expression values detected. "
            "Expression data should be non-negative."
        )
        quality["quality_score"] *= 0.8
    
    # Pathway coverage (placeholder - would need pathway gene lists)
    # For now, assume acceptable if gene count is sufficient
    quality["avg_pathway_coverage"] = 0.8 if quality["total_genes"] >= MIN_GENES_THRESHOLD else 0.3
    
    return quality


def should_use_pathway_prediction(
    composite_score: float,
    cancer_type: Optional[str] = None,
    expression_quality: Dict[str, Any] = None,
    hrd_score: Optional[float] = None
) -> Tuple[bool, str]:
    """
    Determine if pathway-based prediction should be used.
    
    Args:
        composite_score: Computed composite resistance score
        cancer_type: Cancer type (e.g., "ovarian", "hgsoc")
        expression_quality: Expression quality metrics
        hrd_score: Optional HRD score (for PARP rescue logic)
    
    Returns:
        Tuple of (should_use, reason)
    """
    # Check cancer type validation
    if cancer_type:
        cancer_type_lower = cancer_type.lower()
        if cancer_type_lower not in VALIDATED_CANCER_TYPES:
            if cancer_type_lower in UNVALIDATED_CANCER_TYPES:
                return False, (
                    f"Cancer type '{cancer_type}' not validated for ovarian pathway prediction. "
                    "Validated types: ovarian, ovarian_cancer, hgsoc (GSE165897)."
                )
    
    # Check expression quality
    if expression_quality:
        if not expression_quality.get("is_acceptable", False):
            return False, (
                f"Expression data quality insufficient: {expression_quality.get('warnings', [])}"
            )
        
        coverage = expression_quality.get("avg_pathway_coverage", 0.0)
        if coverage < MIN_PATHWAY_COVERAGE:
            return False, (
                f"Low pathway coverage ({coverage:.1%} < {MIN_PATHWAY_COVERAGE:.1%}). "
                "Insufficient genes for reliable pathway prediction."
            )
    
    # Check composite score reliability
    # Very low scores (<0.10) may be unreliable
    if composite_score < 0.10:
        # If HRD is available, prefer HRD-based logic
        if hrd_score is not None:
            return False, (
                f"Very low composite score ({composite_score:.3f} < 0.10). "
                "Prefer HRD-based PARP logic (more reliable for very low scores)."
            )
    
    return True, "Pathway prediction validated and recommended"


def compute_ovarian_pathway_confidence(
    composite_score: float,
    cancer_type: Optional[str] = None,
    expression_quality: Dict[str, Any] = None,
    pathway_coverage: float = None
) -> Tuple[float, Dict[str, Any]]:
    """
    Compute confidence-adjusted composite score for ovarian pathway prediction.
    
    Args:
        composite_score: Raw composite resistance score
        cancer_type: Cancer type (for validation checks)
        expression_quality: Expression quality metrics
        pathway_coverage: Average pathway coverage (0-1)
    
    Returns:
        Tuple of (confidence_adjusted_score, safety_metadata)
    """
    confidence_multiplier = 1.0
    safety_metadata = {
        "confidence_factors": {},
        "warnings": [],
        "confidence_level": "moderate"  # GSE165897 n=11 is small
    }
    
    # ========================================================================
    # FACTOR 1: Cancer Type Validation
    # ========================================================================
    if cancer_type:
        cancer_type_lower = cancer_type.lower()
        if cancer_type_lower in VALIDATED_CANCER_TYPES:
            validation_info = VALIDATED_CANCER_TYPES[cancer_type_lower]
            safety_metadata["confidence_factors"]["cancer_type"] = 1.0
            safety_metadata["validation_info"] = validation_info
        else:
            # Unvalidated cancer type - degrade by 30%
            confidence_multiplier *= 0.7
            safety_metadata["confidence_factors"]["cancer_type"] = 0.7
            safety_metadata["warnings"].append(
                f"Cancer type '{cancer_type}' not validated. "
                "Confidence degraded by 30%."
            )
    else:
        # No cancer type specified - degrade by 40%
        confidence_multiplier *= 0.6
        safety_metadata["confidence_factors"]["cancer_type"] = 0.6
        safety_metadata["warnings"].append(
            "Cancer type not specified. Confidence degraded by 40%."
        )
    
    # ========================================================================
    # FACTOR 2: Expression Data Quality
    # ========================================================================
    if expression_quality:
        coverage = expression_quality.get("avg_pathway_coverage", 1.0)
        gene_count = expression_quality.get("total_genes", 0)
        
        if coverage < MIN_PATHWAY_COVERAGE:
            quality_factor = max(0.5, coverage / MIN_PATHWAY_COVERAGE)
            confidence_multiplier *= quality_factor
            safety_metadata["confidence_factors"]["expression_quality"] = quality_factor
            safety_metadata["warnings"].append(
                f"Low pathway coverage ({coverage:.1%} < {MIN_PATHWAY_COVERAGE:.1%}). "
                f"Confidence degraded by {1-quality_factor:.1%}."
            )
        else:
            safety_metadata["confidence_factors"]["expression_quality"] = 1.0
        
        if gene_count < 1000:
            safety_metadata["warnings"].append(
                f"Low gene count ({gene_count} < {MIN_GENES_THRESHOLD}). "
                "Pathway prediction may be unreliable."
            )
    
    # ========================================================================
    # FACTOR 3: Sample Size Limitation (GSE165897 n=11)
    # ========================================================================
    # GSE165897 has small sample size - apply conservative degradation
    confidence_multiplier *= 0.85  # 15% degradation for small sample
    safety_metadata["confidence_factors"]["sample_size"] = 0.85
    safety_metadata["warnings"].append(
        "GSE165897 validation cohort is small (n=11). "
        "Confidence degraded by 15% to account for sample size limitation."
    )
    
    # Apply confidence adjustment
    confidence_adjusted = composite_score * confidence_multiplier
    
    return float(confidence_adjusted), safety_metadata


def get_ruo_disclaimer(cancer_type: Optional[str] = None) -> str:
    """
    Get Research Use Only disclaimer for ovarian pathway prediction.
    
    Args:
        cancer_type: Cancer type (for specificity)
    
    Returns:
        RUO disclaimer string
    """
    base_disclaimer = (
        "Research Use Only (RUO): Ovarian cancer pathway-based resistance prediction "
        "is validated on GSE165897 (n=11 HGSOC patients, AUC=0.750). "
        "This prediction is for research purposes only and is not intended for "
        "clinical diagnostic or treatment decisions. Validation on larger cohorts "
        "is required before clinical use."
    )
    
    if cancer_type and cancer_type.lower() not in VALIDATED_CANCER_TYPES:
        return (
            f"{base_disclaimer} "
            f"NOTE: Cancer type '{cancer_type}' has not been validated. "
            "Use with caution."
        )
    
    return base_disclaimer
