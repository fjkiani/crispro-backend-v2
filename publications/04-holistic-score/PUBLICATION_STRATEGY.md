# Holistic Score Publication Strategy

**Date:** January 13, 2026  
**Status:** 📋 **STRATEGY DECISION NEEDED**

---

## 🔍 KEY QUESTION: Update Existing or Create New?

### Current Situation

**Existing Publication (`02-trial-matching`):**
- **Focus:** Mechanism-based trial matching methodology
- **Validation:** Non-outcome (mechanism discrimination, matchability prevalence)
- **Status:** ✅ Complete, ready for submission
- **Explicit statement:** "Outcome validation (enrollment/benefit) is explicitly out of scope"

**New Work (TOPACIO Validation):**
- **Focus:** Holistic Score (Mechanism Fit + Eligibility + PGx Safety)
- **Validation:** **Outcome validation** (TOPACIO - predicts ORR)
- **Status:** ✅ Just completed (AUROC=0.714, Q4 vs Q1 OR=9.75)

---

## 📊 COMPARISON

| Aspect | `02-trial-matching` | TOPACIO Validation |
|--------|---------------------|-------------------|
| **Scope** | Mechanism matching methodology | Outcome prediction |
| **Question** | "Does mechanism matching work?" | "Does holistic score predict outcomes?" |
| **Validation** | Non-outcome (discrimination, matchability) | Outcome (ORR prediction) |
| **Data** | TCGA-OV (n=585), mechanism sanity | TOPACIO (n=55), ORR outcomes |
| **Metrics** | Mechanism fit, discrimination ratio | AUROC, OR, correlation |
| **Status** | Complete, ready | Just completed |

---

## 🎯 RECOMMENDATION: **KEEP SEPARATE**

### Why Keep Separate:

1. **Different Research Questions:**
   - `02-trial-matching`: "Can we match patients to trials by mechanism?"
   - TOPACIO: "Does holistic score predict clinical outcomes?"

2. **Different Validation Types:**
   - `02-trial-matching`: Methodology validation (non-outcome)
   - TOPACIO: Outcome validation (predicts ORR)

3. **Different Target Journals:**
   - `02-trial-matching`: Methods/Computational journal (Bioinformatics, PLOS Comp Bio)
   - TOPACIO: Clinical/Translational journal (JCO PO, NPJ PO, Clinical Cancer Research)

4. **Different Audiences:**
   - `02-trial-matching`: Computational biologists, bioinformaticians
   - TOPACIO: Clinical oncologists, trial designers

5. **Natural Progression:**
   - `02-trial-matching` = "We built it" (methodology)
   - TOPACIO = "It works" (outcome validation)
   - These are **two papers in a series**, not one paper

---

## ✅ RECOMMENDED APPROACH

### Option A: Two Separate Publications (RECOMMENDED)

**Paper 1: `02-trial-matching`**
- Title: "Mechanism-Based Clinical Trial Matching Using 7D Pathway Vectors"
- Focus: Methodology, mechanism discrimination, matchability
- Status: ✅ Ready for submission
- Target: Bioinformatics/Computational journal

**Paper 2: `04-holistic-score` (NEW)**
- Title: "Unified Patient-Trial-Dose Feasibility Score Predicts Clinical Trial Outcomes: TOPACIO Validation"
- Focus: Outcome validation, holistic score, ORR prediction
- Status: ✅ Validation complete, needs manuscript
- Target: Clinical/Translational journal (JCO PO, NPJ PO)

**Benefits:**
- Each paper has clear, focused message
- Can submit to appropriate journals
- Natural progression: methodology → outcome validation
- Higher impact (two publications vs one)

---

### Option B: Update Existing Publication

**If we update `02-trial-matching` to include TOPACIO:**

**Pros:**
- Single comprehensive paper
- Shows complete story (methodology → outcome validation)
- May be stronger for clinical journals

**Cons:**
- Changes scope significantly (non-outcome → outcome validation)
- May confuse reviewers (two different validation types)
- Existing abstract explicitly says "outcome validation out of scope"
- Would need to rewrite abstract, introduction, conclusions
- May delay submission of already-complete `02-trial-matching` paper

---

## 📋 DECISION MATRIX

| Factor | Keep Separate | Update Existing |
|--------|---------------|-----------------|
| **Clarity** | ✅ Each paper has clear focus | ⚠️ Mixed validation types |
| **Impact** | ✅ Two publications | ⚠️ One larger publication |
| **Timeline** | ✅ `02-trial-matching` ready now | ❌ Delays existing paper |
| **Target Journals** | ✅ Appropriate for each | ⚠️ May not fit either perfectly |
| **Natural Progression** | ✅ Methodology → Outcome | ⚠️ Combines both |
| **Submission Strategy** | ✅ Submit `02-trial-matching` now | ❌ Wait for TOPACIO manuscript |

---

## 🎯 FINAL RECOMMENDATION

**✅ KEEP SEPARATE - Create `04-holistic-score` publication**

**Rationale:**
1. `02-trial-matching` is **complete and ready** - don't delay it
2. TOPACIO validation is **outcome validation** - different from methodology validation
3. Two focused papers > one mixed paper
4. Natural progression: methodology paper → outcome validation paper
5. Can submit to appropriate journals for each

**Action Plan:**
1. ✅ Submit `02-trial-matching` as-is (methodology paper)
2. ✅ Create `04-holistic-score` publication package (outcome validation paper)
3. ✅ Reference `02-trial-matching` in TOPACIO paper: "Building on our mechanism-based matching methodology [ref], we now validate outcome prediction..."

---

## 📝 NEXT STEPS

1. **Create `publications/04-holistic-score/` directory structure**
2. **Copy TOPACIO validation results** (receipts, figures, scripts)
3. **Draft manuscript** using manager's skeleton (with corrections)
4. **Reference `02-trial-matching`** as methodology foundation

---

**Status:** ⏳ **AWAITING ALPHA DECISION**
