"""
Holistic Score Utilities

Helper functions for vector operations and normalization.
"""

from typing import Dict, List


def dict_to_vector(moa_dict: Dict[str, float]) -> List[float]:
    """Convert MoA dict to 7D array in canonical order."""
    order = ["ddr", "mapk", "pi3k", "vegf", "her2", "io", "efflux"]
    return [moa_dict.get(k, moa_dict.get(k.upper(), 0.0)) for k in order]


def l2_normalize(vector: List[float]) -> List[float]:
    """L2 normalize a vector."""
    import math
    magnitude = math.sqrt(sum(x * x for x in vector))
    if magnitude == 0:
        return [0.0] * len(vector)
    return [x / magnitude for x in vector]
