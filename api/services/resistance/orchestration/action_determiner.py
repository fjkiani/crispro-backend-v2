"""
Action Determiner.

Determines urgency level and recommended actions based on risk level and detected signals.
Supports both OV (ovarian) and MM (multiple myeloma) disease-specific actions.
"""

from typing import List, Dict, Tuple
from ..models import ResistanceRiskLevel, UrgencyLevel, ResistanceSignalData


class ActionDeterminer:
    """
    Determine urgency and recommended actions.
    
    Maps risk level to urgency:
    - HIGH → CRITICAL
    - MEDIUM → ELEVATED
    - LOW → ROUTINE
    
    Supports disease-specific action recommendations.
    """
    
    @staticmethod
    def determine(
        risk_level: ResistanceRiskLevel,
        signal_count: int,
        signals: List[ResistanceSignalData],
        disease: str = "ovarian"
    ) -> Tuple[UrgencyLevel, List[Dict]]:
        """
        Determine urgency and recommended actions (OV-specific).
        
        Args:
            risk_level: Resistance risk level (HIGH/MEDIUM/LOW)
            signal_count: Number of detected signals
            signals: List of detected signals (for mechanism-specific actions)
            disease: Disease type ("ovarian" or "myeloma"), defaults to "ovarian"
            
        Returns:
            Tuple of (urgency, actions) where actions is a list of action dictionaries
        """
        if disease.lower() in ["myeloma", "mm"]:
            return ActionDeterminer.determine_mm(risk_level, signal_count, signals)
        
        # OV-specific actions
        if risk_level == ResistanceRiskLevel.HIGH:
            urgency = UrgencyLevel.CRITICAL
            
            # Build mechanism-specific actions based on detected signals
            escaped_pathways = []
            for sig in signals:
                if sig.escaped_pathways:
                    escaped_pathways.extend(sig.escaped_pathways)
            
            actions = [
                {
                    "action": "ESCALATE_IMAGING",
                    "timeframe": "within 1 week",
                    "rationale": f"HIGH resistance risk ({signal_count} signals). Early imaging may reveal subclinical progression.",
                    "priority": 1
                },
                {
                    "action": "CONSIDER_SWITCH",
                    "timeframe": "within 2 weeks",
                    "rationale": "Mechanism-based resistance predicted. Review next-line options.",
                    "priority": 2,
                    "escaped_pathways": escaped_pathways if escaped_pathways else None
                },
                {
                    "action": "REVIEW_RESISTANCE_PLAYBOOK",
                    "timeframe": "within 1 week",
                    "rationale": "Consult Resistance Playbook for mechanism-specific strategies.",
                    "priority": 3
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
        else:  # LOW
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
    
    @staticmethod
    def determine_mm(
        risk_level: ResistanceRiskLevel,
        signal_count: int,
        signals: List[ResistanceSignalData]
    ) -> Tuple[UrgencyLevel, List[Dict]]:
        """
        Determine MM-specific urgency and recommended actions.
        
        Args:
            risk_level: Resistance risk level (HIGH/MEDIUM/LOW)
            signal_count: Number of detected signals
            signals: List of detected signals
            
        Returns:
            Tuple of (urgency, actions) where actions is a list of action dictionaries
        """
        if risk_level == ResistanceRiskLevel.HIGH:
            urgency = UrgencyLevel.CRITICAL
            
            # Extract detected genes
            detected_genes = []
            for sig in signals:
                if sig.provenance.get("detected_genes"):
                    detected_genes.extend([g["gene"] for g in sig.provenance["detected_genes"]])
            
            actions = [
                {
                    "action": "CONSIDER_INTENSIFICATION",
                    "timeframe": "at next treatment decision",
                    "rationale": f"High-risk gene(s) detected: {', '.join(detected_genes) if detected_genes else 'multiple signals'}. Consider intensified therapy.",
                    "priority": 1
                },
                {
                    "action": "EVALUATE_TRIPLET_REGIMEN",
                    "timeframe": "within 2 weeks",
                    "rationale": "High-risk MM may benefit from triplet or quadruplet regimens.",
                    "priority": 2
                },
                {
                    "action": "CONSIDER_TRANSPLANT_ELIGIBILITY",
                    "timeframe": "if applicable",
                    "rationale": "Assess for autologous stem cell transplant in eligible patients.",
                    "priority": 3
                }
            ]
        elif risk_level == ResistanceRiskLevel.MEDIUM:
            urgency = UrgencyLevel.ELEVATED
            actions = [
                {
                    "action": "MONITOR_MRD",
                    "timeframe": "per protocol",
                    "rationale": "Monitor minimal residual disease status.",
                    "priority": 1
                },
                {
                    "action": "CONSIDER_MAINTENANCE_MODIFICATION",
                    "timeframe": "at maintenance phase",
                    "rationale": "Consider modified maintenance strategy.",
                    "priority": 2
                }
            ]
        else:  # LOW
            urgency = UrgencyLevel.ROUTINE
            actions = [
                {
                    "action": "STANDARD_MONITORING",
                    "timeframe": "per standard of care",
                    "rationale": "Continue standard MM monitoring protocols.",
                    "priority": 1
                }
            ]
        
        return urgency, actions