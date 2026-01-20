> ⚠️ **SUPERSEDED**: This document has been consolidated into `PATIENT_KB_AND_FRONTEND_COMPLETE_STATUS.md`  
> **Please refer to the consolidated document for the latest status.**

---

# 🎯 FRONTEND DISPLAY CAPABILITIES - AYESHA PROFILE

**Date:** January 11, 2026  
**Status:** ✅ **WORKING BACKEND - READY FOR FRONTEND INTEGRATION**  
**Endpoint:** `POST /api/ayesha/complete_care_v2`

---

## 📋 WHAT WE CAN NOW SHOW ON FRONTEND

Based on our fixes and testing, here's what the frontend can display for Ayesha (AK) based on her current pre-NGS profile:

### ✅ **1. CLINICAL TRIALS (10 DDR/PARP-Focused Trials)**

**Status:** ✅ **WORKING** - Returns 10 mechanism-fit ranked trials

**What's Returned:**
- **10 DDR/PARP-focused trials** ranked by mechanism fit (0.75)
- **Top 5 trials:**
  1. `NCT04284969` - **PARP + ATR inhibitors** (DDR_align=0.712)
  2. `NCT02655016` - **PARP + Ceralasertib ATR inhibitor** (DDR_align=0.712)
  3. `NCT04001023` - **PARP inhibitor Olaparib** (DDR_align=0.675)
  4. `NCT02244879` - **DDR pathway (ATR)** (DDR_align=0.675)
  5. `NCT03735979` - **DDR pathway (ATR)** (DDR_align=0.675)

**Fields Available:**
- `nct_id`, `title`, `phase`, `status`
- `mechanism_fit_score` (0.75)
- `mechanism_alignment.alignment_breakdown` (DDR, IO, VEGF, etc.)
- `reasoning.why_eligible`, `reasoning.why_good_fit`
- `provenance.patient_mechanism_vector` (DDR=0.75, IO=0.20)

**Frontend Display:**
- Show **"10 Mechanism-Matched Trials"** section
- Display trials ranked by mechanism fit score
- Show **DDR alignment** as primary mechanism (0.71-0.68)
- Show **patient context** used: "p53=MUTANT_TYPE; PD-L1=POSITIVE (CPS 10)"
- Link to ClinicalTrials.gov for full protocol details

---

### ✅ **2. STANDARD OF CARE RECOMMENDATION**

**Status:** ✅ **WORKING** - Returns NCCN Category 1 regimen

**What's Returned:**
- **Regimen:** "Carboplatin AUC 5-6 + Paclitaxel 175 mg/m²"
- **Confidence:** 0.95 (95%)
- **Rationale:** "NCCN Category 1 for first-line Stage IVB HGSOC"
- **Add-ons:**
  - Bevacizumab 15 mg/kg (confidence 0.90)
    - Rationale: "Ascites/peritoneal disease present → bevacizumab recommended (GOG-218, ICON7)"
- **Evidence:** ["NCCN Guidelines v2024", "GOG-218", "ICON7"]

**Frontend Display:**
- Show **"Standard of Care"** section with regimen
- Display **confidence badge** (95% - High)
- Show **rationale** explanation
- List **add-on options** (bevacizumab) with confidence
- Display **evidence sources** (guidelines, trials)

---

### ✅ **3. CA-125 INTELLIGENCE**

**Status:** ✅ **WORKING** - Returns burden assessment and monitoring strategy

**What's Returned:**
- **Burden Class:** "EXTENSIVE" (score=0.78)
- **Forecast:**
  - Complete response target: <35 U/mL
  - General expectations: ≥70% drop by cycle 3, ≥90% by cycle 6
  - Note: "Baseline CA-125 not available"
- **Monitoring Strategy:**
  - Frequency: "every_2_weeks"
  - Timing: "Until treatment initiation"
  - Rationale: "High baseline; track any changes before treatment"
- **Clinical Notes:** "CA-125 of 2842.0 U/mL indicates EXTENSIVE disease burden (>1,000). CA-125 is highly trackable and suitable for response monitoring."

**Frontend Display:**
- Show **"CA-125 Intelligence"** section (if baseline available)
- Display **burden classification** (EXTENSIVE) with visual indicator
- Show **response forecast** (cycle 3/6 targets)
- Display **monitoring strategy** (frequency, timing)
- Show **clinical notes** for oncologist

**Note:** If `ca125_value` is `null` (as in Ayesha's current profile), the CA-125 tracker component returns `null` and does not render. This is **expected behavior** until baseline labs are uploaded.

---

### ✅ **4. DRUG EFFICACY (WIWFM) STATUS**

**Status:** ✅ **WORKING** - Returns "awaiting_ngs" status with recommendations

**What's Returned:**
- **Status:** "awaiting_ngs"
- **Message:** "Personalized drug efficacy predictions require tumor NGS data (somatic mutations, HRD, TMB, MSI)"
- **NGS Fast-Track:**
  - ctDNA: "Guardant360 - somatic BRCA/HRR, TMB, MSI (7-10 days)"
  - tissue_HRD: "MyChoice - HRD score for PARP maintenance planning (7-14 days)"
  - IHC: "WT1/PAX8/p53 - confirm high-grade serous histology (1-3 days)"
- **Note:** "Once NGS available, WIWFM will provide Evo2-powered S/P/E drug ranking with 70-85% confidence"

**Frontend Display:**
- Show **"Drug Recommendations"** section with status
- Display **"Awaiting NGS"** alert/banner
- List **recommended NGS tests** with turnaround times
- Link to **NGS ordering page** or upload flow
- Explain what **unlocks** when NGS is available (S/P/E drug ranking)

---

### ✅ **5. NEXT TEST RECOMMENDATIONS**

**Status:** ✅ **WORKING** - Returns 2 high-priority test recommendations

**What's Returned:**
- **2 high-priority tests:**
  1. **HRD Score (MyChoice CDx or tissue-based NGS)**
     - Priority: HIGH
     - Turnaround: 10 days
     - Cost: $4,000-$6,000
     - Impact if positive: "HRD ≥42 → PARP maintenance eligible (NCCN Category 1), confidence 90%"
     - Impact if negative: "HRD <42 → PARP reduced benefit (confidence 60%), consider ATR/CHK1 combo trials"
  2. **ctDNA Comprehensive Panel (Guardant360 CDx or FoundationOne Liquid CDx)**
     - Priority: HIGH
     - Turnaround: 7 days
     - Cost: $5,000-$7,000
     - Impact if positive: "MSI-High OR TMB ≥20 → Immunotherapy eligible, confidence 85%"
     - Impact if negative: "MSI-Stable AND TMB <20 → Immunotherapy lower priority (confidence 40%)"

**Frontend Display:**
- Show **"Recommended Next Tests"** section
- Display tests ranked by **priority** (HIGH/MEDIUM/LOW)
- Show **turnaround time** and **cost estimate**
- Display **differential branches** (if positive/negative outcomes)
- Link to **test ordering** flow or provider contact

---

### ✅ **6. PATIENT MECHANISM VECTOR (From Trial Ranking)**

**Status:** ✅ **WORKING** - Embedded in trial provenance

**What's Returned:**
- **Patient Mechanism Vector:** `[0.75, 0.0, 0.0, 0.0, 0.0, 0.20, 0.1]`
  - **DDR:** 0.75 (from p53 MUTANT_TYPE)
  - **MAPK:** 0.0
  - **PI3K:** 0.0
  - **VEGF:** 0.0
  - **HER2:** 0.0
  - **IO:** 0.20 (from PD-L1 CPS 10, **gated** - not MSI-H/TMB-high)
  - **Efflux:** 0.1 (baseline)

**Frontend Display:**
- Show **"Your Mechanism Profile"** visualization
- Display **DDR=0.75** as **dominant pathway** (p53 mutant)
- Display **IO=0.20** as **weak signal** (PD-L1 alone, not MSI-H/TMB-high)
- Explain **why** each pathway is active/inactive
- Show **what unlocks** with NGS (more precise pathway scoring)

---

### ✅ **7. HINT TILES**

**Status:** ✅ **WORKING** - Returns 2 actionable tiles

**What's Returned:**
- **2 hint tiles:**
  1. **Next Test** - "Consider ordering HRD Score" (Priority 1)
  2. **Trials Lever** - "Consider mechanism-aligned trials (10 matched)" (Priority 2)

**Frontend Display:**
- Show **"Recommended Actions"** section
- Display **hint tiles** as clickable cards
- Show **priority** indicators (1, 2, etc.)
- Link to relevant pages (NGS ordering, trial explorer)

---

### ✅ **8. MECHANISM MAP**

**Status:** ✅ **WORKING** - Returns "awaiting_ngs" status (all chips gray)

**What's Returned:**
- **Status:** "awaiting_ngs"
- **Chips:** All 6 chips (DDR, MAPK, PI3K, VEGF, IO, Efflux) show "Awaiting NGS" (gray/default)
- **Message:** "Mechanism map will be available once tumor NGS results are uploaded (7-10 days). Order HRD + ctDNA to unlock."

**Frontend Display:**
- Show **"Mechanism Map"** section (all chips gray)
- Display **"Awaiting NGS"** message
- Show **what unlocks** when NGS is available (green/yellow/red chips based on pathway burden)
- Link to **NGS ordering** flow

---

### ⚠️ **9. DRUG RECOMMENDATIONS (WIWFM)**

**Status:** ⚠️ **LOCKED UNTIL NGS** - Returns "awaiting_ngs" status

**What's Returned:**
- **Status:** "awaiting_ngs"
- **Drugs:** Empty (no recommendations until NGS)
- **Message:** Explains why NGS is required

**Frontend Display:**
- Show **"Drug Recommendations"** section with **"Awaiting NGS"** banner
- Display **why** NGS is required (actionable mutations, HRD, TMB, MSI)
- List **recommended NGS tests** (from next_test_recommender)
- Link to **NGS ordering** flow
- Show **what unlocks** (S/P/E drug ranking with 70-85% confidence)

---

## 🎯 SUMMARY: WHAT FRONTEND CAN DISPLAY NOW

| Component | Status | Data Available | Frontend Display |
|-----------|--------|----------------|------------------|
| **Clinical Trials** | ✅ **WORKING** | 10 DDR/PARP-focused trials | Show ranked list with mechanism fit scores |
| **Standard of Care** | ✅ **WORKING** | NCCN Category 1 regimen | Show regimen, confidence, rationale, add-ons |
| **CA-125 Intelligence** | ⚠️ **LOCKED** | Returns data, but `ca125_value` is `null` | Component returns `null` until baseline labs |
| **Drug Efficacy (WIWFM)** | ⚠️ **LOCKED** | "awaiting_ngs" status | Show alert with NGS recommendations |
| **Next Test Recommendations** | ✅ **WORKING** | 2 high-priority tests | Show prioritized list with turnaround/cost |
| **Patient Mechanism Vector** | ✅ **WORKING** | DDR=0.75, IO=0.20 | Show pathway visualization |
| **Hint Tiles** | ✅ **WORKING** | 2 actionable tiles | Show recommended actions |
| **Mechanism Map** | ⚠️ **LOCKED** | All chips gray (awaiting NGS) | Show "awaiting NGS" message |

---

## 🔧 FRONTEND INTEGRATION NOTES

### **1. Trials Display**
- Use `trials.trials[]` array (10 items)
- Sort by `mechanism_fit_score` (already sorted)
- Display `mechanism_alignment.alignment_breakdown.DDR` as primary match
- Show `reasoning.why_good_fit` for explainability
- Link to ClinicalTrials.gov using `nct_id`

### **2. SOC Display**
- Use `soc_recommendation.regimen`
- Display `soc_recommendation.confidence` as percentage badge
- Show `soc_recommendation.add_ons[]` as optional additions
- List `soc_recommendation.evidence[]` as sources

### **3. CA-125 Display**
- Check if `ca125_value` exists in patient profile
- If `null`, component returns `null` (expected - don't render)
- If exists, use `ca125_intelligence.burden_class` and `forecast`

### **4. WIWFM Display**
- Check `wiwfm.status` - if "awaiting_ngs", show alert
- Display `wiwfm.ngs_fast_track` as recommended tests
- Link to NGS ordering flow

### **5. Next Tests Display**
- Use `next_test_recommender.recommendations[]` array
- Sort by `priority` (1 = highest)
- Display `test_name`, `turnaround_days`, `cost_estimate`
- Show `impact_if_positive` and `impact_if_negative` as differential branches

### **6. Mechanism Vector Display**
- Extract from `trials.trials[0].provenance.patient_mechanism_vector`
- Display as pathway visualization (bar chart or chips)
- Highlight **DDR=0.75** as dominant pathway
- Explain **IO=0.20** is weak (PD-L1 alone, not MSI-H/TMB-high)

---

## 🎯 KEY TAKEAWAYS

1. **Trials are working** - Returns 10 DDR/PARP-focused trials for Ayesha (MBD4 + TP53)
2. **SOC is working** - Returns NCCN Category 1 regimen with confidence
3. **Next tests are working** - Returns prioritized NGS recommendations
4. **WIWFM is locked** - Returns "awaiting_ngs" until actionable NGS data is available
5. **CA-125 is locked** - Component returns `null` until baseline `ca125_value` exists
6. **Mechanism map is locked** - All chips gray until NGS is uploaded

**The frontend can now display:**
- ✅ 10 mechanism-matched trials (DDR/PARP-focused)
- ✅ Standard of care recommendation (NCCN Category 1)
- ✅ Next test recommendations (HRD + ctDNA)
- ✅ Patient mechanism vector (DDR=0.75, IO=0.20)
- ⚠️ WIWFM status ("awaiting_ngs" - explain why)
- ⚠️ CA-125 intelligence (locked until baseline)
- ⚠️ Mechanism map (locked until NGS)
