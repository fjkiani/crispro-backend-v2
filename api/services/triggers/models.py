"""
Data models for trigger system.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum


class TriggerSeverity(str, Enum):
    """Trigger severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class TriggerResult:
    """Result of trigger evaluation."""
    trigger_id: str
    event_type: str
    timestamp: datetime = field(default_factory=datetime.utcnow)
    condition_matched: bool = False
    actions_taken: List[str] = field(default_factory=list)
    notifications_sent: List[Dict] = field(default_factory=list)
    escalations: List[Dict] = field(default_factory=list)
    audit_log: List[Dict] = field(default_factory=list)
    severity: TriggerSeverity = TriggerSeverity.INFO
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'trigger_id': self.trigger_id,
            'event_type': self.event_type,
            'timestamp': self.timestamp.isoformat(),
            'condition_matched': self.condition_matched,
            'actions_taken': self.actions_taken,
            'notifications_sent': self.notifications_sent,
            'escalations': self.escalations,
            'audit_log': self.audit_log,
            'severity': self.severity.value
        }


