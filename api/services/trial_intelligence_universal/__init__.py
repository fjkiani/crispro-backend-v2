"""
⚔️ TRIAL INTELLIGENCE PIPELINE - UNIVERSAL ⚔️

Modular, sequence-based filtering pipeline for clinical trial matching.
Universal version that accepts any patient profile (not just Ayesha).

Architecture:
    STAGE 1: Hard Filters (status, disease, basic stage)
    STAGE 2: Trial Type Classification (interventional vs observational)
    STAGE 3: Location Validation (patient-specific location)
    STAGE 4: Eligibility Scoring (probability calculation)
    STAGE 5: LLM Deep Analysis (trial fit reasoning)
    STAGE 6: Dossier Generation (markdown assembly)

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

from .pipeline import TrialIntelligencePipeline, FilterResult

__all__ = ['TrialIntelligencePipeline', 'FilterResult']


