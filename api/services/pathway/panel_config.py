"""
Panel Configuration: Drug panel configuration management.
"""
from typing import Dict, Any, List


# Simple configurable panel (extensible via env or future DB)
DEFAULT_MM_PANEL: List[Dict[str, Any]] = [
    {"name": "BRAF inhibitor", "moa": "MAPK blockade", "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}},
    {"name": "MEK inhibitor", "moa": "MAPK downstream blockade", "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}},
    {"name": "IMiD", "moa": "immunomodulatory", "pathway_weights": {"ras_mapk": 0.2, "tp53": 0.3}},
    {"name": "Proteasome inhibitor", "moa": "proteostasis stress", "pathway_weights": {"ras_mapk": 0.3, "tp53": 0.4}},
    {"name": "Anti-CD38", "moa": "antibody", "pathway_weights": {"ras_mapk": 0.1, "tp53": 0.1}},
]


def get_default_panel() -> List[Dict[str, Any]]:
    """Get the default MM drug panel configuration."""
    return DEFAULT_MM_PANEL.copy()


