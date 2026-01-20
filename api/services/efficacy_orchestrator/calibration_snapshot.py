"""
Calibration Snapshot: Generate S/P calibration provenance for confidence lifting.
"""
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


def compute_calibration_snapshot(
    seq_scores: List[Dict[str, Any]],
    pathway_scores: Dict[str, float],
    include_calibration_snapshot: bool = False
) -> Optional[Dict[str, Any]]:
    """
    Compute calibration snapshot for S/P signals.
    
    Args:
        seq_scores: Sequence scoring results
        pathway_scores: Pathway scoring results
        include_calibration_snapshot: Whether to include calibration data
        
    Returns:
        Calibration snapshot dict or None if disabled
    """
    if not include_calibration_snapshot:
        return None
        
    try:
        snapshot = {
            "sequence_calibration": {},
            "pathway_calibration": {},
            "percentile_mappings": {},
            "provenance": {
                "method": "calibration_snapshot_v1",
                "status": "computed"
            }
        }
        
        # Process sequence scores
        for i, seq_score in enumerate(seq_scores):
            # Our seq_score dict comes from DrugScorer.seq_score_to_dict
            # keys: sequence_disruption (float), pathway_weights (dict)
            raw_delta = float(seq_score.get("sequence_disruption", 0.0) or 0.0)
            percentile = min(1.0, max(0.0, abs(raw_delta) * 10000.0))
            calibrated = percentile
            conf = min(1.0, 0.5 + 0.4 * percentile)
            gene_key = f"gene_{i}"
            snapshot["sequence_calibration"][gene_key] = {
                "raw_delta": raw_delta,
                "percentile": percentile,
                "calibrated_score": calibrated,
                "confidence": conf
            }
        
        # Process pathway scores
        for pathway, score in pathway_scores.items():
            snapshot["pathway_calibration"][pathway] = {
                "raw_score": score,
                "percentile": min(1.0, max(0.0, score)),  # Simple percentile mapping
                "weight": 1.0  # Placeholder for actual weights
            }
        
        # Add percentile mappings
        snapshot["percentile_mappings"] = {
            "sequence_percentile_thresholds": {
                "high": 0.8,
                "medium": 0.5,
                "low": 0.2
            },
            "pathway_percentile_thresholds": {
                "high": 0.8,
                "medium": 0.5,
                "low": 0.2
            }
        }
        
        logger.info(f"Generated calibration snapshot for {len(seq_scores)} sequence scores and {len(pathway_scores)} pathway scores")
        return snapshot
        
    except Exception as e:
        logger.warning(f"Failed to compute calibration snapshot: {e}")
        return None


def get_percentile_lift(
    calibration_snapshot: Optional[Dict[str, Any]] = None,
    base_confidence: float = 0.5
) -> float:
    """
    Compute confidence lift based on calibration percentiles.
    
    Args:
        calibration_snapshot: Optional calibration data
        base_confidence: Base confidence to lift from
        
    Returns:
        Lifted confidence value
    """
    if not calibration_snapshot:
        return base_confidence
    
    try:
        # Extract sequence percentiles
        seq_cal = calibration_snapshot.get("sequence_calibration", {})
        path_cal = calibration_snapshot.get("pathway_calibration", {})
        
        # Average sequence percentiles
        seq_percentiles = [v.get("percentile", 0.0) for v in seq_cal.values()]
        avg_seq_pct = sum(seq_percentiles) / len(seq_percentiles) if seq_percentiles else 0.0
        
        # Average pathway percentiles
        path_percentiles = [v.get("percentile", 0.0) for v in path_cal.values()]
        avg_path_pct = sum(path_percentiles) / len(path_percentiles) if path_percentiles else 0.0
        
        # Compute lift (modest, capped at +0.1)
        lift = min(0.1, (avg_seq_pct + avg_path_pct) / 2 * 0.15)
        
        return min(1.0, base_confidence + lift)
        
    except Exception as e:
        logger.warning(f"Failed to compute percentile lift: {e}")
        return base_confidence
