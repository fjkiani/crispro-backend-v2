"""
Evidence Models: Data classes for evidence results.
"""
from typing import Dict, Any, List, Optional
from dataclasses import dataclass


@dataclass
class EvidenceHit:
    """Literature evidence result."""
    top_results: List[Dict[str, Any]]
    filtered: List[Dict[str, Any]]
    strength: float
    pubmed_query: Optional[str] = None
    moa_hits: int = 0
    provenance: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.provenance is None:
            self.provenance = {}


@dataclass
class ClinvarPrior:
    """ClinVar prior analysis result."""
    deep_analysis: Optional[Dict[str, Any]]
    prior: float
    provenance: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.provenance is None:
            self.provenance = {}


