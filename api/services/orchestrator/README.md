# 🎛️ Orchestrator Service - Module 10

**Status:** ✅ **COMPLETE**  
**Purpose:** Central patient state management and agent coordination  
**Priority:** 🔴 CRITICAL | **Dependencies:** None | **Consumers:** All agents

---

## 📋 Overview

The Orchestrator Service provides the central coordination layer for the MOAT (Measure of Our Advantage and Trust) patient care pipeline. It manages patient state across all agents, coordinates agent execution, and provides an audit trail for all operations.

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────┐
│         ORCHESTRATOR AGENT               │
│  • Patient state management             │
│  • Agent coordination                   │
│  • Event queue                          │
│  • Audit trail                          │
└───────────────────┬─────────────────────┘
                    │
    ┌───────────────┼───────────────┐
    │               │               │
    ▼               ▼               ▼
┌───────────┐ ┌───────────┐ ┌───────────┐
│ BIOMARKER │ │ RESISTANCE│ │ DRUG      │
│ AGENT     │ │ AGENT     │ │ EFFICACY  │
└───────────┘ └───────────┘ └───────────┘
```

---

## 📁 File Structure

```
api/services/orchestrator/
├── __init__.py              # Package exports
├── state.py                 # PatientState class with audit trail
├── state_store.py           # Persistent storage (file-based, Redis-ready)
├── orchestrator.py          # Main orchestrator class
├── message_bus.py        # Inter-agent communication
└── README.md               # This file
```

---

## 🚀 Core Components

### 1. **PatientState** (`state.py`)

Central state object that tracks:
- Patient identity and metadata
- Current pipeline phase
- All agent outputs (biomarker, resistance, drug ranking, trials, etc.)
- Mechanism vector (7D pathway vector)
- Data quality flags
- Alerts
- Complete audit trail (state changes, agent executions)

**Key Methods:**
- `update(field, value, agent, reason)` - Update state with audit logging
- `add_alert(type, message, severity)` - Add alerts
- `get_progress()` - Calculate pipeline progress (0.0 to 1.0)
- `to_dict()` - Serialize for API responses
- `to_summary()` - Lightweight summary for status checks

### 2. **StateStore** (`state_store.py`)

Persistent storage for patient states:
- File-based storage (JSON files in `data/patient_states/`)
- In-memory caching for performance
- Thread-safe operations
- Automatic directory creation
- **Production-ready:** Easy to swap with Redis/PostgreSQL

**Key Methods:**
- `save(state)` - Persist state to disk
- `get(patient_id)` - Retrieve state by ID
- `get_all()` - List all states
- `delete(patient_id)` - Remove state

### 3. **Orchestrator** (`orchestrator.py`)

Main pipeline coordinator:
- Runs full end-to-end pipeline
- Coordinates all agents (biomarker, resistance, drug efficacy, trial matching, nutrition)
- Handles parallel execution where dependencies allow
- Manages pipeline phases (extracting → analyzing → ranking → matching → planning → monitoring)
- Error handling with graceful degradation
- Event processing (integrated with Module 09)

**Key Methods:**
- `run_full_pipeline(...)` - Execute complete pipeline
- `get_state(patient_id)` - Get current state
- `get_all_states()` - List all states
- `process_event(event_type, data)` - Process incoming events

### 4. **MessageBus** (`message_bus.py`)

Inter-agent communication system:
- Per-agent message queues
- Broadcast messaging
- Timeout support
- Priority handling (future enhancement)

**Key Methods:**
- `register_agent(agent_id, handler)` - Register agent
- `send(message)` - Send message to agent or broadcast
- `receive(agent_id, timeout)` - Receive message
- `process_messages(agent_id)` - Auto-process with handler

---

## 📡 API Endpoints

### `POST /api/orchestrate/full`

Run the complete end-to-end patient care pipeline.

**Request:**
```json
{
  "patient_profile": {
    "disease": "ovarian_cancer_hgs",
    "mutations": [...],
    "biomarker_value": 125.5,
    "biomarker_baseline": 200.0
  },
  "patient_id": "PT-12345",
  "options": {}
}
```

**Response:**
```json
{
  "job_id": "PT-12345",
  "patient_id": "PT-12345",
  "status": "complete",
  "phase": "complete",
  "progress": 1.0,
  "alerts": []
}
```

### `GET /api/orchestrate/status/{patient_id}`

Get current pipeline status.

**Response:**
```json
{
  "patient_id": "PT-12345",
  "phase": "matching",
  "progress": 0.75,
  "updated_at": "2025-01-15T10:30:00Z",
  "alerts": [],
  "care_plan": {...}
}
```

### `GET /api/orchestrate/state/{patient_id}`

Get full patient state (for debugging/admin).

### `POST /api/orchestrate/event`

Process an incoming event (e.g., new lab result).

### `GET /api/orchestrate/states`

List all patient states (for admin/debugging).

---

## 🔄 Pipeline Flow

1. **Phase 1: Data Extraction** (if file provided)
   - Parse NGS PDF, VCF, MAF, etc.
   - Extract mutations, demographics, clinical data

2. **Phase 2: Parallel Analysis**
   - Biomarker analysis (TMB, MSI, HRD)
   - Nutrition planning (can run in parallel)

3. **Phase 3: Resistance Prediction**
   - Requires biomarker profile
   - Uses SAE features from drug efficacy (future)

4. **Phase 4: Drug Ranking**
   - S/P/E framework (Sequence/Pathway/Evidence)
   - Mechanism vector computation
   - Drug ranking with confidence

5. **Phase 5: Trial Matching**
   - Mechanism-based trial matching
   - ClinicalTrials.gov API search
   - Mechanism fit ranking

6. **Phase 6: Care Plan Generation**
   - Aggregate all agent outputs
   - Unified care plan document

7. **Phase 7: Monitoring Configuration**
   - Set up biomarker monitoring
   - Trial monitoring
   - Resistance monitoring

---

## ✅ Integration Status

### ✅ Integrated Agents

- **Biomarker Agent:** `BiomarkerIntelligenceService` - Universal biomarker analysis
- **Resistance Agent:** `ResistanceProphetService` - Early resistance detection (partial)
- **Drug Efficacy Agent:** `EfficacyOrchestrator` - S/P/E framework
- **Trial Matching Agent:** `AutonomousTrialAgent` - Trial search and matching
- **Nutrition Agent:** `DynamicFoodExtractor` - Food/supplement recommendations

### ⏳ Pending Integration

- **Data Extraction Agent:** Module 01 (file parsing)
- **Care Plan Agent:** Module 07 (unified care plan generation)
- **Monitoring Agent:** Module 08 (continuous monitoring)

---

## 🧪 Testing

Unit tests should cover:
- State management (updates, alerts, progress)
- State persistence (save, load, delete)
- Orchestrator pipeline execution
- Message bus communication
- Error handling and graceful degradation

**Target Coverage:** >80%

---

## 📝 Notes

- **File-based storage:** Currently uses JSON files. In production, replace with Redis or PostgreSQL.
- **Agent interfaces:** Agents are called via method reflection. Each agent should expose standard methods.
- **Error handling:** Pipeline continues even if individual agents fail (graceful degradation).
- **Audit trail:** All state changes are logged with agent, timestamp, and reason.
- **Event processing:** Integrated with Module 09 (Trigger System) for automated responses.

---

## 🔗 Related Modules

- **Module 01:** Data Extraction Agent (file parsing)
- **Module 05:** Trial Matching Agent (full implementation)
- **Module 07:** Care Plan Agent (unified care plan)
- **Module 08:** Monitoring Agent (continuous tracking)
- **Module 09:** Trigger System (event-driven automation)

---

**Module Status:** ✅ **COMPLETE**  
**Last Updated:** January 2025



