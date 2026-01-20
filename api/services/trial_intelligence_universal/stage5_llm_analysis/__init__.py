"""
STAGE 5: LLM Deep Analysis

Use Gemini LLM for deep trial fit analysis.

Only called for top survivors (5-10 trials max) to save costs.
"""

from . import trial_fit_analyzer

__all__ = ['trial_fit_analyzer']


