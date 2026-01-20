"""
Prognostic biomarkers for resistance prediction.

Purpose: "What is my expected outlook?"

Detectors:
- mm_high_risk.py - MM high-risk genes (DIS3, TP53) - predicts poor prognosis
  Primary: Prognostic
  Secondary: Predictive (predicts treatment response)
  
- pathway_post_treatment.py - Post-treatment pathway profiling - predicts PFI/outcome
  Primary: Prognostic
  Secondary: Predictive (predicts platinum resistance)
"""
