"""
Trial Matching Service - Module 05

Provides mechanism-based trial matching using:
- AutonomousTrialAgent for query generation and search
- MechanismFitRanker for mechanism-based ranking
- TrialDataEnricher for MoA extraction and eligibility
"""

from .trial_matching_agent import TrialMatchingAgent, TrialMatch, TrialMatchingResult, TrialStatus, TrialPhase, TrialMoA, EligibilityCriteria

__all__ = [
    'TrialMatchingAgent',
    'TrialMatch',
    'TrialMatchingResult',
    'TrialStatus',
    'TrialPhase',
    'TrialMoA',
    'EligibilityCriteria'
]


