"""
Holistic Score Models

Data classes and types for holistic score computation.
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Any

# Manager-Approved Score Weights
MECHANISM_FIT_WEIGHT = 0.5   # Tumor-drug pathway alignment
ELIGIBILITY_WEIGHT = 0.3     # Traditional criteria
PGX_SAFETY_WEIGHT = 0.2      # Dosing tolerability

# Thresholds
CONTRAINDICATION_THRESHOLD = 0.1  # PGx adjustment ≤ 0.1 = contraindicated


@dataclass
class HolisticScoreResult:
    """Unified Patient-Trial-Dose Feasibility Score"""
    
    # Final score
    holistic_score: float  # 0.0 - 1.0
    
    # Component scores
    mechanism_fit_score: float   # 0.0 - 1.0
    eligibility_score: float     # 0.0 - 1.0
    pgx_safety_score: float      # 0.0 - 1.0
    
    # Component weights (for transparency)
    weights: Dict[str, float]
    
    # Detailed breakdown
    mechanism_alignment: Dict[str, float]  # Per-pathway alignment
    eligibility_breakdown: List[str]       # Which criteria met/failed
    pgx_details: Dict[str, Any]            # Pharmacogene details
    
    # Interpretation
    interpretation: str           # "HIGH", "MEDIUM", "LOW", "CONTRAINDICATED"
    recommendation: str           # Human-readable recommendation
    caveats: List[str]            # Warnings/caveats
    
    # Provenance
    provenance: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
