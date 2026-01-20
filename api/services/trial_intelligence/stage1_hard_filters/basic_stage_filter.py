"""
Basic Stage Filter: Stage III/IV eligibility check.

PASS: "Stage IV", "Stage III/IV", "advanced", "metastatic"
WARN: "Stage III only" (may accept Stage IV off-label)
FAIL: "Stage I/II only", "early stage only"
"""

from typing import Tuple, Dict, Any, Optional
from ..config import FilterConfig

def check(trial: dict, ayesha: Dict[str, Any], config: Optional[FilterConfig] = None) -> Tuple[bool, str]:
    """
    Check basic stage eligibility.
    
    Returns:
        (passed, reason)
    """
    if config is None:
        from ..config import get_nyc_metro_config
        config = get_nyc_metro_config()
    
    eligibility = trial.get('eligibility_text', '').lower()
    title = trial.get('title', '').lower()
    description = trial.get('description_text', '').lower()
    
    combined = f"{eligibility} {title} {description}"
    
    patient_stage = ayesha['disease']['stage']  # IVB
    
    # Hard exclusions
    if 'early stage only' in combined or 'stage i/ii only' in combined:
        return (False, f"❌ Early stage only (patient is {patient_stage})")
    
    # Check stage IV keywords from config
    for keyword in config.STAGE_IV_KEYWORDS:
        if keyword in combined:
            return (True, f"✅ {keyword.title()} eligible (patient: {patient_stage})")
    
    # Stage III (may or may not include IV)
    if 'stage iii' in combined or 'stage 3' in combined:
        # Check if IV is also mentioned
        if 'stage iv' in combined or 'iii-iv' in combined or 'iii/iv' in combined:
            return (True, f"✅ Stage III/IV eligible (patient: {patient_stage})")
        # Stage III only - PASS but flag (may accept Stage IV)
        return (True, f"⚠️ Stage III trial (patient {patient_stage} may be eligible)")
    
    # No stage restriction found - assume eligible
    return (True, "✅ No stage restriction (assume eligible)")

