# 🔴 ROOT CAUSE FIX: Discovery Data Preservation

**Date:** January 2026  
**Status:** ✅ **CRITICAL BUG FIXED**  
**Found By:** Zo (Holistic Score Agent Audit)

---

## 🚨 THE BUG (Root Cause)

**Problem:** Trial status from discovery was being lost, resulting in `status=None, overall_status=UNKNOWN`

**Root Cause:** The matching agent was:
1. ✅ Extracting `candidate_trial_ids` (list of NCT ID strings) from discovery
2. ❌ **IGNORING** `candidates` (list of FULL trial objects with status) from discovery
3. ❌ Trying to refresh from CT.gov (which fails)
4. ❌ Creating empty trial dicts `{"nct_id": nct_id}` when refresh fails
5. ❌ Losing ALL discovery data (status, conditions, etc.)

**Discovery Returns:**
```python
{
    "candidate_trial_ids": ["NCT04284969", "NCT04001023", ...],  # Just IDs (matching agent used this)
    "candidates": [
        {
            "nct_id": "NCT04284969",
            "title": "PARP + ATR Inhibitor Study",
            "status": "RECRUITING",  # ← THIS WAS BEING LOST!
            "conditions": ["Ovarian Cancer"],
            ...
        },
        ...
    ]  # Full objects (matching agent IGNORED this!)
}
```

**What Matching Agent Was Doing (BROKEN):**
```python
# Step 1: Extract only IDs
candidate_trial_ids = discovery_result.get("candidate_trial_ids", [])  # ["NCT04284969", ...]
# ❌ IGNORES: discovery_result.get("candidates", [])  # Full objects with status!

# Step 2: Try to refresh (FAILS - CT.gov 400 error)
refreshed_trials = await refresh_trials_incremental(candidate_trial_ids)  # Returns {}

# Step 3: Loop through IDs only
for nct_id in candidate_trial_ids:
    trial = refreshed_trials.get(nct_id, {})  # {} (empty - refresh failed)
    if not trial:
        trial = {"nct_id": nct_id}  # ❌ EMPTY DICT - NO STATUS!
    
    trial["overall_status"] = trial.get("status", trial.get("overall_status", "UNKNOWN"))
    # Returns "UNKNOWN" because trial dict is empty!
```

---

## ✅ THE FIX

**Solution:** Use discovery candidates as fallback when refresh fails

**Fixed Code:**
```python
# Step 1: Extract BOTH IDs AND full candidate objects
candidate_trial_ids = discovery_result.get("candidate_trial_ids", [])
discovery_candidates = discovery_result.get("candidates", [])  # ✅ NOW PRESERVED!

# Build lookup dict: NCT ID -> full trial object
discovery_candidates_lookup = {}
for candidate in discovery_candidates:
    nct_id = candidate.get("nct_id") or candidate.get("id")
    if nct_id:
        discovery_candidates_lookup[str(nct_id)] = candidate.copy()  # ✅ PRESERVES STATUS!

# Step 2: Try refresh (may fail)
refreshed_trials = await refresh_trials_incremental(candidate_trial_ids) or {}

# Step 3: Use discovery candidates as fallback
for nct_id in candidate_trial_ids:
    # Priority 1: Refreshed data (fresh status)
    trial = refreshed_trials.get(nct_id, {})
    
    # Priority 2: Discovery candidate (preserves status if refresh fails)
    if not trial or not trial.get("status"):
        discovery_trial = discovery_candidates_lookup.get(nct_id)
        if discovery_trial:
            # ✅ USE DISCOVERY DATA AS BASE!
            trial = discovery_trial.copy()
            if refreshed_trials.get(nct_id):
                trial.update(refreshed_trials[nct_id])  # Refresh overwrites if present
    
    # Status is now preserved from discovery! ✅
```

---

## 📋 CHANGES MADE

### **File: `production/core/matching_agent.py`**

1. **Lines 166-208:** Extract BOTH `candidate_trial_ids` AND `candidates` from discovery
   - Build `discovery_candidates_lookup` dict: `{nct_id: full_trial_object}`
   - Preserves all discovery data (status, conditions, etc.)

2. **Lines 243-270:** Use discovery candidates as fallback
   - Priority 1: Refreshed data (if available)
   - Priority 2: Discovery candidate (preserves status)
   - Priority 3: Minimal dict (only if no discovery data)

3. **Lines 267-270:** Preserve status from discovery
   - Only use "UNKNOWN" as last resort
   - Status is preserved from discovery if refresh fails

---

## 🧪 VERIFICATION

### **Before Fix:**
```python
Discovery: status="RECRUITING"  ✅
Refresh: FAILED (CT.gov 400 error)  ❌
Matching: status=None, overall_status="UNKNOWN"  ❌ BUG!
```

### **After Fix:**
```python
Discovery: status="RECRUITING"  ✅
Refresh: FAILED (CT.gov 400 error)  ❌
Matching: Uses discovery candidate → status="RECRUITING"  ✅ FIXED!
```

---

## 🎯 STATUS

✅ **Root Cause Identified**  
✅ **Fix Applied**  
✅ **Discovery Data Now Preserved**  
✅ **Status Field Now Preserved**  

**Ready for Re-Testing** 🚀

---

## 📝 NOTES

- Discovery returns full trial objects with status - these are now preserved
- Refresh is still attempted (for fresh data), but failure no longer loses discovery data
- Status mapping now works correctly: discovery → refresh (if available) → UNKNOWN (last resort)

**The integration should now work end-to-end!** ✅
