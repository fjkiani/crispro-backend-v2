"""
Base detector class for all resistance signal detectors.

All signal detectors should inherit from this base class to ensure
consistent interface and event emission capabilities.
"""

from abc import ABC, abstractmethod
from typing import Dict, Optional, Any
import logging

from ..models import ResistanceSignalData

logger = logging.getLogger(__name__)


class BaseResistanceDetector(ABC):
    """
    Abstract base class for all resistance signal detectors.
    
    All detectors must implement:
    - `detect()` method that returns ResistanceSignalData
    - Signal-specific detection logic
    
    All detectors may emit events:
    - `ResistanceSignalDetected` - When signal detected
    - `ResistanceSignalAbsent` - When signal not detected
    """
    
    def __init__(self, event_emitter=None):
        """
        Initialize detector.
        
        Args:
            event_emitter: Optional event emitter for event-driven architecture
        """
        self.event_emitter = event_emitter
        self.logger = logger
    
    @abstractmethod
    async def detect(self, *args, **kwargs) -> ResistanceSignalData:
        """
        Detect resistance signal.
        
        Args:
            *args, **kwargs: Signal-specific input parameters
        
        Returns:
            ResistanceSignalData with detection results
        """
        pass
    
    def _emit_signal_detected(self, signal_data: ResistanceSignalData):
        """Emit ResistanceSignalDetected event if event emitter available."""
        if self.event_emitter:
            try:
                self.event_emitter.emit("ResistanceSignalDetected", signal_data)
            except Exception as e:
                self.logger.warning(f"Failed to emit signal detected event: {e}")
    
    def _emit_signal_absent(self, signal_type: str, reason: str):
        """Emit ResistanceSignalAbsent event if event emitter available."""
        if self.event_emitter:
            try:
                self.event_emitter.emit("ResistanceSignalAbsent", {
                    "signal_type": signal_type,
                    "reason": reason
                })
            except Exception as e:
                self.logger.warning(f"Failed to emit signal absent event: {e}")
