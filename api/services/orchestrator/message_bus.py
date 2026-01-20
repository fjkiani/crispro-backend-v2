"""
Message Bus - Inter-agent communication for the orchestration system.

Provides:
- Standard message format for agent communication
- Pub/sub messaging for event broadcasting
- Request-response patterns for synchronous agent calls
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, Callable, List
from datetime import datetime
from enum import Enum
import uuid
import asyncio
import logging

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """Types of inter-agent messages."""
    REQUEST = "request"      # Agent-to-agent request
    RESPONSE = "response"    # Response to a request
    EVENT = "event"          # Event notification (pub/sub)
    ALERT = "alert"          # Clinical alert
    BROADCAST = "broadcast"  # Broadcast to all agents


@dataclass
class AgentMessage:
    """
    Standard message format for inter-agent communication.
    
    All messages have:
    - Unique ID for tracking
    - Sender and recipient agents
    - Message type
    - Payload data
    - Correlation ID for request-response matching
    """
    sender: str
    recipient: str           # Agent ID or "broadcast"
    message_type: MessageType
    payload: Dict[str, Any]
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    correlation_id: Optional[str] = None  # For request-response matching
    timestamp: datetime = field(default_factory=datetime.utcnow)
    priority: int = 3        # 1=highest, 5=lowest
    patient_id: Optional[str] = None  # Patient context
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'sender': self.sender,
            'recipient': self.recipient,
            'message_type': self.message_type.value,
            'payload': self.payload,
            'correlation_id': self.correlation_id,
            'timestamp': self.timestamp.isoformat(),
            'priority': self.priority,
            'patient_id': self.patient_id
        }


class MessageBus:
    """
    Simple message bus for agent communication.
    
    Features:
    - Queue-based message delivery
    - Priority-based ordering
    - Pub/sub for events
    - Request-response correlation
    """
    
    def __init__(self):
        self._queues: Dict[str, asyncio.PriorityQueue] = {}
        self._handlers: Dict[str, Callable] = {}
        self._subscribers: Dict[str, List[str]] = {}  # event_type -> [agent_ids]
        self._pending_responses: Dict[str, asyncio.Future] = {}
    
    def register_agent(self, agent_id: str, handler: Callable = None):
        """Register an agent to receive messages."""
        self._queues[agent_id] = asyncio.PriorityQueue()
        if handler:
            self._handlers[agent_id] = handler
        logger.debug(f"Registered agent: {agent_id}")
    
    def subscribe(self, agent_id: str, event_type: str):
        """Subscribe an agent to an event type."""
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        if agent_id not in self._subscribers[event_type]:
            self._subscribers[event_type].append(agent_id)
            logger.debug(f"Agent {agent_id} subscribed to {event_type}")
    
    async def send(self, message: AgentMessage) -> None:
        """Send a message to an agent or broadcast."""
        if message.recipient == "broadcast":
            # Broadcast to all registered agents
            for agent_id, queue in self._queues.items():
                if agent_id != message.sender:  # Don't send to self
                    await queue.put((message.priority, message))
        elif message.recipient in self._queues:
            await self._queues[message.recipient].put((message.priority, message))
        else:
            logger.warning(f"Unknown recipient: {message.recipient}")
    
    async def publish_event(self, event_type: str, payload: Dict, sender: str, patient_id: str = None):
        """Publish an event to all subscribers."""
        subscribers = self._subscribers.get(event_type, [])
        
        for agent_id in subscribers:
            message = AgentMessage(
                sender=sender,
                recipient=agent_id,
                message_type=MessageType.EVENT,
                payload={'event_type': event_type, **payload},
                patient_id=patient_id
            )
            await self.send(message)
        
        logger.debug(f"Published {event_type} to {len(subscribers)} subscribers")
    
    async def request(
        self,
        sender: str,
        recipient: str,
        payload: Dict,
        timeout: float = 30.0,
        patient_id: str = None
    ) -> Optional[Dict]:
        """Send a request and wait for response."""
        correlation_id = str(uuid.uuid4())
        
        # Create future for response
        future = asyncio.get_event_loop().create_future()
        self._pending_responses[correlation_id] = future
        
        # Send request
        message = AgentMessage(
            sender=sender,
            recipient=recipient,
            message_type=MessageType.REQUEST,
            payload=payload,
            correlation_id=correlation_id,
            patient_id=patient_id
        )
        await self.send(message)
        
        # Wait for response
        try:
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
        except asyncio.TimeoutError:
            logger.warning(f"Request timeout: {sender} -> {recipient}")
            return None
        finally:
            self._pending_responses.pop(correlation_id, None)
    
    async def respond(self, original_message: AgentMessage, payload: Dict):
        """Respond to a request message."""
        if original_message.correlation_id in self._pending_responses:
            future = self._pending_responses[original_message.correlation_id]
            if not future.done():
                future.set_result(payload)
        else:
            # Send response as message
            response = AgentMessage(
                sender=original_message.recipient,
                recipient=original_message.sender,
                message_type=MessageType.RESPONSE,
                payload=payload,
                correlation_id=original_message.correlation_id,
                patient_id=original_message.patient_id
            )
            await self.send(response)
    
    async def receive(
        self,
        agent_id: str,
        timeout: float = None
    ) -> Optional[AgentMessage]:
        """Receive a message for an agent."""
        if agent_id not in self._queues:
            return None
        
        try:
            if timeout:
                priority, message = await asyncio.wait_for(
                    self._queues[agent_id].get(),
                    timeout=timeout
                )
            else:
                priority, message = await self._queues[agent_id].get()
            return message
        except asyncio.TimeoutError:
            return None
    
    async def process_messages(self, agent_id: str, handler: Callable):
        """Continuously process messages for an agent."""
        while True:
            message = await self.receive(agent_id)
            if message:
                try:
                    result = await handler(message)
                    
                    # Auto-respond to requests
                    if message.message_type == MessageType.REQUEST and result is not None:
                        await self.respond(message, result)
                except Exception as e:
                    logger.error(f"Error processing message in {agent_id}: {e}")


# Singleton instance
_message_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Get the global message bus instance."""
    global _message_bus
    if _message_bus is None:
        _message_bus = MessageBus()
    return _message_bus



