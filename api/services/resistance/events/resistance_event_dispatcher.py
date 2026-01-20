"""
Resistance Event Dispatcher.

Routes resistance events to registered handlers for event-driven integration.
"""

from typing import Dict, List, Callable, Any, Optional
from collections import defaultdict
import logging
from datetime import datetime

from .resistance_events import (
    ResistanceSignalDetected,
    ResistanceSignalAbsent,
    ActionRequired,
    ResistancePredictionComplete,
)

logger = logging.getLogger(__name__)


class ResistanceEventDispatcher:
    """
    Event dispatcher for resistance prediction events.
    
    Routes events to registered handlers:
    - Signal detectors emit ResistanceSignalDetected events
    - Action handlers receive ActionRequired events
    - Trigger engine receives events for downstream workflows
    """
    
    def __init__(self):
        """Initialize event dispatcher with empty handler registry."""
        self.handlers: Dict[str, List[Callable]] = defaultdict(list)
        self.logger = logger
    
    def register_handler(self, event_type: str, handler: Callable):
        """
        Register an event handler for a specific event type.
        
        Args:
            event_type: Event type (e.g., "ResistanceSignalDetected", "ActionRequired")
            handler: Callable that handles the event
        """
        if not callable(handler):
            raise ValueError(f"Handler must be callable, got {type(handler)}")
        
        self.handlers[event_type].append(handler)
        self.logger.debug(f"Registered handler for {event_type}: {handler.__name__}")
    
    def unregister_handler(self, event_type: str, handler: Callable):
        """
        Unregister an event handler.
        
        Args:
            event_type: Event type
            handler: Handler to unregister
        """
        if event_type in self.handlers and handler in self.handlers[event_type]:
            self.handlers[event_type].remove(handler)
            self.logger.debug(f"Unregistered handler for {event_type}: {handler.__name__}")
    
    def emit(self, event_type: str, event_data: Any):
        """
        Emit an event to all registered handlers.
        
        Args:
            event_type: Event type (e.g., "ResistanceSignalDetected")
            event_data: Event data (can be event object or dict)
        """
        handlers = self.handlers.get(event_type, [])
        
        if not handlers:
            self.logger.debug(f"No handlers registered for {event_type}")
            return
        
        self.logger.debug(f"Emitting {event_type} to {len(handlers)} handler(s)")
        
        for handler in handlers:
            try:
                # Call handler with event data
                if isinstance(event_data, dict):
                    handler(event_data)
                else:
                    handler(event_data)
            except Exception as e:
                self.logger.error(
                    f"Error in handler {handler.__name__} for {event_type}: {e}",
                    exc_info=True
                )
    
    # Convenience methods for specific event types
    
    def emit_signal_detected(self, signal_data, detector_id: str, metadata: Optional[Dict] = None):
        """Emit ResistanceSignalDetected event."""
        event = ResistanceSignalDetected(
            signal_data=signal_data,
            timestamp=datetime.utcnow(),
            detector_id=detector_id,
            metadata=metadata
        )
        self.emit("ResistanceSignalDetected", event)
    
    def emit_signal_absent(self, signal_type: str, reason: str, detector_id: str, metadata: Optional[Dict] = None):
        """Emit ResistanceSignalAbsent event."""
        event = ResistanceSignalAbsent(
            signal_type=signal_type,
            reason=reason,
            timestamp=datetime.utcnow(),
            detector_id=detector_id,
            metadata=metadata
        )
        self.emit("ResistanceSignalAbsent", event)
    
    def emit_action_required(
        self,
        risk_level,
        urgency,
        actions: List[Dict],
        signal_count: int,
        probability: float,
        metadata: Optional[Dict] = None
    ):
        """Emit ActionRequired event."""
        event = ActionRequired(
            risk_level=risk_level,
            urgency=urgency,
            actions=actions,
            signal_count=signal_count,
            probability=probability,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        self.emit("ActionRequired", event)
    
    def emit_prediction_complete(self, prediction, metadata: Optional[Dict] = None):
        """Emit ResistancePredictionComplete event."""
        event = ResistancePredictionComplete(
            prediction=prediction,
            timestamp=datetime.utcnow(),
            metadata=metadata
        )
        self.emit("ResistancePredictionComplete", event)
    
    def register_signal_handler(self, handler: Callable):
        """Convenience method to register handler for ResistanceSignalDetected."""
        self.register_handler("ResistanceSignalDetected", handler)
    
    def register_action_handler(self, handler: Callable):
        """Convenience method to register handler for ActionRequired."""
        self.register_handler("ActionRequired", handler)
    
    def register_prediction_handler(self, handler: Callable):
        """Convenience method to register handler for ResistancePredictionComplete."""
        self.register_handler("ResistancePredictionComplete", handler)
