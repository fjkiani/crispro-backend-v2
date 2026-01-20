# 🔴 ASTRADB SYNC FIX - Why No Trials Showing

**Date:** January 10, 2026  
**Issue:** 0 trials returned from AstraDB vector search  
**Root Cause:** AstraDB collection `clinical_trials_eligibility2` is empty  

---

## 🚨 PROBLEM

**Symptoms:**
- Search for "ovarian cancer" returns 0 trials
- Logs show: `✅ Found 0 trials from vector search`
- Warning: `No candidates from AstraDB`

**Root Cause:**
- SQLite has **1,397 trials** ✅
- AstraDB collection `clinical_trials_eligibility2` has **0 trials** ❌
- Vector search requires trials to be in AstraDB with embeddings

---

## ✅ SOLUTION: Sync Trials to AstraDB

**Step 1: Run the Sync Script**

```bash
cd /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal

# Sync all trials (1,397 trials)
python3 scripts/trials/utilities/seed_astradb_from_sqlite.py --batch-size 50 --limit 0

# Or sync first 100 trials (for testing)
python3 scripts/trials/utilities/seed_astradb_from_sqlite.py --batch-size 50 --limit 100
```

**What This Does:**
1. Reads trials from SQLite (`data/clinical_trials.db`)
2. Generates embeddings using Google Embedding API (768-dim vectors)
3. Upserts trials to AstraDB collection `clinical_trials_eligibility2`
4. Enables vector search for semantic search

**Expected Output:**
```
🚀 Starting AstraDB seeding (batch_size=50, limit=0)
✅ Collection 'clinical_trials_eligibility2' already exists
✅ Processing batch 1/28 (50 trials)...
✅ Processing batch 2/28 (50 trials)...
...
🎉 Seeding complete! Processed: 1397, Errors: 0
✅ AstraDB collection 'clinical_trials_eligibility2' now has 1397 documents
```

**Time Estimate:**
- 1,397 trials with batch size 50: ~28 batches
- ~1-2 seconds per batch = **~1-2 minutes total**

---

## 🧪 VERIFICATION

**Step 2: Verify Sync Completed**

**Option A: Check Logs**
Look for: `✅ AstraDB collection 'clinical_trials_eligibility2' now has 1397 documents`

**Option B: Test Search Again**
1. Go to: `http://localhost:5173/universal-trial-intelligence`
2. Search for: `ovarian cancer`
3. Should now return trials (not 0)

**Option C: Check AstraDB Directly**
```python
from api.services.database_connections import get_db_connections
db = get_db_connections()
vector_db = db.get_vector_db_connection()
collection = vector_db.get_collection("clinical_trials_eligibility2")
count = collection.count_documents({}, upper_bound=1000000)
print(f"Trials in AstraDB: {count}")
# Should print: Trials in AstraDB: 1397
```

---

## 📋 DETAILS

### **Why This Happened**
- Trials were saved to SQLite (1,397 trials) ✅
- But AstraDB sync was **never run** ❌
- Vector search requires trials to be in AstraDB with embeddings

### **Why Manual? (The Automation Gap)** ⚠️

**This is exactly the automation gap identified in HANDOFF_MASTER.md (P1 task):**

The sync script exists (`seed_astradb_from_sqlite.py`) but:
- ❌ **No automation/scheduler** runs it automatically
- ❌ **No trigger** when new trials are saved
- ❌ **No background job** to keep AstraDB in sync
- ✅ **Script exists** but must be run manually

**This is documented as P1 (HIGH priority) task in HANDOFF_MASTER.md:**
- Task 3: "Create Auto-Sync Job" 🔄
- Task 4: "Create Unified Scheduler" 🎯
- **Status:** ❌ **NOT DONE** - Scripts exist but no scheduler

### **What Should Happen (Automation Needed)**

**Ideal State:**
1. ✅ New trials saved to SQLite
2. ✅ **Auto-trigger:** Sync script runs automatically
3. ✅ Trials synced to AstraDB with embeddings
4. ✅ Vector search works immediately

**Current State:**
1. ✅ New trials saved to SQLite
2. ❌ **Manual step:** Developer must run sync script
3. ❌ AstraDB stays empty until manual sync
4. ❌ Vector search returns 0 results

### **Prevention (Future) - Options**

**Option 1: Manual (Current - Not Ideal)**
```bash
python3 scripts/trials/utilities/seed_astradb_from_sqlite.py --limit 0
```
- Must remember to run after adding trials
- Easy to forget
- Not scalable

**Option 2: Use Unified Pipeline with `--sync` Flag**
```bash
python3 scripts/trials/production/run_pipeline.py --disease "ovarian cancer" --count 500 --tag --sync
```
- Syncs new trials when using pipeline
- But still requires `--sync` flag
- Only works when using pipeline (not for existing trials)

**Option 3: Implement Automation (P1 Task - RECOMMENDED)** ⚡
- **Auto-sync job** runs after new trials saved
- **Unified scheduler** manages all background jobs
- **No manual intervention** needed
- **See HANDOFF_MASTER.md P1 for implementation details**

---

## 🎯 QUICK FIX COMMAND

**Run this now:**
```bash
cd /Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal && python3 scripts/trials/utilities/seed_astradb_from_sqlite.py --batch-size 50 --limit 0
```

**Then test search again:**
- Go to: `http://localhost:5173/universal-trial-intelligence`
- Search: `ovarian cancer`
- Should now show trials! ✅

---

**Status:** 🔴 **CRITICAL** - AstraDB sync needed before search will work

---

## 🤖 AUTOMATION NEEDED (P1 Task)

**This manual sync exposes the automation gap. To prevent this in the future:**

See **HANDOFF_MASTER.md → P1: HIGH - Automation** for:
- Task 3: Create Auto-Sync Job (`production/core/auto_sync_job.py`)
- Task 4: Create Unified Scheduler (`production/run_scheduler.py`)

**Implementation Priority:**
1. **P0 (NOW):** Run manual sync to fix immediate issue (this document)
2. **P1 (SOON):** Implement automation so this doesn't happen again (HANDOFF_MASTER.md)
