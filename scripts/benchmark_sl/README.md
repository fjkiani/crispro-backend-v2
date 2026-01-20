# Synthetic Lethality Benchmark

**Status:** ⚠️ **REVIEW REQUIRED** - See `ISSUES_FOUND.md`

---

## ⚠️ Critical Issues Identified

The original benchmark had critical flaws:

1. **GUIDANCE_FAST bypasses Evo2** - DDR genes get hardcoded "platinum" response
2. **Benchmark tested rules, not ML** - The "85% TPR" was meaningless
3. **Ground truth was fabricated** - DepMap values were made up

**See `ISSUES_FOUND.md` for full details.**

---

## ✅ Corrected Benchmark Approach

### Option 1: Use Efficacy Endpoint (RECOMMENDED)

```bash
python3 benchmark_efficacy.py test_cases_pilot.json
```

This calls `/api/efficacy/predict` which:
- ✅ Actually uses Evo2 sequence scoring
- ✅ Runs pathway aggregation
- ✅ Integrates evidence
- ✅ Returns ranked drugs

### Option 2: Disable GUIDANCE_FAST

```bash
GUIDANCE_FAST=0 python3 benchmark_synthetic_lethality.py test_cases_pilot.json
```

This forces the synthetic_lethality endpoint to:
- ✅ Call VEP for annotation
- ✅ Compute essentiality scores
- ✅ Run the full pipeline

### Option 3: Original Benchmark (⚠️ Tests Rules Only)

```bash
python3 benchmark_synthetic_lethality.py test_cases_pilot.json
```

⚠️ This only tests if hardcoded rules work!

---

## Files

| File | Purpose | Status |
|------|---------|--------|
| `benchmark_efficacy.py` | **CORRECT** - Tests via efficacy endpoint | ✅ NEW |
| `benchmark_synthetic_lethality.py` | Tests SL endpoint (rules only with FAST mode) | ⚠️ Limited |
| `test_cases_pilot.json` | 10 test cases | ✅ Ready |
| `create_pilot_dataset.py` | Generate test cases | ✅ Ready |
| `download_depmap.py` | Process DepMap data | ✅ Fixed |
| `ISSUES_FOUND.md` | Documents all issues | ✅ NEW |

---

## What We Actually Want to Test

### Synthetic Lethality Prediction = Multiple Components

1. **Sequence Disruption (S)** - Does Evo2 correctly score the variant impact?
2. **Pathway Aggregation (P)** - Are broken pathways identified?
3. **Evidence Integration (E)** - Is clinical evidence considered?
4. **Drug Ranking** - Are correct drugs recommended?

### The Original Benchmark Tested

❌ None of the above for DDR genes
❌ Just "if BRCA in genes → return platinum"

### The Corrected Benchmark Tests

✅ All of the above via `/api/efficacy/predict`

---

## Running the Correct Benchmark

```bash
# Navigate to benchmark directory
cd oncology-coPilot/oncology-backend-minimal/scripts/benchmark_sl

# Run the CORRECT benchmark (uses Evo2)
python3 benchmark_efficacy.py test_cases_pilot.json

# Or with options
python3 benchmark_efficacy.py test_cases_pilot.json --max-concurrent 2 --api-root http://localhost:8000
```

---

## Expected Results

After running the corrected benchmark, you should see:

- **Evo2 Usage Rate:** Should be 100% (or close)
- **Drug Match Accuracy:** Realistic baseline (not artificially inflated)
- **Confidence Scores:** From actual ML predictions

If Evo2 usage is <100%, check:
1. Is the Evo2 service running?
2. Are feature flags set correctly?
3. Check backend logs for errors

---

## Ground Truth Sources

For real benchmarking, use actual data:

1. **DepMap** - Download from https://depmap.org/portal/download/
2. **Published SL pairs** - From peer-reviewed literature
3. **FDA drug labels** - From DailyMed

The `create_pilot_dataset.py` values are **placeholders** for testing infrastructure.
