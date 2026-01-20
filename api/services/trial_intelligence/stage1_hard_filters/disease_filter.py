"""
Disease Filter: Ovarian/Gynecologic cancer only.

PASS: Ovarian cancer, gynecologic cancer
FAIL: Other cancers (breast, lung, etc.)
"""

from typing import Tuple, Dict, Any, Optional
from ..config import FilterConfig

def check(trial: dict, ayesha: Dict[str, Any], config: Optional[FilterConfig] = None) -> Tuple[bool, str]:
    """
    Check if trial matches patient disease.
    
    Returns:
        (passed, reason)
    """
    if config is None:
        from ..config import get_nyc_metro_config
        config = get_nyc_metro_config()
    
    disease_category = trial.get('disease_category', '').lower()
    title = trial.get('title', '').lower()
    description = trial.get('description_text', '').lower()
    
    # Combine all text
    combined = f"{disease_category} {title} {description}"
    
    # Patient disease
    patient_disease = ayesha['disease']['primary_diagnosis'].lower()
    
    # Check for disease keywords from config
    for keyword in config.DISEASE_KEYWORDS:
        if keyword in combined:
            return (True, f"✅ {keyword.title()} cancer trial match")
    
    return (False, f"❌ Not ovarian/gynecologic cancer (category: {disease_category})")

