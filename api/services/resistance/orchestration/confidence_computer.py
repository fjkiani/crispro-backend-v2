"""
Confidence Computer.

Computes prediction confidence from signal confidences, applying penalties and caps.
Implements Manager Q16 penalty (20% if baseline missing) and Manager Q15 cap (0.60 if no CA-125 and <2 signals).
"""

from typing import List, Optional, Tuple
from ..models import ResistanceSignalData
from ..config import CONFIDENCE_CONFIG


class ConfidenceComputer:
    """
    Compute prediction confidence.
    
    Applies:
    - Manager Q16: 20% penalty if baseline missing
    - Manager Q15: Cap at 0.60 if no CA-125 and <2 signals
    """
    
    @staticmethod
    def compute(
        signals: List[ResistanceSignalData],
        baseline_source: str,
        has_ca125: bool,
        signal_count: int
    ) -> Tuple[float, Optional[str]]:
        """
        Compute prediction confidence.
        
        Args:
            signals: List of resistance signals with confidence
            baseline_source: "patient_baseline" or "population_average"
            has_ca125: Whether CA-125 data is available
            signal_count: Number of detected signals
            
        Returns:
            Tuple of (confidence, confidence_cap) where confidence_cap is "MEDIUM" if capped, None otherwise
        """
        # Start with average signal confidence
        active_signals = [sig for sig in signals if sig.confidence > 0.0]
        if not active_signals:
            return 0.0, None
        
        avg_confidence = sum(sig.confidence for sig in active_signals) / len(active_signals)
        
        # Manager Q16: Penalty if baseline missing
        if baseline_source == "population_average":
            avg_confidence *= CONFIDENCE_CONFIG["baseline_penalty"]
        
        # Manager Q15: Cap at 0.60 if no CA-125 and <2 signals
        if not has_ca125 and signal_count < 2:
            if avg_confidence > CONFIDENCE_CONFIG["ca125_missing_cap"]:
                avg_confidence = CONFIDENCE_CONFIG["ca125_missing_cap"]
                return min(avg_confidence, 1.0), "MEDIUM"
        
        return min(avg_confidence, 1.0), None
