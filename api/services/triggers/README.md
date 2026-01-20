# 🔔 Trigger System - Module 09

**Status:** ✅ **COMPLETE**  
**Priority:** 🟡 HIGH | **Dependencies:** All | **Consumers:** Notifications, Alerts

---

## 📋 Overview

The Trigger System provides automated event detection and response. It evaluates conditions against patient data and executes automated actions when triggers are matched.

---

## 🏗️ Architecture

```
TriggerEngine
    │
    ├── Condition Evaluator
    │   ├── TMB >= 10.0
    │   ├── CA-125 elevation
    │   ├── MSI-H detection
    │   └── Trial match score
    │
    ├── Action Handlers
    │   ├── notify_oncologist
    │   ├── run_resistance_analysis
    │   ├── re_match_trials
    │   └── escalate_urgent
    │
    └── Audit Logger
        └── Full action trail
```

---

## 📁 File Structure

```
api/services/triggers/
├── __init__.py
├── trigger_engine.py          # Main trigger engine
├── models.py                   # TriggerResult, TriggerSeverity
└── README.md                   # This file
```

---

## 🚀 Core Components

### **TriggerEngine** (`trigger_engine.py`)

Main trigger engine that evaluates events:

**Key Methods:**
- `evaluate(event_type, data, patient_state)` - Main evaluation method
- `_evaluate_condition()` - Evaluate trigger conditions
- Action handlers (13 handlers implemented)

**Process:**
1. Load trigger definition for event_type
2. Evaluate condition against patient data
3. If condition matched, execute actions
4. Log all actions to audit trail
5. Return TriggerResult

### **Trigger Definitions**

8 trigger types implemented:

1. **resistance_detected** - CA-125 elevation or MAPK mutation in ctDNA
2. **tmb_high_detected** - TMB >= 10.0
3. **msi_high_detected** - MSI-H status
4. **hrd_score_received** - HRD score available
5. **new_trial_available** - High-scoring recruiting trial
6. **adverse_event_reported** - CTCAE grade >= 2
7. **treatment_response** - RECIST assessment received
8. **ngs_results_received** - New NGS report

### **Action Handlers**

13 action handlers implemented:

- `notify_oncologist` - Send notification
- `run_resistance_analysis` - Trigger resistance analysis
- `suggest_alternatives` - Suggest alternative treatments
- `re_match_trials` - Re-match clinical trials
- `update_io_eligibility` - Update IO eligibility
- `escalate_urgent` - Escalate to urgent care
- `add_to_dashboard` - Add to dashboard
- `log_event` - Log to audit trail
- `suggest_supportive_care` - Suggest supportive care
- `flag_lynch_screening` - Flag for Lynch screening
- `confirm_parp_eligibility` - Confirm PARP eligibility
- `recalculate_biomarkers` - Recalculate biomarkers
- `update_resistance_prediction` - Update resistance prediction

---

## 📊 Data Models

### **TriggerResult**

```python
@dataclass
class TriggerResult:
    trigger_id: str
    event_type: str
    timestamp: datetime
    condition_matched: bool
    actions_taken: List[str]
    notifications_sent: List[Dict]
    escalations: List[Dict]
    audit_log: List[Dict]
    severity: TriggerSeverity
```

---

## 🔗 Integration

### **Orchestrator Integration**

The trigger engine is wired to the orchestrator in `orchestrator.py`:

```python
async def process_event(self, event_type: str, data: Dict, patient_id: str):
    from ..triggers import TriggerEngine
    
    state = await self.get_state(patient_id)
    trigger_engine = TriggerEngine()
    result = await trigger_engine.evaluate(event_type, data, state)
    
    if result and result.condition_matched:
        state.add_alert(...)
        state.trigger_history.append(result.to_dict())
```

### **API Integration**

The trigger system is exposed via the orchestrator API:

```yaml
POST /api/orchestrate/event
{
  "event_type": "tmb_high_detected",
  "patient_id": "PT-12345",
  "data": {
    "tmb": 12.5
  }
}
```

---

## ✅ Features

- **8 Trigger Types**: Resistance, TMB-H, MSI-H, HRD, trials, AEs, response, NGS
- **13 Action Handlers**: Comprehensive action library
- **Condition Evaluation**: Flexible condition matching
- **Audit Trail**: Full logging of all actions
- **Escalation Support**: Automatic escalation rules
- **Notification System**: Integrated notifications

---

## 🧪 Testing

**Unit Tests Needed:**
- Condition evaluation
- Action handler execution
- Trigger matching
- Integration with orchestrator

**Target Coverage:** >80%

---

## 📝 Usage Example

```python
from api.services.triggers import TriggerEngine
from api.services.orchestrator.state import PatientState

engine = TriggerEngine()

# Evaluate TMB-H trigger
result = await engine.evaluate(
    event_type='tmb_high_detected',
    data={'tmb': 12.5},
    patient_state=state
)

if result and result.condition_matched:
    print(f"Trigger matched! Actions: {result.actions_taken}")
    print(f"Notifications: {len(result.notifications_sent)}")
```

---

**Module Status:** ✅ **COMPLETE**  
**Last Updated:** January 2025  
**Owner:** Auto (JR Agent D)


