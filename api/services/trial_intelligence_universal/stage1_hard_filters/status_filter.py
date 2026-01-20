"""
Status Filter: Keep RECRUITING trials only.

PASS: RECRUITING, NOT_YET_RECRUITING
FAIL: COMPLETED, WITHDRAWN, SUSPENDED, TERMINATED, etc.
"""

from typing import Tuple, Optional
from ..config import FilterConfig

def check(trial: dict, config: Optional[FilterConfig] = None) -> Tuple[bool, str]:
    """
    Check if trial is recruiting.
    
    Args:
        trial: Trial dictionary
        config: FilterConfig (optional, uses default if None)
    
    Returns:
        (passed, reason)
    """
    if config is None:
        from ..config import get_nyc_metro_config
        config = get_nyc_metro_config()
    
    status = trial.get('status', '').upper()
    
    if not status:
        return (False, "❌ No status information")
    
    if status in config.RECRUITING_STATUSES:
        return (True, f"✅ Status: {status}")
    
    return (False, f"❌ Status: {status} (not recruiting)")

