"""
Resistance Event Definitions.

Defines event types for resistance prediction workflow:
- ResistanceSignalDetected: When a resistance signal is detected
- ResistanceSignalAbsent: When a resistance signal is not detected
- ActionRequired: When actions need to be taken based on risk level
- ResistancePredictionComplete: When a complete prediction is made
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from datetime import datetime

from ..models import ResistanceSignalData, ResistanceRiskLevel, UrgencyLevel, ResistancePrediction


@dataclass
class ResistanceSignalDetected:
    """Event emitted when a resistance signal is detected."""
    signal_data: ResistanceSignalData
    timestamp: datetime
    detector_id: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ResistanceSignalAbsent:
    """Event emitted when a resistance signal is not detected."""
    signal_type: str
    reason: str
    timestamp: datetime
    detector_id: str
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ActionRequired:
    """Event emitted when actions need to be taken based on risk level."""
    risk_level: ResistanceRiskLevel
    urgency: UrgencyLevel
    actions: List[Dict[str, Any]]
    signal_count: int
    probability: float
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()


@dataclass
class ResistancePredictionComplete:
    """Event emitted when a complete resistance prediction is made."""
    prediction: ResistancePrediction
    timestamp: datetime
    metadata: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
