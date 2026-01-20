"""
Event system for resistance prediction.

Provides event-driven integration for resistance detection:
- Event definitions (ResistanceSignalDetected, ActionRequired, etc.)
- Event dispatcher for routing events to handlers
"""

from .resistance_events import (
    ResistanceSignalDetected,
    ResistanceSignalAbsent,
    ActionRequired,
    ResistancePredictionComplete,
)

from .resistance_event_dispatcher import ResistanceEventDispatcher

__all__ = [
    "ResistanceSignalDetected",
    "ResistanceSignalAbsent",
    "ActionRequired",
    "ResistancePredictionComplete",
    "ResistanceEventDispatcher",
]
