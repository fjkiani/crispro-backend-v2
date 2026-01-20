# Legacy Endpoint Analysis: `/api/complete_care/v2` vs `/api/orchestrate/full`

**Date:** January 2025  
**Purpose:** Determine what to do with the legacy `/api/complete_care/v2` endpoint

---

## 🔍 Current State

### **Two Orchestrator Systems Running in Parallel**

1. **`/api/orchestrate/full`** (MOAT Orchestrator - NEWER)
   - **File:** `api/routers/orchestrate.py`
   - **Architecture:** Agent-based with `PatientState` dataclass
   - **Request Schema:** `OrchestratePipelineRequest` (flat: `disease` + `mutations[]`)
   - **Response Schema:** `OrchestratePipelineResponse` (structured agent outputs)
   - **Status:** ✅ Fully implemented, tested, includes `nutrition_plan` and `synthetic_lethality_result`
   - **Used By:** `OrchestratorDashboard.jsx` (new frontend)

2. **`/api/complete_care/v2`** (Universal Complete Care - LEGACY)
   - **File:** `api/routers/complete_care_universal.py`
   - **Architecture:** Service-based HTTP orchestration
   - **Request Schema:** `CompleteCareUniversalRequest` (nested: `patient_profile`)
   - **Response Schema:** `CompleteCareUniversalResponse` (service outputs)
   - **Status:** ✅ Fully implemented, actively maintained
   - **Used By:** `UniversalCompleteCare.jsx` (legacy frontend)

---

## 📊 Key Differences

### **Request Format**

**Legacy (`/api/complete_care/v2`):**
```json
{
  "patient_profile": {
    "demographics": {...},
    "disease": {"type": "ovarian", "stage": "IVB"},
    "treatment": {"line": "first-line"},
    "tumor_context": {"somatic_mutations": [...]},
    "biomarkers": {"ca125_value": 2842}
  },
  "include_trials": true,
  "include_soc": true,
  "include_wiwfm": true
}
```

**New (`/api/orchestrate/full`):**
```json
{
  "disease": "ovarian",
  "mutations": [
    {"gene": "BRCA1", "hgvs_p": "C64R", "chrom": "17", "pos": 43044295, "ref": "T", "alt": "G"}
  ],
  "treatment_line": 1,
  "prior_therapies": [],
  "current_regimen": "carboplatin+paclitaxel"
}
```

### **Response Format**

**Legacy Response:**
```json
{
  "trials": {...},
  "soc_recommendation": {...},
  "biomarker_intelligence": {...},
  "wiwfm": {"drugs": [...]},
  "resistance_prediction": {...},
  "resistance_playbook": {...},
  "next_test_recommender": {...},
  "hint_tiles": [...],
  "mechanism_map": {...}
}
```

**New Response:**
```json
{
  "biomarker_profile": {...},
  "resistance_prediction": {...},
  "drug_ranking": [...],
  "trial_matches": [...],
  "care_plan": {...},
  "nutrition_plan": {...},
  "synthetic_lethality_result": {...},
  "mechanism_vector": [0.5, 0.2, 0.2, 0.3, 0.0, 0.0, 0.0]
}
```

### **Architecture Differences**

| Aspect | Legacy (`/api/complete_care/v2`) | New (`/api/orchestrate/full`) |
|--------|----------------------------------|-------------------------------|
| **Orchestration** | HTTP-based service calls | Agent-based with `PatientState` |
| **State Management** | Stateless (each call independent) | Stateful (`PatientState` persisted) |
| **Error Handling** | Per-service try/catch | Centralized in orchestrator |
| **Provenance** | Per-service tracking | Unified `run_id` across pipeline |
| **File Upload** | Not supported | ✅ Supported (FormData) |
| **Status Polling** | Not supported | ✅ Supported (`/api/orchestrate/status/{patient_id}`) |
| **Agent Outputs** | Service responses | Structured `PatientState` fields |

---

## 🎯 Recommendation: **GRADUAL MIGRATION STRATEGY**

### **Phase 1: Keep Both (Current State)** ✅ **RECOMMENDED**

**Rationale:**
- Legacy endpoint is **actively used** by `UniversalCompleteCare.jsx`
- Legacy endpoint is **fully functional** and maintained
- New endpoint is **better architecture** but requires frontend migration
- **No breaking changes** - both endpoints work

**Action Items:**
1. ✅ Keep `/api/complete_care/v2` operational (no changes)
2. ✅ Continue maintaining both endpoints
3. ✅ Document which endpoint to use for new features

### **Phase 2: Frontend Migration (Next Step)**

**Goal:** Migrate `UniversalCompleteCare.jsx` to use `/api/orchestrate/full`

**Benefits:**
- ✅ Unified architecture (one orchestrator system)
- ✅ File upload support
- ✅ Status polling support
- ✅ Better provenance tracking
- ✅ More structured agent outputs

**Implementation:**
1. Use `orchestratorMapper.js` (already created) to transform data
2. Update `UniversalCompleteCare.jsx` to call `/api/orchestrate/full`
3. Test thoroughly with real patient data
4. Keep legacy endpoint as fallback during migration

### **Phase 3: Deprecation (Future)**

**Timeline:** After frontend migration is complete and validated

**Steps:**
1. Add deprecation warning to `/api/complete_care/v2` responses
2. Monitor usage (log endpoint calls)
3. Set deprecation date (e.g., 3 months notice)
4. Remove endpoint after migration complete

---

## 🧪 Testing Strategy

### **Test Both Endpoints**

**Test File:** `tests/test_both_orchestrators.py`

**Test Cases:**
1. ✅ Legacy endpoint returns expected format
2. ✅ New endpoint returns expected format
3. ✅ Both endpoints handle same patient profile
4. ✅ Response fields match frontend expectations
5. ✅ Error handling works correctly

### **Validation Script**

**File:** `tests/validate_orchestrator_migration.py`

**Purpose:** Validate that new endpoint can replace legacy endpoint

**Checks:**
- All legacy response fields have equivalents in new response
- Data transformation functions work correctly
- Frontend components receive expected data format

---

## 📋 Decision Matrix

| Criteria | Legacy (`/api/complete_care/v2`) | New (`/api/orchestrate/full`) | Winner |
|----------|----------------------------------|-------------------------------|--------|
| **Architecture** | Service-based HTTP | Agent-based with State | ✅ New |
| **File Upload** | ❌ Not supported | ✅ Supported | ✅ New |
| **Status Polling** | ❌ Not supported | ✅ Supported | ✅ New |
| **Provenance** | Per-service | Unified `run_id` | ✅ New |
| **Frontend Usage** | ✅ Active (`UniversalCompleteCare.jsx`) | ✅ Active (`OrchestratorDashboard.jsx`) | ⚖️ Tie |
| **Maintenance** | ✅ Maintained | ✅ Maintained | ⚖️ Tie |
| **Data Format** | Nested `patient_profile` | Flat `disease` + `mutations` | ⚖️ Preference |
| **Agent Outputs** | Service responses | Structured `PatientState` | ✅ New |

**Overall Winner:** ✅ **New (`/api/orchestrate/full`)** - Better architecture, more features

---

## ✅ Final Recommendation

### **IMMEDIATE ACTION: Keep Both Endpoints**

1. ✅ **No breaking changes** - Both endpoints remain operational
2. ✅ **Frontend migration** - Use `orchestratorMapper.js` to migrate `UniversalCompleteCare.jsx`
3. ✅ **Testing** - Validate both endpoints work correctly
4. ✅ **Documentation** - Document which endpoint to use for new features

### **NEXT STEP: Migrate Frontend**

1. Update `UniversalCompleteCare.jsx` to use `/api/orchestrate/full`
2. Use `orchestratorMapper.js` for data transformation
3. Test thoroughly with real patient data
4. Keep legacy endpoint as fallback

### **FUTURE: Deprecate Legacy**

1. After frontend migration validated (3+ months)
2. Add deprecation warnings
3. Monitor usage
4. Remove endpoint after migration complete

---

## 🔧 Implementation Checklist

- [x] Backend: Both endpoints operational
- [x] Backend: New endpoint includes `nutrition_plan` and `synthetic_lethality_result`
- [x] Frontend: `orchestratorMapper.js` created for data transformation
- [ ] Frontend: `UniversalCompleteCare.jsx` migrated to new endpoint
- [ ] Testing: Both endpoints validated with real patient data
- [ ] Documentation: Migration guide created
- [ ] Monitoring: Usage tracking for both endpoints

---

**Status:** ✅ **RECOMMENDATION COMPLETE** - Keep both endpoints, migrate frontend gradually
