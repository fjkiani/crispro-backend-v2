# 🎯 Multi-Disease Trial Matching Roadmap

**Date:** January 28, 2025  
**Goal:** Extend infrastructure to support disease-specific trial matching (CRC, Breast, Brain, Leukemia, MM)

---

## 📋 **ROADMAP OVERVIEW**

### **Phase 1: Infrastructure Foundation** ✅
- ✅ Patient Profile → Search Criteria Mapper (generic)
- ✅ Search Strategy Config System (YAML)
- ✅ Relevance Scoring Rules Config (YAML)
- ✅ Ranking Formulas Config (YAML)

### **Phase 2: Multi-Disease Expansion** ⏳
- ⏳ Disease-Specific Config Modules (per-disease YAML)
- ⏳ Subtype Discrimination System
- ⏳ Dominance Policy Engine
- ⏳ Query Template Generator

### **Phase 3: Cross-Cancer Requirements** ⏳
- ⏳ Eligibility Extraction Service
- ⏳ Safety Layer Integration (PGx + contraindications)
- ⏳ Explainability Contract (dominant pathway + gate evidence)

---

## 🎯 **DISEASE-SPECIFIC BLUEPRINTS**

### **1. Colon (CRC) — Mechanistic Trial Matching**

#### **Mechanism Axes:**
- **IO/MMR:** MSI‑H/dMMR (dominant), TMB‑high (supporting)
- **MAPK:** KRAS/NRAS/BRAF (and resistance biology)
- **EGFR axis:** EGFR mAb sensitivity/resistance (RAS/BRAF status dependent)
- **HER2:** amplification/overexpression (subset)
- **PI3K:** PIK3CA/PTEN (subset; usually secondary)

#### **Evidence Gates:**
- **IO strong:** MSI‑H/dMMR → IO=high
- **IO moderate:** TMB‑high (if validated in CRC context)
- **IO weak:** PD‑L1 alone (generally low weight in CRC)
- **MAPK strong:** KRAS/NRAS/BRAF V600E (high), other MAPK variants (moderate)
- **HER2 strong:** HER2 amplification/IHC3+ (CRC-specific criteria)

#### **Dominance Policy:**
- If MSI‑H/dMMR present → rank IO trials first (PD‑1/PD‑L1 ± CTLA‑4, novel IO combos)
- If BRAF V600E → rank BRAF/MEK/EGFR combo trials first
- If RAS mutant → deprioritize EGFR mAb trials; prefer KRAS-targeted / MAPK pathway trials

#### **Query Templates:**
1. `"metastatic colorectal" + ("MSI-H" OR "dMMR" OR "mismatch repair") + (pembrolizumab OR nivolumab OR PD-1)`
2. `"colorectal" + ("BRAF V600E" OR "BRAF inhibitor" OR encorafenib) + EGFR`
3. `"colorectal" + ("KRAS G12C" OR "KRAS inhibitor" OR sotorasib OR adagrasib)`
4. `"colorectal" + ("HER2 amplified" OR "ERBB2") + (trastuzumab OR tucatinib OR ADC)`
5. `"colorectal" + ("RAS wild type" OR "anti-EGFR") + (cetuximab OR panitumumab)`

---

### **2. Breast — Mechanistic Trial Matching**

#### **Mechanism Axes:**
- **ER signaling (HR+):** Endocrine sensitivity
- **HER2:** HER2+ and HER2-low (for ADCs)
- **DDR/BRCA/HRD:** Germline or somatic
- **PI3K/AKT:** PIK3CA/PTEN/AKT1
- **IO:** Especially TNBC; PD‑L1 context-specific
- **ADC targets:** TROP2, HER2-low, etc.

#### **Evidence Gates:**
- **ER axis strong:** ER/PR positive + endocrine sensitivity markers/history
- **HER2 axis strong:** IHC3+/ISH+; HER2-low is separate gating for ADCs
- **DDR strong:** BRCA1/2 LoF or HRD-high (if available)
- **PI3K strong:** PIK3CA hotspot (H1047R/E545K/E542K) or pathway activation
- **IO strong (TNBC):** PD‑L1 positive by assay-specific thresholds + TNBC context

#### **Dominance Policy:**
- HER2+ dominates over most other axes (HER2-targeted/ADC first)
- HR+ dominates with endocrine backbone; layer PI3K/AKT trials if PIK3CA/PTEN
- DDR high → PARP-focused trials rise (especially BRCA/HRD)
- TNBC + PD‑L1 positive → IO trials rise; otherwise IO is weaker

#### **Query Templates:**
1. `"metastatic breast" + ("HER2 positive" OR ERBB2) + (trastuzumab OR T-DXd OR ADC)`
2. `"breast cancer" + ("HER2-low" OR "T-DXd" OR "trastuzumab deruxtecan")`
3. `"breast cancer" + ("BRCA1" OR "BRCA2" OR "HRD") + (PARP OR olaparib OR niraparib)`
4. `"HR positive breast" + (PIK3CA OR "AKT inhibitor" OR capivasertib)`
5. `"triple negative breast" + (PD-L1 OR pembrolizumab OR atezolizumab)`

---

### **3. Brain (Primary CNS Tumors) — Mechanistic Trial Matching**

**Note:** Brain is heterogeneous; must be diagnosis-specific: GBM vs low-grade glioma vs metastatic brain lesions.

#### **Mechanism Axes (GBM-forward):**
- **RTK/PI3K:** EGFR amplification/EGFRvIII, PTEN loss
- **IDH axis:** IDH1/2 mutation (glioma subtype)
- **DNA repair / MGMT:** MGMT promoter methylation (predictive for temozolomide benefit)
- **Cell cycle/CDK:** CDKN2A/B loss, CDK4/6
- **Angiogenesis/VEGF:** bevacizumab-like approaches
- **IO:** Generally weaker in GBM unless specific markers

#### **Evidence Gates:**
- **IDH strong:** IDH1 R132H etc.
- **EGFR strong:** amplification/EGFRvIII
- **MGMT methylation:** Treatment stratifier gate (not a mechanism vector boost)

#### **Dominance Policy:**
- IDH-mut glioma: IDH inhibitor trials dominate
- EGFR-ampl/vIII: EGFR-targeted / vaccine trials dominate
- Avoid over-weighting IO unless there's strong supporting evidence (TMB-high rare in primary CNS)

#### **Query Templates:**
1. `"glioblastoma" + (EGFRvIII OR EGFR amplification) + (vaccine OR EGFR inhibitor)`
2. `"glioma" + (IDH1 OR IDH inhibitor OR vorasidenib)`
3. `"glioblastoma" + (CDK4/6 OR "cell cycle") + inhibitor`
4. `"glioblastoma" + (MGMT methylated) + temozolomide + "maintenance"`
5. `"glioblastoma" + (bevacizumab OR VEGF)`

---

### **4. Leukemia — Mechanistic Trial Matching**

**Note:** Must model by subtype: AML vs ALL vs CLL.

#### **Mechanism Axes:**
- **AML:** FLT3, IDH1/2, NPM1, TP53/complex karyotype, BCL2 dependency, menin (KMT2A/NRAS contexts)
- **ALL:** BCR-ABL (Ph+), CD19/CD22 targets, CAR-T/bispecifics
- **CLL:** BTK pathway, BCL2 (venetoclax), PI3Kδ

#### **Evidence Gates:**
- Driver mutation gates are usually strong (FLT3-ITD/TKD, IDH1/2, BCR-ABL)
- Cytogenetics/TP53 are high-impact stratifiers (often dominance triggers)

#### **Dominance Policy:**
- If a canonical driver exists (FLT3, IDH, BCR-ABL) → that axis dominates trial matching
- TP53/complex karyotype → prioritize novel mechanisms / transplant/strong regimens trials

#### **Query Templates:**
1. `"AML" + (FLT3 OR gilteritinib OR quizartinib)`
2. `"AML" + (IDH1 OR ivosidenib) / (IDH2 OR enasidenib)`
3. `"AML" + (venetoclax OR BCL2)`
4. `"ALL" + (BCR-ABL OR tyrosine kinase inhibitor)`
5. `"CLL" + (BTK inhibitor OR ibrutinib OR acalabrutinib)` and `"CLL" + venetoclax`

---

### **5. Multiple Myeloma — Mechanistic Trial Matching**

#### **Mechanism Axes:**
- **Proteasome (PI)**
- **Cereblon/IMiD:** len/pom
- **CD38 / BCMA / GPRC5D / FcRH5:** Immunotherapy targets
- **High-risk genetics/cytogenetics:** TP53/del17p, t(4;14), 1q gain
- **Resistance markers:** CRBN alterations, PSMB5 (where supported)

#### **Evidence Gates:**
- Target-antigen presence (BCMA etc.) and prior exposure/refractory status are key
- High-risk cytogenetics should influence prioritization and aggressiveness of approach

#### **Dominance Policy:**
- If triple-class refractory → prioritize BCMA/GPRC5D/FcRH5 trials
- If high-risk (del17p/TP53) → prioritize regimens/trials tailored for high-risk biology

#### **Query Templates:**
1. `"multiple myeloma" + (BCMA OR CAR-T OR bispecific)`
2. `"multiple myeloma" + (GPRC5D OR talquetamab)`
3. `"multiple myeloma" + (FcRH5 OR cevostamab)`
4. `"multiple myeloma" + (proteasome inhibitor) / (cereblon modulator) / (anti-CD38)`

---

## 🔧 **CROSS-CANCER REQUIREMENTS**

### **1. Disease Module Configs**
- **Per-disease YAML files:** `api/resources/disease_modules/{disease}.yaml`
- **Schema:** Pathway axes, gates, dominance rules, query templates
- **Extensible:** Add new diseases via config (no code changes)

### **2. Subtype Discrimination**
- **Required subtypes:**
  - CRC: CRC vs rectal
  - Breast: HR+/HER2+/TNBC
  - Brain: GBM vs IDH glioma
  - Leukemia: AML vs ALL vs CLL
  - MM: Lines/refractory status
- **Implementation:** Subtype extraction from patient profile

### **3. Eligibility Extraction**
- **Required fields:** ECOG, organ function, prior lines, refractory status
- **Service:** `EligibilityExtractionService`
- **Output:** Eligibility filters for CT.gov queries

### **4. Safety Layer**
- **Components:** PGx + contraindications
- **Actions:** Veto/penalty for unsafe trials
- **Integration:** Use existing `PGxScreeningService`

### **5. Explainability Contract**
- **Required outputs per ranked trial:**
  - Dominant pathway match
  - Gate evidence
  - What's missing
- **Format:** Structured explanation JSON

---

## 📋 **IMPLEMENTATION PLAN**

### **Phase 1: Disease Module Configs** (Priority 1)
1. ⏳ Create `api/resources/disease_modules/` directory
2. ⏳ Create disease-specific YAML files:
   - `colon.yaml` (CRC)
   - `breast.yaml`
   - `brain.yaml`
   - `leukemia.yaml`
   - `myeloma.yaml`
   - `ovarian.yaml` (existing, migrate)
3. ⏳ Define schema: mechanism_axes, evidence_gates, dominance_policies, query_templates

### **Phase 2: Disease Module Loader** (Priority 1)
4. ⏳ Build `DiseaseModuleLoader` service
   - Load disease-specific config from YAML
   - Validate schema
   - Cache loaded modules

### **Phase 3: Subtype Discrimination** (Priority 2)
5. ⏳ Build `SubtypeDiscriminator` service
   - Extract subtype from patient profile
   - Map to disease-specific subtypes
   - Filter trials by subtype

### **Phase 4: Dominance Policy Engine** (Priority 2)
6. ⏳ Build `DominancePolicyEngine` service
   - Load dominance policies from disease module
   - Apply policies to rank trials
   - Boost/penalize based on dominance rules

### **Phase 5: Query Template Generator** (Priority 2)
7. ⏳ Build `QueryTemplateGenerator` service
   - Load query templates from disease module
   - Fill templates with patient-specific data
   - Generate CT.gov queries

### **Phase 6: Eligibility Extraction** (Priority 3)
8. ⏳ Build `EligibilityExtractionService`
   - Extract ECOG, organ function, prior lines, refractory status
   - Generate eligibility filters
   - Apply to queries

### **Phase 7: Safety Layer Integration** (Priority 3)
9. ⏳ Integrate `PGxScreeningService` with trial ranking
   - Apply veto/penalty for unsafe trials
   - Filter out contraindicated trials

### **Phase 8: Explainability Contract** (Priority 3)
10. ⏳ Build `TrialExplanationService`
    - Generate dominant pathway match
    - Generate gate evidence
    - Generate "what's missing" analysis

---

## 🎯 **FILE STRUCTURE**

```
api/
  resources/
    disease_modules/
      colon.yaml
      breast.yaml
      brain.yaml
      leukemia.yaml
      myeloma.yaml
      ovarian.yaml
    search_strategies/
      default.yaml
    relevance_scoring_rules/
      default.yaml
    ranking_formulas/
      default.yaml

api/
  services/
    trial_search_criteria_mapper.py  ✅ (exists)
    disease_module_loader.py         ⏳ (to build)
    subtype_discriminator.py         ⏳ (to build)
    dominance_policy_engine.py       ⏳ (to build)
    query_template_generator.py      ⏳ (to build)
    eligibility_extraction_service.py ⏳ (to build)
    trial_explanation_service.py     ⏳ (to build)
```

---

## ✅ **SUCCESS CRITERIA**

### **Infrastructure Quality:**
- ✅ **DRY:** Disease modules in config (not hard-coded)
- ✅ **Extensible:** Add new diseases via YAML (no code changes)
- ✅ **Subtype-aware:** Handles disease subtypes correctly
- ✅ **Policy-driven:** Dominance policies in config

### **Functional Quality:**
- ✅ **Disease-specific:** Correct mechanism axes per disease
- ✅ **Evidence-gated:** Gates applied correctly
- ✅ **Dominance-respecting:** Policies applied to ranking
- ✅ **Explainable:** Each trial has explanation

---

**Status:** Roadmap defined - ready to implement disease modules  
**Next Action:** Create disease module YAML files (start with CRC/colon.yaml)
