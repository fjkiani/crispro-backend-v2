"""
Resistance Probability Computer.

Computes overall resistance probability from individual signals using weighted average by confidence.
"""

from typing import List
from ..models import ResistanceSignalData


class ResistanceProbabilityComputer:
    """
    Compute overall resistance probability from individual signals.
    
    Uses weighted average of signal probabilities, weighted by confidence.
    Handles edge cases: no signals, zero confidence.
    """
    
    @staticmethod
    def compute(signals: List[ResistanceSignalData]) -> float:
        """
        Compute overall resistance probability from individual signals.
        
        Args:
            signals: List of resistance signals with probability and confidence
            
        Returns:
            Overall resistance probability (0.0-1.0)
        """
        if not signals:
            return 0.0
        
        # Filter to signals that were computed (confidence > 0)
        active_signals = [sig for sig in signals if sig.confidence > 0.0]
        
        if not active_signals:
            return 0.0
        
        # Weighted average by confidence
        total_probability = sum(sig.probability * sig.confidence for sig in active_signals)
        total_weight = sum(sig.confidence for sig in active_signals)
        
        overall_probability = total_probability / total_weight if total_weight > 0 else 0.0
        
        # Cap at 1.0
        return min(overall_probability, 1.0)
