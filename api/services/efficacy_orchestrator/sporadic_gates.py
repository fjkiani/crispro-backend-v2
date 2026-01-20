"""
Sporadic Cancer Scoring Gates (Day 2 - Module M3)

Thin orchestrator that applies modular gates for different drug classes and cancer types.

Mission: Handle 85-90% of cancer patients with sporadic (germline-negative) cancers

Architecture:
- Modular gate functions for each drug class/cancer type
- Easy to add new cancer types by creating new gate modules
- Main function orchestrates all gates in priority order

Current Modules:
- parp_gates.py: PARP penalty/rescue (germline + HRD)
- io_pathway_gates.py: IO boost (pathway-based + TMB/MSI)
- ovarian_pathway_gates.py: Ovarian pathway-based PARP/platinum resistance
- confidence_capping.py: Confidence capping by completeness level
"""
from typing import Dict, Any, Optional, List, Tuple, Set
import logging
import numpy as np
import pandas as pd

# Import modular gate functions
from .parp_gates import apply_parp_gates
from .confidence_capping import apply_confidence_capping
from .ovarian_pathway_gates import apply_ovarian_pathway_gates
from .io_pathway_gates import apply_io_boost

logger = logging.getLogger(__name__)

# MMR genes: mutations → MSI-H phenotype
MMR_GENES: Set[str] = {"MLH1", "MSH2", "MSH6", "PMS2", "EPCAM"}

def apply_sporadic_gates(
    drug_name: str,
    drug_class: str,
    moa: str,
    efficacy_score: float,
    confidence: float,
    germline_status: str,
    tumor_context: Optional[Dict[str, Any]] = None,
    germline_mutations: Optional[List[Dict[str, Any]]] = None,
    cancer_type: Optional[str] = None  # NEW: For IO pathway validation checks
) -> Tuple[float, float, List[str]]:
    """
    Apply sporadic cancer scoring gates to adjust efficacy and confidence.
    
    Args:
        drug_name: Name of the drug
        drug_class: Drug class (e.g., "PARP inhibitor", "checkpoint_inhibitor")
        moa: Mechanism of action
        efficacy_score: Base efficacy score (0-1)
        confidence: Base confidence (0-1)
        germline_status: "positive", "negative", "unknown"
        tumor_context: TumorContext dict with TMB, MSI, HRD, mutations, etc.
        germline_mutations: Optional list of germline mutations for hypermutator inference
    
    Returns:
        Tuple of (adjusted_efficacy, adjusted_confidence, rationale_list)
    """
    rationale = []
    original_efficacy = efficacy_score
    original_confidence = confidence
    
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
    
    # ============================================================================
    # GATE 1: PARP INHIBITOR GATES (Modular)
    # ============================================================================
    # Uses modular parp_gates.py for clean separation of concerns
    # ============================================================================
    parp_penalty, parp_rationale = apply_parp_gates(
        drug_class=drug_class,
        moa=moa,
        germline_status=germline_status,
        tumor_context=tumor_context,
        expression_data=tumor_context.get("expression") if tumor_context else None,
        cancer_type=cancer_type
    )
    
    if parp_rationale["gate"] is not None:
        rationale.append(parp_rationale)
        efficacy_score *= parp_penalty
    
    # ============================================================================
    # GATE 1B: OVARIAN PATHWAY-BASED PARP/PLATINUM GATES (Modular)
    # ============================================================================
    # If expression data available, use pathway-based resistance prediction
    # This can further adjust PARP/platinum efficacy beyond HRD-based logic
    # ============================================================================
    if parp_penalty < 1.0 or "platinum" in drug_class.lower() or "platinum" in moa.lower():
        # Only apply if PARP penalty was applied OR if this is a platinum drug
        expression_data = tumor_context.get("expression") if tumor_context else None
        if expression_data is None:
            expression_data = tumor_context.get("rna_seq") if tumor_context else None
        
        # Convert expression dict to DataFrame if needed
        expr_df = None
        if expression_data is not None:
            if isinstance(expression_data, dict):
                expr_df = pd.DataFrame([expression_data]).T
                expr_df.columns = ['sample']
            elif isinstance(expression_data, pd.DataFrame):
                expr_df = expression_data
        
        ovarian_multiplier, ovarian_rationale = apply_ovarian_pathway_gates(
            drug_class=drug_class,
            moa=moa,
            tumor_context=tumor_context,
            expression_data=expr_df,
            cancer_type=cancer_type
        )
        
        if ovarian_rationale["gate"] is not None and ovarian_rationale["verdict"] != "NOT_OVARIAN_DRUG":
            rationale.append(ovarian_rationale)
            # Apply multiplier (can further reduce efficacy if pathway predicts resistance)
            efficacy_score *= ovarian_multiplier
    
    # ============================================================================
    # GATE 2: IMMUNOTHERAPY BOOST (TMB-HIGH / MSI-HIGH)
    # ============================================================================
    # Logic (if-elif chain, mutually exclusive, highest priority wins):
    # - TMB ≥20 → 1.35x boost (highest priority, takes precedence)
    # - MSI-High → 1.30x boost (second priority)
    # - TMB ≥10 but <20 → 1.25x boost (lowest priority)
    # Per Zo's A4 answer: mutually exclusive, not multiplicative
    # ============================================================================
    
    is_checkpoint = (
        "checkpoint" in drug_class.lower() or
        "pd-1" in moa.lower() or
        "pd-l1" in moa.lower() or
        "ctla-4" in moa.lower() or
        "anti-pd1" in drug_name.lower() or
        "anti-pdl1" in drug_name.lower()
    )
    
    if is_checkpoint and tumor_context:
        # ====================================================================
        # GATE 2: IMMUNOTHERAPY BOOST (Multi-Signal Integration)
        # ====================================================================
        # Use modular apply_io_boost() function for clean separation of concerns
        # Priority: Pathway-based LR composite > TMB ≥20 > MSI-H > TMB ≥10 > Hypermutator flag
        # ====================================================================
        expression_data = tumor_context.get("expression")
        if expression_data is None:
            expression_data = tumor_context.get("rna_seq")
        
        # Convert expression dict to DataFrame if needed
        expr_df = None
        if expression_data is not None:
            if isinstance(expression_data, dict):
                expr_df = pd.DataFrame([expression_data]).T
                expr_df.columns = ['sample']
            elif isinstance(expression_data, pd.DataFrame):
                expr_df = expression_data
        
        # Apply IO boost using modular function
        io_boost_factor, io_rationale = apply_io_boost(
            tumor_context=tumor_context,
            expression_data=expr_df,
            germline_mutations=germline_mutations,
            cancer_type=cancer_type  # Pass cancer type for validation checks
        )
        
        # Add rationale to main rationale list
        rationale.append(io_rationale)
        
        # Apply boost (single factor, not multiplicative)
        efficacy_score *= io_boost_factor
        
        if io_boost_factor > 1.0:
            logger.info(f"IO BOOST APPLIED: {drug_name} boosted {io_boost_factor:.2f}x")
    
    # ============================================================================
    # GATE 3: CONFIDENCE CAPPING BY COMPLETENESS LEVEL (Modular)
    # ============================================================================
    # Uses modular confidence_capping.py for clean separation of concerns
    # ============================================================================
    confidence, confidence_rationale = apply_confidence_capping(
        confidence=confidence,
        tumor_context=tumor_context
    )
    
    if confidence_rationale["gate"] is not None:
        rationale.append(confidence_rationale)
    
    # ============================================================================
    # FINAL CLAMPING (ENSURE VALID BOUNDS)
    # ============================================================================
    # Ensure efficacy and confidence remain within valid bounds [0, 1]
    efficacy_score = max(0.0, min(efficacy_score, 1.0))
    confidence = max(0.0, min(confidence, 1.0))
    
    # ============================================================================
    # SUMMARY RATIONALE
    # ============================================================================
    
    efficacy_changed = abs(efficacy_score - original_efficacy) > 0.001
    confidence_changed = abs(confidence - original_confidence) > 0.001
    
    if efficacy_changed or confidence_changed:
        summary = {
            "gate": "SPORADIC_SUMMARY",
            "germline_status": germline_status,
            "level": level,
            "completeness": completeness_score,
            "original_efficacy": original_efficacy,
            "final_efficacy": efficacy_score,
            "efficacy_delta": efficacy_score - original_efficacy,
            "original_confidence": original_confidence,
            "final_confidence": confidence,
            "confidence_delta": confidence - original_confidence,
            "gates_applied": [r["gate"] for r in rationale]
        }
        rationale.append(summary)
        
        logger.info(
            f"🎯 SPORADIC GATES APPLIED: {drug_name} | "
            f"Efficacy: {original_efficacy:.3f} → {efficacy_score:.3f} | "
            f"Confidence: {original_confidence:.3f} → {confidence:.3f} | "
            f"Gates: {', '.join(summary['gates_applied'])}"
        )
    
    return efficacy_score, confidence, rationale

