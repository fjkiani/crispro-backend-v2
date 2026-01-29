"""
Resistance Prophet Engine (Deterministic Logic Mapper)
Phase 7: Centralized, pure logic for transforming Signals + Context -> Prediction.

invariants:
1. Driver Alerts are orthogonal to Clinical Risk (can exist even if Risk is Low).
2. Safety Caps only modulate Clinical Risk/Confidence, not Driver Alerts.
3. Deterministic output from structured inputs.
"""

from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime
import logging

from api.services.resistance_prophet.schemas import (
    ResistancePrediction, ResistanceRiskLevel, UrgencyLevel, 
    ResistanceSignal, ResistanceSignalData, DriverAlert
)
from api.services.resistance_prophet.constants import (
    HIGH_RISK_PROBABILITY, MIN_SIGNALS_FOR_HIGH
)
from api.services.resistance_prophet.aggregation import (
    compute_probability, stratify_risk
)
from api.services.resistance_prophet.actions import determine_actions, build_rationale

logger = logging.getLogger(__name__)


def _extract_driver_alerts(signals: List[ResistanceSignalData]) -> Tuple[List[DriverAlert], Dict]:
    """Extract Genomic Driver Alerts from signals (Orthogonal to Risk)."""
    driver_alerts = []
    alert_context = {}
    
    for sig in signals:
        if sig.signal_type == ResistanceSignal.GENE_LEVEL_RESISTANCE and sig.detected:
            # Extract from provenance
            res_genes = sig.provenance.get("resistance_genes", [])
            for g in res_genes:
                driver_alerts.append(
                    DriverAlert(
                        gene=g.get("gene", "Unknown"),
                        variant=g.get("variant", "Positive"),
                        mechanism=g.get("mechanism", "Genomic Driver"),
                        clinical_implication=g.get("rationale", "Resistance Risk"),
                        evidence_tier="Tier 1"
                    )
                )
            
            if "sensitivity_genes" in sig.provenance:
                alert_context["sensitivity_markers"] = sig.provenance["sensitivity_genes"]
                
    return driver_alerts, alert_context


def _apply_safety_caps(
    prediction: ResistancePrediction, 
    has_ca125_data: bool
) -> ResistancePrediction:
    """
    Apply Legacy Safety Rules (Clinical Caps).
    Invariant: Does NOT alter driver_alerts.
    
    Rules:
    If CA-125 is unavailable and signal count >= 2:
    1. Cap Risk Level to MEDIUM (if HIGH)
    2. Cap Confidence to 0.60
    3. Set confidence_cap = "MEDIUM"
    """
    # Legacy Logic Condition:
    if prediction.signal_count >= 2 and prediction.probability >= HIGH_RISK_PROBABILITY and not has_ca125_data:
        # Rule 1: Cap Risk
        if prediction.risk_level == ResistanceRiskLevel.HIGH:
            prediction.risk_level = ResistanceRiskLevel.MEDIUM
            prediction.warnings.append("Risk capped to MEDIUM due to missing CA-125 data.")
        
        # Rule 2: Cap Confidence
        if prediction.confidence > 0.60:
            prediction.confidence = 0.60
            prediction.confidence_cap = "MEDIUM"
            
    return prediction


def calculate_resistance_prediction(
    signals: List[ResistanceSignalData],
    treatment_history: List,
    baseline_source: str,
    baseline_penalty: bool,
    full_ca125_history_available: bool = False,
    playbook_next_lines: List[Dict] = None
) -> ResistancePrediction:
    """
    Pure Function: Maps Signals + Context -> Final Prediction.
    """
    detected_signals = [s for s in signals if s.detected]
    signal_count = len(detected_signals)
    has_prior_tx = bool(treatment_history and len(treatment_history) > 0)
    
    # 1. Aggregation
    # Strategy: 
    # - Probability: Include ALL signals (Genomic Drivers contribute to risk score).
    # - Signal Count: Exclude Genomic Drivers from "Corroboration Count".
    
    risk_signals = detected_signals
    risk_signal_count = len([s for s in risk_signals if s.signal_type != ResistanceSignal.GENE_LEVEL_RESISTANCE])
    
    # Calculate Components for Provenance (Transparency)
    clinical_signals = [s for s in detected_signals if s.signal_type != ResistanceSignal.GENE_LEVEL_RESISTANCE]
    driver_signals_for_calc = [s for s in detected_signals if s.signal_type == ResistanceSignal.GENE_LEVEL_RESISTANCE]
    
    prob_clinical, _ = compute_probability(clinical_signals)
    prob_driver, _ = compute_probability(driver_signals_for_calc)
    
    # Blended Probability drives Risk
    prob, conf = compute_probability(risk_signals)
    risk_level = stratify_risk(prob, risk_signal_count, treatment_naive=not has_prior_tx)
    
    # 2. Actions & Rationale
    urgency, actions = determine_actions(risk_level, risk_signal_count, signals)
    rationale_list = build_rationale(signals, prob, risk_level, baseline_source)
    
    # 3. Extract Driver Alerts (Invariant 1: Computed before caps, stored separately)
    driver_alerts, alert_context = _extract_driver_alerts(detected_signals)
    
    # 4. Construct Preliminary Prediction
    # Populate Provenance
    provenance_data = {
        "model_version": "resistance_prophet_v2.0_engine",
        "timestamp": datetime.utcnow().isoformat(),
        "engine": "deterministic",
        "probability_components": {
            "clinical": round(prob_clinical, 2),
            "driver": round(prob_driver, 2),
            "blended": round(prob, 2)
        },
        "risk_drivers": {
            "clinical_signal_count": risk_signal_count,
            "driven_by": "blended_probability"
        }
    }

    pred = ResistancePrediction(
        risk_level=risk_level,
        probability=prob,
        confidence=conf,
        signals_detected=signals,
        signal_count=signal_count,
        urgency=urgency,
        recommended_actions=actions,
        next_line_options=playbook_next_lines or [],
        rationale=rationale_list,
        provenance=provenance_data,
        warnings=[],
        baseline_source=baseline_source,
        baseline_penalty_applied=baseline_penalty,
        confidence_cap=None,
        driver_alerts=driver_alerts,
        genomic_alert_context=alert_context
    )
    
    # 5. Apply Safety Caps (Invariant 2: Modulate Clinical Risk)
    pred = _apply_safety_caps(pred, has_ca125_data=full_ca125_history_available)
    
    return pred
