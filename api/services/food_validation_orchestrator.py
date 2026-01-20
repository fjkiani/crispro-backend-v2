"""
Food Validation Orchestrator

Coordinates all validation steps in the pipeline.
Manages flow, errors, and fallbacks.
"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from datetime import datetime

logger = logging.getLogger(__name__)

# Import validation steps
from api.services.food_validation.target_extraction import extract_targets
from api.services.food_validation.evidence_mining import mine_evidence
from api.services.food_validation.spe_scoring import compute_spe_score
from api.services.food_validation.toxicity_mitigation import check_toxicity_mitigation
from api.services.food_validation.boost_calculation import calculate_boosts
from api.services.food_response_builder import build_validation_response, build_error_response


class FoodValidationOrchestrator:
    """
    Orchestrates the food validation pipeline.
    
    Pipeline:
    1. Target Extraction (with optional Research Intelligence)
    2. Evidence Mining (with Research Intelligence paper merging)
    3. SPE Scoring (Sequence, Pathway, Evidence)
    4. Toxicity Mitigation Check (THE MOAT)
    5. Boost Calculation (cancer type, biomarker)
    6. Response Building
    """
    
    async def validate_compound(
        self,
        compound: str,
        disease_context: Dict[str, Any],
        treatment_history: Optional[Dict[str, Any]] = None,
        patient_medications: Optional["List[str]"] = None,
        use_evo2: bool = False,
        use_research_intelligence: bool = False,
        enable_llm_enhancement: bool = False
    ) -> Dict[str, Any]:
        """
        Validate a compound through the complete pipeline.
        
        Args:
            compound: Compound name
            disease_context: Disease context with disease, mutations, biomarkers, pathways
            treatment_history: Treatment history (optional)
            patient_medications: List of patient medications (optional)
            use_evo2: Whether to use Evo2 for sequence scoring
            use_research_intelligence: Whether to use Research Intelligence
            enable_llm_enhancement: Whether to enable LLM enhancement for toxicity
        
        Returns:
            Complete validation response
        """
        run_id = str(uuid.uuid4())
        disease = disease_context.get("disease", "ovarian_cancer_hgs")
        
        try:
            # [1] TARGET EXTRACTION
            extraction_result = await extract_targets(
                compound=compound,
                disease=disease,
                disease_context=disease_context,
                treatment_history=treatment_history,
                use_research_intelligence=use_research_intelligence
            )
            
            if extraction_result.get("error") and not extraction_result.get("targets"):
                return build_error_response(
                    compound=compound,
                    error=extraction_result.get("error", f"No information found for '{compound}'"),
                    run_id=run_id
                )
            
            targets = extraction_result.get("targets", [])
            pathways = extraction_result.get("pathways", [])
            mechanisms = extraction_result.get("mechanisms", [])
            research_intelligence_result = extraction_result.get("research_intelligence_result")
            
            # Determine if Research Intelligence should be used (if not already)
            if not use_research_intelligence:
                use_research_intelligence = (
                    len(targets) < 2 and len(pathways) < 2
                ) or any(word in compound.lower() for word in ["potato", "berry", "fruit", "vegetable", "food", "extract"])
            
            # [2] EVIDENCE MINING
            treatment_line_for_evidence = None
            if treatment_history and 'current_line' in treatment_history:
                treatment_line_for_evidence = treatment_history.get('current_line')
            
            evidence_result = await mine_evidence(
                compound=compound,
                disease=disease,
                pathways=pathways,
                treatment_line=treatment_line_for_evidence,
                research_intelligence_result=research_intelligence_result
            )
            
            evidence_grade = evidence_result.get("evidence_grade", "INSUFFICIENT")
            
            # [3] SPE SCORING
            spe_result = await compute_spe_score(
                compound=compound,
                targets=targets,
                pathways=pathways,
                disease_context=disease_context,
                evidence_grade=evidence_grade,
                treatment_history=treatment_history,
                evo2_enabled=use_evo2
            )
            
            sae_features_flat = spe_result.get("sae_features", {})
            base_overall_score = spe_result.get("overall_score", 0.5)
            
            # [4] BOOST CALCULATION
            boost_result = calculate_boosts(
                compound=compound,
                disease=disease,
                disease_context=disease_context,
                treatment_history=treatment_history
            )
            
            cancer_type_boost = boost_result["cancer_type_boost"]
            biomarker_boost = boost_result["biomarker_boost"]
            boost_reasons = boost_result["reasons"]
            
            # Apply boosts (additive, capped at 1.0)
            total_boost = cancer_type_boost + biomarker_boost
            boosted_score = min(1.0, base_overall_score + total_boost)
            boost_applied = boosted_score - base_overall_score
            
            # [5] DIETICIAN RECOMMENDATIONS
            from api.services.dietician_recommendations import get_dietician_service
            dietician_service = get_dietician_service()
            recommendations = dietician_service.generate_complete_recommendations(
                compound=compound,
                evidence=evidence_result,
                patient_medications=patient_medications or [],
                disease_context=disease_context
            )
            
            # [6] TOXICITY MITIGATION CHECK (THE MOAT)
            toxicity_mitigation = None
            if patient_medications:
                toxicity_mitigation = await check_toxicity_mitigation(
                    compound=compound,
                    patient_medications=patient_medications,
                    disease_context=disease_context,
                    enable_llm_enhancement=enable_llm_enhancement
                )
            
            # [7] BUILD RESPONSE
            response = build_validation_response(
                compound=compound,
                extraction_result=extraction_result,
                evidence_result=evidence_result,
                spe_result=spe_result,
                sae_features_flat=sae_features_flat,
                recommendations=recommendations,
                toxicity_mitigation=toxicity_mitigation,
                boosted_score=boosted_score,
                base_overall_score=base_overall_score,
                boost_applied=boost_applied,
                boost_reasons=boost_reasons,
                treatment_history=treatment_history,
                use_evo2=use_evo2,
                use_research_intelligence=use_research_intelligence,
                research_intelligence_result=research_intelligence_result,
                run_id=run_id
            )
            
            # Update boosts with actual values (response builder sets them to 0.0)
            if response.get("provenance", {}).get("boosts"):
                response["provenance"]["boosts"]["cancer_type_boost"] = round(cancer_type_boost, 3)
                response["provenance"]["boosts"]["biomarker_boost"] = round(biomarker_boost, 3)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in validation pipeline: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return build_error_response(compound=compound, error=str(e), run_id=run_id)


def get_food_validation_orchestrator() -> FoodValidationOrchestrator:
    """Get singleton instance of FoodValidationOrchestrator."""
    if not hasattr(get_food_validation_orchestrator, '_instance'):
        get_food_validation_orchestrator._instance = FoodValidationOrchestrator()
    return get_food_validation_orchestrator._instance

