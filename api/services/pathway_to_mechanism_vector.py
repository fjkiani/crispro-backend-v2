"""
Pathway Score to Mechanism Vector Conversion Service

Converts pathway disruption scores to 6D or 7D mechanism vectors for mechanism fit ranking.
Supports both Manager C7 (6D) and current plan (7D) formats.

The 6D mechanism vector (Manager C7): [DDR, MAPK, PI3K, VEGF, IO, Efflux]
The 7D mechanism vector (current plan): [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]

Used in MBD4+TP53 analysis Phase 4 (Clinical Trial Matching) for mechanism fit ranking.
"""

import logging
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger(__name__)

# Pathway name normalization mapping
PATHWAY_NORMALIZATION = {
    'dna repair': 'ddr',
    'dna_repair': 'ddr',
    'ddr': 'ddr',
    'ras/mapk': 'ras_mapk',
    'ras_mapk': 'ras_mapk',
    'mapk': 'ras_mapk',
    'pi3k': 'pi3k',
    'pi3k/akt': 'pi3k',
    'vegf': 'vegf',
    'angiogenesis': 'vegf',
    'her2': 'her2',
    'her2/neu': 'her2',
    'io': 'io',
    'immunotherapy': 'io',
    'efflux': 'efflux',
    'drug efflux': 'efflux',
    'tp53': 'tp53',  # TP53 stays as tp53 (50% contribution to DDR handled separately)
}

# 6D mechanism vector indices (Manager C7)
MECHANISM_INDICES_6D = {
    'ddr': 0,
    'ras_mapk': 1,
    'pi3k': 2,
    'vegf': 3,
    'io': 4,
    'efflux': 5
}

# 7D mechanism vector indices (current plan)
MECHANISM_INDICES_7D = {
    'ddr': 0,
    'ras_mapk': 1,
    'pi3k': 2,
    'vegf': 3,
    'her2': 4,
    'io': 5,
    'efflux': 6
}


def normalize_pathway_name(pathway: str) -> str:
    """
    Normalize pathway name to standard format.
    
    Handles variations like "DNA Repair" → "ddr", "RAS/MAPK" → "ras_mapk"
    
    Args:
        pathway: Pathway name (any format)
        
    Returns:
        Normalized pathway name (lowercase with underscores)
    """
    if not pathway:
        return ''
    
    pathway_lower = pathway.lower().strip()
    
    # Check direct mapping
    if pathway_lower in PATHWAY_NORMALIZATION:
        return PATHWAY_NORMALIZATION[pathway_lower]
    
    # Check partial matches
    for key, normalized in PATHWAY_NORMALIZATION.items():
        if key in pathway_lower or pathway_lower in key:
            return normalized
    
    # Default: convert to lowercase with underscores
    return pathway_lower.replace(' ', '_').replace('/', '_').replace('-', '_')


def validate_mechanism_vector(
    mechanism_vector: List[float],
    expected_dimension: Optional[int] = None
) -> Tuple[bool, Optional[str]]:
    """
    Validate mechanism vector.
    
    Args:
        mechanism_vector: Mechanism vector to validate
        expected_dimension: Expected dimension (6 or 7), None for auto-detect
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    if not mechanism_vector:
        return False, "Mechanism vector is empty"
    
    dimension = len(mechanism_vector)
    
    # Check dimension
    if dimension not in [6, 7]:
        return False, f"Invalid dimension: {dimension} (expected 6 or 7)"
    
    if expected_dimension and dimension != expected_dimension:
        return False, f"Dimension mismatch: {dimension} != {expected_dimension}"
    
    # Check range (0.0 to 1.0)
    for i, val in enumerate(mechanism_vector):
        if val < 0.0 or val > 1.0:
            return False, f"Value out of range at index {i}: {val} (expected 0.0-1.0)"
    
    # Check if all zeros (warning, not error)
    if all(v == 0.0 for v in mechanism_vector):
        logger.warning("Mechanism vector is all zeros - mechanism fit will be disabled")
    
    return True, None


def convert_moa_dict_to_vector(
    moa_dict: Dict[str, float],
    use_7d: bool = False
) -> List[float]:
    """
    Convert MoA dictionary to mechanism vector list.
    
    Args:
        moa_dict: Dict mapping pathway names to scores (e.g., {"ddr": 0.9, "mapk": 0.0})
        use_7d: Whether to use 7D vector
        
    Returns:
        Mechanism vector as list
    """
    mechanism_map = MECHANISM_INDICES_7D if use_7d else MECHANISM_INDICES_6D
    vector_size = 7 if use_7d else 6
    
    mechanism_vector = [0.0] * vector_size
    
    for pathway, score in moa_dict.items():
        normalized = normalize_pathway_name(pathway)
        idx = mechanism_map.get(normalized)
        if idx is not None:
            # Handle string values like "No", "None", etc. gracefully
            try:
                if isinstance(score, str):
                    score_lower = score.lower().strip()
                    if score_lower in ['no', 'none', 'null', 'n/a', 'na', '']:
                        mechanism_vector[idx] = 0.0
                    else:
                        mechanism_vector[idx] = float(score)
                else:
                    mechanism_vector[idx] = float(score) if score is not None else 0.0
            except (ValueError, TypeError):
                # If conversion fails, default to 0.0
                logger.warning(f"Could not convert score '{score}' for pathway '{pathway}' to float, using 0.0")
                mechanism_vector[idx] = 0.0
    
    return mechanism_vector


def convert_vector_to_moa_dict(
    mechanism_vector: List[float],
    use_7d: bool = False
) -> Dict[str, float]:
    """
    Convert mechanism vector list to MoA dictionary.
    
    Args:
        mechanism_vector: Mechanism vector as list
        use_7d: Whether vector is 7D
        
    Returns:
        Dict mapping pathway names to scores
    """
    mechanism_map = MECHANISM_INDICES_7D if use_7d else MECHANISM_INDICES_6D
    
    # Reverse the mapping
    index_to_pathway = {v: k for k, v in mechanism_map.items()}
    
    moa_dict = {}
    for idx, score in enumerate(mechanism_vector):
        pathway = index_to_pathway.get(idx)
        if pathway:
            moa_dict[pathway] = float(score)
    
    return moa_dict


def convert_pathway_scores_to_mechanism_vector(
    pathway_scores: Dict[str, float],
    tumor_context: Optional[Dict[str, Any]] = None,
    tmb: Optional[float] = None,
    msi_status: Optional[str] = None,
    use_7d: bool = False
) -> Tuple[List[float], str]:
    """
    Convert pathway scores to mechanism vector.
    
    Supports both 6D (Manager C7) and 7D (current plan) formats.
    Auto-detects dimension based on HER2 presence.
    
    Args:
        pathway_scores: Dict mapping pathway names to disruption scores
        tumor_context: Optional tumor context with TMB, MSI status (alternative to tmb/msi_status params)
        tmb: Tumor mutational burden (optional, for IO index calculation) - deprecated, use tumor_context
        msi_status: MSI status (optional) - deprecated, use tumor_context
        use_7d: Whether to use 7D vector (includes HER2) or 6D (Manager C7)
        
    Returns:
        Tuple of (mechanism_vector, dimension_used)
    """
    # Normalize pathway scores
    normalized_scores = {}
    for pathway, score in pathway_scores.items():
        normalized = normalize_pathway_name(pathway)
        if normalized:
            normalized_scores[normalized] = float(score)
    
    # Detect dimension (prefer 7D if HER2 present, else use parameter)
    if 'her2' in normalized_scores or any('her2' in k for k in normalized_scores.keys()):
        use_7d = True
    
    mechanism_map = MECHANISM_INDICES_7D if use_7d else MECHANISM_INDICES_6D
    vector_size = 7 if use_7d else 6
    dimension_used = "7D" if use_7d else "6D"
    
    # Build mechanism vector
    mechanism_vector = [0.0] * vector_size
    
    # Handle TP53 → DDR mapping with 50% contribution (MBD4.mdc Question 7)
    ddr_idx = mechanism_map.get('ddr', 0)
    tp53_score = normalized_scores.get('tp53', 0.0)
    ddr_score = normalized_scores.get('ddr', 0.0)
    
    # Combine DDR + 50% of TP53 (TP53 is part of DNA damage response but not full DDR)
    mechanism_vector[ddr_idx] = ddr_score + (tp53_score * 0.5)
    
    # Map other pathways (skip tp53 and ddr since we already handled them)
    for pathway, score in normalized_scores.items():
        if pathway in ('tp53', 'ddr'):  # Skip TP53 and DDR, already handled above
            continue
        idx = mechanism_map.get(pathway)
        if idx is not None:
            # Accumulate if pathway already has a value (e.g., multiple pathways map to same index)
            mechanism_vector[idx] = max(mechanism_vector[idx], float(score))
    
    # Calculate IO score from tumor context or parameters
    io_idx = 4 if use_7d else 4  # IO is always index 4 in both
    if tumor_context:
        tmb = tumor_context.get('tmb', 0)
        msi_status = tumor_context.get('msi_status', '')
    
    if tmb and tmb >= 20:
        mechanism_vector[io_idx] = 1.0
    elif msi_status and msi_status.upper() in ['MSI-H', 'MSI-HIGH', 'MSI-H']:
        mechanism_vector[io_idx] = 1.0
    else:
        mechanism_vector[io_idx] = 0.0
    
    return mechanism_vector, dimension_used


def extract_pathway_disruption_from_response(response: Dict) -> Optional[Dict[str, float]]:
    """
    Extract pathway_disruption dict from WIWFM response.
    
    Looks for pathway_disruption in:
    - response.provenance["confidence_breakdown"]["pathway_disruption"]
    
    Args:
        response: WIWFM response dict from /api/efficacy/predict
    
    Returns:
        Pathway disruption dict (e.g., {"ddr": 0.8, "tp53": 0.6}) or None if not found
    """
    try:
        confidence_breakdown = response.get("provenance", {}).get("confidence_breakdown", {})
        pathway_disruption = confidence_breakdown.get("pathway_disruption")
        
        if pathway_disruption and isinstance(pathway_disruption, dict):
            return pathway_disruption
        return None
    except (KeyError, AttributeError, TypeError):
        return None


def get_mechanism_vector_from_response(
    response: Dict,
    tumor_context: Optional[Dict[str, Any]] = None,
    tmb: Optional[float] = None,
    msi_status: Optional[str] = None,
    use_7d: bool = False
) -> Optional[Tuple[List[float], str]]:
    """
    Extract pathway_disruption from WIWFM response and convert to mechanism vector.
    
    Convenience function that combines extraction and conversion.
    
    Args:
        response: WIWFM response dict from /api/efficacy/predict
        tumor_context: Optional tumor context with TMB, MSI status (alternative to tmb/msi_status params)
        tmb: Tumor mutational burden (optional, for IO index calculation) - deprecated, use tumor_context
        msi_status: MSI status (optional) - deprecated, use tumor_context
        use_7d: Whether to use 7D vector (includes HER2) or 6D (Manager C7)
    
    Returns:
        Tuple of (mechanism_vector, dimension_used) or None if pathway_disruption not found
    """
    pathway_scores = extract_pathway_disruption_from_response(response)
    
    if pathway_scores is None:
        return None
    
    return convert_pathway_scores_to_mechanism_vector(
        pathway_scores, 
        tumor_context=tumor_context,
        tmb=tmb, 
        msi_status=msi_status,
        use_7d=use_7d
    )
