"""
STAGE 2: Trial Type Classification

Classify trials as INTERVENTIONAL (treatment) vs OBSERVATIONAL (data collection).

Two-tier approach:
1. keyword_classifier: Fast pattern matching (70-90% accuracy)
2. llm_classifier: LLM-based classification for uncertain cases (90-95% accuracy)
"""

from . import keyword_classifier, llm_classifier

__all__ = ['keyword_classifier', 'llm_classifier']


