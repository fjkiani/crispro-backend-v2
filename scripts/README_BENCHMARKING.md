# AYESHA MBD4+TP53 Accuracy Benchmarking Framework

## Overview

Comprehensive benchmarking framework to validate accuracy of MBD4+TP53 HGSOC analysis against:
1. **Ground Truth**: Expected biological pathways and clinical mechanisms
2. **Clinical Evidence**: NCCN guidelines, FDA labels, published literature
3. **Real Patient Cases**: Known clinical outcomes

---

## Quick Start

### 1. Run Accuracy Benchmark

```bash
cd oncology-coPilot/oncology-backend-minimal
python3 scripts/benchmark_mbd4_tp53_accuracy.py
```

**Output**:
- Test results (pass/fail, scores)
- Summary statistics (pass rate, average score)
- JSON report saved to `results/benchmarks/`

### 2. Run Clinical Validation

```bash
python3 scripts/benchmark_clinical_validation.py
```

**Output**:
- Comparison against NCCN/FDA guidelines
- Literature evidence alignment
- Synthetic lethality validation

---

## Test Categories

### 1. Pathway Accuracy
**Tests**: Pathway disruption scores match expected biological pathways
- **DDR Pathway (MBD4)**: Expected 0.9-1.0 (frameshift → complete loss)
- **TP53 Pathway (R175H)**: Expected 0.7-0.9 (hotspot → high disruption)

**Ground Truth**: Based on variant type (frameshift vs. hotspot)

### 2. Drug Recommendation Accuracy
**Tests**: Drug recommendations match NCCN/FDA guidelines
- **PARP Inhibitors**: Should rank #1-3, efficacy ≥0.75
- **Platinum**: Should rank #4, efficacy ≥0.70
- **Evidence Tier**: Should be "supported" or "consider" (not "insufficient")

**Ground Truth**: NCCN Category 1 (preferred) for HRD+ ovarian cancer

### 3. Mechanism Vector Accuracy
**Tests**: Mechanism vectors match expected clinical mechanisms
- **DDR Mechanism**: Expected 1.2-1.5 (DDR + 50% TP53 = 1.0 + 0.8×0.5 = 1.4)
- **Other Pathways**: Should be low (MAPK, PI3K, VEGF, HER2, IO, Efflux)

**Ground Truth**: Based on pathway disruption scores and conversion formula

### 4. Synthetic Lethality Accuracy
**Tests**: Correctly identifies PARP sensitivity
- **Suggested Therapy**: Should be "parp", "platinum", or "olaparib"
- **Vulnerabilities**: Should include PARP, ATR, WEE1, DNA-PK

**Ground Truth**: Literature on MBD4 BER deficiency + TP53 checkpoint loss

### 5. Clinical Evidence Alignment
**Tests**: Evidence tiers match clinical evidence strength
- **PARP Evidence**: Should be "supported" or "consider" (RCT evidence)
- **Platinum Evidence**: Should be "supported" (standard of care)

**Ground Truth**: FDA labels, NCCN guidelines, published RCTs

---

## Ground Truth Sources

### Clinical Guidelines
- **NCCN Guidelines**: Ovarian Cancer (HRD+), Category 1 recommendations
- **FDA Labels**: PARP inhibitors (olaparib, niraparib, rucaparib), platinum
- **Published RCTs**: SOLO-2, PAOLA-1, PRIMA, NOVA, ARIEL3, ARIEL4

### Literature Evidence
- **MBD4**: Base Excision Repair (BER) pathway, DNA glycosylase function
- **TP53**: Cell cycle checkpoint, apoptosis, DNA damage response
- **Synthetic Lethality**: PARP sensitivity with HRD + BER deficiency

### Biological Pathways
- **DDR Pathway**: DNA damage response (MBD4 → BER, TP53 → checkpoint)
- **Mechanism Vectors**: 7D vector [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]

---

## Success Criteria

### Minimum Thresholds
- **Pathway Accuracy**: ≥80% tests pass
- **Drug Accuracy**: ≥90% tests pass (clinical recommendations critical)
- **Mechanism Vector**: ≥80% tests pass
- **Synthetic Lethality**: ≥90% tests pass
- **Evidence Alignment**: ≥80% tests pass

### Overall Pass Rate
- **Target**: ≥85% overall pass rate
- **Critical**: Drug recommendations must be ≥90% (patient safety)

---

## Adding New Test Cases

### 1. Add to Ground Truth

Edit `GROUND_TRUTH` in `benchmark_mbd4_tp53_accuracy.py`:

```python
GROUND_TRUTH = {
    "expected_drugs": {
        "tier1": [
            {"name": "new_drug", "min_efficacy": 0.70, "expected_rank": 5}
        ]
    }
}
```

### 2. Add New Test Function

```python
async def test_new_feature(self):
    """Test new feature accuracy"""
    # Your test logic
    self.add_result(
        "New Feature Test",
        passed, score,
        expected_value,
        actual_value
    )
```

### 3. Register in `run_all_tests()`

```python
async def run_all_tests(self):
    await self.test_new_feature()  # Add here
```

---

## Continuous Integration

### Run on Every Commit

```bash
# In CI/CD pipeline
cd oncology-coPilot/oncology-backend-minimal
python3 scripts/benchmark_mbd4_tp53_accuracy.py
# Exit code 0 if pass_rate >= 0.8, else 1
```

### Regression Testing

```bash
# Compare against baseline
python3 scripts/benchmark_mbd4_tp53_accuracy.py > current_results.txt
diff baseline_results.txt current_results.txt
```

---

## Performance Metrics

### Accuracy Metrics
- **Precision**: Correct positive predictions / Total positive predictions
- **Recall**: Correct positive predictions / Total expected positives
- **F1 Score**: Harmonic mean of precision and recall

### Clinical Metrics
- **NCCN Alignment**: % recommendations matching NCCN Category 1
- **FDA Alignment**: % recommendations matching FDA-approved indications
- **Evidence Strength**: % recommendations with RCT evidence

---

## Known Limitations

1. **Ground Truth Assumptions**:
   - Pathway scores based on variant type (frameshift vs. hotspot)
   - May not capture all biological nuances

2. **Clinical Evidence**:
   - Based on published guidelines (may lag behind latest research)
   - Rare combinations (MBD4+TP53) have limited published evidence

3. **Mechanism Vectors**:
   - 7D vector is simplified representation
   - True biological mechanisms are more complex

---

## Future Enhancements

1. **Real Patient Validation**:
   - Compare predictions with actual clinical outcomes
   - Track response rates, progression-free survival

2. **Multi-Case Benchmarking**:
   - Test on 10+ HGSOC cases (not just MBD4+TP53)
   - Validate across different variant combinations

3. **Trial Matching Validation**:
   - Compare mechanism fit scores with actual trial enrollment
   - Validate trial recommendations against patient outcomes

4. **SAE Comparison**:
   - When True SAE available, compare pathway-based vs. SAE-based
   - Measure accuracy improvement

---

## Output Files

### Benchmark Results
- **Location**: `results/benchmarks/ayesha_accuracy_benchmark_<timestamp>.json`
- **Contents**: Test results, scores, expected vs. actual values

### Clinical Validation
- **Location**: Console output (can be redirected to file)
- **Contents**: Comparison against NCCN/FDA/literature

---

## Example Output

```
================================================================================
AYESHA MBD4+TP53 ACCURACY BENCHMARK RESULTS
================================================================================

Total Tests: 15
Passed: 14 (93.3%)
Failed: 1 (6.7%)
Average Score: 0.912

--------------------------------------------------------------------------------
✅ PASS | Pathway Accuracy - DDR (MBD4)
      Score: 1.000
✅ PASS | Pathway Accuracy - TP53 (R175H)
      Score: 0.875
✅ PASS | Drug Accuracy - olaparib Efficacy
      Score: 0.800
✅ PASS | Drug Accuracy - PARP in Top 3
      Score: 1.000
...
================================================================================
```

---

**Last Updated**: January 27, 2025  
**Status**: ✅ Production Ready

