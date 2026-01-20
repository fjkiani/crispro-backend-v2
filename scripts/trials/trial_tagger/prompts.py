"""
Prompt Engineering for Trial Tagging
=====================================
Optimized prompts for batch trial tagging.
"""

from typing import List
from .db import Trial
from .config import MOA_PATHWAYS, MOA_DESCRIPTIONS


def build_batch_prompt(trials: List[Trial]) -> str:
    """
    Build a prompt to tag MULTIPLE trials at once.
    
    This is the KEY OPTIMIZATION - instead of 1 API call per trial,
    we tag 5-10 trials per API call.
    """
    # Build trial descriptions
    trial_blocks = []
    for i, trial in enumerate(trials, 1):
        block = f"""
TRIAL {i}:
- NCT ID: {trial.nct_id}
- Title: {trial.title}
- Interventions: {trial.interventions}
- Conditions: {trial.conditions}
- Summary: {trial.summary[:300]}
"""
        trial_blocks.append(block)
    
    # Build pathway descriptions
    pathway_desc = "\n".join([f"  - {k}: {v}" for k, v in MOA_DESCRIPTIONS.items()])
    
    prompt = f"""You are a biomedical expert classifying clinical trials by mechanism of action.

TASK: Classify the following {len(trials)} clinical trials into MoA vectors.

PATHWAYS (7D vector, each 0.0-1.0):
{pathway_desc}

TRIALS TO CLASSIFY:
{"".join(trial_blocks)}

RULES:
1. Only assign values > 0.0 if there is CLEAR evidence of that mechanism
2. If multiple mechanisms, assign proportional values (e.g., 0.6 ddr + 0.4 io)
3. If uncertain, use lower confidence (< 0.7)
4. If no clear oncology mechanism, return all zeros with confidence 0.0

Return a JSON array with one object per trial:
```json
[
  {{
    "nct_id": "NCT...",
    "moa_vector": {{"ddr": 0.0, "mapk": 0.0, "pi3k": 0.0, "vegf": 0.0, "her2": 0.0, "io": 0.0, "efflux": 0.0}},
    "confidence": 0.85,
    "primary_moa": "brief description"
  }},
  ...
]
```

Return ONLY the JSON array, no other text:"""

    return prompt


def build_single_prompt(trial: Trial) -> str:
    """Build prompt for a single trial (fallback)."""
    pathway_desc = "\n".join([f"  - {k}: {v}" for k, v in MOA_DESCRIPTIONS.items()])
    
    return f"""Classify this clinical trial by mechanism of action.

PATHWAYS (7D vector, each 0.0-1.0):
{pathway_desc}

TRIAL:
- NCT ID: {trial.nct_id}
- Title: {trial.title}
- Interventions: {trial.interventions}
- Conditions: {trial.conditions}
- Summary: {trial.summary[:400]}

Return JSON:
```json
{{
  "nct_id": "{trial.nct_id}",
  "moa_vector": {{"ddr": 0.0, "mapk": 0.0, "pi3k": 0.0, "vegf": 0.0, "her2": 0.0, "io": 0.0, "efflux": 0.0}},
  "confidence": 0.85,
  "primary_moa": "brief description"
}}
```

Return ONLY the JSON object:"""

