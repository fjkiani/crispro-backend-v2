"""
Patient State Management - Single source of truth for all patient data.

This module defines the core state objects that track a patient's journey
through the MOAT orchestration pipeline.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any
from datetime import datetime
from enum import Enum
import uuid


class StatePhase(str, Enum):
    """Pipeline phases for patient state tracking."""
    INITIALIZED = "initialized"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    RANKING = "ranking"
    MATCHING = "matching"
    PLANNING = "planning"
    MONITORING = "monitoring"
    COMPLETE = "complete"
    ERROR = "error"


class AlertSeverity(str, Enum):
    """Alert severity levels."""
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"


@dataclass
class StateChange:
    """Record of a state change for audit trail."""
    id: str
    timestamp: datetime
    field: str
    old_value: Any
    new_value: Any
    agent: str
    reason: str
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat(),
            'field': self.field,
            'old_value': self.old_value,
            'new_value': self.new_value,
            'agent': self.agent,
            'reason': self.reason
        }


@dataclass
class AgentExecution:
    """Record of agent execution for tracing."""
    agent_id: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    status: str = "running"
    error: Optional[str] = None
    output_summary: Optional[Dict] = None
    duration_ms: Optional[float] = None
    
    def complete(self, output_summary: Dict = None):
        """Mark execution as complete."""
        self.completed_at = datetime.utcnow()
        self.status = "complete"
        self.output_summary = output_summary
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def fail(self, error: str):
        """Mark execution as failed."""
        self.completed_at = datetime.utcnow()
        self.status = "error"
        self.error = error
        self.duration_ms = (self.completed_at - self.started_at).total_seconds() * 1000
    
    def to_dict(self) -> Dict:
        return {
            'agent_id': self.agent_id,
            'started_at': self.started_at.isoformat(),
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'status': self.status,
            'error': self.error,
            'output_summary': self.output_summary,
            'duration_ms': self.duration_ms
        }


@dataclass
class Alert:
    """Patient alert for clinical attention."""
    id: str
    alert_type: str
    message: str
    severity: AlertSeverity
    timestamp: datetime
    source_agent: str
    acknowledged: bool = False
    
    def to_dict(self) -> Dict:
        return {
            'id': self.id,
            'alert_type': self.alert_type,
            'message': self.message,
            'severity': self.severity.value,
            'timestamp': self.timestamp.isoformat(),
            'source_agent': self.source_agent,
            'acknowledged': self.acknowledged
        }


@dataclass
class PatientState:
    """
    Central patient state object.
    
    This is the single source of truth for all patient data
    across all agents in the orchestration pipeline.
    
    Agent outputs are populated as agents complete their work:
    - patient_profile: From 01_DATA_EXTRACTION
    - biomarker_profile: From 02_BIOMARKER
    - resistance_prediction: From 03_RESISTANCE
    - drug_ranking: From 04_DRUG_EFFICACY
    - synthetic_lethality_result: From 14_SYNTHETIC_LETHALITY
    - trial_matches: From 05_TRIAL_MATCHING
    - nutrition_plan: From 06_NUTRITION
    - care_plan: From 07_CARE_PLAN
    - monitoring_config: From 08_MONITORING
    """
    # Identity
    patient_id: str
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    # Current phase
    phase: StatePhase = StatePhase.INITIALIZED
    
    # Disease context
    disease: Optional[str] = None  # "ovarian", "myeloma", etc.
    
    # Agent outputs (populated as agents complete)
    patient_profile: Optional[Dict] = None       # From 01_DATA_EXTRACTION
    biomarker_profile: Optional[Dict] = None     # From 02_BIOMARKER
    resistance_prediction: Optional[Dict] = None # From 03_RESISTANCE
    drug_ranking: Optional[List[Dict]] = None    # From 04_DRUG_EFFICACY
    synthetic_lethality_result: Optional[Dict] = None  # From 14_SYNTHETIC_LETHALITY
    trial_matches: Optional[List[Dict]] = None   # From 05_TRIAL_MATCHING
    nutrition_plan: Optional[Dict] = None        # From 06_NUTRITION
    care_plan: Optional[Dict] = None             # From 07_CARE_PLAN
    monitoring_config: Optional[Dict] = None     # From 08_MONITORING
    
    # Derived data
    mechanism_vector: List[float] = field(default_factory=lambda: [0.0] * 7)
    mutations: List[Dict] = field(default_factory=list)
    
    # Quality & alerts
    data_quality_flags: List[str] = field(default_factory=list)
    alerts: List[Alert] = field(default_factory=list)
    
    # Audit trail
    history: List[StateChange] = field(default_factory=list)
    agent_executions: List[AgentExecution] = field(default_factory=list)
    
    def update(self, field_name: str, value: Any, agent: str, reason: str = ""):
        """Update a field and log the change."""
        old_value = getattr(self, field_name, None)
        setattr(self, field_name, value)
        self.updated_at = datetime.utcnow()
        
        # Log change
        change = StateChange(
            id=str(uuid.uuid4()),
            timestamp=datetime.utcnow(),
            field=field_name,
            old_value=self._summarize(old_value),
            new_value=self._summarize(value),
            agent=agent,
            reason=reason
        )
        self.history.append(change)
    
    def _summarize(self, value: Any) -> Any:
        """Create a summary of a value for logging."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, list):
            return f"List[{len(value)} items]"
        if isinstance(value, dict):
            return f"Dict[{len(value)} keys]"
        if hasattr(value, '__class__'):
            return f"{value.__class__.__name__}"
        return str(value)[:100]
    
    def add_alert(
        self,
        alert_type: str,
        message: str,
        severity: AlertSeverity = AlertSeverity.INFO,
        source_agent: str = "orchestrator"
    ):
        """Add an alert to the state."""
        alert = Alert(
            id=str(uuid.uuid4()),
            alert_type=alert_type,
            message=message,
            severity=severity,
            timestamp=datetime.utcnow(),
            source_agent=source_agent
        )
        self.alerts.append(alert)
    
    def start_agent(self, agent_id: str) -> AgentExecution:
        """Start tracking an agent execution."""
        execution = AgentExecution(
            agent_id=agent_id,
            started_at=datetime.utcnow()
        )
        self.agent_executions.append(execution)
        return execution
    
    def get_completed_agents(self) -> List[str]:
        """Get list of completed agent IDs."""
        return [e.agent_id for e in self.agent_executions if e.status == "complete"]
    
    def get_progress_percent(self) -> int:
        """Calculate pipeline progress percentage."""
        agent_weights = {
            'extraction': 10,
            'biomarker': 15,
            'resistance': 15,
            'drug_efficacy': 20,
            'synthetic_lethality': 10,
            'trial_matching': 15,
            'nutrition': 5,
            'care_plan': 15,
            'monitoring': 5
        }
        
        completed = self.get_completed_agents()
        progress = sum(agent_weights.get(a, 0) for a in completed)
        return min(100, progress)
    
    def to_dict(self) -> Dict:
        """Serialize state to dictionary for API response."""
        return {
            'patient_id': self.patient_id,
            'disease': self.disease,
            'phase': self.phase.value,
            'progress_percent': self.get_progress_percent(),
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat(),
            
            # Agent output availability
            'has_patient_profile': self.patient_profile is not None,
            'has_biomarker_profile': self.biomarker_profile is not None,
            'has_resistance_prediction': self.resistance_prediction is not None,
            'has_drug_ranking': self.drug_ranking is not None,
            'has_synthetic_lethality': self.synthetic_lethality_result is not None,
            'has_trial_matches': self.trial_matches is not None,
            'has_nutrition_plan': self.nutrition_plan is not None,
            'has_care_plan': self.care_plan is not None,
            'has_monitoring_config': self.monitoring_config is not None,
            
            # Derived data
            'mutation_count': len(self.mutations),
            'mechanism_vector': self.mechanism_vector,
            
            # Quality
            'data_quality_flags': self.data_quality_flags,
            'alert_count': len(self.alerts),
            'alerts': [a.to_dict() for a in self.alerts[-5:]],  # Last 5 alerts
            
            # Execution tracking
            'completed_agents': self.get_completed_agents(),
            'history_count': len(self.history)
        }
    
    def to_full_dict(self) -> Dict:
        """Full serialization including all agent outputs."""
        base = self.to_dict()
        base.update({
            'patient_profile': self.patient_profile,
            'biomarker_profile': self.biomarker_profile,
            'resistance_prediction': self.resistance_prediction,
            'drug_ranking': self.drug_ranking,
            'synthetic_lethality_result': self.synthetic_lethality_result,
            'trial_matches': self.trial_matches,
            'nutrition_plan': self.nutrition_plan,
            'care_plan': self.care_plan,
            'monitoring_config': self.monitoring_config,
            'mutations': self.mutations,
            'all_alerts': [a.to_dict() for a in self.alerts],
            'history': [h.to_dict() for h in self.history[-20:]],  # Last 20 changes
            'agent_executions': [e.to_dict() for e in self.agent_executions]
        })
        return base


