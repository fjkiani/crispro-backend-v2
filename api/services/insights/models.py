"""
Insights Models: Data classes for insights results.
"""
from typing import Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class InsightsBundle:
    """Bundled insights results."""
    functionality: Optional[float] = None
    chromatin: Optional[float] = None
    essentiality: Optional[float] = None
    regulatory: Optional[float] = None
    provenance: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.provenance is None:
            self.provenance = {}


