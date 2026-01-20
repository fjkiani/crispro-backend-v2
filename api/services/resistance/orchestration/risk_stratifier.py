"""
Risk Stratifier.

Stratifies resistance risk level based on probability, signal count, and CA-125 availability.
Implements Manager Q9 thresholds and Manager Q15 cap.
"""

from ..models import ResistanceRiskLevel
from ..config import RISK_STRATIFICATION_THRESHOLDS


class RiskStratifier:
    """
    Stratify resistance risk level.
    
    Manager Q9 thresholds:
    - HIGH: >=0.70 probability + >=2 signals
    - MEDIUM: 0.50-0.69 or exactly 1 signal
    - LOW: <0.50 probability
    
    Manager Q15: Cap at MEDIUM if no CA-125 and <2 signals
    """
    
    @classmethod
    def stratify(
        cls,
        probability: float,
        signal_count: int,
        has_ca125: bool
    ) -> ResistanceRiskLevel:
        """
        Stratify resistance risk level.
        
        Args:
            probability: Overall resistance probability (0.0-1.0)
            signal_count: Number of detected signals
            has_ca125: Whether CA-125 data is available
            
        Returns:
            ResistanceRiskLevel (HIGH/MEDIUM/LOW)
        """
        thresholds = RISK_STRATIFICATION_THRESHOLDS
        
        # Manager Q15: If no CA-125 and <2 signals, cap at MEDIUM
        if not has_ca125 and signal_count < 2 and probability >= thresholds["high_risk_probability"]:
            return ResistanceRiskLevel.MEDIUM
        
        # Manager Q9: Risk stratification
        if probability >= thresholds["high_risk_probability"] and signal_count >= thresholds["min_signals_for_high"]:
            return ResistanceRiskLevel.HIGH
        elif probability >= thresholds["medium_risk_probability"] or signal_count == 1:
            return ResistanceRiskLevel.MEDIUM
        else:
            return ResistanceRiskLevel.LOW
