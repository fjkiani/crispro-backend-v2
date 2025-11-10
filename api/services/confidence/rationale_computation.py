"""
Rationale Computation: Rationale breakdown generation.
"""
from typing import Dict, Any, List


def compute_rationale_breakdown(seq_score: float, seq_pct: float, 
                               pathway_scores: Dict[str, float], path_pct: float,
                               evidence_strength: float) -> List[Dict[str, Any]]:
    """
    Compute rationale breakdown for transparency.
    
    Args:
        seq_score: Sequence score
        seq_pct: Sequence percentile
        pathway_scores: Pathway scores dictionary
        path_pct: Pathway percentile
        evidence_strength: Evidence strength
        
    Returns:
        List of rationale components
    """
    rationale = [
        {"type": "sequence", "value": seq_score, "percentile": seq_pct},
        {
            "type": "pathway",
            "percentile": path_pct,
            "breakdown": {
                "ras_mapk": round(pathway_scores.get("ras_mapk", 0.0), 3),
                "tp53": round(pathway_scores.get("tp53", 0.0), 3)
            }
        },
        {"type": "evidence", "strength": evidence_strength},
    ]
    
    return rationale


