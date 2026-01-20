# Frontend Deliverables for Plumber (Testing Phase)

**Date:** 2026-01-11  
**Status:** ⚠️ **PLUMBER TESTING - FRONTEND WORK NEEDED**  
**Scope:** What needs to be built on the frontend so Ayesha can see all MOAT capabilities

---

## ✅ COMPLETED (Zo just shipped)

1. **IO Safest Selection** ✅
   - Backend: `api/services/io_safest_selection_service.py`
   - Frontend: `AyeshaCompleteCare.jsx` requests `include_io_selection=true`
   - Frontend: `IOSafestSelectionCard.jsx` renders results
   - Status: **SHIPPED (RUO)**

2. **Essentiality Scores** ✅
   - Backend: `api/routers/insights.py` → `/api/insights/predict_gene_essentiality`
   - Frontend: `AyeshaCompleteCare.jsx` calls endpoint for MBD4/TP53
   - Frontend: `EssentialityScoreDisplay.jsx` renders results
   - Status: **WIRED** (audit needs update)

3. **PGx Safety** ✅ `pgx_care_plan_integration.py` → adds `pgx_screening` to drugs
   - Frontend: `DrugRankingPanel.jsx` renders `drug.pgx_screening` block
   - Status: **WIRED** (audit needs update)

---

## ❌ REMAINING ORPHANED (Backend ✅, Frontend ❌)

### 1. Synthetic Lethality (MBD4+TP53→DDR)

**Backend:** ✅ `api/routers/guidance.py` → `POST /api/guidance/synthetic_lethality`  
**Status:** ORPHANED (never called from frontend)

**Frontend Deliverable:**

**File:** `oncology-frontend/src/pages/AyeshaCompleteCare.jsx`

**Task:** Add API call in `handleGeneratePlan` function (after existing `complete_care_v2` call):

```javascript
// PLUMBER TASK 3: Call Synthetic Lethality endpoint
let syntheticLethalityResult = null;
try {
  const slMutations = [];
  // Add MBD4 from germline
  const mbd4Mutation = patientProfile.germline?.mutations?.find(m => m.gene === "MBD4");
  if (mbd4Mutation) {
    slMutations.push({
      gene: mbd4Mutation.gene,
      hgvs_p: mbd4Mutation.protein_change || null
    });
  }
  // Add Tic (IHC evidence)
  const tp53Mutation = patientProfile.tumor_context?.somatic_mutations?.find(m => m.gene === "TP53");
  if (tp53Mutation) {
    slMutations.push({ gene: tp53Mutation.gene });
  }

  if (slMutations.length > 0) {
    const slResponse = await fetch(`${import.meta.env.VITE_API_ROOT}/api/guidance/synthetic_lethality`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        disease: patientProfile.disease?.type || 'ovarian_cancer_hgs',
        mutations: slMutations,
        api_base: import.meta.env.VITE_API_ROOT || 'http://localhost:8000'
      })
    });
    
    if (slResponse.ok) {
      syntheticLethalityResult = await slResponse.json();
      console.log('[AyeshaCompleteCare] Synthetic Lethality result:', syntheticLethalityResult);
    }
  }
} catch (err) {
  console.error('[AyeshaCompleteCare] Synthetic Lethality call failed:', err);
}
```

**Task:** Add to `transformedData`:
```javascript
const transformedData = {
  ...data,
  synthetic_lethality: syntheticLethalityResult,  // PLUMBER TASK 3
  // ... rest
};
```

**Task:** Render in JSX (add after Mechanism Map section):
```jsx
{/* Synthetic Lethality Analysis */}
{result.synthetic_lethality && (
  <Box sx={{ mb: 3 }}>
    <SyntheticLethalityCard 
      slData={result.synthetic_lethality}
      patientGenes={['MBD4', 'TP53']}
    />
  </Box>
)}
```

**Component:** Create `oncology-frontend/src/components/ayesha/SyntheticLethalityCard.jsx` (see PLUMBER TASK 8 template in MOAT_CAPABILITY_AUDIT.md lines 756-809)

**Priority:** P1 - HIGH

---

### 2. VUS Resolution (PDGFRA p.S755P)

**Backend:** ✅ `api/routers/vus.py` → `POST /api/vus/identify`  
**Status:** ORPHANED (never called from frontend)

**Frontend Deliverable:**

**File:** `oncology-frontend/src/pages/AyeshaCompleteCare.jsx`

**Task:** Add API call in `handleGeneratePlan` (after VUS loop - **ALREADY EXISTS** but verify it's working):

```javascript
// PLUMBER TASK 4: Call VUS Resolution for PDGFRA
let vusResults = {};
t vusMutations = patientProfile.germline?.mutations?.filter(m => m.classification === 'VUS') || [];
for (const vus of vusMutations) {
  try {
    const vusResponse = await fetch(`${import.meta.env.VITE_API_ROOT}/api/vus/identify`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        variant: {
          gene: vus.gene,
          hgvs_c: vus.variant || null,
          hgvs_p: vus.protein_change || null
        }
      })
    });
    
    if (vusResponse.ok) {
      vusResults[vus.gene] = await vusResponse.json();
    }
  } catch (err) {
    console.error(`[AyeshaCompleteCare] VUS Resolution call failed for ${vus.gene}:`, err);
  }
}
```

**Task:** Add to `transformedData`:
```javascript
vus_results: vusResults,  // PLUMBER TASK 4
```

**Task:** Render in JSX (check if `VUSResolutionCard` component exists, or create it):
```jsx
{/* VUS Resolution */}
{Object.keys(result.vus_results || {}).length > 0 && (
  <Box sx={{ mb: 3 }}>
    {Object.entries(result.vus_results).map(([gene, vusData]) => (
      <VUSResolutionCard
        key={gene}
        variant={{
          gene: gene,
          hgvs_c: patientProfile.germline?.mutations?.find(m => m.gene === gene)?.variant,
          hgvs_p: patientProfile.germline?.mutations?.find(m => m.gene === gene)?.protein_change
        }}
        vusData={vusData}
        onResolve={async (variant) => {
          const response = await fetch(`${import.meta.env.VITE_API_ROOT}/api/vus/identify`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variant })
          });
          return response.json();
        }}
      />
    ))}
  </Box>
)}
```

**Component:** Verify `oncology-frontend/src/components/ayesha/VUSResolutionCard.jsx` exists (or create it per MOAT_CAPABILITY_AUDIT.md)

**Priority:** P1 - HIGH

---

### 3. Holistic Score (Patient-Trial-Dose)

**Backend:** ✅ `api/services/holistic_score_service.py`  
**Status:** ORPHANED (never surced in frontend)

**Frontend Deliverable:**

**File:** `oncology-frontend/src/pages/AyeshaCompleteCare.jsx`

**Task:** Holistic Score is already computed in backend for trials (if `holistic_score` field exists in `trials.trials[]` items), but **not displayed**.

**Task:** In `TrialMatchesCard` or trial rendering component, add:
```jsx
{trial.holistic_score !== undefined && (
  <Chip
    label={`Holistic: ${(trial.holistic_score * 100).toFixed(0)}%`}
    color={trial.holistic_score >= 0.7 ? 'success' : trial.holistic_score >= 0.5 ? 'warning' : 'default'}
    size="small"
    variant="outlined"
  />
)}
```

**Note:** Holistic Score is backend-computed; frontend just needs to **render** it if present.

**Priority:** P2 - MEDIUM

---

## ⚠️ BUGS (Backend issues, not frontend)

### 1. Clinical Trials (Returns 0)

**Backend Bug:** `api/routers/ayesha_orchestrator_v2.py` lines 428-439  
**Issue:** Field name mismatch (`pd_l1.cps` vs `pd_l1_cps`) breaks trial matching  
**Frontend Fix:** Already done (Zo added  keys + nested keys in profile)  
**Backend Fix:** **PLUMBER TASK 1** (backend fix, not frontend)

**Priority:** P0 - CRITICAL

---

### 2. Sporadic Gates Confidence Capping

**Backend Bug:** `completeness_score` defaults to 0 → L0 cap (0.4)  
**Frontend Fix:** Already done (Zo added `completeness_score: 0.55` to profile)  
**Backend:** Already reads it correctly

**Priority:** P0 - CRITICAL (already fixed)

---

## 🔒 LOCKED (Legitimately not available)

- **WIWFM Drug Efficacy**: Requires NGS (no NGS data for Ayesha yet)
- **CA-125 Intelligence**: Requires CA-125 value (no value in profile)

---

## 📋 SUMMARY: What Plumber Needs to Build

### P1 - HIGH (This Week)

1. **Synthetic Lethality Card Component** (`SyntheticLethalityCard.jsx`)
   - Create component (template in MOAT_CAPABILITY_AUDIT.md lines 756-809)
   - Wire API call in `AyeshaCompleteCare.jsx`
   - Render in JSX

2. **VUS Resolution** (verify existing code works)
   - Verify `VUSResolutionCard.jsx` exists
   - Verify API call in `AyesheteCare.jsx` works
   - Verify rendering in JSX works

### P2 - MEDIUM (This Sprint)

3. **Holistic Score Display** (just rendering, backend already computes)
   - Add holistic score chip to trial cards
   - No new API calls needed

---

## 🧪 TESTING CHECKLIST

For each frontend deliverable, plumber should:

1. **Manual Test:**
   - Load Ayesha Complete Care page
   - Click "Generate Complete Care Plan"
   - Verify new UI sections appear
   - Verify data is non-empty (not hardcoded)

2. **API Test:**
   - Open browser DevTools → Network tab
   - Verify API calls are made (not 404)
   - Verify API responses are non-empty JSON (not `{}`)
   - Verify responses contain expected fields

3. **Visual Test:**
   - Verify RUO disclaimers are present
   - Verify error handling (graceful degradation if API fails)
   - Verify loading states (if added)

---

## 📝 NOTES

- **IO Safest Selection**: ✅ Already shipped by Zo
- **Essentiality**: ✅ Already wired by Zo (audit needs update)
- **PGx Safety**: ✅ Alre Zo (audit needs update)
- **Synthetic Lethality**: ❌ Still orphaned (needs frontend work)
- **VUS Resolution**: ❌ Still orphaned (code exists, verify it works)
- **Holistic Score**: ❌ Still orphaned (backend computes, frontend just needs to render)

**Last Updated:** 2026-01-11  
**By:** Zo (Alpha's Agent)
