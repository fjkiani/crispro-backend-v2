"""
LLM Explanation Enhancer - Adds personalized "HOW" and "WHY" explanations.

Takes structured data from all services and enhances it with detailed,
personalized explanations using LLM.
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, Any, List, Optional
import logging
import hashlib
import json

# Add project root to path for LLM API access
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.tools.llm_api import query_llm
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Try Gemini API as fallback
try:
    import google.generativeai as genai
    if os.getenv("GEMINI_API_KEY"):
        genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
        GEMINI_AVAILABLE = True
    else:
        GEMINI_AVAILABLE = False
except ImportError:
    GEMINI_AVAILABLE = False

logger = logging.getLogger(__name__)


class LLMExplanationEnhancer:
    """Enhance structured data with personalized LLM explanations."""
    
    def __init__(self):
        self.llm_available = LLM_AVAILABLE or GEMINI_AVAILABLE
        self.cache = {}  # Simple in-memory cache (can be replaced with Redis)
    
    async def enhance_explanations(
        self,
        structured_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Add personalized explanations to structured data.
        
        Args:
            structured_data: Data from all services (genomics, drugs, nutrition, etc.)
            patient_context: Patient profile and treatment context
        
        Returns:
            Same structure but with 'how_it_works' and 'why_it_matters' fields added
        """
        if not self.llm_available:
            logger.warning("LLM not available - returning structured data without enhancements")
            return structured_data
        
        enhanced_data = structured_data.copy()
        
        # Enhance genomic findings
        if "genomic_findings" in enhanced_data:
            enhanced_data["genomic_findings"] = await self._enhance_genomic_findings(
                enhanced_data["genomic_findings"], patient_context
            )
        
        # Enhance drug explanations
        if "toxicity_assessment" in enhanced_data:
            enhanced_data["toxicity_assessment"] = await self._enhance_drug_explanations(
                enhanced_data["toxicity_assessment"], patient_context
            )
        
        # Enhance nutrition protocol
        if "nutrition_protocol" in enhanced_data:
            enhanced_data["nutrition_protocol"] = await self._enhance_nutrition_protocol(
                enhanced_data["nutrition_protocol"], patient_context
            )
        
        # Enhance treatment optimization
        if "treatment_optimization" in enhanced_data:
            enhanced_data["treatment_optimization"] = await self._enhance_treatment_optimization(
                enhanced_data["treatment_optimization"], patient_context
            )
        
        return enhanced_data
    
    async def _enhance_genomic_findings(
        self,
        genomic_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance genomic findings with detailed explanations."""
        enhanced = genomic_data.copy()
        
        critical_findings = enhanced.get("critical_findings", [])
        for finding in critical_findings:
            gene = finding.get("gene", "")
            if not gene:
                continue
            
            # Check cache
            cache_key = f"genomic_{gene}_{finding.get('zygosity', 'unknown')}"
            if cache_key in self.cache:
                finding["llm_enhanced_explanation"] = self.cache[cache_key]
                continue
            
            # Generate explanation
            prompt = self._build_genomic_prompt(finding, genomic_data, patient_context)
            explanation = await self._call_llm(prompt)
            
            if explanation:
                finding["llm_enhanced_explanation"] = explanation
                self.cache[cache_key] = explanation
        
        return enhanced
    
    async def _enhance_drug_explanations(
        self,
        toxicity_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance drug explanations with patient-specific details."""
        enhanced = toxicity_data.copy()
        
        drug_explanations = enhanced.get("drug_explanations", [])
        for drug_data in drug_explanations:
            drug_name = drug_data.get("drug_name", "")
            if not drug_name:
                continue
            
            # Check cache
            cache_key = f"drug_{drug_name}_{patient_context.get('treatment_line', 'unknown')}"
            if cache_key in self.cache:
                drug_data["llm_enhanced_mechanism"] = self.cache[cache_key]
                continue
            
            # Generate enhanced explanation
            prompt = self._build_drug_moa_prompt(drug_data, patient_context)
            explanation = await self._call_llm(prompt)
            
            if explanation:
                drug_data["llm_enhanced_mechanism"] = explanation
                self.cache[cache_key] = explanation
        
        return enhanced
    
    async def _enhance_nutrition_protocol(
        self,
        nutrition_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance nutrition protocol with detailed mechanisms."""
        enhanced = nutrition_data.copy()
        
        supplements = enhanced.get("supplements", [])
        for supp in supplements:
            compound = supp.get("compound", "")
            if not compound:
                continue
            
            # Check cache
            cache_key = f"nutrition_{compound}_{patient_context.get('treatment_line', 'unknown')}"
            if cache_key in self.cache:
                supp["llm_enhanced_mechanism"] = self.cache[cache_key]
                supp["llm_enhanced_rationale"] = self.cache.get(f"{cache_key}_rationale", "")
                continue
            
            # Generate mechanism explanation
            mechanism_prompt = self._build_supplement_mechanism_prompt(supp, patient_context)
            mechanism = await self._call_llm(mechanism_prompt)
            
            # Generate patient rationale
            rationale_prompt = self._build_supplement_rationale_prompt(supp, patient_context)
            rationale = await self._call_llm(rationale_prompt)
            
            if mechanism:
                supp["llm_enhanced_mechanism"] = mechanism
                self.cache[cache_key] = mechanism
            
            if rationale:
                supp["llm_enhanced_rationale"] = rationale
                self.cache[f"{cache_key}_rationale"] = rationale
        
        return enhanced
    
    async def _enhance_treatment_optimization(
        self,
        optimization_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Enhance treatment optimization with detailed explanations."""
        enhanced = optimization_data.copy()
        
        tests = enhanced.get("tests_to_request", [])
        for test in tests:
            test_name = test.get("name", "")
            if not test_name:
                continue
            
            # Check cache
            cache_key = f"test_{test_name}"
            if cache_key in self.cache:
                test["llm_enhanced_how"] = self.cache[cache_key]
                test["llm_enhanced_why"] = self.cache.get(f"{cache_key}_why", "")
                continue
            
            # Generate explanations
            how_prompt = self._build_test_how_prompt(test, patient_context)
            why_prompt = self._build_test_why_prompt(test, patient_context)
            
            how_explanation = await self._call_llm(how_prompt)
            why_explanation = await self._call_llm(why_prompt)
            
            if how_explanation:
                test["llm_enhanced_how"] = how_explanation
                self.cache[cache_key] = how_explanation
            
            if why_explanation:
                test["llm_enhanced_why"] = why_explanation
                self.cache[f"{cache_key}_why"] = why_explanation
        
        return enhanced
    
    def _build_genomic_prompt(
        self,
        finding: Dict[str, Any],
        genomic_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for genomic finding explanation."""
        gene = finding.get("gene", "")
        variant = finding.get("variant", "")
        zygosity = finding.get("zygosity", "")
        pathway = finding.get("pathway", "")
        
        biological = genomic_data.get("biological_explanations", {}).get(gene, "")
        clinical = genomic_data.get("clinical_implications", {}).get(gene, "")
        
        current_drugs = patient_context.get("current_drugs", [])
        treatment_line = patient_context.get("treatment_line", "first-line")
        
        return f"""You are an oncology genomics expert explaining a critical finding to a patient.

PATIENT CONTEXT:
- Gene: {gene}
- Variant: {variant}
- Zygosity: {zygosity.upper()}
- Pathway: {pathway}
- Current Drugs: {', '.join(current_drugs) if current_drugs else 'None'}
- Treatment Line: {treatment_line}

BASE EXPLANATION:
{biological}

CLINICAL IMPACT:
{clinical}

INSTRUCTIONS:
1. Explain HOW {gene} works in simple terms (use analogies)
2. Explain WHY {zygosity} loss matters for THIS patient
3. Connect to current treatment ({', '.join(current_drugs) if current_drugs else 'treatment'})
4. Explain what this means for future treatment options
5. Keep it clear and personalized (mention "YOUR" not "the patient's")

Generate a detailed, personalized explanation (3-4 paragraphs):"""
    
    def _build_drug_moa_prompt(
        self,
        drug_data: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for drug MoA explanation."""
        drug_name = drug_data.get("drug_name", "")
        moa = drug_data.get("moa", "")
        mechanism = drug_data.get("mechanism", "")
        patient_impact = drug_data.get("patient_specific_impact", "")
        
        genomic_findings = patient_context.get("genomic_findings", {})
        critical_findings = genomic_findings.get("critical_findings", [])
        
        return f"""You are an oncology expert explaining how a drug works to a patient.

DRUG: {drug_name}
MECHANISM OF ACTION: {moa}

HOW IT WORKS (BASE):
{mechanism}

PATIENT-SPECIFIC IMPACT:
{patient_impact}

PATIENT'S GENOMICS:
{', '.join([f.get('gene', '') for f in critical_findings[:3]]) if critical_findings else 'None identified'}

INSTRUCTIONS:
1. Explain HOW {drug_name} works (step-by-step, use analogies)
2. Explain WHY toxicity happens (connect to patient's genomics if relevant)
3. Explain HOW patient's genomic profile affects toxicity risk
4. Use "YOUR" language (personalized)
5. Be specific about mechanisms, not generic

Generate a detailed explanation (2-3 paragraphs):"""
    
    def _build_supplement_mechanism_prompt(
        self,
        supp: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for supplement mechanism explanation."""
        compound = supp.get("compound", "")
        score = supp.get("score", 0)
        base_mechanism = supp.get("mechanism", "")
        
        current_drugs = patient_context.get("current_drugs", [])
        genomic_findings = patient_context.get("genomic_findings", {})
        critical_findings = genomic_findings.get("critical_findings", [])
        
        return f"""You are explaining how a supplement works at the molecular level.

SUPPLEMENT: {compound}
MOAT SCORE: {score:.2f}
BASE MECHANISM: {base_mechanism}

PATIENT CONTEXT:
- Current Drugs: {', '.join(current_drugs) if current_drugs else 'None'}
- Genomic Findings: {', '.join([f.get('gene', '') for f in critical_findings[:2]]) if critical_findings else 'None'}

INSTRUCTIONS:
1. Explain HOW {compound} works at the molecular level (pathways, enzymes, etc.)
2. Be specific about mechanisms (not just "antioxidant" - explain what it does)
3. Connect to patient's current drugs if relevant
4. Use scientific but accessible language

Generate a detailed mechanism explanation (2-3 sentences):"""
    
    def _build_supplement_rationale_prompt(
        self,
        supp: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for supplement patient rationale."""
        compound = supp.get("compound", "")
        base_rationale = supp.get("rationale", "")
        
        genomic_findings = patient_context.get("genomic_findings", {})
        critical_findings = genomic_findings.get("critical_findings", [])
        
        return f"""You are explaining why a supplement matters for THIS specific patient.

SUPPLEMENT: {compound}
BASE RATIONALE: {base_rationale}

PATIENT'S GENOMICS:
{', '.join([f"{f.get('gene', '')} ({f.get('zygosity', '')})" for f in critical_findings[:2]]) if critical_findings else 'None'}

INSTRUCTIONS:
1. Explain WHY {compound} matters for THIS patient (connect to their genomics)
2. Explain WHY the timing matters (connect to their current drugs)
3. Explain WHAT the MOAT score means (why {supp.get('score', 0):.2f} for this patient)
4. Use "YOUR" language (personalized)
5. Be specific about connections, not generic

Generate a personalized rationale (2-3 sentences):"""
    
    def _build_test_how_prompt(
        self,
        test: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for test 'HOW' explanation."""
        test_name = test.get("name", "")
        base_how = test.get("how", "")
        
        return f"""You are explaining how a medical test works.

TEST: {test_name}
BASE EXPLANATION: {base_how}

INSTRUCTIONS:
1. Explain HOW {test_name} works (technology, methodology)
2. Explain what it measures
3. Explain the threshold/cutoff (if applicable)
4. Use accessible language but be accurate

Generate a clear explanation (2-3 sentences):"""
    
    def _build_test_why_prompt(
        self,
        test: Dict[str, Any],
        patient_context: Dict[str, Any]
    ) -> str:
        """Build prompt for test 'WHY' explanation."""
        test_name = test.get("name", "")
        base_why = test.get("why", "")
        
        genomic_findings = patient_context.get("genomic_findings", {})
        critical_findings = genomic_findings.get("critical_findings", [])
        
        return f"""You are explaining why a patient needs a specific test.

TEST: {test_name}
BASE RATIONALE: {base_why}

PATIENT'S GENOMICS:
{', '.join([f.get('gene', '') for f in critical_findings[:2]]) if critical_findings else 'None'}

INSTRUCTIONS:
1. Explain WHY this patient needs {test_name} (connect to their genomics)
2. Explain what the prediction is (what we expect to find)
3. Explain WHY it matters (what happens if positive/negative)
4. Use "YOUR" language (personalized)

Generate a personalized explanation (2-3 sentences):"""
    
    async def _call_llm(self, prompt: str) -> Optional[str]:
        """Call LLM with prompt, with fallback handling."""
        if not self.llm_available:
            return None
        
        try:
            # Try query_llm first (synchronous, needs threading)
            if LLM_AVAILABLE:
                result = await asyncio.to_thread(query_llm, prompt, provider="gemini")
                if result and not result.startswith("Error"):
                    return result.strip()
            
            # Fallback to Gemini API directly
            if GEMINI_AVAILABLE:
                model = genai.GenerativeModel(os.getenv("LIT_LLM_MODEL", "gemini-2.5-flash"))
                response = await asyncio.to_thread(model.generate_content, prompt)
                text = getattr(response, "text", None) or str(response)
                if text and not text.startswith("Error"):
                    return text.strip()
            
            return None
        
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
            return None













