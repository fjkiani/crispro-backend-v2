"""
Trial Refresh Service - Filter Module

Utility functions for filtering trial data (e.g., by state).
"""

from typing import Dict, Any, List


def filter_locations_by_state(
    trial_data: Dict[str, Dict[str, Any]], 
    state: str
) -> Dict[str, Dict[str, Any]]:
    """
    Filter trial locations to only include specific state.
    
    Args:
        trial_data: Output from refresh_trial_status (NCT ID -> trial data)
        state: Two-letter state code (e.g., "NY")
        
    Returns:
        Filtered trial data with only matching state locations.
        Trials with no matching locations are excluded.
    """
    filtered = {}
    state_upper = state.upper()
    
    for nct_id, data in trial_data.items():
        locations = data.get("locations", [])
        
        # Filter locations to only matching state
        state_locations = [
            loc for loc in locations
            if loc.get("state", "").upper() == state_upper
        ]
        
        # Only include trial if it has at least one location in the state
        if state_locations:
            filtered[nct_id] = {
                **data,
                "locations": state_locations
            }
    
    return filtered


def filter_recruiting_trials(
    trial_data: Dict[str, Dict[str, Any]]
) -> Dict[str, Dict[str, Any]]:
    """
    Filter trials to only include those with RECRUITING or NOT_YET_RECRUITING status.
    
    Args:
        trial_data: Output from refresh_trial_status
        
    Returns:
        Filtered trial data with only recruiting trials
    """
    recruiting_statuses = ["RECRUITING", "NOT_YET_RECRUITING"]
    
    return {
        nct_id: data for nct_id, data in trial_data.items()
        if data.get("status", "").upper() in recruiting_statuses
    }

