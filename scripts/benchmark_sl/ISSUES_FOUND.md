# ⚠️ Benchmark Issues Found & Fixed

**Date:** January 28, 2025  
**Reviewer:** Manager Review

---

## 🔴 Critical Issue #1: GUIDANCE_FAST Bypasses All ML

**Problem:** The `/api/guidance/synthetic_lethality` endpoint has a "fast path" that:

```python
# From guidance.py lines 412-427
fast_enabled = os.getenv("GUIDANCE_FAST", "1").strip() not in {"0", "false", "False"}
if fast_enabled and any(g in dna_repair_genes for g in by_gene.keys()):
    return {
        "suggested_therapy": "platinum",
        "damage_report": [],          # ← EMPTY - no analysis
        "essentiality_report": [],    # ← EMPTY - no Evo2
        "guidance": None,
    }
```

**Impact:**
- For BRCA1, BRCA2, ATM, ATR, CHEK2 → Returns hardcoded "platinum"
- No VEP annotation
- No Evo2 sequence scoring
- No essentiality calculation
- **The benchmark was testing if hardcoded rules work, NOT if the ML model works**

**Evidence from cache.json:**
```json
{"SL_001": {"suggested_therapy": "platinum", "damage_report": [], "essentiality_report": []}}
```

---

## 🔴 Critical Issue #2: Benchmark Tests Rules, Not ML

**Problem:** The "85.7% TPR" result is meaningless because:

1. Ground truth says "BRCA1 mutation → SL detected"
2. API rule says "if BRCA1 → return platinum"
3. Benchmark says "platinum returned → SL detected"
4. **This is circular logic!**

**The benchmark was NOT testing:**
- Evo2 sequence disruption scores
- Pathway aggregation
- Essentiality predictions
- Drug ranking algorithms

---

## 🟠 High Issue #3: Ground Truth Values Are Fabricated

**Problem:** The test dataset has hardcoded values like:
```json
"depmap_essentiality": {"BRCA1": 0.92}
```

These values are **made up**, not from actual DepMap data.

**Impact:** Cannot validate essentiality predictions against real data.

---

## 🟠 High Issue #4: Drug Matching Logic Flawed

**Problem:** The benchmark expected "Olaparib" but API returns "platinum".

**Reality:** For BRCA-mutated ovarian cancer:
- First-line: Platinum-based chemotherapy
- Maintenance: PARP inhibitors (Olaparib)

Both are clinically valid! The matching logic should recognize this.

---

## 🟡 Medium Issue #5: DepMap Download Script Broken

**Problem:** 
```python
# Line 42 has syntax error - missing closing parenthesis
breast_lines = df[df['cell_line_name'].str.contains('BREAST', case=False, na=False)
```

Also, the DepMap URL is incorrect and requires authentication.

---

## ✅ Fixes Applied

### Fix 1: Created proper benchmark using `/api/efficacy/predict`
- File: `benchmark_efficacy.py`
- Actually calls Evo2 through the efficacy pipeline
- Tests real ML predictions

### Fix 2: Option to disable GUIDANCE_FAST
- Run: `GUIDANCE_FAST=0 python benchmark_synthetic_lethality.py`
- Forces full pipeline including Evo2

### Fix 3: Fixed drug matching logic
- Added "platinum" as valid for HRD cases
- Both platinum and PARP inhibitors are correct

### Fix 4: Updated ground truth
- Marked values as "needs_validation"
- Added notes about data sources

### Fix 5: Fixed DepMap script syntax error

---

## 📋 Correct Benchmark Approach

To properly benchmark synthetic lethality predictions:

1. **Use `/api/efficacy/predict`** which actually runs:
   - Evo2 sequence scoring
   - Pathway aggregation
   - Evidence integration
   - Drug ranking

2. **Or set `GUIDANCE_FAST=0`** to force full pipeline

3. **Validate against real ground truth:**
   - DepMap actual values (not made up)
   - Published SL pairs with citations
   - FDA-approved drug labels

---

## 🎯 What the Previous Results Actually Showed

| Metric | Reported | Reality |
|--------|----------|---------|
| SL Detection TPR | 85.7% | Testing if "BRCA → platinum" rule works |
| Drug Match | 10% | "Platinum" not matched to "Olaparib" |
| Essentiality Correlation | 1.0 | From 1 data point (meaningless) |
| Evo2 Used | Implied | **Actually NO for DDR genes** |



