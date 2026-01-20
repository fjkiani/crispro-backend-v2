# 🔬 Backend Services Integration Plan for Research Intelligence
## Biomarker-Driven Orchestration Architecture

**Status:** 📋 Review & Planning Phase  
**Date:** January 2025  
**Focus:** Maximum output from minimum input (query/biomarkers)  
**Architecture:** Modular, biomarker-centric integration

---

## 🎯 Executive Summary

This document provides a comprehensive line-by-line review of all backend services and plans their integration into the Research Intelligence framework. The core principle: **Biomarkers are the primary input that orchestrates all downstream services**, enabling maximum clinical intelligence from minimal user input.

### Key Integration Principles

1. **Biomarker-Centric Design**: Biomarker values + disease type → triggers all downstream analysis
2. **Modular Architecture**: Each service remains independent, composable, testable
3. **Progressive Enhancement**: Services activate based on available data (biomarkers → genomics → treatment context)
4. **Maximum Output, Minimum Input**: Single biomarker value + query → comprehensive analysis

---

## 📊 Service Capability Matrix

### 1. **Biomarker Intelligence Universal** ⭐ PRIMARY INPUT

**Location:** `api/services/biomarker_intelligence_universal/`

**Core Capabilities:**
- ✅ Universal biomarker monitoring (CA-125, PSA, CEA, etc.)
- ✅ Disease-specific threshold configuration
- ✅ Burden classification (MINIMAL/MODERATE/SIGNIFICANT/EXTENSIVE)
- ✅ Response forecasting (cycle 3/6 milestones)
- ✅ Resistance signal detection (ON_THERAPY_RISE, INADEQUATE_RESPONSE, MINIMAL_RESPONSE)
- ✅ Monitoring strategy recommendations
- ✅ Clinical notes generation

**Key Outputs:**
```python
{
    "biomarker_type": "ca125",
    "burden_class": "EXTENSIVE",
    "burden_score": 0.85,
    "forecast": {
        "cycle3_expected_value": 150.0,
        "cycle3_status": "ON_TRACK",
        "complete_response_target": 35.0
    },
    "resistance_signals": [...],
    "monitoring_strategy": {...},
    "clinical_notes": "...",
    "provenance": {...}
}
```

**Integration Points:**
- **→ Comprehensive Analysis**: Biomarker burden → genomic risk stratification
- **→ Evidence**: Biomarker trends → literature search context
- **→ Food Validation**: Biomarker burden → nutrition protocol urgency
- **→ Trial Intelligence**: Biomarker status → trial eligibility filtering
- **→ Therapy Fit**: Biomarker response → drug efficacy validation

**Biomarker-Driven Triggers:**
- `burden_class == "EXTENSIVE"` → Trigger comprehensive MOAT analysis
- `resistance_signals` present → Trigger alternative therapy search
- `forecast.cycle3_status == "BELOW_EXPECTED"` → Trigger evidence mining for resistance mechanisms

---

### 2. **Comprehensive Analysis (MOAT)**

**Location:** `api/services/comprehensive_analysis/`

**Core Components:**
- **GenomicAnalyzer**: Critical gene identification (MBD4, BRCA1/2, TP53, ATM, CHEK2)
- **DrugMoAExplainer**: Mechanism explanations + patient-specific toxicity
- **MOATAnalysisGenerator**: Full orchestration (genomics → toxicity → nutrition → timing)

**Key Capabilities:**
- ✅ Critical genomic finding identification
- ✅ Biological mechanism explanations (HOW)
- ✅ Clinical impact explanations (WHY)
- ✅ Pathway connections (DNA Repair, Inflammation, Cardiometabolic, Pharmacogenomics)
- ✅ Drug MoA step-by-step explanations
- ✅ Patient-specific toxicity risk assessment
- ✅ Mitigation strategy generation

**Integration with Biomarkers:**
```python
# Biomarker → Genomic Context
biomarker_result = biomarker_service.analyze_biomarker(...)
if biomarker_result["burden_class"] == "EXTENSIVE":
    # Trigger comprehensive genomic analysis
    genomic_findings = genomic_analyzer.analyze_critical_findings(
        germline_variants=extract_from_biomarker_context(biomarker_result),
        somatic_variants=[]
    )
    
    # Biomarker resistance signals → drug MoA analysis
    if biomarker_result["resistance_signals"]:
        for drug in current_treatment:
            moa_explanation = drug_moa_explainer.explain_drug_mechanism(
                drug, genomic_findings, germline_genes
            )
```

**Biomarker-Driven Workflow:**
1. Biomarker burden → Extract disease context → Genomic analysis
2. Biomarker resistance signals → Drug MoA toxicity analysis
3. Biomarker forecast → Treatment optimization recommendations

---

### 3. **Evidence Services**

**Location:** `api/services/evidence/`

**Core Components:**
- **LiteratureClient**: PubMed search with MoA-aware filtering
- **ClinVarClient**: Variant classification and prior strength
- **BadgeComputation**: Evidence tier determination

**Key Capabilities:**
- ✅ MoA-aware literature filtering (PARP, platinum, BRCA-specific)
- ✅ Publication type scoring (RCT > Guideline > Review)
- ✅ Evidence strength calculation (0-1 scale)
- ✅ ClinVar prior analysis (pathogenic/benign with review status)
- ✅ Badge computation (StrongLiterature, MoAAligned, ClinVarStrong, RCT, Guideline)

**Integration with Biomarkers:**
```python
# Biomarker → Evidence Search Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract disease + biomarker type for evidence search
disease = biomarker_result["disease_type"]
biomarker_type = biomarker_result["biomarker_type"]

# Resistance signals → mechanism-specific evidence
if biomarker_result["resistance_signals"]:
    for signal in biomarker_result["resistance_signals"]:
        # Search for resistance mechanism evidence
        evidence = await literature(
            api_base=api_base,
            gene=signal.get("related_gene", ""),
            hgvs_p="",
            drug_name=current_drug,
            drug_moa=get_drug_moa(current_drug),
            disease=disease
        )
```

**Biomarker-Driven Evidence Triggers:**
- `burden_class == "EXTENSIVE"` → Search for high-burden treatment strategies
- `resistance_signals` → Search for resistance mechanism literature
- `forecast.cycle3_status == "BELOW_EXPECTED"` → Search for alternative therapies

---

### 4. **Food Validation**

**Location:** `api/services/food_validation/`

**Core Components:**
- **TargetExtraction**: Compound target/pathway extraction (with Research Intelligence integration)
- **SPEScoring**: Sequence/Pathway/Evidence scoring
- **ToxicityMitigation**: Drug toxicity mitigation via foods
- **BoostCalculation**: Cancer type + biomarker boosts
- **EvidenceMining**: Evidence grade determination
- **SAEFeatures**: Sequencing/Appropriateness/Efficacy features

**Key Capabilities:**
- ✅ Research Intelligence integration for target extraction
- ✅ SPE scoring (Sequence 30%, Pathway 40%, Evidence 30%)
- ✅ Toxicity mitigation via pathway overlap
- ✅ Biomarker-specific food boosts (HRD+, TMB-H, MSI-H, HER2+, BRCA)
- ✅ Treatment line appropriateness
- ✅ Cross-resistance detection

**Integration with Biomarkers:**
```python
# Biomarker → Food Validation Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract biomarkers for boost calculation
biomarkers = {
    biomarker_result["biomarker_type"]: biomarker_result["current_value"]
}

# Add biomarker-derived flags
if biomarker_result["burden_class"] == "EXTENSIVE":
    biomarkers["HIGH_BURDEN"] = True

# Calculate biomarker boosts
boosts = calculate_boosts(
    compound="NAC",
    disease=biomarker_result["disease_type"],
    disease_context={"biomarkers": biomarkers},
    treatment_history=extract_from_biomarker(biomarker_result)
)

# Toxicity mitigation based on biomarker burden
if biomarker_result["burden_class"] in ["SIGNIFICANT", "EXTENSIVE"]:
    toxicity_mitigation = await check_toxicity_mitigation(
        compound="NAC",
        patient_medications=current_drugs,
        disease_context={"biomarkers": biomarkers}
    )
```

**Biomarker-Driven Food Validation:**
- Biomarker burden → Urgency for nutrition protocol
- Biomarker type (CA-125, PSA, CEA) → Disease-specific food recommendations
- Resistance signals → Toxicity mitigation priority

---

### 5. **Insights Services**

**Location:** `api/services/insights/`

**Core Components:**
- **BundleClient**: Orchestrates functionality, chromatin, essentiality, regulatory insights

**Key Capabilities:**
- ✅ Protein functionality change prediction
- ✅ Chromatin accessibility assessment
- ✅ Gene essentiality scoring
- ✅ Regulatory/splicing impact assessment
- ✅ Parallel execution with error resilience

**Integration with Biomarkers:**
```python
# Biomarker → Genomic Variants → Insights
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract variants from biomarker context (if available)
variants = extract_variants_from_biomarker_context(biomarker_result)

# Get insights for critical variants
for variant in variants:
    insights = await bundle(
        api_base=api_base,
        gene=variant["gene"],
        variant=variant,
        hgvs_p=variant.get("hgvs_p", "")
    )
    
    # Use insights to enhance biomarker interpretation
    if insights.essentiality > 0.7:
        biomarker_result["high_essentiality_genes"].append(variant["gene"])
```

**Biomarker-Driven Insights:**
- Biomarker resistance → Check essentiality of resistance-related genes
- Biomarker burden → Assess functionality of burden-related pathways

---

### 6. **Nutrition Services**

**Location:** `api/services/nutrition/`

**Core Components:**
- **NutritionAgent**: Toxicity-aware nutrition planning

**Key Capabilities:**
- ✅ Pathway overlap computation (germline genes + drug MoA)
- ✅ Mitigating foods extraction (THE MOAT)
- ✅ LLM-enhanced rationales (optional)
- ✅ Food recommendations (prioritize/avoid)
- ✅ Drug-food interaction checking
- ✅ Timing rules generation

**Integration with Biomarkers:**
```python
# Biomarker → Nutrition Protocol
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract treatment context from biomarker
treatment_context = {
    "current_drugs": extract_drugs_from_biomarker(biomarker_result),
    "treatment_line": biomarker_result.get("treatment_line", "first-line"),
    "cycle_number": biomarker_result.get("cycle", 1)
}

# Generate nutrition plan based on biomarker burden
nutrition_plan = await nutrition_agent.generate_nutrition_plan(
    patient_id=patient_id,
    mutations=extract_mutations_from_biomarker(biomarker_result),
    germline_genes=extract_germline_genes(biomarker_result),
    current_drugs=treatment_context["current_drugs"],
    disease=biomarker_result["disease_type"],
    treatment_line=treatment_context["treatment_line"]
)

# Adjust nutrition urgency based on biomarker burden
if biomarker_result["burden_class"] == "EXTENSIVE":
    nutrition_plan["urgency"] = "HIGH"
    nutrition_plan["immediate_actions"] = [...]
```

**Biomarker-Driven Nutrition:**
- Biomarker burden → Nutrition protocol urgency
- Resistance signals → Enhanced toxicity mitigation
- Forecast milestones → Timing protocol adjustments

---

### 7. **Pathway Services**

**Location:** `api/services/pathway/`

**Core Components:**
- **DrugMapping**: Drug-to-pathway mapping utilities
- **Aggregation**: Sequence score aggregation by pathway
- **PanelConfig**: Disease-specific drug panel configuration

**Key Capabilities:**
- ✅ Drug-to-pathway weight mapping
- ✅ Gene-to-pathway mapping (RAS/MAPK, DDR, TP53, PI3K, VEGF, Pharmacogenes)
- ✅ Pathway aggregation from sequence scores
- ✅ Disease-specific panel configuration

**Integration with Biomarkers:**
```python
# Biomarker → Pathway Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract disease for pathway mapping
disease = biomarker_result["disease_type"]

# Get pathway weights for current drugs
for drug in current_drugs:
    pathway_weights = get_pathway_weights_for_drug(drug, disease)
    
    # Biomarker burden → pathway stress
    if biomarker_result["burden_class"] == "EXTENSIVE":
        # Increase pathway weights for stress-related pathways
        pathway_weights["dna_repair"] *= 1.2
        pathway_weights["inflammation"] *= 1.2
```

**Biomarker-Driven Pathways:**
- Biomarker burden → Pathway stress indicators
- Resistance signals → Pathway escape mechanisms

---

### 8. **Therapy Fit Services**

**Location:** `api/services/therapy_fit/`

**Core Components:**
- **Config**: Disease validation and normalization

**Key Capabilities:**
- ✅ Disease type validation and normalization
- ✅ Default model selection per disease
- ✅ Universal disease support

**Integration with Biomarkers:**
```python
# Biomarker → Therapy Fit Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Validate disease from biomarker
is_valid, normalized_disease = validate_disease_type(
    biomarker_result["disease_type"]
)

# Get default model for disease
default_model = get_default_model(normalized_disease)

# Use in therapy fit prediction
therapy_fit_result = await predict_therapy_fit(
    disease=normalized_disease,
    mutations=extract_mutations(biomarker_result),
    model=default_model
)
```

---

### 9. **Trial Intelligence Universal**

**Location:** `api/services/trial_intelligence_universal/`

**Core Components:**
- **Pipeline**: 6-stage progressive filtering
  - Stage 1: Hard filters (status, disease, stage)
  - Stage 2: Trial type classification
  - Stage 3: Location validation
  - Stage 4: Eligibility scoring
  - Stage 5: LLM deep analysis
  - Stage 6: Dossier assembly

**Key Capabilities:**
- ✅ Progressive filtering with audit trail
- ✅ Composite scoring (stage1 15%, stage2 35%, stage3 25%, stage4 25%)
- ✅ LLM analysis for top trials
- ✅ Location-aware filtering (NYC metro)
- ✅ Eligibility probability calculation

**Integration with Biomarkers:**
```python
# Biomarker → Trial Matching Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Build patient profile from biomarker
patient_profile = {
    "demographics": {
        "patient_id": patient_id,
        "name": patient_name
    },
    "disease": {
        "primary_diagnosis": biomarker_result["disease_type"],
        "stage": extract_stage_from_biomarker(biomarker_result)
    },
    "biomarkers": {
        biomarker_result["biomarker_type"]: {
            "current_value": biomarker_result["current_value"],
            "baseline_value": biomarker_result.get("baseline_value"),
            "burden_class": biomarker_result["burden_class"],
            "resistance_signals": biomarker_result["resistance_signals"]
        }
    },
    "treatment_history": {
        "current_line": biomarker_result.get("treatment_line", "first-line"),
        "cycle": biomarker_result.get("cycle", 1)
    }
}

# Run trial intelligence pipeline
pipeline = TrialIntelligencePipeline(patient_profile, use_llm=True)
results = await pipeline.execute(candidate_trials)

# Filter by biomarker status
if biomarker_result["resistance_signals"]:
    # Prioritize trials for resistant patients
    results["top_tier"] = filter_resistance_trials(results["top_tier"])
```

**Biomarker-Driven Trial Matching:**
- Biomarker burden → Trial eligibility filtering
- Resistance signals → Alternative therapy trials
- Forecast milestones → Trial timing recommendations

---

### 10. **Trials Services**

**Location:** `api/services/trials/`

**Core Components:**
- **TrialMatchingAgent**: Mechanism-based trial matching

**Key Capabilities:**
- ✅ Autonomous query generation
- ✅ Mechanism fit ranking (7D vectors)
- ✅ Eligibility scoring
- ✅ Combined scoring (0.7×eligibility + 0.3×mechanism)

**Integration with Biomarkers:**
```python
# Biomarker → Trial Matching
biomarker_result = biomarker_service.analyze_biomarker(...)

# Build biomarker profile
biomarker_profile = {
    biomarker_result["biomarker_type"]: {
        "value": biomarker_result["current_value"],
        "classification": biomarker_result["burden_class"]
    }
}

# Extract mechanism vector from biomarker context
mechanism_vector = extract_mechanism_vector_from_biomarker(biomarker_result)

# Match trials
agent = TrialMatchingAgent()
result = await agent.match(
    patient_profile=build_patient_profile(biomarker_result),
    biomarker_profile=biomarker_profile,
    mechanism_vector=mechanism_vector,
    max_results=10
)
```

---

### 11. **Risk Benefit Validation**

**Location:** `risk_benefit_validation/`

**Core Capabilities:**
- ✅ Deterministic logic validation
- ✅ Synthetic test cases (N=15)
- ✅ Composition policy validation (HIGH/MODERATE/LOW toxicity)

**Integration with Biomarkers:**
```python
# Biomarker → Risk/Benefit Context
biomarker_result = biomarker_service.analyze_biomarker(...)

# Biomarker burden → risk stratification
if biomarker_result["burden_class"] == "EXTENSIVE":
    risk_level = "HIGH"
elif biomarker_result["burden_class"] == "SIGNIFICANT":
    risk_level = "MODERATE"
else:
    risk_level = "LOW"

# Use in risk/benefit validation
risk_benefit_result = validate_risk_benefit(
    drug=drug,
    risk_level=risk_level,
    biomarker_context=biomarker_result
)
```

---

### 12. **Therapy Fit Validation**

**Location:** `therapy_fit_validation/`

**Core Capabilities:**
- ✅ S/P/E framework validation (Sequence 30%, Pathway 40%, Evidence 30%)
- ✅ Pathway alignment validation
- ✅ Insight chips validation
- ✅ Preflight gates

**Integration with Biomarkers:**
```python
# Biomarker → Therapy Fit Validation
biomarker_result = biomarker_service.analyze_biomarker(...)

# Extract mutations from biomarker context
mutations = extract_mutations_from_biomarker(biomarker_result)

# Validate therapy fit
therapy_fit_result = validate_therapy_fit(
    disease=biomarker_result["disease_type"],
    mutations=mutations,
    biomarker_burden=biomarker_result["burden_class"]
)
```

---

## 🔄 Biomarker-Driven Integration Workflow

### **Phase 1: Biomarker Input** (Minimal Input)

```python
# User provides:
input = {
    "disease_type": "ovarian_cancer_hgs",
    "biomarker_type": "ca125",  # Optional, auto-detected
    "current_value": 850.0,
    "baseline_value": 1200.0,  # Optional
    "cycle": 3,  # Optional
    "treatment_ongoing": True
}

# Biomarker Intelligence analyzes
biomarker_result = biomarker_service.analyze_biomarker(**input)
```

### **Phase 2: Context Extraction** (Automatic)

```python
# Extract context from biomarker result
context = {
    "disease": biomarker_result["disease_type"],
    "burden_class": biomarker_result["burden_class"],
    "burden_score": biomarker_result["burden_score"],
    "resistance_signals": biomarker_result["resistance_signals"],
    "forecast": biomarker_result["forecast"],
    "monitoring_strategy": biomarker_result["monitoring_strategy"]
}
```

### **Phase 3: Service Orchestration** (Progressive Enhancement)

```python
# Service activation based on biomarker context

# ALWAYS: Evidence search
evidence_result = await evidence_service.search(
    disease=context["disease"],
    biomarker_type=biomarker_result["biomarker_type"],
    resistance_signals=context["resistance_signals"]
)

# IF burden_class == "EXTENSIVE": Comprehensive analysis
if context["burden_class"] == "EXTENSIVE":
    moat_result = await moat_generator.generate_comprehensive_analysis(
        patient_profile=build_profile_from_biomarker(biomarker_result),
        treatment_context=extract_treatment_context(biomarker_result)
    )

# IF resistance_signals: Alternative therapy search
if context["resistance_signals"]:
    trial_results = await trial_intelligence_pipeline.execute(
        patient_profile=build_profile_from_biomarker(biomarker_result)
    )

# ALWAYS: Nutrition protocol
nutrition_plan = await nutrition_agent.generate_nutrition_plan(
    patient_id=patient_id,
    mutations=extract_mutations(biomarker_result),
    current_drugs=extract_drugs(biomarker_result),
    disease=context["disease"]
)

# IF treatment_ongoing: Food validation
if biomarker_result.get("treatment_ongoing"):
    food_validation = await validate_food(
        compound="NAC",
        disease=context["disease"],
        disease_context={"biomarkers": {biomarker_result["biomarker_type"]: biomarker_result["current_value"]}}
    )
```

### **Phase 4: Research Intelligence Integration** (Query + Biomarkers)

```python
# User provides query + biomarkers
query = "What are the resistance mechanisms for CA-125 rising on carboplatin?"

# Research Intelligence orchestrates:
research_result = await research_intelligence_orchestrator.research_question(
    question=query,
    context={
        "disease": biomarker_result["disease_type"],
        "biomarkers": {
            biomarker_result["biomarker_type"]: {
                "current": biomarker_result["current_value"],
                "baseline": biomarker_result.get("baseline_value"),
                "burden": biomarker_result["burden_class"],
                "resistance_signals": biomarker_result["resistance_signals"]
            }
        },
        "treatment_context": extract_treatment_context(biomarker_result)
    }
)

# Research Intelligence uses biomarker context to:
# 1. Enhance literature search (MoA-aware filtering)
# 2. Prioritize evidence (resistance mechanisms)
# 3. Generate MOAT analysis (toxicity + nutrition)
# 4. Match trials (resistance-specific)
# 5. Validate therapy fit (biomarker-driven)
```

---

## 🎯 Integration Architecture: Biomarker → All Services

```
┌─────────────────────────────────────────────────────────────┐
│                    USER INPUT (MINIMAL)                     │
│  Query: "Why is CA-125 rising?"                            │
│  Biomarker: {disease: "ovarian_cancer_hgs", value: 850}    │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│         BIOMARKER INTELLIGENCE (PRIMARY ORCHESTRATOR)      │
│  • Burden classification                                    │
│  • Response forecast                                        │
│  • Resistance signal detection                              │
│  • Monitoring strategy                                      │
└──────┬──────────────┬──────────────┬──────────────┬─────────┘
       │              │              │              │
       ▼              ▼              ▼              ▼
┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
│ EVIDENCE    │ │ COMPREHENSIVE│ │ FOOD        │ │ TRIAL       │
│ SERVICES    │ │ ANALYSIS     │ │ VALIDATION  │ │ INTELLIGENCE│
│             │ │              │ │             │ │             │
│ • Literature│ │ • Genomics   │ │ • SPE Score │ │ • Pipeline  │
│ • ClinVar   │ │ • Drug MoA   │ │ • Toxicity  │ │ • Matching  │
│ • Badges    │ │ • Nutrition  │ │ • Boosts    │ │ • Ranking   │
└──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘
       │               │                │               │
       └───────────────┴────────────────┴───────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              RESEARCH INTELLIGENCE ORCHESTRATOR            │
│  • Synthesizes all service outputs                          │
│  • LLM-enhanced explanations                                │
│  • MOAT analysis integration                                │
│  • Comprehensive report generation                          │
└─────────────────────────────────────────────────────────────┘
```

---

## 📋 Service Integration Checklist

### **Tier 1: Core Integration** (Always Active)

- [x] **Biomarker Intelligence** → Primary input orchestrator
- [x] **Evidence Services** → Literature + ClinVar for all biomarker contexts
- [x] **Nutrition Services** → Always generate nutrition protocol
- [x] **Pathway Services** → Pathway mapping for all diseases

### **Tier 2: Conditional Integration** (Biomarker-Driven)

- [ ] **Comprehensive Analysis** → Trigger if `burden_class == "EXTENSIVE"` OR `resistance_signals` present
- [ ] **Food Validation** → Trigger if `treatment_ongoing == True`
- [ ] **Trial Intelligence** → Trigger if `resistance_signals` present OR user query mentions "trials"
- [ ] **Insights Services** → Trigger if genomic variants available in biomarker context

### **Tier 3: Advanced Integration** (Query-Driven)

- [ ] **Therapy Fit Validation** → Trigger if query mentions "therapy fit" OR "drug efficacy"
- [ ] **Risk Benefit Validation** → Trigger if query mentions "risk" OR "toxicity"
- [ ] **Trial Matching Agent** → Trigger if query mentions "clinical trials" OR "trials"

---

## 🔧 Implementation Plan

### **Sprint 1-5: Biomarker Intelligence Enhancement**

**Goal:** Make biomarker intelligence the primary orchestrator

**Tasks:**
1. Add context extraction methods to `BiomarkerIntelligenceService`
   - `extract_disease_context()` → Returns disease + biomarker metadata
   - `extract_treatment_context()` → Returns treatment line, cycle, drugs
   - `extract_genomic_context()` → Returns mutations if available
   - `extract_resistance_context()` → Returns resistance signals + recommendations

2. Add service trigger methods
   - `should_trigger_comprehensive_analysis()` → Based on burden_class
   - `should_trigger_trial_search()` → Based on resistance_signals
   - `should_trigger_food_validation()` → Based on treatment_ongoing

3. Add integration hooks
   - `get_evidence_search_context()` → Returns context for evidence services
   - `get_nutrition_context()` → Returns context for nutrition agent
   - `get_trial_matching_context()` → Returns context for trial intelligence

### **Sprint 6-10: Evidence Services Integration**

**Goal:** Biomarker-driven evidence search

**Tasks:**
1. Enhance `literature_client.py` to accept biomarker context
   - Add biomarker-specific MoA terms (CA-125 → platinum, PARP)
   - Add resistance signal → mechanism mapping
   - Add burden class → evidence priority

2. Enhance `clinvar_client.py` to use biomarker context
   - Extract variants from biomarker context
   - Prioritize ClinVar lookup for resistance-related genes

3. Enhance `badge_computation.py` to consider biomarker context
   - Biomarker burden → evidence strength boost
   - Resistance signals → mechanism alignment boost

### **Sprint 11-15: Comprehensive Analysis Integration**

**Goal:** Biomarker-driven MOAT analysis

**Tasks:**
1. Modify `MOATAnalysisGenerator` to accept biomarker input
   - Add `biomarker_context` parameter
   - Extract patient profile from biomarker result
   - Extract treatment context from biomarker result

2. Enhance `GenomicAnalyzer` to use biomarker context
   - Biomarker burden → genomic risk stratification
   - Resistance signals → critical gene prioritization

3. Enhance `DrugMoAExplainer` to use biomarker context
   - Resistance signals → alternative drug recommendations
   - Biomarker burden → toxicity risk adjustment

### **Sprint 16-20: Food Validation Integration**

**Goal:** Biomarker-driven food validation

**Tasks:**
1. Enhance `target_extraction.py` to use biomarker context
   - Biomarker type → disease-specific target extraction
   - Resistance signals → mechanism-specific targets

2. Enhance `boost_calculation.py` to use biomarker values
   - Current biomarker value → boost calculation
   - Burden class → urgency boost

3. Enhance `toxicity_mitigation.py` to use biomarker context
   - Biomarker burden → mitigation priority
   - Resistance signals → enhanced mitigation

### **Sprint 21-25: Trial Intelligence Integration**

**Goal:** Biomarker-driven trial matching

**Tasks:**
1. Enhance `TrialIntelligencePipeline` to accept biomarker input
   - Build patient profile from biomarker result
   - Extract eligibility criteria from biomarker context
   - Filter trials based on biomarker status

2. Enhance trial matching to use biomarker context
   - Resistance signals → alternative therapy trials
   - Biomarker burden → trial urgency filtering

### **Sprint 26-30: Research Intelligence Orchestration**

**Goal:** Unified biomarker-driven Research Intelligence

**Tasks:**
1. Create `BiomarkerDrivenOrchestrator` class
   - Accepts: query + biomarker input
   - Orchestrates: All services based on biomarker context
   - Returns: Comprehensive analysis report

2. Integrate all services into Research Intelligence
   - Biomarker → Evidence → Comprehensive Analysis → Nutrition → Trials
   - Progressive enhancement based on available data
   - Maximum output from minimum input

---

## 🎯 Success Criteria

### **Minimum Viable Integration**

- ✅ Biomarker input → All core services activated
- ✅ Biomarker burden → Comprehensive analysis triggered
- ✅ Resistance signals → Trial search triggered
- ✅ Treatment ongoing → Food validation triggered

### **Optimal Integration**

- ✅ Single biomarker value + query → Full Research Intelligence report
- ✅ Biomarker context → Enhanced evidence search
- ✅ Biomarker context → Personalized nutrition protocol
- ✅ Biomarker context → Mechanism-aligned trial matching

---

## 📝 Notes

- **Modularity**: All services remain independent and testable
- **Progressive Enhancement**: Services activate based on available data
- **Biomarker-Centric**: Biomarkers are the primary input orchestrator
- **Maximum Output, Minimum Input**: Query + biomarkers → comprehensive analysis

---

**Last Updated:** January 2025  
**Status:** 📋 Review Complete - Ready for Implementation  
**Next Steps:** Begin Sprint 1-5 (Biomarker Intelligence Enhancement)

