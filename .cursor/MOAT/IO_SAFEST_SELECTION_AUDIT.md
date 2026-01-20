# IO Safest Selection — Manager Decisions (Locked)

**Date:** 2026-01-11  
**Owner:** Zo  
**Scope:** Defines the canonical “safest IO selection” behavior so plumbing + frontend work stays consistent.

---

## Decisions (answers to plumber questions)

### 1) PD‑L1 threshold
- **Rule**: **PD‑L1 CPS ≥ 1** is treated as an **eligibility signal**: `PDL1_POSITIVE_CPS`.
- **Interpretation**: PD‑L1 is **supportive / indication-dependent** (not a guaranteed benefit signal). We surface this via `eligibility_quality=inferred` when PD‑L1 is the only signal.

### 2) Hypermutator inference logic (MBD4 / POLE / POLD1)
- **Rule**: Presence of a hypermutator gene is treated as a **supportive eligibility signal** only: `HYPERMUTATOR_INFERRED:<genes>`.
- **Not allowed**: Do **n “measured TMB-high” and do **not** imply IO benefit.
- **Product behavior**: If eligibility is based only on PD‑L1/hypermutator signals, return `eligibility_quality=inferred` and set `evidence_gap` recommending confirmatory biomarkers.

### 3) Organ risk flags (e.g., prior pneumonitis)
- **Schema**: `patient_context.organ_risk_flags: List[str]`.
- **Policy**: Conservative down-ranking via **risk multiplier** + explicit rationale. No silent exclusion.
- **Implemented MVP**: `prior_pneumonitis` increases risk for drugs with pneumonitis ≥ 3% (adds a `risk_factors` entry).

### 4) RUO disclaimer text
- **Exact string** (must match backend output):
  - `Research Use Only (RUO). This is decision support, not medical advice.`

### 5) Insufficient evidence message
- When no signals exist, return:
  - `eligible=false`
  - `evidence_gap="No IO eligibility signals found (need MSI/TMB/PD-L1 or hypermutator evidence)."`
  - `needs_confirmatory_biomarkers=["tmb","msi_status","mmr_status","pd_l1_cps"]`

---

## Iation notes

### Backend
- **Eligibility parsing supports multiple shapes**:
  - `tumor_context.pd_l1_cps`
  - `tumor_context.pd_l1.cps`
  - `tumor_context.biomarkers.pd_l1_cps`
  - Same for `mmr_status` and `msi_status`.
- **Germline hypermutator support**: `germline_mutations` are included in the hypermutator gene check.
- **Eligibility quality**:
  - `measured`: MSI‑H / dMMR / TMB≥10
  - `inferred`: only PD‑L1 and/or hypermutator
  - `insufficient`: no signals

### Frontend (Ayesha)
- Must show `io_selection` block on the patient page.
- Must preserve the RUO disclaimer and display `evidence_gap` when eligibility is inferred.

---

## Files changed to enforce these decisions
- `oncology-coPilot/oncology-backend-minimal/api/services/io_safest_selection_service.py`
- `oncology-coPilot/oncology-backend-minimal/api/services/toxicity_pathway_mappings.py`
- `oncology-coPilot/oncology-backend-minimal/api/routers/ayesha_orchestrator_v2.py`
- `oncology-coPilot/oncology-frontend/src/pages/AyeshaCompleteCare. `oncology-coPilot/oncology-frontend/src/components/ayesha/IOSafestSelectionCard.jsx`
- `oncology-coPilot/oncology-backend-minimal/tests/unit/test_io_safest_selection_service.py`
- `oncology-coPilot/oncology-backend-minimal/tests/integration/test_io_selection_router.py`
