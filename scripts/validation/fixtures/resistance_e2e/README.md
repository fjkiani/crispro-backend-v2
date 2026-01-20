# Resistance E2E Fixtures

**Purpose:** Deterministic test fixtures for end-to-end resistance prediction validation.

**Location:** `scripts/validation/fixtures/resistance_e2e/`

---

## Fixture Descriptions

### `l0_mutations_only.json`
**Input Level:** L1 (mutations-only MVP)  
**Expected Confidence Cap:** 0.6  
**Expected Flags:**
- `INPUT_LEVEL_L1`
- `MISSING_CA125_HISTORY`

**What it proves:**
- MVP works with mutations-only input (CA-125 series missing is a data gap, not an error)
- Confidence is appropriately capped at 0.6 for L1 completeness
- Missing inputs are flagged as data gaps (not errors)

**Mutations:**
- MBD4 p.Ile413Serfs*2 (frameshift)
- TP53 p.Arg175His (missense)

---

### `l1_with_ca125.json`
**Input Level:** L2 (mutations + CA-125 series)  
**Expected Confidence Cap:** 0.8  
**Expected Flags:**
- `INPUT_LEVEL_L2`

**What it proves:**
- CA-125 series + mutations enables L2 completeness (confidence cap 0.8)
- Missing optional markers do not block MVP
- CA-125 kinetics can be used for resistance monitoring

**CA-125 History:**
- 3 measurements showing initial drop then rise (potential resistance signal)

---

### `l2_full_completeness.json`
**Input Level:** L2 (mutations + CA-125 + HRD score)  
**Expected Confidence Cap:** 0.8  
**Expected Flags:**
- `INPUT_LEVEL_L2`

**What it proves:**
- Full completeness (mutations + biomarkers + HRD) enables highest confidence cap (0.8; conservative until Ring-2 outcomes validation)
- Expression data is optional (RUO; MVP works without it)
- HRD score integration works when available

**HRD Score:** 42.5

---

### `edge_case_2_of_3_trigger.json`
**Input Level:** L2  
**Expected Confidence Cap:** 0.8  
**Expected Flags:**
- `INPUT_LEVEL_L2`

**What it proves:**
- "2-of-3 trigger" logic works (HRD drop + CA-125 inadequate response + DNA repair capacity drop)
- NF1 loss (MAPK activation) triggers resistance detection
- CA-125 rising trend (>25% from nadir) is detected

**Mutations:**
- NF1 p.Arg1946* (stop gained)

**CA-125 History:**
- Rising trend: 200 → 250 → 320 U/mL

---

### `expression_present_ruo.json`
**Input Level:** L1  
**Expected Confidence Cap:** 0.6  
**Expected Flags:**
- `INPUT_LEVEL_L1`
- `MISSING_CA125_HISTORY` (CA-125 series not present; data gap)

**What it proves:**
- Expression data enables MFAP-4/EMT resistance rules (GSE63885 validated)
- MVP works without expression, but if present, unlocks additional biomarkers
- RUO (Research Use Only) data is handled gracefully

**Expression Data:**
- MFAP4: 2.3 TPM
- Vimentin: 1.8 TPM (EMT marker)
- E-cadherin: 0.5 TPM (epithelial marker)

---

## Usage

Run the fixture-driven validator:

```bash
python3 oncology-coPilot/oncology-backend-minimal/scripts/validation/validate_resistance_e2e_fixtures.py
```

Or via the Ring-1 suite:

```bash
python3 oncology-coPilot/oncology-backend-minimal/scripts/validation/run_resistance_validation_suite.py --ring1
```

---

## Adding New Fixtures

1. Create a new JSON file in this directory
2. Follow the schema:
   - `description`: Human-readable description
   - `expected_input_level`: "L0" | "L1" | "L2"
   - `expected_confidence_cap`: float (0.0-1.0)
   - `expected_flags`: List[str] (flags that should appear in provenance)
   - `patient_profile`: Full patient profile matching `/api/complete_care/v2` input schema
3. Add the fixture name to `validate_resistance_e2e_fixtures.py::main()` fixture list
4. Update this README

---

## Notes

- **Expression data is optional**: MVP must work without expression. If present, it enables ECM/EMT expression rules, but absence is a data gap, not an error.
- **CA-125 series missing**: flagged as `MISSING_CA125_HISTORY` (data gap; does not block mutations-only MVP).

