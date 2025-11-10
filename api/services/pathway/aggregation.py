"""
Pathway Aggregation: Sequence score aggregation by pathway.
"""
from typing import Dict, Any, List


def aggregate_pathways(seq_scores: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Aggregate sequence scores by pathway.
    
    Args:
        seq_scores: List of sequence scores with pathway information
        
    Returns:
        Dict mapping pathway names to aggregated scores
    """
    pathway_totals = {}
    pathway_counts = {}
    
    for score in seq_scores:
        if not isinstance(score, dict):
            continue
            
        # Extract pathway information from the score
        pathway_weights = score.get("pathway_weights", {})
        sequence_disruption = float(score.get("sequence_disruption", 0.0))
        
        # Aggregate by pathway
        for pathway, weight in pathway_weights.items():
            if pathway not in pathway_totals:
                pathway_totals[pathway] = 0.0
                pathway_counts[pathway] = 0
            
            pathway_totals[pathway] += sequence_disruption * weight
            pathway_counts[pathway] += 1
    
    # Compute average scores
    pathway_scores = {}
    for pathway in pathway_totals:
        if pathway_counts[pathway] > 0:
            pathway_scores[pathway] = pathway_totals[pathway] / pathway_counts[pathway]
        else:
            pathway_scores[pathway] = 0.0
    
    return pathway_scores


