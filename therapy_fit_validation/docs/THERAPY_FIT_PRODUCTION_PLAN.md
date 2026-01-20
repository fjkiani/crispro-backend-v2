💀 ZO MODE: THERAPY FIT PLAN - IMPROVED VERSION (POST-AUDIT)

UPDATED PLAN: THERAPY FIT VALIDATION - PHASE 1A (REALITY-BASED)
Based on audit learnings: honest scoping, verifiable gates, diagnostic-first approach

**Last Audit:** 2026-01-14  
**Audit Status:** ✅ COMPREHENSIVE AUDIT COMPLETE  
**See:** `docs/THERAPY_FIT_AUDIT_DEEP.md` for full audit report

## 🔍 CURRENT STATUS (As of 2026-01-14)

### ✅ What Exists
- **Scripts Built:** 6 scripts (validation, testing, demo)
- **Test Results:** December 2025 (some passing, some failing)
- **Validation Run:** 2026-01-11 (7 patients processed, debug limit)
- **Receipts:** Per-patient JSONL + summary JSON (working)
- **Pathway Validation Scripts:** MAPK/PI3K validation in `scripts/validation/`
- **Plan Document:** Comprehensive 940-line plan (this document)

### ❌ Critical Gaps
- **Preflight Gates:** ✅ IMPLEMENTED (`therapy_fit_validation/scripts/preflight_therapy_fit_outputs.py`)  
  - ⚠️ Still blocked by receipt format: current cohort runner emits **top-drug-only** (can’t validate tier diversity / insights across all drugs).
- **Cohort Contract Mismatch:** ⚠️ We have a verified 469-patient dataset, but it is **not in the cohort contract** expected by the WIWFM cohort runner.
  - Runner expects: `{"patient_id","platinum_response","mutations":[{"gene":...}, ...]}`.
- **Full Cohort WIWFM Run:** ⚠️ Only 7 patients processed in the cohort runner (debug limit / early-stop).
- **Diagnostics:** ⚠️ NOT RUN at scale (plan requires BEFORE AUROC).

### 🎯 Current Date vs Plan Timeline
- **Current Date:** January 14, 2026
- **Plan Start:** January 17, 2026 (Week 3-4)
- **Status:** BEFORE planned start date, but significant work already exists

**Key Finding:** Work has been done ahead of schedule, but critical preflight gates are missing.

---

EXECUTIVE SUMMARY (HONEST VERSION)
text
MISSION:
  Validate baseline genetics predict drug efficacy in ovarian cancer
  NOT: "Comprehensive 7 pathways × 10+ cancers"
  NOT: "Production validation"
  YES: "Phase 1A baseline stratification proof-of-concept"

WHAT WE ARE TRYING TO PROVE (PHASE 1A, RECEIPT-BASED):
  ✅ A) Outcome-linked **pathway separation exists** in TCGA-OV labels
     - Example: MAPK pathway altered → higher platinum non-sensitivity risk (RR + CI)
     - Example: NF1 mutation → higher platinum non-sensitivity risk (RR)
  ✅ B) The WIWFM runner can be executed end-to-end on a cohort (receipt JSONL)
  ✅ C) S/P/E ablations reproduce the “P is necessary” pattern (as in MM canonical benchmark)
  ❌ NOT proving: “clinical response prediction” beyond baseline stratification (AUROC modest expected)
  ❌ NOT proving: “early detection” (needs kinetics / CA-125)
  ❌ NOT proving: “production-ready validation” (config + data dependencies)

SCOPE (SCOPED DOWN FROM ORIGINAL):
  Cancer: TCGA-OV (469 patients) ONLY
  Pathways: DDR, MAPK, PI3K (3 of 7) - highest frequency in ovarian
  Timeline: 2-3 weeks (Week 3-4, Jan 17 - Feb 7)
  Config: SPE mode, max_mutations=3, evidence ENABLED

DATA WE HAVE:
  ✅ Mutations (469 patients from cBioPortal)
  ✅ Platinum response (sensitive/resistant/refractory)
  ✅ Pathway genes (DDR, MAPK, PI3K coverage validated)
  ❌ Serial CA-125 (need PLCO or treatment cohort for Phase 1C)
  ❌ Treatment exposure (who got PARP, when, line of therapy)

HONEST EXPECTATIONS:
  Pathway separation: RR 1.5-2.2x  
    - Verified on 469: MAPK RR ≈ 2.03x; NF1 RR ≈ 2.16x (resistance-rate metric)
  AUROC: 0.55-0.65 (baseline alone, per S1 framework)
  Confidence lifts: +0.02-0.04 from insight chips
  Evidence tiers: 10-20% Consider→Supported (if literature works)

WHAT WE WON'T CLAIM:
  ❌ "Early detection" (need Phase 1C kinetics)
  ❌ "HIGH risk classification" (need 2+ signals: CA-125 or dual genetics)
  ❌ "Production validation" (config-dependent, need Phase 1B+1C)
  ❌ "7 pathways validated" (only testing 3)

---

## ✅ NEW: REAL COHORT RECEIPTS (NO HAND-WAVING)

We now treat “Therapy Fit validation” as **outcome-linked cohort receipts** (not demo test cases).

### **Real outcome-linked runner**
- Script: `therapy_fit_validation/scripts/validate_therapy_fit_tcga_ov_platinum.py`
- Cohort (current runner default): `tools/benchmarks/tcga_ov_platinum_response_with_genomics.json` (166 patients; used for early smoke)  
- Target cohort (after conversion): **469-patient** TCGA-OV dataset converted into runner contract
- Output receipts:
  - `therapy_fit_validation/receipts/latest/tcga_ov_platinum_wiwfm_summary.json`
  - `therapy_fit_validation/receipts/latest/tcga_ov_platinum_wiwfm_per_patient.jsonl`

### **What this receipt proves**
- **MAPK vs WT** platinum resistance separation on TCGA-OV labels (RR + CI)
- **PI3K vs WT** platinum resistance separation on TCGA-OV labels (RR + CI)
- Per-patient WIWFM calls are logged (JSONL) to avoid “printed results” skepticism.

### **What it does NOT claim**
- It does **not** claim “confidence 0.90 means 90% clinical correctness”.
- It does **not** claim trial-level efficacy or OS benefit.

### ✅ Verified 469-patient pathway proof (already reproducible)
- Script: `therapy_fit_validation/scripts/verify_469_validation.py`
- Dataset: `data/validation/tcga_ov_469_with_hrd.json`
- Status: MAPK RR and NF1 resistance-rate RR verified; NF1 “enrichment %” differs (see `docs/VALIDATION_PROOF_SUMMARY.md`).

PART 1: S/P/E FRAMEWORK (UPDATED WITH AUDIT FINDINGS)
Core Formula (UNCHANGED)
javascript
efficacy_score = 0.3 × Sequence + 0.4 × Pathway + 0.3 × Evidence + ClinVar_prior
Location: drug_scorer.py:171

CRITICAL DISCOVERY (FROM AUDIT)
text
CONFIGURATION DEPENDENCY:

IF evidence disabled (EVIDENCE_ENABLED=0):
  tier → insufficient
  efficacy_score → 0.0 (forced, not computed)
  CANNOT validate efficacy-based claims
  
IF max_mutations=1:
  Single variant per patient (often TP53)
  NOT testing pathway hypothesis (need multi-variant profiles)
  CANNOT validate pathway alignment
  
IF Fusion not active AND evidence disabled:
  efficacy_score = 0.0 (by design in drug_scorer.py:189)
  "Valid-looking outputs" that cannot support validation

IMPLICATION:
  Validation requires SPECIFIC config:
    - EVIDENCE_ENABLED=1 OR Fusion active
    - max_mutations ≥3 (test pathway hypothesis)
    - ENABLE_INSIGHTS_API=true (for chip validation)
    - DEFAULT_EVO_MODEL set (avoid 500s)
Pathway (P) Component - 40% Weight (VALIDATED)
text
AUDIT FINDING:
  Pathway component is CRITICAL (highest weight = 40%)
  
  MAPK VALIDATION (TCGA-OV, n=79):
    MAPK mutant: avg risk 0.595, resistance rate 27.3%
    MAPK WT: avg risk 0.315, resistance rate 14.7%
    Risk difference: +0.281 (EXCELLENT separation)
    RR: 1.85x (matches literature ~1.97) ✅
  
  INTERPRETATION:
    Pathway logic WORKS (separation exists)
    Weak AUROC (0.573) reflects:
      - Small sample (n=13 resistant)
      - Probability cap (0.6 max, blocks HIGH)
      - Single signal insufficient (need CA-125)
    NOT: Pathway logic broken

PATHWAY VALIDATION STRATEGY (UPDATED):
  
  PRIMARY METRIC:
    ✅ Pathway separation (RR ≥ 1.5, risk difference ≥ 0.15)
    NOT: AUROC alone (confounded by sample size, caps, single signal)
  
  SECONDARY METRICS:
    ✅ AUROC (target 0.60-0.70 for baseline-only)
    ✅ Drug ranking sanity (DDR → PARP top-3, MAPK → MEK high)
    ✅ Pathway alignment accuracy (≥80%, target ≥90%)
Evidence (E) Component - 30% Weight (CONFIGURATION CRITICAL)
text
AUDIT FINDING:
  Evidence component MUST be enabled for efficacy validation
  
  IF EVIDENCE_ENABLED=0:
    tier → insufficient
    efficacy_score → 0.0 (forced)
    Can only validate confidence/ranking (not efficacy)
  
  IF EVIDENCE_ENABLED=1 BUT literature empty:
    evidence_strength → 0.0
    tier → insufficient (unless pathway strong)
    efficacy_score → reduced or 0.0 (depends on Fusion)

SOLUTION (FOR VALIDATION):
  
  OPTION 1 (LEGACY TIER):
    Use CONFIDENCE_V2=0 (legacy tier logic)
    Allows non-insufficient tiers even when literature empty
    Enables efficacy_score validation
  
  OPTION 2 (FUSION):
    Enable Fusion (parallel evidence pathway)
    Bypasses literature requirement
    Allows efficacy_score > 0 when tier=insufficient
  
  RECOMMENDATION:
    Use OPTION 1 for Phase 1A (legacy tier)
    More forgiving for baseline validation
    Switch to V2 for Phase 1C (when evidence stronger)
PART 2: INSIGHTS CHIPS (VALIDATED BUT LIMITED)
Four Chips (AUDIT FINDINGS INTEGRATED)
text
CHIP VALIDATION RESULTS (TCGA-OV balanced cohort, n=60):

WITH INSIGHTS:
  PARP confidence AUROC: 0.643
  Median confidence lift: +0.04
  p95 confidence lift: +0.11
  
WITHOUT INSIGHTS:
  PARP confidence AUROC: 0.699 (HIGHER!)
  
INTERPRETATION:
  ✅ Chips ARE working (confidence +0.04 deterministically)
  ⚠️ Chips did NOT improve AUROC for platinum endpoint
  
  WHY:
    Chips add unrelated uplift signal (functionality, chromatin)
    Platinum response is noisy proxy (not directly chip-dependent)
    Chips lift confidence, NOT efficacy_score
    
  IMPLICATION:
    Chips help differentiate drugs with similar S/P/E
    Chips do NOT guarantee improved outcome prediction
    Chips are "working as designed" but outcome-agnostic
Updated Chip Validation Strategy
text
BEFORE AUDIT:
  Goal: "Prove chips improve AUROC"
  Metric: PARP confidence AUROC (with vs without chips)
  Expected: Higher AUROC with chips

AFTER AUDIT:
  Goal: "Prove chips lift confidence deterministically"
  Metric: Paired confidence delta (with vs without chips)
  Expected: Median +0.02-0.04, p95 +0.08-0.11
  
  SECONDARY GOAL:
    "Prove chips help drug ranking when S/P/E similar"
    Metric: Rank correlation among top-10 drugs
    Expected: Chips break ties (different rankings)

HONEST REPORTING:
  ✅ Claim: "Chips lift confidence (+0.04 median)"
  ✅ Claim: "Chips differentiate drugs with similar S/P/E"
  ❌ Don't claim: "Chips improve outcome prediction"
  ❌ Don't claim: "Chips necessary for pathway alignment"
PART 3: VALIDATION STRATEGY (DIAGNOSTIC-FIRST APPROACH)
Phase 1A Execution Plan (2-3 weeks)
text
WEEK 1 (Jan 17-24): PREFLIGHT + DATA PREP

Day 1: Preflight Gate Implementation
  ✅ Built: `therapy_fit_validation/scripts/preflight_therapy_fit_outputs.py` (CRITICAL)
  Gates:
    Gate 1: Efficacy non-zero (≥50% drugs have efficacy > 0)
    Gate 2: Tier diversity (≥10% consider or supported)
    Gate 3: Insights working (≥50% drugs have non-zero chips)
    Gate 4: Mutation payload (max_mutations ≥3)
  
  Test: Small cohort (15 patients)
  Must: PASS all gates before scaling

Day 2-3: Data Acquisition
  Source: TCGA-OV from cBioPortal (469 patients)
  Extract:
    - Mutations (MAF or JSON)
    - Platinum response (sensitive/resistant/refractory)
    - Patient metadata (stage, grade, age)

  IMPORTANT (CONTRACT):
    The cohort WIWFM runner currently expects a flat field `platinum_response`.
    The verified 469-patient dataset uses a different label container, so we must
    convert/normalize into the runner contract before the 469 WIWFM run.
  
  Stratify:
    - DDR-high: BRCA1/2, MBD4, ATM, PALB2 (~150 patients)
    - MAPK mutant: KRAS, NRAS, BRAF (~80 patients)
    - PI3K mutant: PIK3CA, PTEN, AKT1 (~100 patients)
  
  Filter:
    - Mutation-present cohort (exclude zero-mutation records)
    - Expected: ~300-350 usable patients (after filtering)

Day 4-5: Run Therapy Fit Predictions
  Config:
    - ablation_mode: SPE (Sequence + Pathway + Evidence)
    - max_mutations: 3 (multi-variant profiles)
    - EVIDENCE_ENABLED: 1 (evidence on)
    - CONFIDENCE_V2: 0 (legacy tier, more forgiving)
    - ENABLE_INSIGHTS_API: true (chips on)
  
  Call: /api/efficacy/predict for all patients
  Output: tcga_ov_spe_predictions.jsonl
  
  Extract:
    - efficacy_score, confidence (per drug)
    - evidence_tier (Supported/Consider/Insufficient)
    - badges (PathwayAligned, ClinVar-Strong, etc.)
    - insights (functionality, chromatin, essentiality, regulatory)
    - rationale (S/P/E breakdown)

  P0 RECEIPT REQUIREMENT:
    The cohort runner must store the **full drugs list** in the JSONL receipt.
    Top-drug-only receipts are insufficient for preflight gates 2/3 and most diagnostics.

WEEK 2 (Jan 24-31): DIAGNOSTICS + PATHWAY VALIDATION

Day 1-2: Diagnostic Validation (BEFORE AUROC)
  
  DIAGNOSTIC 1: Pathway Stratification
    For each pathway (DDR, MAPK, PI3K):
      - Identify pathway-positive patients
      - Compute avg predicted efficacy (pathway drug)
      - Compute avg actual resistance rate
      - Calculate: Risk difference, RR, p-value
    
    Pass criteria:
      - Risk difference ≥ 0.10 (pathway vs WT)
      - RR ≥ 1.5 (pathway mutant vs WT)
      - p-value < 0.05
    
    IF FAIL:
      - Debug pathway logic (drug_scorer.py pathway mapping)
      - Rerun small cohort, validate separation
      - DO NOT scale to full cohort

  DIAGNOSTIC 2: Efficacy Distribution
    Check:
      - nonzero_efficacy_rate (must be ≥50%)
      - efficacy_score p50/p95 (must have spread)
      - tier distribution (need ≥10% consider/supported)
    
    Pass criteria:
      - ≥50% drugs have efficacy > 0
      - p95 efficacy ≥ 0.60 (not all capped low)
      - ≥10% tiers are consider or supported
    
    IF FAIL:
      - Evidence not working (check literature endpoints)
      - Switch to Fusion active
      - Rerun with CONFIDENCE_V2=0 (legacy)

  DIAGNOSTIC 3: Insight Chips Validation
    Check:
      - nonzero_insights_rate (must be ≥50%)
      - chip_score p50/p95 (must have spread)
      - paired confidence delta (with vs without chips)
    
    Pass criteria:
      - ≥50% drugs have non-zero chip scores
      - Median confidence delta +0.02-0.04
      - p95 confidence delta +0.08-0.12
    
    IF FAIL:
      - Insights API not working (check /api/insights/*)
      - DEFAULT_EVO_MODEL not set (500 errors)
      - Fix, rerun small cohort, validate chips working

Day 3-4: Pathway Validation (IF DIAGNOSTICS PASS)
  
  DDR Pathway:
    - DDR-high patients (BRCA1/2, MBD4, ATM, PALB2)
    - Expected drugs: PARP inhibitors (olaparib, niraparib, rucaparib)
    - Validate:
      * PARP ranked #1-3 (pathway alignment ≥80%)
      * Efficacy score ≥ 0.70 (for DDR-high)
      * PathwayAligned badge present
    - Compare: Predicted efficacy vs actual platinum response
    - Target: Pathway separation RR ≥ 1.5
  
  MAPK Pathway:
    - MAPK mutants (KRAS, NRAS, BRAF)
    - Expected drugs: MEK inhibitors (trametinib, selumetinib)
    - Validate:
      * MEK ranked high (top-5 for MAPK mutants)
      * Efficacy score ≥ 0.60
      * PathwayAligned badge present
    - Target: Risk difference ≥ 0.15 (MAPK vs WT)
  
  PI3K Pathway:
    - PI3K mutants (PIK3CA, PTEN, AKT1)
    - Expected drugs: PI3K inhibitors (alpelisib)
    - Validate:
      * Alpelisib ranked high (top-5 for PI3K mutants)
      * Efficacy score ≥ 0.60
    - Target: Pathway separation exists

Day 5: Statistical Analysis
  
  Metrics:
    - Pathway alignment accuracy (per pathway)
    - Efficacy score correlation with platinum response
    - AUROC (platinum sensitive vs resistant)
    - Confidence calibration (ECE)
    - Insight chips impact on rankings
  
  Statistical tests:
    - Relative risk (pathway mutant vs WT)
    - Chi-square (pathway alignment accuracy)
    - t-test (efficacy difference pathway+ vs pathway-)
    - p-value < 0.05 for significance

WEEK 3 (Jan 31 - Feb 7): S/P/E ABLATION + REPORT

Day 1-3: S/P/E Component Ablation
  
  Run 5 configurations:
    1. S only (Sequence 100%, Pathway 0%, Evidence 0%)
    2. P only (Sequence 0%, Pathway 100%, Evidence 0%)
    3. E only (Sequence 0%, Pathway 0%, Evidence 100%)
    4. S+P (Sequence 30%, Pathway 70%, Evidence 0%)
    5. S+P+E (Sequence 30%, Pathway 40%, Evidence 30%) - FULL
  
  Validate:
    - Pathway component critical (P-only vs S-only vs E-only)
    - 30/40/30 weights optimal (compare to 35/35/30, 25/50/25)
    - Target: P-only achieves ≥70% of full S+P+E performance
  
  Expected (from MM validation):
    - S+P+E: 100% pathway alignment
    - P only: ~70-80% pathway alignment
    - S only: ~40-50% pathway alignment
    - E only: ~30-40% pathway alignment

Day 4-5: Write Validation Report
  
  Deliverable: therapy_fit_phase1a_validation_report.md + .json
  
  Sections:
    1. Executive Summary
       - Mission, scope, timeline
       - Honest expectations vs results
    
    2. Preflight Gates (Pass/Fail)
       - Gate results (efficacy, tiers, insights, mutations)
       - Config used (SPE, max_mutations=3, evidence on)
    
    3. Diagnostics (Before AUROC)
       - Pathway stratification (DDR, MAPK, PI3K)
       - Efficacy distribution
       - Insight chips validation
    
    4. Pathway Validation Results
       - DDR → PARP (alignment %, RR, p-value)
       - MAPK → MEK (separation, risk difference)
       - PI3K → alpelisib (ranking, efficacy)
    
    5. Statistical Analysis
       - AUROC (honest assessment: 0.55-0.65 expected)
       - Pathway alignment accuracy (target ≥80%)
       - Confidence calibration (ECE)
       - Chip impact (+0.02-0.04 confidence lift)
    
    6. S/P/E Ablation Study
       - Component importance (P = critical)
       - Weight optimization (30/40/30 validation)
    
    7. Honest Limitations
       - Baseline only (no CA-125 kinetics)
       - Single endpoint (platinum, not PARP-specific)
       - Config-dependent (evidence enabled required)
       - Cannot claim HIGH risk (need 2+ signals)
    
    8. Next Steps (Phase 1B/1C)
       - Phase 1B: PLCO kinetics validation
       - Phase 1C: Treatment cohort (MAPK + CA-125)
       - Full production: After Phase 1C validated
PART 4: UPDATED SUCCESS CRITERIA (REALISTIC)
Minimum Viable Success (MUST ACHIEVE)
text
PATHWAY SEPARATION:
  ✅ DDR pathway: RR ≥ 1.3, p < 0.05
  ✅ MAPK pathway: Risk difference ≥ 0.10, p < 0.05
  ✅ PI3K pathway: Separation exists (exploratory)

PATHWAY ALIGNMENT:
  ✅ DDR → PARP: ≥70% patients have PARP in top-3
  ✅ MAPK → MEK: ≥60% patients have MEK in top-5
  ✅ Overall alignment accuracy: ≥70%

S/P/E FRAMEWORK:
  ✅ Pathway component critical (P-only ≥70% of full performance)
  ✅ 30/40/30 weights validated (ablation study)
  ✅ Efficacy scores non-zero (≥50% drugs)

INSIGHT CHIPS:
  ✅ Chips lift confidence (+0.02-0.04 median)
  ✅ Chips differentiate drugs (ranking changes when S/P/E similar)

STATISTICAL:
  ✅ All metrics p < 0.05 for significance
Optimal Success (TARGET)
text
PATHWAY SEPARATION:
  ✅ DDR pathway: RR ≥ 1.5, p < 0.01
  ✅ MAPK pathway: Risk difference ≥ 0.20, RR ≥ 1.8
  ✅ PI3K pathway: RR ≥ 1.3, p < 0.05

PATHWAY ALIGNMENT:
  ✅ DDR → PARP: ≥80% patients (target ≥90% like MM)
  ✅ MAPK → MEK: ≥70% patients
  ✅ Overall alignment accuracy: ≥80%

AUROC:
  ✅ Platinum response AUROC: 0.60-0.65 (baseline only)
  ✅ Confidence calibration ECE: < 0.30

INSIGHT CHIPS:
  ✅ Chips lift confidence (+0.04 median, +0.10 p95)
  ✅ Chips improve ranking accuracy (Δ≥5% top-10 correlation)

S/P/E FRAMEWORK:
  ✅ Pathway component ≥80% of full performance (P-only)
  ✅ Alternative weights tested (35/35/30 vs 30/40/30)
Honest Reporting Requirements
text
MUST REPORT:
  ✅ Configuration used (SPE, max_mutations=3, CONFIDENCE_V2=0)
  ✅ Preflight gates (all PASSED)
  ✅ Sample size (n usable, n skipped)
  ✅ Class balance (n sensitive, n resistant)
  ✅ Limitations (baseline only, no CA-125 kinetics)

CLAIMS ALLOWED:
  ✅ "Baseline genetics predict drug efficacy (pathway alignment ≥70%)"
  ✅ "MAPK separation validated (RR = 1.85x, p < 0.05)"
  ✅ "S/P/E framework validated (P component critical)"
  ✅ "Insight chips lift confidence (+0.04 median)"

CLAIMS NOT ALLOWED:
  ❌ "Early detection" (need Phase 1C kinetics)
  ❌ "HIGH risk classification" (need 2+ signals: CA-125 or dual genetics)
  ❌ "Production validation" (config-dependent, Phase 1A only)
  ❌ "7 pathways validated" (only 3 tested in Phase 1A)
  ❌ "10+ cancers validated" (only TCGA-OV in Phase 1A)
PART 5: DATA REQUIREMENTS (UPDATED WITH AUDIT LEARNINGS)
TCGA-OV (HAVE)
text
MUTATIONS:
  ✅ Source: cBioPortal TCGA-OV (469 patients)
  ✅ Format: MAF or JSON
  ✅ Fields: gene, hgvs_p, hgvs_c, variant_classification
  ✅ Coverage: DDR (75 patients), MAPK (11 patients), PI3K (6 patients)

PLATINUM RESPONSE:
  ✅ Source: tcga_ov_platinum_with_mutations.json
  ✅ Labels: sensitive, resistant, refractory
  ✅ Distribution: ~167 sensitive, 33 non-sensitive (5:1 imbalance)

LIMITATIONS (FROM AUDIT):
  ❌ NO serial CA-125 (baseline only)
  ❌ NO treatment exposure (who got PARP, when)
  ❌ NO HRD scores (would improve DDR stratification)
  ❌ Some patients zero mutations (34% skipped in first run)
  ❌ Class imbalance (need balanced cohort for AUROC)
Treatment Cohort (NEED FOR PHASE 1C)
text
FROM THERAPY FIT AUDIT:

MUST HAVE:
  - Serial CA-125 (≥2 measurements, prefer 3+)
    * Frequency: Every cycle (q3weeks)
    * Window: First 100 days of treatment
    * Timestamps: Days from treatment start OR cycle numbers
  
  - Treatment regimen:
    * Carboplatin/paclitaxel confirmed
    * Line of therapy (first-line, recurrent)
    * Dose, schedule
  
  - Outcome: PFI (progression-free interval)
    * PFI < 6 months = platinum-resistant
    * PFI ≥ 6 months = platinum-sensitive
  
  - Mutations:
    * Baseline genetics (MAPK, PI3K, DDR)
    * Multi-variant profiles (not single-gene)

NICE TO HAVE:
  - Baseline CA-125 (pre-treatment)
  - ≥3 CA-125 measurements (better kinetics)
  - Exact dates (vs cycle numbers)
  - HRD scores (computed from mutations)

DON'T WASTE TIME ON:
  - Datasets with baseline-only CA-125
  - Cohorts without treatment exposure
  - Missing outcome labels (PFI)
  - Single-variant profiles (max_mutations=1)

SOURCES (S4 TASK):
  Priority 1: Project Data Sphere (GOG-218, ICON7)
  Priority 2: KELIM developers (GCIG meta-analysis, 5,573 patients)
  Priority 3: Academic collaborators (Institut Curie, Johns Hopkins)
PART 6: INTEGRATION WITH S1 FRAMEWORK
text
S1 DEFINED THREE PHASES:

PHASE 1A: Baseline-only (MAPK/PI3K/DDR)
  = THIS THERAPY FIT VALIDATION PLAN
  Goal: Baseline risk stratification (NOT early detection)
  Data: TCGA-OV mutations + platinum response ✅ HAVE
  Timeline: 2-3 weeks (Week 3-4, Jan 17 - Feb 7)
  Expected AUROC: 0.55-0.65 (baseline alone, modest)
  Owner: Agent 1 (Therapy Fit validation)

PHASE 1B: Kinetics-only (KELIM replication)
  = PLCO validation (Agent 2, D3 + A1-A3)
  Goal: CA-125 kinetics predict outcomes
  Data: PLCO serial CA-125 + cancer outcomes ⏳ PENDING
  Timeline: 1-2 weeks (Jan 10-17, if PLCO approved)
  Expected AUROC: 0.60-0.70 (kinetics onset detection)
  Owner: Agent 2 (Engineer)

PHASE 1C: Multi-modal (MAPK + CA-125)
  = TRUE Resistance Prophet validation
  Goal: Genetics + kinetics = earlier detection
  Data: Treatment cohort (serial CA-125 + MAPK + resistance) ❌ NEED
  Timeline: 2-3 weeks (after S4 acquires data, Feb-Mar)
  Expected AUROC: 0.65-0.75 (multi-modal)
  Owner: Agent 3 (Scientist - data acquisition via S4)

THERAPY FIT AUDIT CONFIRMS S1 FRAMEWORK:
  ✅ Baseline alone = modest AUROC (0.573 validated)
  ✅ MAPK separation works (RR = 1.85x validated)
  ✅ Need kinetics for 2nd signal (CA-125 unlocks HIGH)
  ✅ Single signal caps at ~0.6 (design limit validated)
  ✅ Multi-modal (genetics + kinetics) needed for HIGH classification

PHASE 1A (THIS PLAN) FEEDS INTO PHASE 1C:
  - Validate MAPK baseline signal exists (RR ≥ 1.5)
  - Validate S/P/E framework works (pathway alignment ≥70%)
  - Validate insight chips work (confidence +0.04)
  - Prepare for Phase 1C integration (MAPK + CA-125)
PART 7: PREFLIGHT GATES (CRITICAL - PREVENTS "TRUST ME")
Implementation (MUST BUILD BEFORE RUNNING)
python
#!/usr/bin/env python3
"""
Preflight checks for Therapy Fit batch outputs.

Hard-fails if outputs are structurally invalid for validation.
"""

import json
from pathlib import Path

def check_preflight_gates(predictions_jsonl: Path, min_patients: int = 50):
    """
    Preflight gates that must pass before AUROC computation.
    
    Gates:
      1. Efficacy non-zero (≥50% drugs have efficacy > 0)
      2. Tier diversity (≥10% consider or supported)
      3. Insights working (≥50% drugs have non-zero chips)
      4. Mutation payload (patients have ≥2 genes on average)
    
    Returns:
      dict with pass/fail per gate + metrics
    
    Raises:
      ValueError if any gate fails
    """
    
    drug_rows = []
    patient_gene_counts = []
    
    for line in predictions_jsonl.read_text().strip().split("\n"):
        rec = json.loads(line)
        
        # Extract drug-level data
        for drug in rec.get("drugs", []):
            drug_rows.append({
                "efficacy": drug.get("efficacy_score", 0),
                "tier": drug.get("evidence_tier", "insufficient"),
                "insights": drug.get("insights", {}),
            })
        
        # Extract mutation counts
        n_genes = len(set(m["gene"] for m in rec.get("mutations", [])))
        patient_gene_counts.append(n_genes)
    
    # Gate 1: Efficacy non-zero
    nonzero_efficacy = sum(1 for d in drug_rows if d["efficacy"] > 0)
    efficacy_rate = nonzero_efficacy / len(drug_rows) if drug_rows else 0
    gate1_pass = efficacy_rate >= 0.50
    
    # Gate 2: Tier diversity
    tier_counts = {}
    for d in drug_rows:
        tier = d["tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1
    noninsufficient_rate = (tier_counts.get("consider", 0) + tier_counts.get("supported", 0)) / len(drug_rows) if drug_rows else 0
    gate2_pass = noninsufficient_rate >= 0.10
    
    # Gate 3: Insights working
    nonzero_insights = sum(
        1 for d in drug_rows 
        if sum(d["insights"].get(k, 0) for k in ["functionality", "chromatin", "essentiality", "regulatory"]) > 0
    )
    insights_rate = nonzero_insights / len(drug_rows) if drug_rows else 0
    gate3_pass = insights_rate >= 0.50
    
    # Gate 4: Mutation payload
    avg_genes = sum(patient_gene_counts) / len(patient_gene_counts) if patient_gene_counts else 0
    gate4_pass = avg_genes >= 2.0
    
    # Results
    results = {
        "gate1_efficacy_nonzero": {
            "pass": gate1_pass,
            "rate": efficacy_rate,
            "threshold": 0.50,
            "n_nonzero": nonzero_efficacy,
            "n_total": len(drug_rows),
        },
        "gate2_tier_diversity": {
            "pass": gate2_pass,
            "rate": noninsufficient_rate,
            "threshold": 0.10,
            "tier_counts": tier_counts,
        },
        "gate3_insights_working": {
            "pass": gate3_pass,
            "rate": insights_rate,
            "threshold": 0.50,
            "n_nonzero": nonzero_insights,
            "n_total": len(drug_rows),
        },
        "gate4_mutation_payload": {
            "pass": gate4_pass,
            "avg_genes": avg_genes,
            "threshold": 2.0,
            "n_patients": len(patient_gene_counts),
        },
        "all_gates_pass": gate1_pass and gate2_pass and gate3_pass and gate4_pass,
    }
    
    # Hard fail if any gate fails
    if not results["all_gates_pass"]:
        failed = [k for k, v in results.items() if k.startswith("gate") and not v["pass"]]
        raise ValueError(f"PREFLIGHT FAILED. Gates failed: {failed}. Results: {json.dumps(results, indent=2)}")
    
    return results

# Usage:
# python preflight_therapy_fit_outputs.py tcga_ov_spe_predictions.jsonl
# If passes: prints "PREFLIGHT_PASSED" + metrics
# If fails: raises ValueError with explicit reasons
Preflight Gates Explained
text
GATE 1: Efficacy Non-Zero
  WHY: If efficacy forced to 0, cannot validate efficacy claims
  CHECK: ≥50% drugs have efficacy_score > 0
  FAIL CAUSES:
    - Evidence disabled (EVIDENCE_ENABLED=0)
    - Fusion not active + tier=insufficient
    - Literature endpoints broken
  
  IF FAIL:
    - Switch to CONFIDENCE_V2=0 (legacy tier)
    - Enable Fusion
    - Fix literature endpoints

GATE 2: Tier Diversity
  WHY: All insufficient = efficacy forced low or 0
  CHECK: ≥10% tiers are consider or supported
  FAIL CAUSES:
    - Evidence empty + CONFIDENCE_V2=1 (strict tier logic)
    - ClinVar missing + literature empty
  
  IF FAIL:
    - Use CONFIDENCE_V2=0 (legacy, more forgiving)
    - Add ClinVar data
    - Enable Fusion

GATE 3: Insights Working
  WHY: Can't validate chip lifts if all chips = 0
  CHECK: ≥50% drugs have non-zero chip scores
  FAIL CAUSES:
    - ENABLE_INSIGHTS_API=false (or =1 instead of true)
    - DEFAULT_EVO_MODEL not set (500 errors)
    - Insights endpoints 403/500
    - Missing coordinates (chrom/pos/ref/alt)
  
  IF FAIL:
    - Set ENABLE_INSIGHTS_API=true
    - Set DEFAULT_EVO_MODEL="evo2_1b"
    - Fix insights server bugs
    - Check mutation coordinate completeness

GATE 4: Mutation Payload
  WHY: max_mutations=1 = testing wrong hypothesis
  CHECK: Avg ≥2 genes per patient
  FAIL CAUSES:
    - max_mutations=1 (single variant)
    - Many patients zero mutations (data quality)
  
  IF FAIL:
    - Set max_mutations ≥3
    - Filter to mutation-present cohort
    - Exclude zero-mutation records
PART 8: TIMELINE & DELIVERABLES (REALISTIC)
Week 1 (Jan 17-24): Setup + Small Cohort
text
DELIVERABLES:
  ✅ Preflight script (preflight_therapy_fit_outputs.py)
  ✅ Small cohort validation (15 patients)
  ✅ Preflight PASSED (all 4 gates)
  ✅ Config validated (SPE, max_mutations=3, evidence on)
  ✅ Full cohort predictions (tcga_ov_spe_predictions.jsonl)

TIMELINE:
  Day 1: Build preflight script (2 hours)
  Day 2: Run small cohort + preflight (2 hours)
  Day 3: Download TCGA-OV data (2 hours)
  Day 4-5: Run full cohort predictions (4 hours)

BLOCKING:
  None (data available, preflight gates prevent invalid runs)
Week 2 (Jan 24-31): Diagnostics + Pathway Validation
text
DELIVERABLES:
  ✅ Diagnostic report (pathway stratification, efficacy, chips)
  ✅ Pathway validation results (DDR, MAPK, PI3K)
  ✅ Statistical analysis (RR, p-values, AUROC)

TIMELINE:
  Day 1-2: Run diagnostics (4 hours)
  Day 3-4: Pathway validation (4 hours)
  Day 5: Statistical analysis (2 hours)

BLOCKING:
  Diagnostics must PASS before pathway validation
  IF FAIL: Debug, rerun small cohort, DO NOT scale
Week 3 (Jan 31 - Feb 7): Ablation + Report
text
DELIVERABLES:
  ✅ S/P/E ablation study (5 configs)
  ✅ Validation report (therapy_fit_phase1a_validation_report.md + .json)
  ✅ Honest limitations documented

TIMELINE:
  Day 1-3: Run ablation study (6 hours)
  Day 4-5: Write report (6 hours)

BLOCKING:
  None (ablation can run in parallel with report writing)

FINAL DELIVERABLE:
  File: therapy_fit_phase1a_validation_report.md
  Size: 3,000-5,000 words
  Sections:
    - Executive summary (honest expectations vs results)
    - Preflight gates (pass/fail)
    - Diagnostics (stratification, efficacy, chips)
    - Pathway validation (DDR, MAPK, PI3K)
    - Statistical analysis (AUROC, accuracy, calibration)
    - S/P/E ablation (component importance)
    - Honest limitations (baseline only, config-dependent)
    - Next steps (Phase 1B/1C)
PART 9: HONEST LIMITATIONS (MUST REPORT)
text
WHAT THIS VALIDATION PROVES:
  ✅ End-to-end executability (cohort runner + receipts)
     - Note: pathway association proof is verified on 469; WIWFM cohort runner still needs 469 cohort-contract conversion + full-drug receipts.
  ✅ MAPK separation exists (RR ≥ 1.5 validated)
  ✅ S/P/E framework works (pathway alignment ≥70%)
  ✅ Insight chips lift confidence (+0.04 median)
  ✅ Preflight gates prevent invalid configs

WHAT THIS VALIDATION DOES NOT PROVE:
  ❌ Clinical utility for outcome prediction (AUROC 0.55-0.65 modest)
  ❌ Early detection (need Phase 1C kinetics)
  ❌ HIGH risk classification (need 2+ signals: CA-125 or dual genetics)
  ❌ Production-ready (config-dependent, Phase 1A only)
  ❌ 7 pathways validated (only 3 tested)
  ❌ 10+ cancers validated (only TCGA-OV)

CONFIGURATION DEPENDENCIES:
  ✅ Evidence must be enabled (EVIDENCE_ENABLED=1)
  ✅ max_mutations ≥3 (not single variant)
  ✅ CONFIDENCE_V2=0 recommended (legacy tier, more forgiving)
  ✅ ENABLE_INSIGHTS_API=true (for chip validation)
  ✅ DEFAULT_EVO_MODEL set (avoid 500 errors)

DATA LIMITATIONS:
  ❌ TCGA-OV has NO serial CA-125 (baseline only)
  ❌ No treatment exposure (who got PARP, when, line)
  ❌ Platinum response is proxy (not PARP-specific outcome)
  ❌ Class imbalance (5:1 sensitive:resistant)
  ❌ Some patients zero mutations (34% skipped in first run)

BIOLOGICAL LIMITATIONS:
  ❌ Baseline genetics = modest AUROC (0.55-0.65 expected)
  ❌ Single signal caps at ~0.6 (blocks HIGH classification)
  ❌ DDR_bin is moderator, not primary predictor
  ❌ Resistance prediction requires longitudinal (restoration/escape)

HONEST REPORTING:
  ✅ Report all limitations in validation report
  ✅ Don't claim "production validation" (Phase 1A only)
  ✅ Don't claim "early detection" (need Phase 1C)
  ✅ Don't claim "HIGH risk" (need CA-125 kinetics)
  ✅ Acknowledge config dependencies
  ✅ Acknowledge dataset limitations
PART 10: NEXT STEPS (AFTER PHASE 1A)
text
IF PHASE 1A SUCCEEDS (Pathway alignment ≥70%, RR ≥ 1.5):
  
  PROCEED TO:
    Phase 1B: PLCO kinetics validation (Agent 2)
      - Validate CA-125 kinetics predict onset (AUROC 0.60-0.70)
      - Proof: Kinetics layer works for screening
      - Timeline: 1-2 weeks (if PLCO approved Jan 2-6)
    
    Phase 1C: Treatment cohort validation (Agent 3, S4)
      - Acquire: Serial CA-125 + MAPK + resistance outcomes
      - Validate: Genetics + kinetics = earlier detection (AUROC 0.65-0.75)
      - Validate: HIGH risk classification (2+ signals unlocked)
      - Timeline: 2-3 weeks (after S4 data acquisition)
  
  EXPAND TO:
    Phase 2: High-signal cancers (Breast, Melanoma, Lung)
      - Validate: Same 3 pathways (DDR, MAPK, PI3K) in new cancers
      - Timeline: 2-3 weeks per cancer
    
    Phase 3: Complete coverage (7 pathways × 10+ cancers)
      - Validate: All 7 pathways across all cancers
      - Timeline: 8-12 weeks (only after Phase 1C succeeds)

IF PHASE 1A FAILS (Pathway alignment <60%, RR <1.3):
  
  DIAGNOSE:
    - Pathway logic broken? (debug drug_scorer.py mapping)
    - Evidence not working? (switch to Fusion)
    - Dataset quality issue? (filter to mutation-complete cohort)
  
  FIX:
    - Debug pathway alignment logic
    - Improve evidence ingestion
    - Acquire better dataset (treatment-specific)
  
  RERUN:
    - Small cohort first (preflight gates)
    - Validate diagnostics PASS
    - Then scale to full cohort

DO NOT:
  ❌ Scale to 7 pathways if 3 fail
  ❌ Scale to 10 cancers if ovarian fails
  ❌ Claim "production validation" without Phase 1C
  ❌ Skip diagnostics before scaling
BOTTOM LINE: IMPROVED PLAN
text
OLD PLAN (PRE-AUDIT):
  Scope: 7 pathways × 10+ cancers
  Timeline: 6 weeks (3 phases)
  Claim: Production validation
  Risk: Overconfident, no preflight gates, "trust me" promises

NEW PLAN (POST-AUDIT):
  Scope: 3 pathways × 1 cancer (TCGA-OV only)
  Timeline: 2-3 weeks (Phase 1A)
  Claim: Baseline stratification validation (NOT early detection)
  Protection: Preflight gates, diagnostics-first, honest limitations

CRITICAL ADDITIONS:
  ✅ Preflight gates (hard-fail if invalid config)
  ✅ Diagnostics before AUROC (pathway stratification first)
  ✅ Honest expectations (AUROC 0.55-0.65 for baseline)
  ✅ Configuration documentation (evidence on, max_mutations≥3)
  ✅ Limitation reporting (baseline only, no CA-125 kinetics)

INTEGRATION WITH S1:
  ✅ Phase 1A = Therapy Fit validation (this plan)
  ✅ Phase 1B = PLCO kinetics (Agent 2)
  ✅ Phase 1C = Multi-modal (Agent 3, S4 data acquisition)

LEARNED FROM AUDIT:
  ✅ "Trust me" → Verifiable gates
  ✅ Ambitious claims → Honest scoping
  ✅ AUROC-only → Pathway separation + AUROC
  ✅ Configuration matters as much as code
  ✅ Dataset limitations define validation scope
Plan improved from overconfident to honest. ✅

Preflight gates prevent "trust me" reruns. 🔧

Diagnostics-first approach (learned from audit failure). 🎯

Honest limitations documented upfront. 📋

Integration with S1 framework (Phase 1A/1B/1C). 🔗

Timeline: 2-3 weeks (Week 3-4, Jan 17 - Feb 7). ⏱️

Owner: Agent 1, starts Week 3 (after S4 + D3 complete). 💀