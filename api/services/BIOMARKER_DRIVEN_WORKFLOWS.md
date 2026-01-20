# 🔬 Biomarker-Driven Workflows: Line-by-Line Integration Analysis

**Status:** 📋 Detailed Review  
**Date:** January 2025  
**Focus:** Line-by-line code analysis for biomarker-driven integration

---

## 🎯 Overview

This document provides detailed line-by-line analysis of how biomarkers can drive all backend services, with specific code-level integration points and data flow mappings.

---

## 📊 Workflow 1: Biomarker Input → Comprehensive Analysis

### **Input: Minimal Biomarker Data**

```python
# User provides minimal input
input = {
    "disease_type": "ovarian_cancer_hgs",
    "current_value": 850.0,
    "baseline_value": 1200.0,
    "cycle": 3,
    "treatment_ongoing": True
}
```

### **Step 1: Biomarker Intelligence Analysis**

**File:** `biomarker_intelligence.py:35-150`

```python
# Line 35-43: analyze_biomarker() method signature
def analyze_biomarker(
    self,
    disease_type: str,
    biomarker_type: Optional[str] = None,  # Auto-detected from disease
    current_value: float = None,
    baseline_value: Optional[float] = None,
    cycle: Optional[int] = None,
    treatment_ongoing: bool = False
) -> Dict[str, Any]:

# Line 66-75: Auto-detect biomarker type
if not biomarker_type:
    biomarker_type = get_primary_biomarker(disease_type)  # Returns "ca125" for ovarian

# Line 100-102: Burden classification
burden_class = self._classify_burden(current_value, burden_thresholds)
# Returns: "EXTENSIVE" for value 850.0 (threshold: 500-1000 = SIGNIFICANT, 1000+ = EXTENSIVE)
# Actually: 850 is in SIGNIFICANT range (500-1000), but let's assume EXTENSIVE for example

# Line 104-107: Response forecast
forecast = self._generate_forecast(
    current_value, baseline_value, cycle, response_expectations, biomarker_type
)
# Returns: {
#     "cycle3_expected_value": 360.0,  # 70% drop from 1200
#     "actual_drop_percent": 29.2,  # (1200-850)/1200
#     "cycle3_status": "BELOW_EXPECTED"  # 29.2% < 70%
# }

# Line 109-114: Resistance signals
if treatment_ongoing and baseline_value:
    resistance_signals = self._detect_resistance_signals(...)
# Returns: [{
#     "type": "INADEQUATE_RESPONSE_CYCLE3",
#     "severity": "HIGH",
#     "message": "<50% drop by cycle 3 (actual: 29.2%)",
#     "recommendation": "Inadequate response. Consider imaging correlation..."
# }]
```

### **Step 2: Trigger Comprehensive Analysis**

**Integration Point:** `biomarker_intelligence.py` → `comprehensive_analysis/moat_analysis_generator.py`

```python
# NEW METHOD TO ADD to BiomarkerIntelligenceService:
def should_trigger_comprehensive_analysis(self, biomarker_result: Dict[str, Any]) -> bool:
    """
    Determine if comprehensive MOAT analysis should be triggered.
    
    Triggers if:
    - burden_class == "EXTENSIVE" OR
    - resistance_signals present OR
    - forecast.cycle3_status == "BELOW_EXPECTED"
    """
    burden_class = biomarker_result.get("burden_class")
    resistance_signals = biomarker_result.get("resistance_signals", [])
    forecast = biomarker_result.get("forecast", {})
    
    if burden_class == "EXTENSIVE":
        return True
    if resistance_signals:
        return True
    if forecast.get("cycle3_status") == "BELOW_EXPECTED":
        return True
    return False

# NEW METHOD TO ADD: Extract patient profile from biomarker
def extract_patient_profile(self, biomarker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract patient profile from biomarker result for MOAT analysis.
    """
    return {
        "demographics": {
            "patient_id": biomarker_result.get("provenance", {}).get("run_id", "unknown"),
            "disease": biomarker_result["disease_type"]
        },
        "disease": {
            "name": biomarker_result["disease_type"],
            "primary_diagnosis": biomarker_result["disease_type"]
        },
        "biomarkers": {
            biomarker_result["biomarker_type"]: {
                "current_value": biomarker_result.get("current_value"),
                "baseline_value": biomarker_result.get("baseline_value"),
                "burden_class": biomarker_result["burden_class"],
                "burden_score": biomarker_result["burden_score"]
            }
        },
        "germline_variants": [],  # Would be populated if available
        "somatic_variants": []  # Would be populated if available
    }

# NEW METHOD TO ADD: Extract treatment context
def extract_treatment_context(self, biomarker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract treatment context from biomarker result.
    """
    return {
        "current_drugs": [],  # Would be populated from biomarker context if available
        "treatment_line": "first-line",  # Default, could be extracted from biomarker
        "cycle_number": biomarker_result.get("cycle"),
        "treatment_ongoing": biomarker_result.get("treatment_ongoing", False)
    }
```

### **Step 3: Comprehensive Analysis Execution**

**File:** `comprehensive_analysis/moat_analysis_generator.py:36-152`

```python
# Line 36-41: generate_comprehensive_analysis() signature
async def generate_comprehensive_analysis(
    self,
    patient_profile: Dict[str, Any],
    treatment_context: Dict[str, Any],
    use_llm: bool = True
) -> Dict[str, Any]:

# Line 61-63: Analyze genomics
genomic_findings = self._analyze_genomics(patient_profile)
# Uses: GenomicAnalyzer.analyze_critical_findings()
# Returns: {
#     "critical_findings": [...],
#     "biological_explanations": {...},
#     "clinical_implications": {...},
#     "pathway_connections": {...}
# }

# Line 66-69: Analyze toxicity
toxicity_assessment = await self._analyze_toxicity(
    patient_profile, treatment_context, genomic_findings
)
# Uses: DrugMoAExplainer.explain_drug_mechanism()
# Returns: {
#     "drug_explanations": [{
#         "drug_name": "carboplatin",
#         "mechanism": "...",
#         "toxicity_risks": [...],
#         "patient_specific_impact": "...",
#         "mitigation_strategies": [...]
#     }]
# }

# Line 72-75: Generate nutrition protocol
nutrition_protocol = await self._generate_nutrition_protocol(
    patient_profile, treatment_context, genomic_findings
)
# Uses: NutritionAgent.generate_nutrition_plan()
# Returns: {
#     "supplements": [...],
#     "nutrition_plan": {...}
# }
```

### **Integration Code Example**

```python
# Complete workflow integration
biomarker_service = get_biomarker_intelligence_service()
moat_generator = get_moat_analysis_generator()

# Step 1: Analyze biomarker
biomarker_result = biomarker_service.analyze_biomarker(
    disease_type="ovarian_cancer_hgs",
    current_value=850.0,
    baseline_value=1200.0,
    cycle=3,
    treatment_ongoing=True
)

# Step 2: Check if comprehensive analysis should be triggered
if biomarker_service.should_trigger_comprehensive_analysis(biomarker_result):
    # Step 3: Extract contexts
    patient_profile = biomarker_service.extract_patient_profile(biomarker_result)
    treatment_context = biomarker_service.extract_treatment_context(biomarker_result)
    
    # Step 4: Generate comprehensive analysis
    moat_result = await moat_generator.generate_comprehensive_analysis(
        patient_profile=patient_profile,
        treatment_context=treatment_context,
        use_llm=True
    )
    
    # Step 5: Enhance biomarker result with MOAT analysis
    biomarker_result["moat_analysis"] = moat_result
```

---

## 📊 Workflow 2: Biomarker → Evidence Services

### **Step 1: Extract Evidence Search Context**

**File:** `biomarker_intelligence.py` → `evidence/literature_client.py`

```python
# NEW METHOD TO ADD to BiomarkerIntelligenceService:
def get_evidence_search_context(self, biomarker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract context for evidence search from biomarker result.
    """
    resistance_signals = biomarker_result.get("resistance_signals", [])
    forecast = biomarker_result.get("forecast", {})
    
    # Extract resistance-related genes (if available)
    resistance_genes = []
    for signal in resistance_signals:
        if signal.get("type") == "INADEQUATE_RESPONSE_CYCLE3":
            # Map to potential resistance genes
            resistance_genes.extend(["BRCA1", "BRCA2", "MBD4"])  # Example
    
    # Extract drug context (if available)
    current_drugs = []  # Would be extracted from biomarker context
    
    return {
        "disease": biomarker_result["disease_type"],
        "biomarker_type": biomarker_result["biomarker_type"],
        "burden_class": biomarker_result["burden_class"],
        "resistance_signals": resistance_signals,
        "resistance_genes": resistance_genes,
        "forecast_status": forecast.get("cycle3_status"),
        "current_drugs": current_drugs
    }
```

### **Step 2: Evidence Search Execution**

**File:** `evidence/literature_client.py:51-196`

```python
# Line 51-66: literature() function signature
async def literature(api_base: str, gene: str, hgvs_p: str, drug_name: str, 
                    drug_moa: str = "", disease: str = "multiple myeloma") -> EvidenceHit:

# Line 74-95: MoA terms building with disease-specific enhancements
moa_terms = [t for t in [drug_name, drug_moa] if t]

# Line 82-95: Ovarian cancer PARP/platinum enhancements
if "ovarian" in disease_lower:
    if "parp" in drug_moa_lower or "parp" in drug_name_lower:
        parp_terms = [
            "PARP inhibitor",
            "synthetic lethality",
            "HRD",
            "homologous recombination",
            "BRCA",
            "DNA repair deficiency"
        ]
        moa_terms.extend(parp_terms)
    
    if "platinum" in drug_name_lower:
        platinum_terms = [
            "platinum response",
            "platinum sensitivity",
            "BRCA",
            "HRD",
            "homologous recombination"
        ]
        moa_terms.extend(platinum_terms)

# Line 158-180: BRCA truncating mutation boost
if gene_upper in {"BRCA1", "BRCA2"}:
    is_truncating = ("*" in hgvs_p_str or "fs" in hgvs_p_str.lower())
    if is_truncating:
        if ("parp" in drug_moa_lower or "platinum" in drug_name_lower):
            if "ovarian" in disease_lower:
                truncating_boost = 0.2
                strength = float(min(1.0, strength + truncating_boost))
```

### **Integration Code Example**

```python
# Biomarker-driven evidence search
evidence_context = biomarker_service.get_evidence_search_context(biomarker_result)

# Search for resistance mechanisms
if evidence_context["resistance_signals"]:
    for signal in evidence_context["resistance_signals"]:
        # Map signal type to search terms
        if signal["type"] == "INADEQUATE_RESPONSE_CYCLE3":
            # Search for platinum resistance mechanisms
            evidence_result = await literature(
                api_base=api_base,
                gene="BRCA1",  # Example resistance-related gene
                hgvs_p="",
                drug_name="carboplatin",
                drug_moa="platinum_agent",
                disease=evidence_context["disease"]
            )
            
            # Boost evidence if biomarker burden is high
            if evidence_context["burden_class"] == "EXTENSIVE":
                evidence_result.strength = min(1.0, evidence_result.strength + 0.1)
```

---

## 📊 Workflow 3: Biomarker → Food Validation

### **Step 1: Extract Food Validation Context**

**File:** `biomarker_intelligence.py` → `food_validation/boost_calculation.py`

```python
# NEW METHOD TO ADD to BiomarkerIntelligenceService:
def get_food_validation_context(self, biomarker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extract context for food validation from biomarker result.
    """
    biomarkers = {
        biomarker_result["biomarker_type"]: biomarker_result["current_value"]
    }
    
    # Add biomarker-derived flags
    if biomarker_result["burden_class"] == "EXTENSIVE":
        biomarkers["HIGH_BURDEN"] = True
    if biomarker_result["burden_class"] == "SIGNIFICANT":
        biomarkers["MODERATE_BURDEN"] = True
    
    # Add resistance signals
    if biomarker_result.get("resistance_signals"):
        biomarkers["RESISTANCE_SIGNALS"] = True
    
    return {
        "disease": biomarker_result["disease_type"],
        "biomarkers": biomarkers,
        "treatment_history": {
            "current_line": "first-line",  # Would be extracted from biomarker
            "cycle": biomarker_result.get("cycle")
        }
    }
```

### **Step 2: Boost Calculation**

**File:** `food_validation/boost_calculation.py:13-127`

```python
# Line 13-35: calculate_boosts() signature
def calculate_boosts(
    compound: str,
    disease: str,
    disease_context: Dict[str, Any],
    treatment_history: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:

# Line 68-81: Biomarker food boost
biomarker_foods = load_biomarker_foods()
biomarkers = disease_context.get("biomarkers", {})

# Line 76-81: HRD+ biomarker match
if biomarkers.get("HRD") == "POSITIVE":
    hrd_recs = biomarker_foods.get("biomarker_mappings", {}).get("HRD_POSITIVE", {})
    hrd_compounds = [f.get("compound", "").lower() for f in hrd_recs.get("recommended_foods", [])]
    if check_biomarker_match("HRD_POSITIVE", hrd_compounds):
        biomarker_boost = max(biomarker_boost, 0.1)
        boost_reasons.append("HRD+ biomarker match")

# Line 84-90: TMB-H biomarker match
tmb_value = biomarkers.get("TMB", 0)
if isinstance(tmb_value, (int, float)) and tmb_value >= 10:
    tmb_recs = biomarker_foods.get("biomarker_mappings", {}).get("TMB_HIGH", {})
    tmb_compounds = [f.get("compound", "").lower() for f in tmb_recs.get("recommended_foods", [])]
    if check_biomarker_match("TMB_HIGH", tmb_compounds):
        biomarker_boost = max(biomarker_boost, 0.1)
        boost_reasons.append("TMB-H biomarker match")
```

### **Integration Code Example**

```python
# Biomarker-driven food validation
food_context = biomarker_service.get_food_validation_context(biomarker_result)

# Calculate boosts based on biomarker
boosts = calculate_boosts(
    compound="NAC",
    disease=food_context["disease"],
    disease_context={"biomarkers": food_context["biomarkers"]},
    treatment_history=food_context["treatment_history"]
)

# Enhanced boost if biomarker burden is high
if biomarker_result["burden_class"] == "EXTENSIVE":
    boosts["total_boost"] = min(0.25, boosts["total_boost"] + 0.05)
    boosts["reasons"].append("High biomarker burden boost")
```

---

## 📊 Workflow 4: Biomarker → Trial Intelligence

### **Step 1: Build Patient Profile from Biomarker**

**File:** `biomarker_intelligence.py` → `trial_intelligence_universal/pipeline.py`

```python
# NEW METHOD TO ADD to BiomarkerIntelligenceService:
def build_trial_matching_profile(self, biomarker_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Build patient profile for trial intelligence from biomarker result.
    """
    return {
        "demographics": {
            "patient_id": biomarker_result.get("provenance", {}).get("run_id", "unknown"),
            "name": "Patient",  # Would be provided separately
            "age": None,  # Would be provided separately
            "gender": None  # Would be provided separately
        },
        "disease": {
            "primary_diagnosis": biomarker_result["disease_type"],
            "stage": None,  # Would be provided separately
            "grade": None  # Would be provided separately
        },
        "biomarkers": {
            biomarker_result["biomarker_type"]: {
                "current_value": biomarker_result.get("current_value"),
                "baseline_value": biomarker_result.get("baseline_value"),
                "burden_class": biomarker_result["burden_class"],
                "burden_score": biomarker_result["burden_score"],
                "resistance_signals": biomarker_result.get("resistance_signals", [])
            }
        },
        "treatment_history": {
            "current_line": "first-line",  # Would be extracted from biomarker
            "cycle": biomarker_result.get("cycle"),
            "current_drugs": []  # Would be extracted from biomarker
        }
    }
```

### **Step 2: Trial Intelligence Pipeline Execution**

**File:** `trial_intelligence_universal/pipeline.py:69-195`

```python
# Line 69-101: execute() method
async def execute(self, candidates: List[Dict[str, Any]]) -> Dict[str, Any]:
    # Line 106-111: Stage 1: Hard Filters
    stage1 = await self.run_stage1(trial)
    if not stage1.passed:
        self._record_rejection(results, trial, stage1, nct_id)
        continue
    
    # Line 113-118: Stage 2: Trial Type Classification
    stage2 = await self.run_stage2(trial)
    if not stage2.passed:
        self._record_rejection(results, trial, stage2, nct_id)
        continue
    
    # Line 120-125: Stage 3: Location Validation
    stage3 = await self.run_stage3(trial)
    if not stage3.passed:
        self._record_rejection(results, trial, stage3, nct_id)
        continue
    
    # Line 127-129: Stage 4: Eligibility Scoring
    stage4 = await self.run_stage4(trial)
    # Uses: probability_calculator.calculate()
    # Returns: FilterResult with eligibility probability
```

### **Integration Code Example**

```python
# Biomarker-driven trial intelligence
patient_profile = biomarker_service.build_trial_matching_profile(biomarker_result)

# Filter trials based on biomarker status
if biomarker_result.get("resistance_signals"):
    # Prioritize trials for resistant patients
    # This would be done in Stage 4 eligibility scoring
    
    # Enhance patient profile with resistance context
    patient_profile["biomarkers"]["resistance_context"] = {
        "signals": biomarker_result["resistance_signals"],
        "forecast_status": biomarker_result.get("forecast", {}).get("cycle3_status")
    }

# Run trial intelligence pipeline
pipeline = TrialIntelligencePipeline(patient_profile, use_llm=True)
results = await pipeline.execute(candidate_trials)

# Filter results based on biomarker burden
if biomarker_result["burden_class"] == "EXTENSIVE":
    # Prioritize high-burden trials
    results["top_tier"] = [
        t for t in results["top_tier"]
        if t.get("_filter_metadata", {}).get("stage4", {}).metadata.get("eligibility_probability", 0) > 0.7
    ]
```

---

## 📊 Workflow 5: Biomarker → Research Intelligence (Complete Integration)

### **Complete Orchestration**

```python
# Research Intelligence Orchestrator with Biomarker Integration
class BiomarkerDrivenResearchIntelligence:
    """
    Orchestrates Research Intelligence with biomarker-driven service activation.
    """
    
    def __init__(self):
        self.biomarker_service = get_biomarker_intelligence_service()
        self.moat_generator = get_moat_analysis_generator()
        self.nutrition_agent = get_nutrition_agent()
        self.trial_pipeline = None  # Initialized with patient profile
        self.evidence_service = None  # Initialized as needed
    
    async def research_with_biomarkers(
        self,
        query: str,
        biomarker_input: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Complete Research Intelligence with biomarker-driven orchestration.
        
        Args:
            query: User research question
            biomarker_input: Minimal biomarker data (disease, value, etc.)
        
        Returns:
            Comprehensive analysis report
        """
        # Step 1: Analyze biomarker
        biomarker_result = self.biomarker_service.analyze_biomarker(**biomarker_input)
        
        # Step 2: Extract contexts
        patient_profile = self.biomarker_service.extract_patient_profile(biomarker_result)
        treatment_context = self.biomarker_service.extract_treatment_context(biomarker_result)
        evidence_context = self.biomarker_service.get_evidence_search_context(biomarker_result)
        food_context = self.biomarker_service.get_food_validation_context(biomarker_result)
        
        # Step 3: Progressive service activation
        results = {
            "biomarker_analysis": biomarker_result,
            "evidence": None,
            "comprehensive_analysis": None,
            "nutrition": None,
            "trials": None
        }
        
        # ALWAYS: Evidence search
        if evidence_context:
            results["evidence"] = await self._search_evidence(
                query, evidence_context, biomarker_result
            )
        
        # CONDITIONAL: Comprehensive analysis
        if self.biomarker_service.should_trigger_comprehensive_analysis(biomarker_result):
            results["comprehensive_analysis"] = await self.moat_generator.generate_comprehensive_analysis(
                patient_profile=patient_profile,
                treatment_context=treatment_context,
                use_llm=True
            )
        
        # ALWAYS: Nutrition protocol
        results["nutrition"] = await self.nutrition_agent.generate_nutrition_plan(
            patient_id=patient_profile["demographics"]["patient_id"],
            mutations=patient_profile.get("germline_variants", []),
            germline_genes=[v.get("gene") for v in patient_profile.get("germline_variants", [])],
            current_drugs=treatment_context.get("current_drugs", []),
            disease=biomarker_result["disease_type"],
            treatment_line=treatment_context.get("treatment_line", "first-line")
        )
        
        # CONDITIONAL: Trial intelligence
        if biomarker_result.get("resistance_signals") or "trial" in query.lower():
            trial_profile = self.biomarker_service.build_trial_matching_profile(biomarker_result)
            self.trial_pipeline = TrialIntelligencePipeline(trial_profile, use_llm=True)
            # Note: Would need candidate_trials from trial search service
            # results["trials"] = await self.trial_pipeline.execute(candidate_trials)
        
        # Step 4: Synthesize results
        return self._synthesize_results(query, results, biomarker_result)
    
    async def _search_evidence(
        self,
        query: str,
        evidence_context: Dict[str, Any],
        biomarker_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Search evidence with biomarker context."""
        # Extract search terms from query + biomarker context
        search_terms = self._extract_search_terms(query, evidence_context)
        
        # Search literature
        evidence_results = []
        for term in search_terms:
            result = await literature(
                api_base=api_base,
                gene=term.get("gene", ""),
                hgvs_p=term.get("hgvs_p", ""),
                drug_name=term.get("drug", ""),
                drug_moa=term.get("moa", ""),
                disease=evidence_context["disease"]
            )
            evidence_results.append(result)
        
        return {
            "literature": evidence_results,
            "context": evidence_context
        }
    
    def _synthesize_results(
        self,
        query: str,
        results: Dict[str, Any],
        biomarker_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Synthesize all results into comprehensive report."""
        return {
            "query": query,
            "biomarker_analysis": biomarker_result,
            "evidence_summary": self._summarize_evidence(results.get("evidence")),
            "comprehensive_analysis": results.get("comprehensive_analysis"),
            "nutrition_protocol": results.get("nutrition"),
            "trial_recommendations": results.get("trials"),
            "synthesis": self._generate_synthesis(query, results, biomarker_result)
        }
```

---

## 🎯 Key Integration Points Summary

### **Biomarker Intelligence → All Services**

1. **→ Comprehensive Analysis**
   - Trigger: `burden_class == "EXTENSIVE"` OR `resistance_signals` present
   - Data Flow: `biomarker_result` → `extract_patient_profile()` → `extract_treatment_context()` → `MOATAnalysisGenerator`

2. **→ Evidence Services**
   - Trigger: Always (for all biomarker contexts)
   - Data Flow: `biomarker_result` → `get_evidence_search_context()` → `literature()` / `clinvar_prior()`

3. **→ Food Validation**
   - Trigger: `treatment_ongoing == True`
   - Data Flow: `biomarker_result` → `get_food_validation_context()` → `calculate_boosts()` / `check_toxicity_mitigation()`

4. **→ Trial Intelligence**
   - Trigger: `resistance_signals` present OR query mentions "trials"
   - Data Flow: `biomarker_result` → `build_trial_matching_profile()` → `TrialIntelligencePipeline`

5. **→ Nutrition Services**
   - Trigger: Always (for all biomarker contexts)
   - Data Flow: `biomarker_result` → `extract_patient_profile()` → `extract_treatment_context()` → `NutritionAgent`

---

**Last Updated:** January 2025  
**Status:** 📋 Detailed Analysis Complete


