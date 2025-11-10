"""
Pathway Models: Data classes for pathway-related data.
"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class DrugPanel:
    """Drug panel configuration."""
    name: str
    moa: str
    pathway_weights: Dict[str, float]


