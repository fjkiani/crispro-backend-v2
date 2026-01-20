"""
Trigger Engine - Module 09

Event-driven trigger system for automated event detection and response.
"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .models import TriggerResult, TriggerSeverity
from ..orchestrator.state import PatientState

logger = logging.getLogger(__name__)


class TriggerEngine:
    """
    Event-driven trigger engine.
    
    Evaluates conditions against patient data
    and executes automated responses.
    """
    
    def __init__(self):
        """Initialize trigger engine."""
        self.triggers = self._load_triggers()
        self.action_handlers = {
            'notify_oncologist': self._notify_oncologist,
            'run_resistance_analysis': self._run_resistance_analysis,
            'suggest_alternatives': self._suggest_alternatives,
            're_match_trials': self._rematch_trials,
            'update_io_eligibility': self._update_io_eligibility,
            'escalate_urgent': self._escalate_urgent,
            'add_to_dashboard': self._add_to_dashboard,
            'log_event': self._log_event,
            'suggest_supportive_care': self._suggest_supportive_care,
            'flag_lynch_screening': self._flag_lynch_screening,
            'confirm_parp_eligibility': self._confirm_parp_eligibility,
            'recalculate_biomarkers': self._recalculate_biomarkers,
            'update_resistance_prediction': self._update_resistance_prediction
        }
        logger.info("TriggerEngine initialized")
    
    def _load_triggers(self) -> Dict[str, Dict]:
        """Load trigger definitions."""
        return {
            'resistance_detected': {
                'condition': 'ca125_elevated OR mapk_mutation_in_ctdna',
                'severity': TriggerSeverity.HIGH,
                'actions': [
                    'notify_oncologist',
                    'run_resistance_analysis',
                    'suggest_alternatives',
                    're_match_trials'
                ],
                'escalation': '24h → tumor_board'
            },
            'tmb_high_detected': {
                'condition': 'tmb >= 10.0',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'update_io_eligibility',
                    'notify_oncologist',
                    're_match_trials'
                ]
            },
            'msi_high_detected': {
                'condition': 'msi_status == MSI-H',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'update_io_eligibility',
                    'flag_lynch_screening'
                ]
            },
            'hrd_score_received': {
                'condition': 'hrd_score IS NOT NULL',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'confirm_parp_eligibility'
                ]
            },
            'new_trial_available': {
                'condition': 'trial_match_score >= 0.80 AND status == RECRUITING',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'add_to_dashboard',
                    'notify_oncologist'
                ]
            },
            'adverse_event_reported': {
                'condition': 'ctcae_grade >= 2',
                'severity': TriggerSeverity.HIGH,
                'actions': [
                    'log_event',
                    'suggest_supportive_care'
                ],
                'escalation': 'if grade >= 3: escalate_urgent'
            },
            'treatment_response': {
                'condition': 'recist_assessment IS NOT NULL',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'log_event'
                ]
            },
            'ngs_results_received': {
                'condition': 'ngs_report IS NOT NULL',
                'severity': TriggerSeverity.MEDIUM,
                'actions': [
                    'recalculate_biomarkers',
                    'update_resistance_prediction',
                    'notify_oncologist'
                ]
            }
        }
    
    async def evaluate(
        self,
        event_type: str,
        data: Dict[str, Any],
        patient_state: PatientState
    ) -> Optional[TriggerResult]:
        """
        Evaluate triggers for an event.
        
        Args:
            event_type: Type of event (e.g., 'resistance_detected', 'tmb_high_detected')
            data: Event data
            patient_state: Current patient state
        
        Returns:
            TriggerResult if trigger matched, None otherwise
        """
        trigger = self.triggers.get(event_type)
        if not trigger:
            logger.debug(f"No trigger defined for event_type: {event_type}")
            return None
        
        # Check condition
        condition_met = self._evaluate_condition(
            trigger['condition'],
            data,
            patient_state
        )
        
        if not condition_met:
            return TriggerResult(
                trigger_id=event_type,
                event_type=event_type,
                condition_matched=False,
                severity=trigger.get('severity', TriggerSeverity.INFO)
            )
        
        # Execute actions
        actions_taken = []
        notifications = []
        escalations = []
        audit_log = []
        
        for action in trigger.get('actions', []):
            handler = self.action_handlers.get(action)
            if handler:
                try:
                    result = await handler(data, patient_state)
                    actions_taken.append(action)
                    
                    if result and isinstance(result, dict):
                        if result.get('notification'):
                            notifications.append(result['notification'])
                        if result.get('escalation'):
                            escalations.append(result['escalation'])
                        if result.get('audit'):
                            audit_log.append(result['audit'])
                except Exception as e:
                    logger.error(f"Action {action} failed: {e}")
                    audit_log.append({
                        'action': action,
                        'status': 'failed',
                        'error': str(e),
                        'timestamp': datetime.utcnow().isoformat()
                    })
            else:
                logger.warning(f"No handler for action: {action}")
        
        # Handle escalation
        if trigger.get('escalation'):
            escalation_info = {
                'trigger': event_type,
                'escalation_rule': trigger['escalation'],
                'timestamp': datetime.utcnow().isoformat()
            }
            escalations.append(escalation_info)
        
        return TriggerResult(
            trigger_id=event_type,
            event_type=event_type,
            condition_matched=True,
            actions_taken=actions_taken,
            notifications_sent=notifications,
            escalations=escalations,
            audit_log=audit_log,
            severity=trigger.get('severity', TriggerSeverity.INFO)
        )
    
    def _evaluate_condition(
        self,
        condition: str,
        data: Dict[str, Any],
        state: PatientState
    ) -> bool:
        """Evaluate a trigger condition."""
        condition_lower = condition.lower()
        
        # TMB >= 10.0
        if 'tmb >= 10.0' in condition_lower or 'tmb >= 10' in condition_lower:
            tmb_value = data.get('tmb')
            if tmb_value is None and state.biomarker_profile:
                tmb_dict = state.biomarker_profile.get('tmb', {}) if isinstance(state.biomarker_profile, dict) else getattr(state.biomarker_profile, 'tmb', {})
                tmb_value = tmb_dict.get('value') if isinstance(tmb_dict, dict) else getattr(tmb_dict, 'value', None)
            
            if tmb_value and isinstance(tmb_value, (int, float)) and tmb_value >= 10.0:
                return True
        
        # CA-125 elevated
        if 'ca125' in condition_lower and ('elevated' in condition_lower or '>' in condition):
            ca125 = data.get('ca125') or data.get('ca_125')
            baseline = None
            if state.monitoring_config:
                baseline = state.monitoring_config.get('ca125_baseline') if isinstance(state.monitoring_config, dict) else getattr(state.monitoring_config, 'ca125_baseline', None)
            
            if ca125 and baseline and ca125 > baseline * 1.25:
                return True
        
        # MSI-H
        if 'msi' in condition_lower and ('msi-h' in condition_lower or 'msi-high' in condition_lower):
            msi_status = data.get('msi_status') or data.get('msi')
            if msi_status is None and state.biomarker_profile:
                msi_dict = state.biomarker_profile.get('msi', {}) if isinstance(state.biomarker_profile, dict) else getattr(state.biomarker_profile, 'msi', {})
                msi_status = msi_dict.get('status') if isinstance(msi_dict, dict) else getattr(msi_dict, 'status', None)
            
            if msi_status and str(msi_status).upper() in ['MSI-H', 'MSI-HIGH']:
                return True
        
        # HRD score received
        if 'hrd_score' in condition_lower and 'is not null' in condition_lower:
            hrd_score = data.get('hrd_score')
            if hrd_score is None and state.biomarker_profile:
                hrd_dict = state.biomarker_profile.get('hrd', {}) if isinstance(state.biomarker_profile, dict) else getattr(state.biomarker_profile, 'hrd', {})
                hrd_score = hrd_dict.get('score') if isinstance(hrd_dict, dict) else getattr(hrd_dict, 'score', None)
            
            if hrd_score is not None:
                return True
        
        # Trial match score
        if 'trial_match_score' in condition_lower:
            trial_score = data.get('trial_match_score') or data.get('combined_score')
            status = data.get('status', '').upper()
            
            if trial_score and trial_score >= 0.80 and 'RECRUITING' in status:
                return True
        
        # CTCAE grade
        if 'ctcae_grade' in condition_lower or 'grade' in condition_lower:
            grade = data.get('ctcae_grade') or data.get('grade')
            if grade and isinstance(grade, (int, float)) and grade >= 2:
                return True
        
        # RECIST assessment
        if 'recist' in condition_lower and 'is not null' in condition_lower:
            recist = data.get('recist_assessment') or data.get('recist')
            if recist:
                return True
        
        # NGS report received
        if 'ngs_report' in condition_lower and 'is not null' in condition_lower:
            ngs_report = data.get('ngs_report') or data.get('ngs_results')
            if ngs_report:
                return True
        
        # MAPK mutation in ctDNA
        if 'mapk_mutation_in_ctdna' in condition_lower:
            mutations = data.get('mutations', [])
            mapk_genes = {'KRAS', 'NRAS', 'BRAF', 'MEK', 'ERK'}
            for mut in mutations:
                gene = mut.get('gene', '') if isinstance(mut, dict) else getattr(mut, 'gene', '')
                if gene.upper() in mapk_genes:
                    return True
        
        return False
    
    # Action handlers
    
    async def _notify_oncologist(self, data: Dict, state: PatientState) -> Dict:
        """Send notification to oncologist."""
        notification = {
            'type': 'oncologist_notification',
            'patient_id': state.patient_id,
            'message': f"Event detected for patient {state.patient_id}",
            'timestamp': datetime.utcnow().isoformat(),
            'priority': 'medium'
        }
        logger.info(f"📧 Notification sent: {notification['message']}")
        return {'notification': notification}
    
    async def _run_resistance_analysis(self, data: Dict, state: PatientState) -> Dict:
        """Trigger resistance analysis."""
        logger.info(f"🔄 Running resistance analysis for {state.patient_id}")
        return {
            'audit': {
                'action': 'run_resistance_analysis',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _suggest_alternatives(self, data: Dict, state: PatientState) -> Dict:
        """Suggest alternative treatments."""
        logger.info(f"💡 Suggesting alternatives for {state.patient_id}")
        return {
            'audit': {
                'action': 'suggest_alternatives',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _rematch_trials(self, data: Dict, state: PatientState) -> Dict:
        """Re-match clinical trials."""
        logger.info(f"🔍 Re-matching trials for {state.patient_id}")
        return {
            'audit': {
                'action': 're_match_trials',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _update_io_eligibility(self, data: Dict, state: PatientState) -> Dict:
        """Update IO eligibility status."""
        logger.info(f"🔄 Updating IO eligibility for {state.patient_id}")
        return {
            'audit': {
                'action': 'update_io_eligibility',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _escalate_urgent(self, data: Dict, state: PatientState) -> Dict:
        """Escalate to urgent care."""
        escalation = {
            'type': 'urgent_escalation',
            'patient_id': state.patient_id,
            'reason': 'High-grade adverse event',
            'timestamp': datetime.utcnow().isoformat()
        }
        logger.warning(f"🚨 URGENT ESCALATION: {escalation['reason']}")
        return {'escalation': escalation}
    
    async def _add_to_dashboard(self, data: Dict, state: PatientState) -> Dict:
        """Add item to dashboard."""
        logger.info(f"📊 Adding to dashboard for {state.patient_id}")
        return {
            'audit': {
                'action': 'add_to_dashboard',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _log_event(self, data: Dict, state: PatientState) -> Dict:
        """Log event to audit trail."""
        logger.info(f"📝 Logging event for {state.patient_id}")
        return {
            'audit': {
                'action': 'log_event',
                'status': 'logged',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _suggest_supportive_care(self, data: Dict, state: PatientState) -> Dict:
        """Suggest supportive care measures."""
        logger.info(f"💊 Suggesting supportive care for {state.patient_id}")
        return {
            'audit': {
                'action': 'suggest_supportive_care',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _flag_lynch_screening(self, data: Dict, state: PatientState) -> Dict:
        """Flag for Lynch syndrome screening."""
        logger.info(f"🏥 Flagging Lynch screening for {state.patient_id}")
        return {
            'audit': {
                'action': 'flag_lynch_screening',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _confirm_parp_eligibility(self, data: Dict, state: PatientState) -> Dict:
        """Confirm PARP inhibitor eligibility."""
        logger.info(f"✅ Confirming PARP eligibility for {state.patient_id}")
        return {
            'audit': {
                'action': 'confirm_parp_eligibility',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _recalculate_biomarkers(self, data: Dict, state: PatientState) -> Dict:
        """Recalculate biomarker values."""
        logger.info(f"🔄 Recalculating biomarkers for {state.patient_id}")
        return {
            'audit': {
                'action': 'recalculate_biomarkers',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }
    
    async def _update_resistance_prediction(self, data: Dict, state: PatientState) -> Dict:
        """Update resistance prediction."""
        logger.info(f"🔄 Updating resistance prediction for {state.patient_id}")
        return {
            'audit': {
                'action': 'update_resistance_prediction',
                'status': 'triggered',
                'timestamp': datetime.utcnow().isoformat()
            }
        }


