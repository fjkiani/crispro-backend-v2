"""
PFS_STATUS Parser: Parse progression-free survival status from various formats.

Handles TCGA dataset formats:
- "0:CENSORED" or "0:DiseaseFree" → 0 (censored)
- "1:PROGRESSION" or "1:Recurred/Progressed" → 1 (event)
- Numeric 0/1
"""

from typing import Optional, Tuple


def parse_pfs_status(pfs_status: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse PFS_STATUS into (event, status).
    
    Args:
        pfs_status: PFS_STATUS string from TCGA dataset
        
    Returns:
        (event, status): 
        - event: 1 if progression, 0 if censored, None if unparseable
        - status: "progressed" or "censored" or None
    """
    if not pfs_status:
        return None, None
    
    pfs_status_str = str(pfs_status).upper()
    
    # Format: "0:CENSORED" or "0:DiseaseFree"
    if "0:" in pfs_status_str or "0:CENSORED" in pfs_status_str or "0:DISEASEFREE" in pfs_status_str:
        return 0, "censored"
    
    # Format: "1:PROGRESSION" or "1:Recurred/Progressed"
    if "1:" in pfs_status_str or "1:PROGRESSION" in pfs_status_str or "1:RECURRED" in pfs_status_str:
        return 1, "progressed"
    
    # Numeric format
    try:
        event = int(pfs_status_str.strip())
        if event == 0:
            return 0, "censored"
        elif event == 1:
            return 1, "progressed"
    except (ValueError, TypeError):
        pass
    
    return None, None


def parse_os_status(os_status: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Parse OS_STATUS into (event, status).
    
    Similar to PFS_STATUS but for overall survival.
    
    Args:
        os_status: OS_STATUS string from TCGA dataset
        
    Returns:
        (event, status): 
        - event: 1 if death, 0 if alive, None if unparseable
        - status: "deceased" or "alive" or None
    """
    if not os_status:
        return None, None
    
    os_status_str = str(os_status).upper()
    
    # Format: "0:ALIVE" or "0:LIVING"
    if "0:" in os_status_str or "0:ALIVE" in os_status_str or "0:LIVING" in os_status_str:
        return 0, "alive"
    
    # Format: "1:DECEASED" or "1:DEAD"
    if "1:" in os_status_str or "1:DECEASED" in os_status_str or "1:DEAD" in os_status_str:
        return 1, "deceased"
    
    # Numeric format
    try:
        event = int(os_status_str.strip())
        if event == 0:
            return 0, "alive"
        elif event == 1:
            return 1, "deceased"
    except (ValueError, TypeError):
        pass
    
    return None, None

