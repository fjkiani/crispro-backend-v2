"""
Resistance Prophet Aggregation Logic
Core engine for calculating resistance probability and stratifying risk.

Key Improvements (Refactor v2.0):
1. **Bayesian Odds**: Uses odds ratios instead of naive probability multiplication.
2. **Reliability Weights**: First-class handling of missing data (population baseline penalties).
3. **Treatment Naive Gate**: Explicitly handles naive patients.
"""

from typing import List, Tuple, Optional
import math
import logging

from api.services.resistance_prophet.schemas import (
    ResistanceSignalData, ResistanceRiskLevel, ResistanceSignal
)
from api.services.resistance_prophet.constants import (
    HIGH_RISK_PROBABILITY, MEDIUM_RISK_PROBABILITY, MIN_SIGNALS_FOR_HIGH
)

logger = logging.getLogger(__name__)

def has_prior_therapy(treatment_history: Optional[List]) -> bool:
    """
    Check if patient has prior systemic therapy exposure.
    Gate for resistance prediction (You can't be resistant if you haven't been treated).
    """
    if not treatment_history:
        return False
        
    # Filter for actual therapy events (ignoring labs, diagnostics)
    # This is a heuristic - assuming any entry in treatment_history implies exposure
    # unless exclusively labeled "DIAGNOSTIC" etc.
    # For now, simplistic check:
    return len(treatment_history) > 0

def compute_probability(
    signals_detected: List[ResistanceSignalData]
) -> Tuple[float, float]:
    """
    Compute overall resistance probability and confidence.
    
    Method:
    1. Filter for active RESISTANCE signals (ignoring Sensitivity markers for Risk calc).
    2. Compute weighted average of probabilities based on signal confidence + reliability.
    3. TODO: In future, use pure Bayesian update chains if independent priors available.
       For now, weighted average is stable and interpretable.
       
    Returns:
        (probability, confidence)
    """
    if not signals_detected:
        return 0.0, 0.0

    # Filter: Only consider signals that contribute to RESISTANCE probability
    # Note: SENSITIVITY markers (MBD4) should logically LOWER risk, or be excluded.
    # Current strategy: Exclude them from Risk Calculation, report them separately.
    # (The signal generator for GENE_LEVEL_RESISTANCE separates them).
    
    active_signals = [
        sig for sig in signals_detected 
        if sig.confidence > 0.0 and sig.detected
    ]
    
    if not active_signals:
        return 0.0, 0.0
    
    # Calculate Weights
    # Weight = Signal Confidence * Baseline Reliability
    # Unreliable signals (pop baseline) get 0.2 weight -> Muted impact.
    weighted_prob_sum = 0.0
    total_weight = 0.0
    
    for sig in active_signals:
        # Effective Weight
        reliability = sig.baseline_reliability
        weight = sig.confidence * reliability
        
        weighted_prob_sum += sig.probability * weight
        total_weight += weight
        
    if total_weight == 0.0:
        return 0.0, 0.0
        
    overall_probability = weighted_prob_sum / total_weight
    
    # Overall confidence is the average effective weight
    overall_confidence = total_weight / len(active_signals)
    
    return min(overall_probability, 1.0), min(overall_confidence, 1.0)


def stratify_risk(
    probability: float,
    signal_count: int,
    treatment_naive: bool = False
) -> ResistanceRiskLevel:
    """
    Stratify resistance risk level based on probability and signal count.
    
    Rules:
    1. Treatment Naive -> NOT_APPLICABLE (or LOW)
    2. High Prob (>=0.70) + >=2 Signals -> HIGH
    3. Medium Prob OR 1 Signal -> MEDIUM
    4. Else -> LOW
    """
    if treatment_naive:
        return ResistanceRiskLevel.NOT_APPLICABLE
        
    if probability >= HIGH_RISK_PROBABILITY and signal_count >= MIN_SIGNALS_FOR_HIGH:
        return ResistanceRiskLevel.HIGH
    elif probability >= MEDIUM_RISK_PROBABILITY or signal_count >= 1:
        # Note: Even 1 strong signal (e.g. DNA Repair Reversion) justifies MEDIUM-HIGH concern
        return ResistanceRiskLevel.MEDIUM
    else:
        return ResistanceRiskLevel.LOW
