"""
Food Validation Response Builder

Builds and transforms validation responses for frontend consumption.
Extracted from hypothesis_validator.py for modularity.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


def build_sae_structure(sae_features_flat: Dict[str, Any], treatment_history: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Transform flat SAE features to nested structure for frontend.
    
    Frontend expects: {line_fitness: {score, status, reason}, cross_resistance: {risk, score, reason}, sequencing_fitness: {score, optimal, reason}}
    
    Args:
        sae_features_flat: Flat SAE features from service
        treatment_history: Treatment history context
    
    Returns:
        Nested SAE structure
    """
    if not sae_features_flat:
        # Default structured SAE if no features provided
        return {
            "line_fitness": {
                "score": 0.6,
                "status": "moderate",
                "reason": "No treatment line context provided"
            },
            "cross_resistance": {
                "risk": "LOW",
                "score": 0.0,
                "reason": "No prior therapies to assess cross-resistance"
            },
            "sequencing_fitness": {
                "score": 0.6,
                "optimal": False,
                "reason": "No treatment history provided"
            }
        }
    
    line_appropriateness = sae_features_flat.get("line_appropriateness", 0.6)
    cross_resistance = sae_features_flat.get("cross_resistance", 0.0)
    sequencing_fitness = sae_features_flat.get("sequencing_fitness", 0.6)
    
    # Categorize line appropriateness
    if line_appropriateness >= 0.8:
        line_status = "appropriate"
        line_reason = f"Appropriate for treatment line {treatment_history.get('current_line', 'current') if treatment_history else 'current'}"
    elif line_appropriateness >= 0.6:
        line_status = "moderate"
        line_reason = f"Moderately appropriate for treatment line {treatment_history.get('current_line', 'current') if treatment_history else 'current'}"
    else:
        line_status = "inappropriate"
        line_reason = f"Limited appropriateness for treatment line {treatment_history.get('current_line', 'current') if treatment_history else 'current'}"
    
    # Categorize cross-resistance risk
    if cross_resistance <= 0.3:
        cross_risk = "LOW"
        cross_reason = "No significant overlap detected with prior therapies"
    elif cross_resistance <= 0.6:
        cross_risk = "MEDIUM"
        cross_reason = "Some potential overlap with prior therapies"
    else:
        cross_risk = "HIGH"
        cross_reason = "Significant overlap with prior therapies - caution advised"
    
    # Determine sequencing fitness
    sequencing_optimal = sequencing_fitness >= 0.7
    if sequencing_optimal:
        seq_reason = "Good timing and sequencing fit for current treatment line"
    else:
        seq_reason = "Suboptimal sequencing - consider alternative timing"
    
    return {
        "line_fitness": {
            "score": round(line_appropriateness, 3),
            "status": line_status,
            "reason": line_reason
        },
        "cross_resistance": {
            "risk": cross_risk,
            "score": round(cross_resistance, 3),
            "reason": cross_reason
        },
        "sequencing_fitness": {
            "score": round(sequencing_fitness, 3),
            "optimal": sequencing_optimal,
            "reason": seq_reason
        }
    }


def build_validation_response(
    compound: str,
    extraction_result: Dict[str, Any],
    evidence_result: Dict[str, Any],
    spe_result: Dict[str, Any],
    sae_features_flat: Dict[str, Any],
    recommendations: Dict[str, Any],
    toxicity_mitigation: Optional[Dict[str, Any]],
    boosted_score: float,
    base_overall_score: float,
    boost_applied: float,
    boost_reasons: list,
    treatment_history: Optional[Dict[str, Any]],
    use_evo2: bool,
    use_research_intelligence: bool,
    research_intelligence_result: Optional[Dict[str, Any]] = None,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build complete validation response with all components.
    
    Args:
        compound: Compound name
        extraction_result: Target/pathway extraction results
        evidence_result: Evidence mining results
        spe_result: SPE scoring results
        sae_features_flat: Flat SAE features
        recommendations: Dietician recommendations
        toxicity_mitigation: Toxicity mitigation info (if applicable)
        boosted_score: Final score after boosts
        base_overall_score: Base score before boosts
        boost_applied: Amount of boost applied
        boost_reasons: List of boost reasons
        treatment_history: Treatment history context
        use_evo2: Whether Evo2 was used
        use_research_intelligence: Whether Research Intelligence was used
        research_intelligence_result: Research Intelligence results (if used)
        run_id: Run ID for provenance
    
    Returns:
        Complete validation response dictionary
    """
    import uuid
    
    if run_id is None:
        run_id = str(uuid.uuid4())
    
    # Transform SAE features to nested structure
    structured_sae = build_sae_structure(sae_features_flat, treatment_history)
    
    # Extract evidence grade
    evidence_grade = evidence_result.get("evidence_grade", "INSUFFICIENT")
    
    # Extract targets, pathways, mechanisms
    targets = extraction_result.get("targets", [])
    pathways = extraction_result.get("pathways", [])
    mechanisms = extraction_result.get("mechanisms", [])
    
    # Build provenance
    provenance = {
        "run_id": run_id,
        "method": "dynamic_food_validation_v2",
        "profile": {
            "use_evo2": use_evo2,
            "research_intelligence_used": use_research_intelligence
        },
        "sources": [
            extraction_result.get("source", "unknown"),
            "enhanced_evidence_service",
            "dietician_recommendations"
        ] + (["research_intelligence"] if use_research_intelligence else []),
        "timestamp": datetime.utcnow().isoformat(),
        # Merge SPE provenance
        **spe_result.get("provenance", {}),
        # Boost tracking
                "boosts": {
                    "base_score": round(base_overall_score, 3),
                    "cancer_type_boost": 0.0,  # Will be set by caller
                    "biomarker_boost": 0.0,  # Will be set by caller
                    "total_boost": round(boost_applied, 3),
                    "final_score": round(boosted_score, 3),
                    "boost_reasons": boost_reasons
                } if boost_applied > 0 else None,
        # Research Intelligence metadata
        "research_intelligence": {
            "used": use_research_intelligence,
            "mechanisms_found": len([m for m in mechanisms if m not in extraction_result.get("mechanisms", [])]) if use_research_intelligence else 0,
            "pathways_found": len([p for p in pathways if p not in extraction_result.get("pathways", [])]) if use_research_intelligence else 0,
            "overall_confidence": research_intelligence_result.get("synthesized_findings", {}).get("overall_confidence") if research_intelligence_result else None
        } if use_research_intelligence else None
    }
    
    # Build complete response
    response = {
        "status": "SUCCESS",
        "compound": compound,
        "alignment_score": round(boosted_score, 3),
        "overall_score": round(boosted_score, 3),
        "confidence": spe_result.get("confidence", 0.5),
        "verdict": spe_result.get("verdict", "NOT_SUPPORTED"),
        # Calibrated scoring fields
        "spe_percentile": spe_result.get("spe_percentile"),
        "interpretation": spe_result.get("interpretation"),
        # Existing fields
        "spe_breakdown": spe_result.get("spe_breakdown", {}),
        "sae_features": structured_sae,  # Nested structure for frontend
        "targets": targets,
        "pathways": pathways,
        "mechanisms": mechanisms,
        "mechanism_scores": extraction_result.get("mechanism_scores", {}),
        "evidence": {
            "papers": evidence_result.get("papers", [])[:5],  # Top 5 for display
            "evidence_grade": evidence_grade,
            "total_papers": evidence_result.get("total_papers", 0),
            "rct_count": evidence_result.get("rct_count", 0),
            "mechanisms": evidence_result.get("mechanisms", []),
            "query_used": evidence_result.get("query_used", "")
        },
        "dietician_recommendations": recommendations,
        "toxicity_mitigation": toxicity_mitigation,  # THE MOAT
        "extraction_source": extraction_result.get("source", "unknown"),
        "provenance": provenance
    }
    
    return response


def build_error_response(
    compound: str,
    error: str,
    run_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Build error response.
    
    Args:
        compound: Compound name
        error: Error message
        run_id: Run ID for provenance
    
    Returns:
        Error response dictionary
    """
    import uuid
    
    if run_id is None:
        run_id = str(uuid.uuid4())
    
    return {
        "status": "ERROR",
        "error": error,
        "compound": compound,
        "provenance": {
            "run_id": run_id,
            "timestamp": datetime.utcnow().isoformat()
        }
    }

