"""
Sporadic Cancer Scoring Gates (Day 2 - Module M3)

Applies germline gating, PARP penalty, immunotherapy boosts, and confidence capping
based on tumor context and germline status.

Mission: Handle 85-90% of cancer patients with sporadic (germline-negative) cancers
"""
from typing import Dict, Any, Optional, List, Tuple
import logging

logger = logging.getLogger(__name__)


def apply_sporadic_gates(
    drug_name: str,
    drug_class: str,
    moa: str,
    efficacy_score: float,
    confidence: float,
    germline_status: str,
    tumor_context: Optional[Dict[str, Any]] = None
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
        tumor_context: TumorContext dict with TMB, MSI, HRD, etc.
    
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
    # GATE 1: PARP INHIBITOR PENALTY (GERMLINE GATING)
    # ============================================================================
    # Critical for Ayesha: Germline BRCA- patients need HRD rescue for PARP!
    # 
    # Logic:
    # - Germline positive → Full PARP effect (1.0x)
    # - Germline negative + HRD ≥42 → Rescue PARP! (1.0x) ⚔️
    # - Germline negative + HRD <42 → Reduced effect (0.6x)
    # - Unknown germline + unknown HRD → Conservative penalty (0.8x)
    # ============================================================================
    
    if "parp" in drug_class.lower() or "parp" in moa.lower():
        parp_penalty = 1.0  # Default: no penalty
        
        if germline_status == "positive":
            # Germline BRCA1/2 positive → full PARP effect
            parp_penalty = 1.0
            rationale.append({
                "gate": "PARP_GERMLINE",
                "verdict": "FULL_EFFECT",
                "penalty": 1.0,
                "reason": "Germline BRCA1/2 positive → PARP inhibitor appropriate"
            })
        
        elif germline_status == "negative":
            # Germline negative → check tumor HRD
            if tumor_context and tumor_context.get("hrd_score") is not None:
                hrd_score = tumor_context["hrd_score"]
                
                if hrd_score >= 42:
                    # HRD-high rescue! ⚔️
                    parp_penalty = 1.0
                    rationale.append({
                        "gate": "PARP_HRD_RESCUE",
                        "verdict": "RESCUED",
                        "penalty": 1.0,
                        "hrd_score": hrd_score,
                        "reason": f"Germline negative BUT HRD-high (≥42): score={hrd_score:.1f} → PARP rescued! ⚔️"
                    })
                else:
                    # HRD present but <42
                    parp_penalty = 0.6
                    rationale.append({
                        "gate": "PARP_HRD_LOW",
                        "verdict": "REDUCED",
                        "penalty": 0.6,
                        "hrd_score": hrd_score,
                        "reason": f"Germline negative, HRD<42 (score={hrd_score:.1f}) → PARP reduced to 0.6x"
                    })
            else:
                # Unknown HRD, germline negative
                parp_penalty = 0.8
                rationale.append({
                    "gate": "PARP_UNKNOWN_HRD",
                    "verdict": "CONSERVATIVE",
                    "penalty": 0.8,
                    "reason": "Germline negative, HRD unknown → PARP conservative penalty 0.8x"
                })
        
        elif germline_status == "unknown":
            # Unknown germline, unknown HRD
            parp_penalty = 0.8
            rationale.append({
                "gate": "PARP_UNKNOWN_GERMLINE",
                "verdict": "CONSERVATIVE",
                "penalty": 0.8,
                "reason": "Germline status unknown → PARP conservative penalty 0.8x"
            })
        
        # Apply penalty
        efficacy_score *= parp_penalty
    
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
        # IO boost logic: Use HIGHEST boost (if-elif chain, not multiplicative)
        # Priority: MSI-H (1.30x) > TMB ≥20 (1.35x) > TMB ≥10 (1.25x)
        # Per Zo's A4 answer: mutually exclusive, highest priority wins
        io_boost_factor = 1.0
        
        tmb = tumor_context.get("tmb")
        msi_status = tumor_context.get("msi_status")
        
        # IO boost priority: TMB ≥20 (1.35x) > MSI-H (1.30x) > TMB ≥10 (1.25x)
        # Check TMB ≥20 first (highest boost, takes precedence)
        if tmb is not None and tmb >= 20:
            io_boost_factor = 1.35
            rationale.append({
                "gate": "IO_TMB_BOOST",
                "verdict": "BOOSTED",
                "boost": 1.35,
                "tmb": tmb,
                "reason": f"TMB-high (≥20): {tmb:.1f} mut/Mb → Checkpoint inhibitor boost 1.35x"
            })
        # Check MSI-H (second priority)
        elif msi_status:
            # Accept both "MSI-H" and "MSI-High" formats (case-insensitive)
            msi_upper = str(msi_status).upper()
            if msi_upper in ["MSI-H", "MSI-HIGH"]:
                io_boost_factor = 1.30
                rationale.append({
                    "gate": "IO_MSI_BOOST",
                    "verdict": "BOOSTED",
                    "boost": 1.30,
                    "msi_status": msi_status,
                    "reason": f"MSI-High ({msi_status}) → Checkpoint inhibitor boost 1.30x"
                })
        # Check TMB ≥10 (lowest priority)
        elif tmb is not None and tmb >= 10:
            io_boost_factor = 1.25
            rationale.append({
                "gate": "IO_TMB_BOOST",
                "verdict": "BOOSTED",
                "boost": 1.25,
                "tmb": tmb,
                "reason": f"TMB-intermediate (≥10): {tmb:.1f} mut/Mb → Checkpoint inhibitor boost 1.25x"
            })
        
        # Apply boost (single factor, not multiplicative)
        efficacy_score *= io_boost_factor
        
        if io_boost_factor > 1.0:
            logger.info(f"✅ IO BOOST APPLIED: {drug_name} boosted {io_boost_factor:.2f}x")
    
    # ============================================================================
    # GATE 3: CONFIDENCE CAPPING BY COMPLETENESS LEVEL
    # ============================================================================
    # Logic:
    # - Level 0 (completeness <0.3): Cap confidence at 0.4 (low quality data)
    # - Level 1 (0.3 ≤ completeness <0.7): Cap confidence at 0.6 (moderate quality)
    # - Level 2 (completeness ≥0.7): No cap (high quality data)
    # ============================================================================
    
    if level == "L0":
        # Cap at 0.4 for minimal data
        if confidence > 0.4:
            confidence = 0.4
            rationale.append({
                "gate": "CONFIDENCE_CAP_L0",
                "verdict": "CAPPED",
                "cap": 0.4,
                "level": "L0",
                "completeness": completeness_score,
                "reason": f"Level 0 data (completeness={completeness_score:.2f}) → confidence capped at 0.4"
            })
    
    elif level == "L1":
        # Cap at 0.6 for partial data
        if confidence > 0.6:
            confidence = 0.6
            rationale.append({
                "gate": "CONFIDENCE_CAP_L1",
                "verdict": "CAPPED",
                "cap": 0.6,
                "level": "L1",
                "completeness": completeness_score,
                "reason": f"Level 1 data (completeness={completeness_score:.2f}) → confidence capped at 0.6"
            })
    
    # Level 2: No cap (full report, high quality)
    
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

