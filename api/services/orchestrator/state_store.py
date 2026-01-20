"""
State Store - Persistent storage for patient states.

Uses JSON files for simplicity. In production, replace with Redis or PostgreSQL.
"""

from typing import Dict, List, Optional
import json
from pathlib import Path
from datetime import datetime
import asyncio
import logging
import hashlib

from .state import PatientState, StatePhase, Alert, AlertSeverity, StateChange, AgentExecution

logger = logging.getLogger(__name__)


class StateStore:
    """
    Persistent storage for patient states.
    
    Features:
    - In-memory cache for fast reads
    - JSON file persistence for durability
    - Thread-safe operations with asyncio Lock
    - Automatic state reconstruction on load
    
    In production, replace with:
    - Redis for distributed caching
    - PostgreSQL for durable storage
    - Event sourcing for complete audit trail
    """
    
    def __init__(self, storage_dir: str = "data/patient_states"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, PatientState] = {}
        self._lock = asyncio.Lock()
    
    async def save(self, state: PatientState) -> None:
        """Save patient state to storage with versioning."""
        async with self._lock:
            # Update cache
            self._cache[state.patient_id] = state
            
            # Create version identifier (hash of state content)
            state_version = self._version_state(state)
            
            # Persist to file
            file_path = self.storage_dir / f"{state.patient_id}.json"
            data = self._serialize(state)
            data['version'] = state_version
            data['saved_at'] = datetime.utcnow().isoformat()
            
            # Write synchronously (for simplicity - use aiofiles in production)
            try:
                with open(file_path, 'w') as f:
                    json.dump(data, f, indent=2, default=str)
                logger.debug(f"Saved state for patient {state.patient_id} (version: {state_version[:8]})")
            except Exception as e:
                logger.error(f"Failed to save state for {state.patient_id}: {e}")
                raise
    
    async def get(self, patient_id: str) -> Optional[PatientState]:
        """Get patient state by ID with recovery support."""
        # Check cache first
        if patient_id in self._cache:
            return self._cache[patient_id]
        
        # Load from file
        file_path = self.storage_dir / f"{patient_id}.json"
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
            
            state = self._deserialize(data)
            self._cache[patient_id] = state
            logger.debug(f"Loaded state for patient {patient_id} (version: {data.get('version', 'unknown')[:8]})")
            return state
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted state file for {patient_id}: {e}")
            # Try to recover from backup if available
            backup_path = self.storage_dir / f"{patient_id}.json.backup"
            if backup_path.exists():
                logger.info(f"Attempting recovery from backup for {patient_id}")
                try:
                    with open(backup_path, 'r') as f:
                        data = json.load(f)
                    state = self._deserialize(data)
                    self._cache[patient_id] = state
                    return state
                except Exception as backup_error:
                    logger.error(f"Backup recovery failed for {patient_id}: {backup_error}")
            return None
        except Exception as e:
            logger.error(f"Failed to load state for {patient_id}: {e}")
            return None
    
    async def get_all(self, limit: int = 50, phase: str = None) -> List[PatientState]:
        """Get all patient states with optional filtering."""
        states = []
        
        for file_path in list(self.storage_dir.glob("*.json"))[:limit * 2]:
            patient_id = file_path.stem
            state = await self.get(patient_id)
            
            if state:
                # Apply phase filter if specified
                if phase and state.phase.value != phase:
                    continue
                states.append(state)
                
                if len(states) >= limit:
                    break
        
        # Sort by updated_at descending
        states.sort(key=lambda s: s.updated_at, reverse=True)
        return states[:limit]
    
    async def delete(self, patient_id: str) -> bool:
        """Delete patient state."""
        async with self._lock:
            # Remove from cache
            if patient_id in self._cache:
                del self._cache[patient_id]
            
            # Remove file
            file_path = self.storage_dir / f"{patient_id}.json"
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted state for patient {patient_id}")
                return True
            return False
    
    async def exists(self, patient_id: str) -> bool:
        """Check if patient state exists."""
        if patient_id in self._cache:
            return True
        
        file_path = self.storage_dir / f"{patient_id}.json"
        return file_path.exists()
    
    def _serialize(self, state: PatientState) -> Dict:
        """Serialize state to JSON-compatible dict."""
        return {
            'patient_id': state.patient_id,
            'disease': state.disease,
            'phase': state.phase.value,
            'created_at': state.created_at.isoformat(),
            'updated_at': state.updated_at.isoformat(),
            
            # Agent outputs
            'patient_profile': state.patient_profile,
            'biomarker_profile': state.biomarker_profile,
            'resistance_prediction': state.resistance_prediction,
            'drug_ranking': state.drug_ranking,
            'trial_matches': state.trial_matches,
            'nutrition_plan': state.nutrition_plan,
            'care_plan': state.care_plan,
            'monitoring_config': state.monitoring_config,
            
            # Derived data
            'mechanism_vector': state.mechanism_vector,
            'mutations': state.mutations,
            
            # Quality & alerts
            'data_quality_flags': state.data_quality_flags,
            'alerts': [self._serialize_alert(a) for a in state.alerts],
            
            # Audit trail
            'history': [h.to_dict() for h in state.history[-100:]],  # Keep last 100
            'agent_executions': [e.to_dict() for e in state.agent_executions]
        }
    
    def _serialize_alert(self, alert: Alert) -> Dict:
        return {
            'id': alert.id,
            'alert_type': alert.alert_type,
            'message': alert.message,
            'severity': alert.severity.value,
            'timestamp': alert.timestamp.isoformat(),
            'source_agent': alert.source_agent,
            'acknowledged': alert.acknowledged
        }
    
    def _deserialize(self, data: Dict) -> PatientState:
        """Deserialize JSON data to PatientState."""
        state = PatientState(
            patient_id=data['patient_id']
        )
        
        state.disease = data.get('disease')
        state.phase = StatePhase(data['phase'])
        state.created_at = datetime.fromisoformat(data['created_at'])
        state.updated_at = datetime.fromisoformat(data['updated_at'])
        
        # Agent outputs
        state.patient_profile = data.get('patient_profile')
        state.biomarker_profile = data.get('biomarker_profile')
        state.resistance_prediction = data.get('resistance_prediction')
        state.drug_ranking = data.get('drug_ranking')
        state.trial_matches = data.get('trial_matches')
        state.nutrition_plan = data.get('nutrition_plan')
        state.care_plan = data.get('care_plan')
        state.monitoring_config = data.get('monitoring_config')
        
        # Derived data
        state.mechanism_vector = data.get('mechanism_vector', [0.0] * 7)
        state.mutations = data.get('mutations', [])
        
        # Quality & alerts
        state.data_quality_flags = data.get('data_quality_flags', [])
        state.alerts = [self._deserialize_alert(a) for a in data.get('alerts', [])]
        
        # Audit trail (simplified - just keep count)
        state.history = [self._deserialize_history(h) for h in data.get('history', [])]
        state.agent_executions = [self._deserialize_execution(e) for e in data.get('agent_executions', [])]
        
        return state
    
    def _deserialize_alert(self, data: Dict) -> Alert:
        return Alert(
            id=data['id'],
            alert_type=data['alert_type'],
            message=data['message'],
            severity=AlertSeverity(data['severity']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            source_agent=data['source_agent'],
            acknowledged=data.get('acknowledged', False)
        )
    
    def _deserialize_history(self, data: Dict) -> StateChange:
        return StateChange(
            id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp']),
            field=data['field'],
            old_value=data['old_value'],
            new_value=data['new_value'],
            agent=data['agent'],
            reason=data['reason']
        )
    
    def _deserialize_execution(self, data: Dict) -> AgentExecution:
        execution = AgentExecution(
            agent_id=data['agent_id'],
            started_at=datetime.fromisoformat(data['started_at'])
        )
        if data.get('completed_at'):
            execution.completed_at = datetime.fromisoformat(data['completed_at'])
        execution.status = data.get('status', 'running')
        execution.error = data.get('error')
        execution.output_summary = data.get('output_summary')
        execution.duration_ms = data.get('duration_ms')
        return execution
    
    def _version_state(self, state: PatientState) -> str:
        """Create version identifier for state (hash of content)."""
        # Serialize state to get consistent representation
        data = self._serialize(state)
        # Create hash of serialized data
        state_str = json.dumps(data, sort_keys=True, default=str)
        return hashlib.sha256(state_str.encode()).hexdigest()


# Singleton instance
_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    """Get the global state store instance."""
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store



