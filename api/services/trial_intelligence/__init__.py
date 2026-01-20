"""
⚔️ TRIAL INTELLIGENCE PIPELINE ⚔️

Modular, sequence-based filtering pipeline for clinical trial matching.

Architecture:
    STAGE 1: Hard Filters (status, disease, basic stage)
    STAGE 2: Trial Type Classification (interventional vs observational)
    STAGE 3: Location Validation (NYC metro only)
    STAGE 4: Eligibility Scoring (probability calculation)
    STAGE 5: LLM Deep Analysis (trial fit reasoning)
    STAGE 6: Dossier Generation (markdown assembly)

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

from .pipeline import TrialIntelligencePipeline, FilterResult

__all__ = ['TrialIntelligencePipeline', 'FilterResult']


