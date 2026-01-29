"""
Resistance Prophet Actions
Determines clinical actions and generates rationales based on risk level.
Orchestrates the "Bridge" to the Playbook Service.
"""

from typing import List, Dict, Tuple, Optional
import logging

from api.services.resistance_prophet.schemas import (
    ResistanceRiskLevel, UrgencyLevel, ResistanceSignalData, ResistanceSignal
)

logger = logging.getLogger(__name__)

def determine_actions(
    risk_level: ResistanceRiskLevel,
    signal_count: int,
    signals_detected: List[ResistanceSignalData]
) -> Tuple[UrgencyLevel, List[Dict]]:
    """
    Determine urgency and immediate clinical actions.
    This is the text displayed on the 'Alert' card.
    The detailed options come from the Playbook (Next Line Options).
    """
    if risk_level == ResistanceRiskLevel.NOT_APPLICABLE:
        return UrgencyLevel.ROUTINE, [
            {
                "action": "ESTABLISH_BASELINE",
                "timeframe": "at initiation",
                "rationale": "Patient is treatment naive. Establish baseline SAE profile.",
                "priority": 1
            }
        ]
        
    if risk_level == ResistanceRiskLevel.HIGH:
        urgency = UrgencyLevel.CRITICAL
        
        # Check specific drivers
        has_restoration = any(s.signal_type == ResistanceSignal.DNA_REPAIR_RESTORATION for s in signals_detected if s.detected)
        has_escape = any(s.signal_type == ResistanceSignal.PATHWAY_ESCAPE for s in signals_detected if s.detected)
        
        rationale_text = f"HIGH resistance risk ({signal_count} signals)."
        if has_restoration:
            rationale_text += " DNA Repair Restoration detected (Synthetic Lethality lost)."
        elif has_escape:
            rationale_text += " Target Pathway Escape detected."

        actions = [
            {
                "action": "ESCALATE_IMAGING",
                "timeframe": "within 1 week",
                "rationale": f"{rationale_text} Early imaging may reveal subclinical progression.",
                "priority": 1
            },
            {
                "action": "CONSIDER_SWITCH",
                "timeframe": "within 2 weeks",
                "rationale": "Mechanism-based resistance predicted. Review Playbook options.",
                "priority": 2,
                "context": "restoration" if has_restoration else "escape" if has_escape else "general"
            }
        ]
        
    elif risk_level == ResistanceRiskLevel.MEDIUM:
        urgency = UrgencyLevel.ELEVATED
        actions = [
            {
                "action": "MONITOR_WEEKLY",
                "timeframe": "4 weeks",
                "rationale": f"MEDIUM resistance risk. Weekly monitoring recommended.",
                "priority": 1
            },
            {
                "action": "REASSESS",
                "timeframe": "after 4 weeks",
                "rationale": "Re-run Resistance Prophet to assess trend.",
                "priority": 2
            }
        ]
    else:
        urgency = UrgencyLevel.ROUTINE
        actions = [
            {
                "action": "ROUTINE_MONITORING",
                "timeframe": "per standard of care",
                "rationale": "LOW resistance risk. Continue routine monitoring.",
                "priority": 1
            }
        ]
        
    return urgency, actions

def build_rationale(
    signals_detected: List[ResistanceSignalData],
    probability: float,
    risk_level: ResistanceRiskLevel,
    baseline_source: str
) -> List[str]:
    """
    Build human-readable rationale list.
    """
    rationale = []
    
    # Header
    rationale.append(
        f"Overall resistance probability: {probability:.1%} ({risk_level.value} risk)"
    )
    
    # Baseline Note
    if baseline_source == "population_average":
        rationale.append("⚠️ Note: Using population baseline (Lower Reliability).")
        
    # Active Signals
    active_sigs = [s for s in signals_detected if s.detected]
    if active_sigs:
        for sig in active_sigs:
            rationale.append(f"• {sig.signal_type.value}: DETECTED (Conf: {sig.confidence:.2f})")
            if sig.rationale:
                rationale.append(f"  → {sig.rationale}")
    else:
        rationale.append("• No resistance signals detected.")
        
    return rationale
