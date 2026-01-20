"""
LLM-Enhanced Toxicity Rationale Service

Uses LLM to generate personalized, context-aware explanations for:
1. Why a food mitigates drug toxicity
2. Patient-friendly summaries
3. Timing/dosage rationale based on treatment context

This implements Phase 3 of TOXICITY_MOAT_IMPLEMENTATION_TASKS.md
and enhances Module 06 (Nutrition Agent) from MOAT orchestration.

Created: 2025-01-28
Status: Phase 3 - LLM Enhancement
"""

import sys
import os
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add project root to path for LLM API access
# From: oncology-coPilot/oncology-backend-minimal/api/services/
# To: crispr-assistant-main/
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.tools.llm_api import query_llm
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    print(f"Warning: LLM API not available: {e}. Falling back to static rationales.")


TOXICITY_RATIONALE_PROMPT = """You are a precision oncology nutritionist. Generate a concise, evidence-based explanation for why this food/supplement helps mitigate drug-induced toxicity.

PATIENT CONTEXT:
- Cancer Type: {cancer_type}
- Current Drug: {drug_name} (Mechanism: {drug_moa})
- Germline Variants: {germline_genes}
- Toxicity Pathway: {toxicity_pathway}
- Treatment Phase: {treatment_phase}

FOOD/SUPPLEMENT:
- Compound: {compound}
- Mechanism: {base_mechanism}
- Recommended Timing: {timing}
- Dose: {dose}

INSTRUCTIONS:
1. Explain why this compound specifically helps with {drug_name} toxicity
2. Mention the pathway connection ({toxicity_pathway})
3. Explain optimal timing around chemotherapy
4. Keep to 2-3 sentences, patient-friendly language
5. Do NOT claim it "cures" or "treats" - use "may help support", "can help protect"

Generate a personalized rationale:"""


PATIENT_SUMMARY_PROMPT = """You are explaining toxicity mitigation to a cancer patient in simple terms.

The patient is on {drug_name} chemotherapy.
We've identified that {compound} may help protect against {toxicity_type}.

Write a 2-sentence patient-friendly explanation that:
1. Explains what the drug does that causes this side effect
2. Explains how the supplement may help
3. Uses simple language (8th grade reading level)
4. Avoids medical jargon

Patient explanation:"""


async def generate_toxicity_rationale(
    compound: str,
    drug_name: str,
    drug_moa: str,
    toxicity_pathway: str,
    germline_genes: List[str],
    cancer_type: str = "cancer",
    treatment_phase: str = "active treatment",
    base_mechanism: str = "",
    timing: str = "",
    dose: str = "",
    provider: str = "gemini"
) -> Dict[str, Any]:
    """
    Generate LLM-enhanced rationale for toxicity mitigation.
    
    Args:
        compound: Food/supplement name
        drug_name: Drug name (e.g., "carboplatin")
        drug_moa: Mechanism of action (e.g., "platinum_agent")
        toxicity_pathway: Pathway being mitigated (e.g., "dna_repair")
        germline_genes: List of germline variant genes
        cancer_type: Cancer type
        treatment_phase: Treatment phase (e.g., "first-line chemotherapy")
        base_mechanism: Base mechanism description (fallback)
        timing: Recommended timing
        dose: Recommended dose
        provider: LLM provider (default: "gemini")
    
    Returns:
        Dict with:
        - rationale: Personalized mechanism explanation
        - patient_summary: Patient-friendly explanation
        - confidence: Confidence in the recommendation
        - llm_enhanced: Whether LLM was used
    """
    
    result = {
        "rationale": base_mechanism,  # Fallback
        "patient_summary": f"{compound} may help support your body during {drug_name} treatment.",
        "confidence": 0.6,
        "llm_enhanced": False
    }
    
    if not LLM_AVAILABLE:
        return result
    
    try:
        # Generate personalized rationale
        rationale_prompt = TOXICITY_RATIONALE_PROMPT.format(
            cancer_type=cancer_type,
            drug_name=drug_name,
            drug_moa=drug_moa,
            toxicity_pathway=toxicity_pathway,
            germline_genes=", ".join(germline_genes) if germline_genes else "none identified",
            treatment_phase=treatment_phase,
            compound=compound,
            base_mechanism=base_mechanism,
            timing=timing,
            dose=dose
        )
        
        # query_llm is synchronous, wrap in asyncio.to_thread for async context
        rationale = await asyncio.to_thread(query_llm, rationale_prompt, provider)
        
        if rationale and not rationale.startswith("Error") and len(rationale.strip()) > 20:
            result["rationale"] = rationale.strip()
            result["llm_enhanced"] = True
            result["confidence"] = 0.75
        
        # Generate patient summary
        toxicity_type_map = {
            "dna_repair": "DNA damage",
            "inflammation": "inflammation and immune reactions",
            "cardiometabolic": "heart stress"
        }
        toxicity_type = toxicity_type_map.get(toxicity_pathway, "side effects")
        
        patient_prompt = PATIENT_SUMMARY_PROMPT.format(
            drug_name=drug_name,
            compound=compound,
            toxicity_type=toxicity_type
        )
        
        patient_summary = await asyncio.to_thread(query_llm, patient_prompt, provider)
        
        if patient_summary and not patient_summary.startswith("Error") and len(patient_summary.strip()) > 20:
            result["patient_summary"] = patient_summary.strip()
    
    except Exception as e:
        print(f"LLM rationale generation failed: {e}")
        import traceback
        traceback.print_exc()
        # Keep fallback values
    
    return result


async def generate_mitigation_dossier(
    patient_context: Dict[str, Any],
    medications: List[str],
    mitigating_foods: List[Dict[str, Any]],
    provider: str = "gemini"
) -> Dict[str, Any]:
    """
    Generate a complete toxicity mitigation dossier using LLM.
    
    This creates a structured document similar to MBD4_TP53_CLINICAL_DOSSIER.md
    but focused on toxicity mitigation and food recommendations.
    
    Args:
        patient_context: Dict with cancer_type, germline_genes, treatment_line
        medications: List of drug names
        mitigating_foods: List of food recommendations from get_mitigating_foods()
        provider: LLM provider
    
    Returns:
        Dict with dossier sections:
        - executive_summary
        - toxicity_assessment
        - food_recommendations (with LLM rationales)
        - timing_protocol
        - monitoring_recommendations
    """
    
    germline_genes = patient_context.get("germline_genes", [])
    cancer_type = patient_context.get("cancer_type", "cancer")
    treatment_line = patient_context.get("treatment_line", "active treatment")
    
    dossier = {
        "executive_summary": "",
        "toxicity_assessment": {},
        "food_recommendations": [],
        "timing_protocol": "",
        "monitoring_recommendations": "",
        "llm_enhanced": False
    }
    
    # Enhance each food recommendation with LLM rationale
    enhanced_foods = []
    for food in mitigating_foods:
        for drug in medications:
            from api.services.toxicity_pathway_mappings import get_drug_moa
            drug_moa = get_drug_moa(drug)
            
            if drug_moa == "unknown":
                continue
            
            enhanced = await generate_toxicity_rationale(
                compound=food.get("compound", ""),
                drug_name=drug,
                drug_moa=drug_moa,
                toxicity_pathway=food.get("pathway", ""),
                germline_genes=germline_genes,
                cancer_type=cancer_type,
                treatment_phase=treatment_line,
                base_mechanism=food.get("mechanism", ""),
                timing=food.get("timing", ""),
                dose=food.get("dose", ""),
                provider=provider
            )
            
            enhanced_food = {**food, **enhanced}
            enhanced_foods.append(enhanced_food)
            break  # Only enhance once per food
    
    dossier["food_recommendations"] = enhanced_foods
    
    # Generate executive summary if LLM available
    if LLM_AVAILABLE and enhanced_foods:
        try:
            summary_prompt = f"""Summarize the following toxicity mitigation plan in 3-4 sentences:

Patient: {cancer_type}, on {', '.join(medications)}
Germline variants: {', '.join(germline_genes) if germline_genes else 'none'}
Recommended foods: {', '.join([f['compound'] for f in enhanced_foods[:3]])}

Focus on: What toxicities are being addressed and how the foods help."""

            summary = await asyncio.to_thread(query_llm, summary_prompt, provider)
            if summary and not summary.startswith("Error") and len(summary.strip()) > 50:
                dossier["executive_summary"] = summary.strip()
                dossier["llm_enhanced"] = True
        except Exception as e:
            print(f"Executive summary generation failed: {e}")
    
    return dossier


# Singleton service
_llm_toxicity_service = None

def get_llm_toxicity_service():
    """
    Get singleton LLM toxicity service instance.
    
    Returns:
        Dict with service functions and availability status
    """
    global _llm_toxicity_service
    if _llm_toxicity_service is None:
        _llm_toxicity_service = {
            "generate_rationale": generate_toxicity_rationale,
            "generate_dossier": generate_mitigation_dossier,
            "available": LLM_AVAILABLE
        }
    return _llm_toxicity_service






