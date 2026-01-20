"""
Toxicity Mitigation Step

Checks if a compound mitigates toxicity from patient medications.
THE MOAT - connecting toxicity assessment to food recommendations.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def check_toxicity_mitigation(
    compound: str,
    patient_medications: List[str],
    disease_context: Dict[str, Any],
    enable_llm_enhancement: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Check if compound mitigates toxicity from patient medications.
    
    Args:
        compound: Compound name
        patient_medications: List of medication names
        disease_context: Disease context with mutations (for germline genes)
        enable_llm_enhancement: Whether to enable LLM enhancement
    
    Returns:
        {
            "mitigates": True,
            "target_drug": "...",
            "target_moa": "...",
            "pathway": "...",
            "mechanism": "...",
            "timing": "...",
            "evidence_tier": "...",
            "dose": "...",
            "care_plan_ref": "...",
            "llm_enhanced": True (if enabled),
            "llm_rationale": "...",
            "patient_summary": "...",
            "llm_confidence": 0.0-1.0
        } or None if no mitigation
    """
    if not patient_medications:
        return None
    
    try:
        from api.services.toxicity_pathway_mappings import (
            compute_pathway_overlap, get_mitigating_foods, get_drug_moa
        )
        
        # Extract genes from disease_context mutations (conservative: treat as potential germline)
        germline_genes = []
        mutations = disease_context.get("mutations", [])
        for mut in mutations:
            if isinstance(mut, dict) and mut.get("gene"):
                germline_genes.append(mut["gene"])
            elif isinstance(mut, str):
                # Handle string format like "BRCA1 V600E" or just "BRCA1"
                gene = mut.split()[0] if " " in mut else mut
                germline_genes.append(gene)
        
        if not germline_genes:
            return None
        
        # Check each medication for toxicity mitigation
        for drug in patient_medications:
            if not drug or not isinstance(drug, str):
                continue
            
            drug_name = drug.strip()
            moa = get_drug_moa(drug_name)
            
            # Only proceed if we have a known MoA and germline genes
            if moa != "unknown" and germline_genes:
                # Compute pathway overlap
                pathway_overlap = compute_pathway_overlap(germline_genes, moa)
                mitigating_foods = get_mitigating_foods(pathway_overlap)
                
                # Check if current compound is a mitigating food
                compound_lower = compound.lower()
                for food in mitigating_foods:
                    food_name_lower = food["compound"].lower()
                    
                    # Flexible matching: check if compound name appears in food name or vice versa
                    # Examples: "NAC" matches "NAC (N-Acetyl Cysteine)", "Vitamin D" matches "Vitamin D3"
                    if (compound_lower in food_name_lower or 
                        food_name_lower.split("(")[0].strip().lower() in compound_lower or
                        any(word in compound_lower for word in food_name_lower.split() if len(word) > 3)):
                        
                        toxicity_mitigation = {
                            "mitigates": True,
                            "target_drug": drug_name,
                            "target_moa": moa,
                            "pathway": food["pathway"],
                            "mechanism": food["mechanism"],
                            "timing": food["timing"],
                            "evidence_tier": food.get("evidence_tier", "MODERATE"),
                            "dose": food.get("dose", ""),
                            "care_plan_ref": food.get("care_plan_ref", "")
                        }
                        
                        # LLM Enhancement (optional)
                        if enable_llm_enhancement:
                            try:
                                from api.services.llm_toxicity_service import get_llm_toxicity_service
                                llm_service = get_llm_toxicity_service()
                                
                                if llm_service["available"]:
                                    # Extract germline genes from disease_context
                                    germline_genes_for_llm = []
                                    if disease_context:
                                        mutations = disease_context.get("mutations", [])
                                        for mut in mutations:
                                            if isinstance(mut, dict) and mut.get("gene"):
                                                germline_genes_for_llm.append(mut["gene"])
                                            elif isinstance(mut, str):
                                                gene = mut.split()[0] if " " in mut else mut
                                                germline_genes_for_llm.append(gene)
                                    
                                    # Generate LLM-enhanced rationale
                                    enhanced = await llm_service["generate_rationale"](
                                        compound=compound,
                                        drug_name=toxicity_mitigation["target_drug"],
                                        drug_moa=toxicity_mitigation["target_moa"],
                                        toxicity_pathway=toxicity_mitigation["pathway"],
                                        germline_genes=germline_genes_for_llm,
                                        cancer_type=disease_context.get("disease", "cancer") if disease_context else "cancer",
                                        treatment_phase=disease_context.get("treatment_line", "active treatment"),
                                        base_mechanism=toxicity_mitigation["mechanism"],
                                        timing=toxicity_mitigation["timing"],
                                        dose=toxicity_mitigation.get("dose", ""),
                                        provider="gemini"
                                    )
                                    
                                    # Add LLM-enhanced fields
                                    if enhanced.get("llm_enhanced"):
                                        toxicity_mitigation["llm_rationale"] = enhanced.get("rationale")
                                        toxicity_mitigation["patient_summary"] = enhanced.get("patient_summary")
                                        toxicity_mitigation["llm_enhanced"] = True
                                        toxicity_mitigation["llm_confidence"] = enhanced.get("confidence", 0.75)
                            except Exception as e:
                                logger.warning(f"LLM enhancement failed: {e}")
                                # Don't fail - just continue without LLM enhancement
                        
                        return toxicity_mitigation
            
    except Exception as e:
        # Don't fail the entire request if toxicity check fails
        logger.warning(f"Toxicity mitigation check failed: {e}")
        import traceback
        logger.debug(traceback.format_exc())
    
    return None

