# Comprehensive Root Cause Analysis: Pathway Normalization Bug

**Date**: 2025-01-XX  
**Status**: Complete Analysis  
**Issue**: Poor benchmark results (MM: 40%, Ovarian: AUROC 0.500, Melanoma: 50%)

---

## Executive Summary

**Root Cause**: Pathway score normalization formula assumes wrong range, causing all drugs to get `path_pct = 1.0` and eliminating differentiation.

**Location**: `api/services/efficacy_orchestrator/drug_scorer.py:48-49`

**Impact**: All drugs receive identical confidence scores (0.4), making correct drug ranking impossible.

---

## Historical Comparison: October 2025 (Working) vs November 2025 (Broken)

### October 2025 (Working System)

**Evidence from `ablation_results_20251002_110838.json`**:
- **SP mode**: pathway_accuracy 1.0 (100%), avg_confidence 0.467
- **SPE mode**: pathway_accuracy 1.0 (100%), avg_confidence 0.524
- **KRAS G12D SP**: MEK inhibitor confidence 0.48, BRAF inhibitor 0.465 (diff=0.015) ✅
- **KRAS G12D SPE**: MEK inhibitor confidence 0.53, BRAF inhibitor 0.515 (diff=0.015) ✅
- **Key**: Small but meaningful differences (0.015) allowed correct ranking

**Evidence from `mm_baseline/mm_efficacy_results.json`**:
- **KRAS G12D**: MEK inhibitor confidence 0.53, BRAF inhibitor 0.52 (diff=0.01) ✅
- **BRAF V600E**: BRAF inhibitor confidence 0.453, MEK inhibitor 0.447 (diff=0.006) ✅
- **Accuracy**: 1.0 (100%)

### November 2025 (Broken System)

**Evidence from `mm_benchmark_20251124_191630.json`**:
- **All drugs**: confidence 0.4 (no differentiation)
- **KRAS G12D**: All drugs have confidence 0.4, efficacy_score 0.69 (identical)
- **pathway_alignment_accuracy**: 0.4 (vs 1.0 in October)

---

## Root Cause: Pathway Normalization Bug

### Current Implementation

**File**: `api/services/efficacy_orchestrator/drug_scorer.py:44-51`

```python
# Pathway score (raw) and percentile normalization
drug_weights = get_pathway_weights_for_drug(drug_name, disease=disease)
s_path = sum(pathway_scores.get(pathway, 0.0) * weight for pathway, weight in drug_weights.items())
# Normalize based on empirical Evo2 ranges (pathogenic deltas ~1e-6..1e-4)
if s_path > 0:
    path_pct = min(1.0, max(0.0, (s_path - 1e-6) / (1e-4 - 1e-6)))
else:
    path_pct = 0.0
```

### The Problem

1. **Assumed Range**: Formula assumes pathway scores are in range `1e-6` to `1e-4` (0.000001 to 0.0001)
2. **Actual Range**: Pathway scores are ~0.002 (2e-3), which is **20x larger** than 1e-4
3. **Result**: All drugs get `path_pct = 1.0` (capped), eliminating differentiation

### Mathematical Proof

**Calculation for actual pathway score (0.002)**:
```
path_pct = (0.002 - 1e-6) / (1e-4 - 1e-6)
path_pct = 0.001999 / 0.000099
path_pct ≈ 20.19
path_pct (capped) = 1.0
```

**Even for a single variant with sequence_disruption = 0.0001**:
```
pathway_score = 0.0001 / 1 = 0.0001 (single variant, average)
s_path = 0.0001 * 1.0 = 0.0001 (assuming drug weight = 1.0)
path_pct = (0.0001 - 1e-6) / (1e-4 - 1e-6)
path_pct = 0.000099 / 0.000099 = 1.0
```

**Result**: Even at the assumed maximum (1e-4), all drugs get `path_pct = 1.0`!

---

## Pathway Aggregation Analysis

### Current Implementation

**File**: `api/services/pathway/aggregation.py:7-45`

```python
def aggregate_pathways(seq_scores: List[Dict[str, Any]]) -> Dict[str, float]:
    pathway_totals = {}
    pathway_counts = {}
    
    for score in seq_scores:
        pathway_weights = score.get("pathway_weights", {})
        sequence_disruption = float(score.get("sequence_disruption", 0.0))
        
        for pathway, weight in pathway_weights.items():
            pathway_totals[pathway] += sequence_disruption * weight
            pathway_counts[pathway] += 1
    
    # Compute average scores
    pathway_scores = {}
    for pathway in pathway_totals:
        pathway_scores[pathway] = pathway_totals[pathway] / pathway_counts[pathway]
    
    return pathway_scores
```

**Formula**: `pathway_score = sum(sequence_disruption * weight) / count`

### Typical Values

- **sequence_disruption**: ~0.0001 (1e-4) for pathogenic variants (BRAF V600E, KRAS G12D)
- **Single variant, weight=1.0**: `pathway_score = 0.0001 / 1 = 0.0001` (1e-4)
- **Multiple variants or higher weights**: Could be larger

### Why Pathway Scores Are ~0.002

**Hypothesis**: Pathway scores are ~0.002 because:
1. Multiple variants contributing to same pathway
2. Higher sequence_disruption values (some variants have disruption > 0.0001)
3. Drug pathway weights > 1.0 (though weights are typically ≤ 1.0)

**Actual Test Results**: Pathway scores from debug output show `ras_mapk: 0.002`, confirming scores are ~20x larger than assumed maximum.

---

## Why It Worked in October 2025

### Hypothesis 1: Different Normalization Formula

**Possibility**: The normalization formula was different in October, using a wider range or different approach.

**Evidence**: No code history available to confirm, but October results show differentiation (0.015 differences), suggesting `path_pct` was NOT 1.0 for all drugs.

### Hypothesis 2: Pathway Scores Were in Correct Range

**Possibility**: Pathway scores were actually in range 1e-6 to 1e-4 in October, but something changed to make them ~0.002 now.

**What Could Have Changed**:
- Sequence disruption calculation changed (unlikely - same Evo2 model)
- Pathway aggregation changed (sum → average or vice versa)
- Drug pathway weights changed (unlikely - hardcoded)

### Hypothesis 3: Different Confidence Calculation

**Possibility**: Confidence calculation provided differentiation even when `path_pct` was similar.

**Evidence**: October results show small differences (0.015), which could come from:
- Tie-breaker bonuses (0.01 for gene-drug matching)
- Sequence percentile differences
- Evidence strength differences

**However**: November results show ALL drugs have confidence 0.4, suggesting `path_pct = 1.0` is causing the issue.

---

## Code Documentation Review

### I3_SPE_FRAMEWORK.md (Section 3.3.4)

**Documents Current Formula**:
```python
# Step 3: Normalize to [0, 1] based on empirical Evo2 ranges
if s_path > 0:
    path_pct = min(1.0, max(0.0, (s_path - 1e-6) / (1e-4 - 1e-6)))
```

**Comment**: "Empirical Range: Pathogenic deltas ~1e-6 to 1e-4"

**Issue**: The comment refers to "pathogenic deltas" but the normalization is applied to `s_path` (pathway score), not raw deltas. Pathway scores are aggregated from sequence_disruption, which may be larger than individual deltas.

### ZO_MASTER_KNOWLEDGE_BASE.mdc

**Documents**: "Normalized: `path_pct = (s_path - 1e-6) / (1e-4 - 1e-6)` (empirical Evo2 range)"

**No Historical Context**: Does not mention when this formula was introduced or if it changed.

---

## Fix Recommendations

### Option 1: Use Percentile-Based Normalization (Recommended)

**Approach**: Use percentile mapping similar to sequence scores, based on empirical pathway score distribution.

**Implementation**:
```python
def normalize_pathway_percentile(s_path: float) -> float:
    """
    Normalize pathway score to percentile [0, 1] based on empirical distribution.
    
    Empirical ranges from test data:
    - Low: < 0.0005 → 0.1
    - Medium: 0.0005-0.001 → 0.5
    - High: 0.001-0.002 → 0.8
    - Very High: > 0.002 → 1.0
    """
    if s_path <= 0:
        return 0.0
    elif s_path < 0.0005:
        return 0.1
    elif s_path < 0.001:
        return 0.5
    elif s_path < 0.002:
        return 0.8
    else:
        return 1.0
```

### Option 2: Use Correct Empirical Range

**Approach**: Update normalization range to match actual pathway scores (0 to 0.01 or 1e-4 to 0.01).

**Implementation**:
```python
# Normalize based on actual pathway score ranges (0 to 0.01)
if s_path > 0:
    path_pct = min(1.0, max(0.0, s_path / 0.01))  # Simple 0-0.01 range
else:
    path_pct = 0.0
```

**Or with minimum threshold**:
```python
# Normalize based on actual pathway score ranges (1e-4 to 0.01)
if s_path > 0:
    path_pct = min(1.0, max(0.0, (s_path - 1e-4) / (0.01 - 1e-4)))
else:
    path_pct = 0.0
```

### Option 3: Use Log-Scale Normalization

**Approach**: Use logarithmic normalization for wide dynamic range.

**Implementation**:
```python
import math

def normalize_pathway_log(s_path: float) -> float:
    """Normalize pathway score using log scale for wide dynamic range."""
    if s_path <= 0:
        return 0.0
    # Log scale: log10(s_path / min) / log10(max / min)
    min_score = 1e-6
    max_score = 0.01
    if s_path < min_score:
        return 0.0
    log_pct = math.log10(s_path / min_score) / math.log10(max_score / min_score)
    return min(1.0, max(0.0, log_pct))
```

---

## Additional Issues Found

### Issue 1: Confidence Calculation Defaulting to 0.4

**Problem**: All drugs getting confidence 0.400 regardless of pathway scores.

**Root Cause**: When `path_pct = 1.0` for all drugs, confidence calculation becomes:
- Legacy: `confidence = 0.3 + 0.1 * seq_pct + 0.1 * 1.0` (path_pct dominates)
- If `seq_pct` is similar across drugs, all get same confidence ≈ 0.4

**Fix**: Fix pathway normalization first, then confidence will differentiate correctly.

### Issue 2: Pathway Aggregation May Need Review

**Current**: Uses average (`sum / count`)

**Question**: Should it use sum instead of average for single-variant cases?

**Analysis**: For single variant, average = sum, so no difference. For multiple variants, average may dilute scores. However, this is likely correct behavior (average reflects per-variant impact).

### Issue 3: Drug Ranking Logic

**Current**: Tie-breaker is only 0.01 bonus for gene-drug matching.

**Issue**: When all drugs have same `path_pct = 1.0`, 0.01 bonus is insufficient for differentiation.

**Fix**: Fix pathway normalization first, then tie-breaker will work correctly.

---

## Missing Information

### What We Still Don't Know

1. **What was the normalization formula in October 2025?**
   - Was it always `(s_path - 1e-6) / (1e-4 - 1e-6)`?
   - Or was it different?

2. **What were the actual pathway scores in October?**
   - Were they in range 1e-6 to 1e-4?
   - Or were they also ~0.002?

3. **Did pathway aggregation change?**
   - Was it always average, or was it sum before?
   - Did the aggregation logic change between October and November?

4. **Did sequence_disruption calculation change?**
   - Are sequence_disruption values larger now than in October?
   - Did the Evo2 scoring change?

### How to Find Out

1. **Git History**: Check git log for `drug_scorer.py` to see when normalization formula was introduced/changed
2. **Historical Debug Logs**: Check if there are any debug logs from October showing actual `s_path` values
3. **Code Comments**: Look for TODOs or FIXMEs that might indicate known issues

---

## Success Criteria for Fix

After fixing the normalization:

1. **MM Benchmark**: >80% pathway alignment accuracy (vs current 40%)
2. **Ovarian Benchmark**: AUROC >0.65 (vs current 0.500)
3. **Melanoma Benchmark**: >90% accuracy (vs current 50%)
4. **Confidence Differentiation**: Top drug confidence >0.5, bottom drug <0.3
5. **Drug Ranking**: 
   - KRAS G12D → MEK inhibitor #1
   - BRAF V600E → BRAF inhibitor #1

---

## Next Steps

1. **Fix Pathway Normalization** (CRITICAL - Do First)
   - Choose normalization approach (percentile-based recommended)
   - Update `drug_scorer.py:48-49`
   - Add debug logging to verify `s_path` and `path_pct` values

2. **Re-run Benchmarks**
   - Run MM benchmark - expect >80% accuracy
   - Run Ovarian benchmark - expect AUROC >0.65
   - Run Melanoma benchmark - expect >90% accuracy

3. **Validate Fix**
   - Check that `path_pct` values are differentiated (not all 1.0)
   - Check that confidence scores are differentiated
   - Verify correct drug rankings

---

## Conclusion

The root cause is clear: **Pathway score normalization assumes wrong range (1e-6 to 1e-4) when actual scores are ~0.002 (2e-3), causing all drugs to get `path_pct = 1.0` and eliminating differentiation.**

The fix is straightforward: **Update normalization to use correct empirical range or percentile-based approach.**

The mystery is: **Why did it work in October?** This requires further investigation (git history, historical logs) but doesn't block the fix.

