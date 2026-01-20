"""
Resistance Detection Service (SAE Phase 2 - Task 7)
===================================================
Enhanced resistance detection with 2-of-3 trigger logic and HR restoration patterns.

Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C7, R2)
Owner: Zo (Lead Commander)
Date: January 13, 2025

2-of-3 Trigger Rule (Manager's C7):
Alert resistance if 2 of 3 conditions met:
1. HRD drop >= 15 points
2. DNA repair capacity drop >= 0.20
3. CA-125 inadequate response (on-therapy rise OR <50% drop by cycle 3)

HR Restoration Pattern (Manager's R2):
Detect resistance IMMEDIATELY (don't wait for radiology):
- HRD score drop + coherent SAE signal → Immediate alert
- Switch recommendation triggered (ATR/CHK1 trials)
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Manager's Policy Constants
RESISTANCE_HRD_DROP_THRESHOLD = 15  # Points (C7)
RESISTANCE_DNA_REPAIR_DROP_THRESHOLD = 0.20  # 0-1 scale (C7)
RESISTANCE_CA125_DROP_CYCLE3_THRESHOLD = 0.50  # <50% drop by cycle 3 (C7)

# HR Restoration Pattern Detection
HR_RESTORATION_HRD_DROP_MIN = 10  # Minimum HRD drop to suspect HR restoration
HR_RESTORATION_DNA_REPAIR_DROP_MIN = 0.15  # Minimum DNA repair drop


@dataclass
class ResistanceAlert:
    """
    Resistance alert with 2-of-3 trigger logic and HR restoration pattern.
    
    Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C7, R2)
    """
    # Alert Status
    resistance_detected: bool  # True if 2-of-3 triggers met
    hr_restoration_suspected: bool  # True if HR restoration pattern detected
    immediate_alert: bool  # True if should alert NOW (don't wait for radiology)
    
    # Triggers
    triggers_met: List[str]  # List of met triggers (hrd_drop, dna_repair_drop, ca125_inadequate)
    trigger_count: int  # Number of triggers met (need ≥2 for alert)
    
    # Detailed Signals
    hrd_signal: Dict[str, Any]  # HRD drop details
    dna_repair_signal: Dict[str, Any]  # DNA repair capacity drop details
    ca125_signal: Dict[str, Any]  # CA-125 inadequate response details
    
    # Recommendations
    recommended_actions: List[str]  # Clinical actions (order tests, switch therapy)
    recommended_trials: List[str]  # Trial types to consider (ATR/CHK1, WEE1)
    
    # Provenance
    timestamp: str
    provenance: Dict[str, Any]


class ResistanceDetectionService:
    """
    Enhanced resistance detection with SAE integration.
    
    Detects resistance patterns IMMEDIATELY (not waiting for radiology):
    - 2-of-3 trigger rule (HRD drop, DNA repair drop, CA-125 inadequate)
    - HR restoration pattern (HRD + DNA repair coherent drop)
    - Immediate alerts and trial switch recommendations
    """
    
    def __init__(self):
        self.logger = logger
    
    def detect_resistance(
        self,
        current_hrd: float,
        previous_hrd: Optional[float],
        current_dna_repair_capacity: float,
        previous_dna_repair_capacity: Optional[float],
        ca125_intelligence: Optional[Dict],
        treatment_on_parp: bool = False
    ) -> ResistanceAlert:
        """
        Detect resistance with 2-of-3 trigger rule.
        
        Manager Policy: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C7, R2)
        
        Args:
            current_hrd: Current HRD score (0-100)
            previous_hrd: Previous HRD score (baseline or last measurement)
            current_dna_repair_capacity: Current DNA repair capacity (0-1)
            previous_dna_repair_capacity: Previous DNA repair capacity
            ca125_intelligence: CA-125 intelligence from ca125_intelligence service
            treatment_on_parp: True if patient currently on PARP inhibitor
        
        Returns:
            ResistanceAlert with all signals and recommendations
        """
        triggers_met = []
        
        # ============================================================
        # TRIGGER 1: HRD Drop >= 15 Points (C7)
        # ============================================================
        hrd_drop = 0.0
        hrd_signal = {"triggered": False, "reason": "No baseline HRD available"}
        
        if previous_hrd is not None:
            hrd_drop = previous_hrd - current_hrd
            
            if hrd_drop >= RESISTANCE_HRD_DROP_THRESHOLD:
                triggers_met.append("hrd_drop")
                hrd_signal = {
                    "triggered": True,
                    "hrd_previous": previous_hrd,
                    "hrd_current": current_hrd,
                    "hrd_drop": hrd_drop,
                    "threshold": RESISTANCE_HRD_DROP_THRESHOLD,
                    "reason": f"HRD dropped {hrd_drop:.0f} points (threshold: {RESISTANCE_HRD_DROP_THRESHOLD})"
                }
            else:
                hrd_signal = {
                    "triggered": False,
                    "hrd_previous": previous_hrd,
                    "hrd_current": current_hrd,
                    "hrd_drop": hrd_drop,
                    "threshold": RESISTANCE_HRD_DROP_THRESHOLD,
                    "reason": f"HRD drop {hrd_drop:.0f} below threshold (stable)"
                }
        
        # ============================================================
        # TRIGGER 2: DNA Repair Capacity Drop >= 0.20 (C7)
        # ============================================================
        dna_repair_drop = 0.0
        dna_repair_signal = {"triggered": False, "reason": "No baseline DNA repair capacity available"}
        
        if previous_dna_repair_capacity is not None:
            dna_repair_drop = previous_dna_repair_capacity - current_dna_repair_capacity
            
            if dna_repair_drop >= RESISTANCE_DNA_REPAIR_DROP_THRESHOLD:
                triggers_met.append("dna_repair_drop")
                dna_repair_signal = {
                    "triggered": True,
                    "dna_repair_previous": previous_dna_repair_capacity,
                    "dna_repair_current": current_dna_repair_capacity,
                    "dna_repair_drop": dna_repair_drop,
                    "threshold": RESISTANCE_DNA_REPAIR_DROP_THRESHOLD,
                    "reason": f"DNA repair capacity dropped {dna_repair_drop:.2f} (threshold: {RESISTANCE_DNA_REPAIR_DROP_THRESHOLD})"
                }
            else:
                dna_repair_signal = {
                    "triggered": False,
                    "dna_repair_previous": previous_dna_repair_capacity,
                    "dna_repair_current": current_dna_repair_capacity,
                    "dna_repair_drop": dna_repair_drop,
                    "threshold": RESISTANCE_DNA_REPAIR_DROP_THRESHOLD,
                    "reason": f"DNA repair drop {dna_repair_drop:.2f} below threshold (stable)"
                }
        
        # ============================================================
        # TRIGGER 3: CA-125 Inadequate Response (C7)
        # ============================================================
        ca125_signal = {"triggered": False, "reason": "No CA-125 intelligence available"}
        
        if ca125_intelligence:
            resistance_rule = ca125_intelligence.get("resistance_rule", {})
            
            if resistance_rule.get("triggered"):
                triggers_met.append("ca125_inadequate")
                ca125_signal = {
                    "triggered": True,
                    "reason": "CA-125 inadequate response or on-therapy rise",
                    "details": resistance_rule
                }
            else:
                ca125_signal = {
                    "triggered": False,
                    "reason": "CA-125 response adequate (on track)",
                    "details": resistance_rule
                }
        
        # ============================================================
        # 2-OF-3 RULE (C7)
        # ============================================================
        trigger_count = len(triggers_met)
        resistance_detected = trigger_count >= 2
        
        # ============================================================
        # HR RESTORATION PATTERN (R2) - IMMEDIATE ALERT
        # ============================================================
        hr_restoration_suspected = False
        
        if treatment_on_parp:
            # HR restoration pattern: HRD drop + DNA repair drop (coherent signal)
            hr_restoration_suspected = (
                hrd_drop >= HR_RESTORATION_HRD_DROP_MIN and
                dna_repair_drop >= HR_RESTORATION_DNA_REPAIR_DROP_MIN
            )
        
        # Immediate alert if HR restoration (don't wait for radiology)
        immediate_alert = hr_restoration_suspected or resistance_detected
        
        # ============================================================
        # RECOMMENDATIONS (R2)
        # ============================================================
        recommended_actions = []
        recommended_trials = []
        
        if resistance_detected or hr_restoration_suspected:
            # IMMEDIATE ACTIONS
            recommended_actions.append("🚨 ALERT ONCOLOGIST IMMEDIATELY - Resistance suspected")
            recommended_actions.append("📋 Order updated HRD test (confirm HR restoration)")
            recommended_actions.append("📋 Order ctDNA panel (check for reversion mutations)")
            
            if hr_restoration_suspected:
                recommended_actions.append("⚠️ HR RESTORATION SUSPECTED - Consider switching from PARP")
            
            # TRIAL RECOMMENDATIONS
            recommended_trials.append("ATR inhibitor trials (Ceralasertib, Elimusertib)")
            recommended_trials.append("ATR + PARP combination trials")
            recommended_trials.append("CHK1 inhibitor trials (if ATR contraindicated)")
            recommended_trials.append("WEE1 inhibitor trials (Adavosertib)")
            
            if treatment_on_parp:
                recommended_actions.append("⚠️ SWITCH STRATEGY - Current PARP therapy may be failing")
        
        # ============================================================
        # PROVENANCE
        # ============================================================
        provenance = {
            "detection_method": "2-of-3 trigger rule + HR restoration pattern",
            "manager_policy": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C7, R2)",
            "thresholds": {
                "hrd_drop": RESISTANCE_HRD_DROP_THRESHOLD,
                "dna_repair_drop": RESISTANCE_DNA_REPAIR_DROP_THRESHOLD,
                "ca125_drop_cycle3": RESISTANCE_CA125_DROP_CYCLE3_THRESHOLD,
                "hr_restoration_hrd_min": HR_RESTORATION_HRD_DROP_MIN,
                "hr_restoration_dna_repair_min": HR_RESTORATION_DNA_REPAIR_DROP_MIN
            },
            "triggers_evaluated": ["hrd_drop", "dna_repair_drop", "ca125_inadequate"],
            "triggers_met": triggers_met,
            "trigger_count": trigger_count,
            "resistance_logic": "2-of-3 triggers OR HR restoration pattern"
        }
        
        return ResistanceAlert(
            resistance_detected=resistance_detected,
            hr_restoration_suspected=hr_restoration_suspected,
            immediate_alert=immediate_alert,
            triggers_met=triggers_met,
            trigger_count=trigger_count,
            hrd_signal=hrd_signal,
            dna_repair_signal=dna_repair_signal,
            ca125_signal=ca125_signal,
            recommended_actions=recommended_actions,
            recommended_trials=recommended_trials,
            timestamp=datetime.now().isoformat(),
            provenance=provenance
        )


# Singleton instance
_resistance_detection_service = None

def get_resistance_detection_service() -> ResistanceDetectionService:
    """Get singleton Resistance Detection Service instance"""
    global _resistance_detection_service
    if _resistance_detection_service is None:
        _resistance_detection_service = ResistanceDetectionService()
    return _resistance_detection_service


def detect_resistance(
    current_hrd: float,
    previous_hrd: Optional[float],
    current_dna_repair_capacity: float,
    previous_dna_repair_capacity: Optional[float],
    ca125_intelligence: Optional[Dict],
    treatment_on_parp: bool = False
) -> Dict[str, Any]:
    """
    Convenience function for resistance detection.
    
    Returns dict representation of ResistanceAlert.
    """
    service = get_resistance_detection_service()
    alert = service.detect_resistance(
        current_hrd=current_hrd,
        previous_hrd=previous_hrd,
        current_dna_repair_capacity=current_dna_repair_capacity,
        previous_dna_repair_capacity=previous_dna_repair_capacity,
        ca125_intelligence=ca125_intelligence,
        treatment_on_parp=treatment_on_parp
    )
    return asdict(alert)

