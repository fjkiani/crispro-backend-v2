"""
Keyword-Based Trial Type Classifier

Fast pattern matching to classify trials as:
- INTERVENTIONAL: Treatment trials with drugs/therapy
- OBSERVATIONAL: Data collection, tissue studies, AI models
- UNKNOWN: Insufficient signals (requires LLM)

Performance: <1ms per trial, 70-90% accuracy
"""

from typing import Tuple

# Observational keywords (strong signals for non-treatment studies)
OBSERVATIONAL_KEYWORDS = [
    'observational', 'non-interventional', 'noninterventional',
    'registry', 'tissue procurement', 'tissue collection',
    'biobank', 'biorepository', 'correlative study',
    'biomarker study', 'imaging study', 'ai model',
    'artificial intelligence', 'machine learning',
    'retrospective', 'archived tissue', 'tumor samples',
    'specimen collection', 'data collection',
    'natural history', 'epidemiology', 'surveillance',
    'chart review', 'database study', 'cohort study',
    'tumor infiltrating t cells', 'hypoxia imaging',
    'pet/ct imaging', 'mri study', 'ct features'
]

# Interventional keywords (strong signals for treatment trials)
INTERVENTIONAL_KEYWORDS = [
    'randomized', 'placebo', 'double-blind', 'single-blind',
    'treatment', 'therapy', 'drug', 'medication',
    'intervention', 'experimental', 'investigational',
    'phase i', 'phase ii', 'phase iii', 'phase 1', 'phase 2', 'phase 3',
    'clinical trial', 'dosing', 'dose escalation',
    'safety and efficacy', 'response rate', 'survival',
    'maintenance therapy', 'combination therapy',
    'adverse events', 'toxicity', 'maximum tolerated dose',
    'pharmacokinetics', 'pharmacodynamics'
]

def classify(trial: dict) -> Tuple[str, float, str]:
    """
    Classify trial type using keyword matching.
    
    Args:
        trial: Trial dictionary
    
    Returns:
        (trial_type, confidence, reasoning)
        - trial_type: 'INTERVENTIONAL' | 'OBSERVATIONAL' | 'UNKNOWN'
        - confidence: 0.0 to 1.0
        - reasoning: Explanation of classification
    """
    title = trial.get('title', '').lower()
    description = trial.get('description_text', '').lower()
    eligibility = trial.get('eligibility_text', '').lower()
    
    combined_text = f"{title} {description} {eligibility}"
    
    # Count keyword matches
    obs_matches = [kw for kw in OBSERVATIONAL_KEYWORDS if kw in combined_text]
    int_matches = [kw for kw in INTERVENTIONAL_KEYWORDS if kw in combined_text]
    
    obs_count = len(obs_matches)
    int_count = len(int_matches)
    
    # Decision logic
    if obs_count > int_count and obs_count >= 2:
        # Strong observational signal
        return (
            'OBSERVATIONAL',
            min(0.95, 0.7 + (obs_count * 0.05)),  # Confidence increases with matches
            f"Observational keywords: {', '.join(obs_matches[:3])} (+{obs_count-3} more)" if obs_count > 3 
            else f"Observational keywords: {', '.join(obs_matches)}"
        )
    
    elif int_count > obs_count and int_count >= 2:
        # Strong interventional signal
        return (
            'INTERVENTIONAL',
            min(0.95, 0.7 + (int_count * 0.05)),
            f"Interventional keywords: {', '.join(int_matches[:3])} (+{int_count-3} more)" if int_count > 3
            else f"Interventional keywords: {', '.join(int_matches)}"
        )
    
    elif obs_count >= 1:
        # Weak observational signal
        return (
            'OBSERVATIONAL',
            0.6,
            f"Weak observational signal: {obs_matches[0]}"
        )
    
    elif int_count >= 1:
        # Weak interventional signal
        return (
            'INTERVENTIONAL',
            0.6,
            f"Weak interventional signal: {int_matches[0]}"
        )
    
    else:
        # Insufficient signals
        return (
            'UNKNOWN',
            0.5,
            "Insufficient keywords - requires LLM classification"
        )


