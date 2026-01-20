"""
Target Extraction Step

Extracts targets, pathways, and mechanisms for a compound.
Handles Research Intelligence integration for complex queries.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


async def extract_targets(
    compound: str,
    disease: str,
    disease_context: Dict[str, Any],
    treatment_history: Optional[Dict[str, Any]] = None,
    use_research_intelligence: bool = False
) -> Dict[str, Any]:
    """
    Extract targets, pathways, and mechanisms for a compound.
    
    Args:
        compound: Compound name
        disease: Disease ID
        disease_context: Disease context with mutations, biomarkers, etc.
        treatment_history: Treatment history (optional)
        use_research_intelligence: Whether to use Research Intelligence
    
    Returns:
        {
            "targets": [...],
            "pathways": [...],
            "mechanisms": [...],
            "source": "dynamic_extraction" | "research_intelligence" | "both",
            "research_intelligence_result": {...} (if used),
            "error": "..." (if extraction failed)
        }
    """
    from api.services.dynamic_food_extraction import get_dynamic_extractor
    
    # [1] Standard dynamic extraction
    extractor = get_dynamic_extractor()
    extraction_result = await extractor.extract_all(compound, disease)
    
    if extraction_result.get("error") and not extraction_result.get("targets"):
        return {
            "targets": [],
            "pathways": [],
            "mechanisms": [],
            "source": "dynamic_extraction",
            "error": extraction_result.get("error", f"No information found for '{compound}'")
        }
    
    targets = extraction_result.get("targets", [])
    pathways = extraction_result.get("pathways", [])
    mechanisms = extraction_result.get("mechanisms", [])
    
    # [2] Research Intelligence boost (if needed)
    research_intelligence_result = None
    if use_research_intelligence:
        try:
            from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
            
            logger.info(f"🔬 Using Research Intelligence for '{compound}'")
            orchestrator = ResearchIntelligenceOrchestrator()
            
            if orchestrator.is_available():
                # Build context
                ri_context = {
                    "disease": disease,
                    "treatment_line": treatment_history.get("current_line", "L1") if treatment_history else "L1",
                    "biomarkers": disease_context.get("biomarkers", {})
                }
                
                # Formulate research question
                research_question = f"How does {compound} help with {disease.replace('_', ' ')}?"
                
                # Run research intelligence
                research_intelligence_result = await orchestrator.research_question(
                    question=research_question,
                    context=ri_context
                )
                
                # Extract mechanisms and pathways from research intelligence
                synthesized = research_intelligence_result.get("synthesized_findings", {})
                ri_mechanisms = synthesized.get("mechanisms", [])
                
                # Add mechanisms from research intelligence
                mechanisms_added = 0
                targets_added = 0
                for mech in ri_mechanisms:
                    mech_name = mech.get("name", "").lower() if isinstance(mech, dict) else str(mech).lower()
                    if mech_name and mech_name not in [m.lower() for m in mechanisms]:
                        mechanisms.append(mech_name)
                        mechanisms_added += 1
                    
                    # Extract targets if available
                    target = mech.get("target", "") if isinstance(mech, dict) else ""
                    if target and target not in targets:
                        targets.append(target)
                        targets_added += 1
                
                # Extract pathways from MOAT analysis
                moat_analysis = research_intelligence_result.get("moat_analysis", {})
                ri_pathways = moat_analysis.get("pathways", [])
                pathways_added = 0
                for pathway in ri_pathways:
                    if pathway not in pathways:
                        pathways.append(pathway)
                        pathways_added += 1
                
                logger.info(f"✅ Research Intelligence found {len(ri_mechanisms)} mechanisms, {len(ri_pathways)} pathways")
                logger.info(f"   Added: {mechanisms_added} mechanisms, {targets_added} targets, {pathways_added} pathways")
                
        except Exception as e:
            logger.warning(f"⚠️ Research Intelligence failed: {e}, continuing with standard extraction")
            import traceback
            logger.debug(traceback.format_exc())
            research_intelligence_result = None
    
    # Determine source
    source = "both" if research_intelligence_result else "dynamic_extraction"
    
    return {
        "targets": targets,
        "pathways": pathways,
        "mechanisms": mechanisms,
        "source": source,
        "research_intelligence_result": research_intelligence_result,
        "mechanism_scores": extraction_result.get("mechanism_scores", {})
    }

