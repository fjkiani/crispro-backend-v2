"""
LLM-Enhanced Food Validation Service

Uses LLM to provide:
1. Personalized rationales (treatment line + biomarker context)
2. Mechanism synthesis (beyond keyword matching)
3. Evidence interpretation (treatment line filtering)
4. Patient-specific recommendations

Integrates with evidence doctrines for trustworthy outputs.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
import json
import logging

logger = logging.getLogger(__name__)

# Load .env file from project root
try:
    from dotenv import load_dotenv
    # Find project root (crispr-assistant-main) and load .env
    PROJECT_ROOT_FOR_ENV = Path(__file__).resolve()
    for _ in range(5):  # Go up 5 levels to reach crispr-assistant-main
        PROJECT_ROOT_FOR_ENV = PROJECT_ROOT_FOR_ENV.parent
    env_path = PROJECT_ROOT_FOR_ENV / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        logger.info(f"Loaded .env from: {env_path}")
    else:
        logger.warning(f".env file not found at: {env_path}")
except ImportError:
    pass  # dotenv not installed, rely on environment variables
except Exception as e:
    logger.warning(f"Failed to load .env: {e}")

# Import LLM API from src/tools/llm_api.py
# Use same pattern as trial_fit_analyzer.py which works
PROJECT_ROOT = Path(__file__).resolve()
# Go up: services (1) -> api (2) -> oncology-backend-minimal (3) -> oncology-coPilot (4) -> crispr-assistant-main (5)
for _ in range(5):
    PROJECT_ROOT = PROJECT_ROOT.parent
llm_api_path = PROJECT_ROOT / "src" / "tools"
if llm_api_path.exists():
    sys.path.insert(0, str(llm_api_path))

try:
    from llm_api import get_llm_chat_response, query_llm
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    # Don't use logger here as it might not be initialized yet
    pass

class FoodLLMEnhancementService:
    """
    LLM enhancement for food validation recommendations.
    
    Provides:
    - Personalized rationales
    - Mechanism synthesis
    - Treatment-line-specific explanations
    - Evidence interpretation
    """
    
    def __init__(self):
        self.llm_available = LLM_AVAILABLE
        self.provider = "gemini"  # Default provider
        self.model = "gemini-2.5-pro"  # Default model (matches trial_fit_analyzer)
    
    async def generate_personalized_rationale(
        self,
        compound: str,
        disease: str,
        cancer_type: str,
        treatment_line: Optional[str],
        biomarkers: Dict[str, Any],
        pathways: List[str],
        sae_features: Dict[str, Any],
        evidence_grade: str,
        total_papers: int,
        rct_count: int
    ) -> str:
        """
        Generate personalized rationale using LLM.
        
        Integrates:
        - Treatment line context
        - Biomarker matches
        - Pathway targeting
        - Evidence strength
        - SAE features
        """
        if not self.llm_available:
            return self._generate_fallback_rationale(
                compound, disease, treatment_line, biomarkers, evidence_grade
            )
        
        # Format biomarkers
        biomarker_text = self._format_biomarkers(biomarkers)
        
        # Format treatment line
        treatment_line_text = self._format_treatment_line(treatment_line)
        
        # Format SAE features
        sae_text = self._format_sae_features(sae_features)
        
        prompt = f"""You are a clinical oncology nutrition expert. Generate a personalized rationale for recommending {compound} to a patient.

**PATIENT CONTEXT:**
- Cancer Type: {cancer_type} ({disease})
- Treatment Line: {treatment_line_text}
- Biomarkers: {biomarker_text}
- Target Pathways: {', '.join(pathways[:5])}

**EVIDENCE:**
- Evidence Grade: {evidence_grade}
- Total Papers: {total_papers}
- RCT Count: {rct_count}

**TREATMENT LINE INTELLIGENCE:**
{sae_text}

**YOUR TASK:**
Write a 2-3 sentence personalized rationale explaining:
1. Why {compound} is recommended for THIS patient (cancer type + treatment line)
2. How it targets the disrupted pathways
3. Why it's appropriate for their treatment line
4. Any biomarker-specific benefits

Be specific, evidence-based, and patient-friendly. Use clinical language but avoid jargon.

Format: Plain text, no markdown."""

        try:
            conversation_history = [
                {
                    "role": "system",
                    "content": "You are a clinical oncology nutrition expert. Provide evidence-based, personalized recommendations with clear rationale."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # get_llm_chat_response is synchronous (uses subprocess)
            # Call directly like trial_fit_analyzer does
            response = get_llm_chat_response(
                conversation_history=conversation_history,
                provider=self.provider,
                model_name=self.model
            )
            
            # Clean response
            response = response.strip()
            if response.startswith('"') and response.endswith('"'):
                response = response[1:-1]
            
            return response
            
        except Exception as e:
            logger.error(f"LLM rationale generation failed: {e}")
            return self._generate_fallback_rationale(
                compound, disease, treatment_line, biomarkers, evidence_grade
            )
    
    async def synthesize_mechanisms_llm(
        self,
        compound: str,
        disease: str,
        pathways: List[str],
        papers: List[Dict[str, Any]],
        max_mechanisms: int = 5
    ) -> List[str]:
        """
        Use LLM to synthesize mechanisms from papers (beyond keyword matching).
        
        Returns list of mechanism names discovered by LLM.
        """
        if not self.llm_available or not papers:
            return []
        
        # Build context from top papers
        papers_text = "\n\n".join([
            f"PMID: {p.get('pmid', 'N/A')}\n"
            f"Title: {p.get('title', 'N/A')}\n"
            f"Abstract: {p.get('abstract', '')[:800]}"
            for p in papers[:8]  # Top 8 papers
        ])
        
        prompt = f"""You are a biomedical research analyst. Analyze these research papers about {compound} for {disease}.

**PAPERS:**
{papers_text}

**TARGET PATHWAYS:**
{', '.join(pathways[:5])}

**YOUR TASK:**
Extract mechanisms of action for {compound} that relate to these pathways. Look for:
- How {compound} interacts with pathway components
- Novel mechanisms not captured by simple keyword matching
- Pathway-specific effects

Return a JSON array of mechanism names (brief, lowercase_with_underscores):
["mechanism1", "mechanism2", "mechanism3"]

Return ONLY the JSON array, no other text."""

        try:
            conversation_history = [
                {
                    "role": "system",
                    "content": "You are a biomedical research analyst. Return valid JSON arrays only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # get_llm_chat_response is synchronous (uses subprocess)
            # Call directly like trial_fit_analyzer does
            response = get_llm_chat_response(
                conversation_history=conversation_history,
                provider=self.provider,
                model_name=self.model
            )
            
            # Clean and parse JSON
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            # Parse JSON array
            mechanisms = json.loads(response)
            if isinstance(mechanisms, list):
                return mechanisms[:max_mechanisms]
            else:
                return []
                
        except Exception as e:
            logger.error(f"LLM mechanism synthesis failed: {e}")
            return []
    
    async def interpret_evidence_for_treatment_line(
        self,
        compound: str,
        disease: str,
        treatment_line: Optional[str],
        evidence_grade: str,
        papers: List[Dict[str, Any]],
        total_papers: int,
        rct_count: int
    ) -> Dict[str, Any]:
        """
        Use LLM to interpret evidence in context of treatment line.
        
        Returns interpretation with treatment-line-specific insights.
        """
        if not self.llm_available:
            return {
                "interpretation": f"Evidence grade: {evidence_grade} ({total_papers} papers, {rct_count} RCTs)",
                "treatment_line_relevance": "Not analyzed (LLM unavailable)",
                "confidence_note": ""
            }
        
        # Filter papers by treatment line relevance
        treatment_line_papers = self._filter_papers_by_treatment_line(papers, treatment_line)
        
        treatment_line_text = self._format_treatment_line(treatment_line)
        
        prompt = f"""You are a clinical oncology evidence analyst. Interpret the evidence for {compound} in {disease} specifically for {treatment_line_text}.

**EVIDENCE SUMMARY:**
- Evidence Grade: {evidence_grade}
- Total Papers: {total_papers}
- RCT Count: {rct_count}
- Treatment-Line-Relevant Papers: {len(treatment_line_papers)}

**TREATMENT LINE CONTEXT:**
{treatment_line_text}

**YOUR TASK:**
Provide a brief interpretation (2-3 sentences) covering:
1. How strong is the evidence for THIS treatment line?
2. Are there treatment-line-specific considerations?
3. What is the confidence level for this recommendation?

Return JSON:
{{
  "interpretation": "brief interpretation text",
  "treatment_line_relevance": "high|moderate|low",
  "confidence_note": "brief confidence assessment"
}}"""

        try:
            conversation_history = [
                {
                    "role": "system",
                    "content": "You are a clinical oncology evidence analyst. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # get_llm_chat_response is synchronous (uses subprocess)
            # Call directly like trial_fit_analyzer does
            response = get_llm_chat_response(
                conversation_history=conversation_history,
                provider=self.provider,
                model_name=self.model
            )
            
            # Clean and parse JSON
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            interpretation = json.loads(response)
            return interpretation
            
        except Exception as e:
            logger.error(f"LLM evidence interpretation failed: {e}")
            return {
                "interpretation": f"Evidence grade: {evidence_grade} ({total_papers} papers, {rct_count} RCTs)",
                "treatment_line_relevance": "unknown",
                "confidence_note": "LLM interpretation unavailable"
            }
    
    async def generate_patient_specific_recommendations(
        self,
        compound: str,
        disease: str,
        cancer_type: str,
        treatment_line: Optional[str],
        biomarkers: Dict[str, Any],
        sae_features: Dict[str, Any],
        dosage: str,
        evidence: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Generate patient-specific recommendations using LLM.
        
        Returns structured recommendations with timing, monitoring, and safety notes.
        """
        if not self.llm_available:
            return {
                "timing": "As directed by healthcare provider",
                "monitoring": "Standard monitoring",
                "safety_notes": "Consult healthcare provider before use",
                "patient_instructions": f"Take {dosage} as recommended"
            }
        
        biomarker_text = self._format_biomarkers(biomarkers)
        treatment_line_text = self._format_treatment_line(treatment_line)
        
        prompt = f"""You are a clinical oncology nutrition expert. Generate patient-specific recommendations for {compound}.

**PATIENT CONTEXT:**
- Cancer Type: {cancer_type} ({disease})
- Treatment Line: {treatment_line_text}
- Biomarkers: {biomarker_text}
- Current Dosage: {dosage}

**TREATMENT LINE INTELLIGENCE:**
- Line Appropriateness: {sae_features.get('line_fitness', {}).get('score', 0):.1%}
- Cross-Resistance Risk: {sae_features.get('cross_resistance', {}).get('risk', 'UNKNOWN')}
- Sequencing Fitness: {'Optimal' if sae_features.get('sequencing_fitness', {}).get('optimal', False) else 'Suboptimal'}

**EVIDENCE:**
- Grade: {evidence.get('evidence_grade', 'UNKNOWN')}
- Papers: {evidence.get('total_papers', 0)}
- RCTs: {evidence.get('rct_count', 0)}

**YOUR TASK:**
Generate patient-specific recommendations covering:
1. **Timing**: When to take this (with meals, before/after treatment, etc.)
2. **Monitoring**: What to monitor (lab values, side effects, etc.)
3. **Safety Notes**: Specific safety considerations for this patient
4. **Patient Instructions**: Clear, actionable instructions

Return JSON:
{{
  "timing": "when and how to take",
  "monitoring": "what to monitor",
  "safety_notes": "specific safety considerations",
  "patient_instructions": "clear instructions"
}}"""

        try:
            conversation_history = [
                {
                    "role": "system",
                    "content": "You are a clinical oncology nutrition expert. Return valid JSON only."
                },
                {
                    "role": "user",
                    "content": prompt
                }
            ]
            
            # get_llm_chat_response is synchronous (uses subprocess)
            # Call directly like trial_fit_analyzer does
            response = get_llm_chat_response(
                conversation_history=conversation_history,
                provider=self.provider,
                model_name=self.model
            )
            
            # Clean and parse JSON
            response = response.strip()
            if "```json" in response:
                response = response.split("```json")[1].split("```")[0].strip()
            elif "```" in response:
                response = response.split("```")[1].split("```")[0].strip()
            
            recommendations = json.loads(response)
            return recommendations
            
        except Exception as e:
            logger.error(f"LLM patient recommendations failed: {e}")
            return {
                "timing": "As directed by healthcare provider",
                "monitoring": "Standard monitoring",
                "safety_notes": "Consult healthcare provider before use",
                "patient_instructions": f"Take {dosage} as recommended"
            }
    
    def _format_biomarkers(self, biomarkers: Dict[str, Any]) -> str:
        """Format biomarkers for LLM prompt."""
        if not biomarkers:
            return "None specified"
        
        parts = []
        if biomarkers.get('HRD') == 'POSITIVE':
            parts.append("HRD+ (Homologous Recombination Deficiency)")
        if biomarkers.get('TMB', 0) >= 10:
            parts.append(f"TMB-high ({biomarkers.get('TMB')} mutations/Mb)")
        if biomarkers.get('MSI') == 'HIGH':
            parts.append("MSI-high (Microsatellite Instability)")
        if biomarkers.get('HER2') == 'POSITIVE':
            parts.append("HER2+")
        if biomarkers.get('germline_BRCA') == 'POSITIVE':
            parts.append("Germline BRCA+")
        
        return ", ".join(parts) if parts else "None specified"
    
    def _format_treatment_line(self, treatment_line: Optional[str]) -> str:
        """Format treatment line for LLM prompt."""
        if not treatment_line:
            return "Not specified"
        
        line_lower = treatment_line.lower()
        if any(term in line_lower for term in ["l1", "first", "frontline", "primary"]):
            return "First-line chemotherapy (L1)"
        elif any(term in line_lower for term in ["l2", "second", "second-line"]):
            return "Second-line therapy (L2)"
        elif any(term in line_lower for term in ["l3", "third", "third-line", "maintenance"]):
            return "Third-line or maintenance therapy (L3)"
        else:
            return f"Treatment line: {treatment_line}"
    
    def _format_sae_features(self, sae_features: Dict[str, Any]) -> str:
        """Format SAE features for LLM prompt."""
        if not sae_features:
            return "No treatment line intelligence available"
        
        line_fitness = sae_features.get('line_fitness', {})
        cross_resistance = sae_features.get('cross_resistance', {})
        sequencing_fitness = sae_features.get('sequencing_fitness', {})
        
        return f"""- Line Appropriateness: {line_fitness.get('score', 0):.1%} ({line_fitness.get('status', 'unknown')})
- Cross-Resistance Risk: {cross_resistance.get('risk', 'UNKNOWN')} (score: {cross_resistance.get('score', 0):.2f})
- Sequencing Fitness: {sequencing_fitness.get('score', 0):.1%} ({'Optimal' if sequencing_fitness.get('optimal', False) else 'Suboptimal'})"""
    
    def _filter_papers_by_treatment_line(
        self,
        papers: List[Dict[str, Any]],
        treatment_line: Optional[str]
    ) -> List[Dict[str, Any]]:
        """Filter papers by treatment line relevance."""
        if not treatment_line or not papers:
            return papers
        
        treatment_line_lower = treatment_line.lower()
        relevant_terms = []
        
        if any(term in treatment_line_lower for term in ["l1", "first", "frontline", "primary"]):
            relevant_terms = ["first-line", "frontline", "primary", "initial treatment", "neoadjuvant"]
        elif any(term in treatment_line_lower for term in ["l2", "second", "second-line"]):
            relevant_terms = ["second-line", "second line", "salvage", "relapsed"]
        elif any(term in treatment_line_lower for term in ["l3", "third", "third-line", "maintenance"]):
            relevant_terms = ["third-line", "third line", "maintenance", "salvage", "refractory"]
        
        if not relevant_terms:
            return papers
        
        # Score papers by treatment line relevance
        scored_papers = []
        for paper in papers:
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            text_combined = title + " " + abstract
            
            relevance_score = sum(1 for term in relevant_terms if term in text_combined)
            paper["treatment_line_relevance"] = relevance_score
            scored_papers.append(paper)
        
        # Sort by relevance
        scored_papers.sort(key=lambda p: p.get("treatment_line_relevance", 0), reverse=True)
        return scored_papers
    
    def _generate_fallback_rationale(
        self,
        compound: str,
        disease: str,
        treatment_line: Optional[str],
        biomarkers: Dict[str, Any],
        evidence_grade: str
    ) -> str:
        """Generate fallback rationale without LLM."""
        parts = [f"{compound} is recommended for {disease}"]
        
        if treatment_line:
            parts.append(f"during {self._format_treatment_line(treatment_line).lower()}")
        
        biomarker_parts = []
        if biomarkers.get('HRD') == 'POSITIVE':
            biomarker_parts.append("HRD+")
        if biomarkers.get('TMB', 0) >= 10:
            biomarker_parts.append("TMB-high")
        
        if biomarker_parts:
            parts.append(f"for patients with {', '.join(biomarker_parts)}")
        
        parts.append(f"based on {evidence_grade.lower()} evidence.")
        
        return " ".join(parts)


# Singleton
_food_llm_service_instance = None

def get_food_llm_enhancement_service() -> FoodLLMEnhancementService:
    """Get singleton instance."""
    global _food_llm_service_instance
    if _food_llm_service_instance is None:
        _food_llm_service_instance = FoodLLMEnhancementService()
    return _food_llm_service_instance


