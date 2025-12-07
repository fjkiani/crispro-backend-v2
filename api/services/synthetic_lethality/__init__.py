"""
Synthetic Lethality & Essentiality Agent - Module 14

Identifies double-hit vulnerabilities and scores gene essentiality for precision drug targeting.

Owner: AI Agent (Synthetic Lethality Specialist)
Status: ⏳ PENDING → Implementation in progress
"""

from .sl_agent import SyntheticLethalityAgent
from .models import (
    SyntheticLethalityRequest,
    SyntheticLethalityResult,
    GeneEssentialityScore,
    PathwayAnalysis,
    DrugRecommendation,
    AIExplanation,
    EssentialityLevel,
    PathwayStatus,
    MutationInput,
    SLOptions
)

__all__ = [
    'SyntheticLethalityAgent',
    'SyntheticLethalityRequest',
    'SyntheticLethalityResult',
    'GeneEssentialityScore',
    'PathwayAnalysis',
    'DrugRecommendation',
    'AIExplanation',
    'EssentialityLevel',
    'PathwayStatus',
    'MutationInput',
    'SLOptions'
]

