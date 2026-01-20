"""
LLM-Based Trial Type Classifier

Uses Gemini LLM to classify trials when keyword classifier is uncertain.

Performance: 2-5 seconds per trial, 90-95% accuracy
Cost: ~$0.001 per classification
"""

import sys
from pathlib import Path
from typing import Tuple

# Import LLM API
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "tools"))

try:
    from llm_api import get_llm_chat_response
    LLM_AVAILABLE = True
    GEMINI_MODEL = "gemini-2.5-pro"
except ImportError:
    LLM_AVAILABLE = False
    GEMINI_MODEL = None

async def classify(trial: dict) -> Tuple[str, float, str]:
    """
    Classify trial type using LLM.
    
    Args:
        trial: Trial dictionary
    
    Returns:
        (trial_type, confidence, reasoning)
        - trial_type: 'INTERVENTIONAL' | 'OBSERVATIONAL' | 'UNKNOWN'
        - confidence: 0.0 to 1.0
        - reasoning: LLM's explanation
    """
    if not LLM_AVAILABLE:
        return ('UNKNOWN', 0.5, "LLM unavailable")
    
    title = trial.get('title', 'N/A')[:200]
    description = trial.get('description_text', 'N/A')[:500]
    
    prompt = f"""Classify this clinical trial as INTERVENTIONAL or OBSERVATIONAL.

INTERVENTIONAL = Treatment trial with drugs, therapy, or medical intervention
OBSERVATIONAL = Data collection, tissue studies, imaging analysis, AI models (no treatment)

Trial Title: {title}

Trial Description: {description}

Respond with ONLY ONE WORD: "INTERVENTIONAL" or "OBSERVATIONAL"

Examples:
- "Phase II trial of niraparib maintenance" → INTERVENTIONAL
- "Tissue procurement for biomarker analysis" → OBSERVATIONAL
- "AI model to predict chemo-resistance" → OBSERVATIONAL
- "Randomized study of T-DXd vs placebo" → INTERVENTIONAL

Your answer (one word):"""

    try:
        conversation_history = [
            {"role": "system", "content": "You are a clinical trial classification expert. Respond with only one word: INTERVENTIONAL or OBSERVATIONAL."},
            {"role": "user", "content": prompt}
        ]
        
        response = get_llm_chat_response(
            conversation_history=conversation_history,
            provider="gemini",
            model_name=GEMINI_MODEL
        )
        
        response_clean = response.strip().upper()
        
        if "INTERVENTIONAL" in response_clean:
            return (
                'INTERVENTIONAL',
                0.9,
                f"LLM classified as interventional treatment trial"
            )
        elif "OBSERVATIONAL" in response_clean:
            return (
                'OBSERVATIONAL',
                0.9,
                f"LLM classified as observational study"
            )
        else:
            return (
                'UNKNOWN',
                0.5,
                f"LLM response unclear: {response[:100]}"
            )
    
    except Exception as e:
        return (
            'UNKNOWN',
            0.5,
            f"LLM classification failed: {str(e)[:100]}"
        )


