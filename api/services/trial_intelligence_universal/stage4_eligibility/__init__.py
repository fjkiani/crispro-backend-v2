"""
STAGE 4: Eligibility Scoring

Calculate probability that Ayesha is eligible for each trial.

Considers:
- Stage match (IVB)
- Treatment line (first-line)
- Biomarker gates (HER2, HRD, BRCA)

Returns composite probability (0.0 to 1.0)
"""

from . import probability_calculator

__all__ = ['probability_calculator']


