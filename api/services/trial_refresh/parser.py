"""
Trial Refresh Service - Parser Module

Parses ClinicalTrials.gov API v2 response to extract status and locations.
"""

from typing import Dict, Any, List
from datetime import datetime, timezone


def parse_trial_locations_and_status(study: Dict[str, Any]) -> Dict[str, Any]:
    """
    Parse a single study from API response to extract status and locations.
    
    Args:
        study: Raw study object from ClinicalTrials.gov API v2
        
    Returns:
        Dict with keys: status, locations (list), last_updated (ISO timestamp)
        Returns None if study is invalid (no NCT ID)
    """
    protocol_section = study.get("protocolSection", {})
    
    # Extract NCT ID
    identification = protocol_section.get("identificationModule", {})
    nct_id = identification.get("nctId")
    
    if not nct_id:
        return None
    
    # Extract overall status
    status_module = protocol_section.get("statusModule", {})
    overall_status = status_module.get("overallStatus", "UNKNOWN")
    
    # Extract locations with contacts
    contacts_locations = protocol_section.get("contactsLocationsModule", {})
    locations_list = contacts_locations.get("locations", [])
    
    locations = []
    for loc in locations_list:
        loc_status = loc.get("status", "")
        
        # Only include recruiting locations
        if loc_status.upper() in ["RECRUITING", "NOT_YET_RECRUITING"]:
            # Extract contact info (first contact if multiple exist)
            contact_list = loc.get("contacts", [])
            contact = contact_list[0] if contact_list else {}
            
            location_data = {
                "facility": loc.get("facility", ""),
                "city": loc.get("city", ""),
                "state": loc.get("state", ""),
                "zip": loc.get("zip", ""),
                "status": loc_status.lower(),
                "contact_name": contact.get("name", ""),
                "contact_phone": contact.get("phone", ""),
                "contact_email": contact.get("email", "")
            }
            
            locations.append(location_data)
    
    return {
        "status": overall_status,
        "locations": locations,
        "last_updated": datetime.now(timezone.utc).isoformat()
    }


def parse_batch_response(data: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """
    Parse batch API response into dict mapping NCT ID to trial data.
    
    Args:
        data: JSON response from ClinicalTrials.gov API
        
    Returns:
        Dict mapping NCT ID -> {status, locations, last_updated}
    """
    results = {}
    
    studies = data.get("studies", [])
    for study in studies:
        # Extract NCT ID first
        protocol_section = study.get("protocolSection", {})
        identification = protocol_section.get("identificationModule", {})
        nct_id = identification.get("nctId")
        
        if not nct_id:
            continue
        
        # Parse trial data
        parsed = parse_trial_locations_and_status(study)
        if parsed:
            results[nct_id] = parsed
    
    return results

