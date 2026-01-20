"""
NYC Metro Location Detector

Checks if trial has at least one NYC metro area location.

PASS: At least one site in allowed states/cities
FAIL: Only international sites, or no location data
"""

from typing import Tuple, List, Dict, Any, Optional
from ..config import FilterConfig

def check(trial: dict, config: Optional[FilterConfig] = None) -> Tuple[bool, List[Dict[str, Any]], str]:
    """
    Check if trial has locations in allowed states/cities.
    
    Returns:
        (has_location, matching_locations, reasoning)
    """
    if config is None:
        from ..config import get_nyc_metro_config
        config = get_nyc_metro_config()
    
    locations = trial.get('locations_data', [])
    
    if not locations:
        # Check if we should allow trials without location data
        if config.ALLOW_TRIALS_WITHOUT_LOCATION and not config.REQUIRE_LOCATION_DATA:
            # Allow trial to pass but flag it for manual review
            return (True, [], "⚠️ No location data available - requires manual verification")
        else:
            return (False, [], "No location data available")
    
    matching_locations = []
    
    for loc in locations:
        facility = loc.get('facility', '').lower()
        city = loc.get('city', '').lower()
        state = loc.get('state', '').upper()
        country = loc.get('country', '').lower()
        
        # Only check USA locations
        if country and 'united states' not in country and 'usa' not in country:
            continue
        
        # Check major cancer centers (exact match)
        if any(center.lower() in facility for center in config.MAJOR_CANCER_CENTERS):
            matching_locations.append(loc)
            continue
        
        # Check allowed cities
        if any(allowed_city.lower() in city for allowed_city in config.NYC_METRO_CITIES):
            matching_locations.append(loc)
            continue
        
        # Check allowed states
        if state in config.ALLOWED_STATES:
            # Additional check: if it's a major medical center, likely accessible
            if any(keyword in facility for keyword in ['hospital', 'medical center', 'cancer center', 'university']):
                matching_locations.append(loc)
                continue
    
    if matching_locations:
        # Format nice reasoning
        center_names = [loc.get('facility', 'Unknown')[:50] for loc in matching_locations[:3]]
        states_found = list(set([loc.get('state', 'Unknown') for loc in matching_locations]))
        if len(matching_locations) > 3:
            reasoning = f"Found {len(matching_locations)} locations in {', '.join(states_found)}: {', '.join(center_names)} (+{len(matching_locations)-3} more)"
        else:
            reasoning = f"Found {len(matching_locations)} location(s) in {', '.join(states_found)}: {', '.join(center_names)}"
        
        return (True, matching_locations, reasoning)
    
    else:
        # Show where the trial IS located (for debugging)
        non_matching_cities = list(set([loc.get('city', 'Unknown') for loc in locations[:5]]))
        non_matching_countries = list(set([loc.get('country', 'Unknown') for loc in locations[:5]]))
        non_matching_states = list(set([loc.get('state', 'Unknown') for loc in locations[:5]]))
        
        if any('italy' in c.lower() or 'italia' in c.lower() for c in non_matching_countries):
            return (False, [], f"❌ Trial in Italy 🇮🇹 (not in allowed states: {', '.join(config.ALLOWED_STATES)})")
        
        elif any('china' in c.lower() or 'japan' in c.lower() or 'korea' in c.lower() for c in non_matching_countries):
            return (False, [], f"❌ Trial in Asia (not in allowed states: {', '.join(config.ALLOWED_STATES)})")
        
        elif any('europe' in c.lower() or 'france' in c.lower() or 'germany' in c.lower() for c in non_matching_countries):
            return (False, [], f"❌ Trial in Europe (not in allowed states: {', '.join(config.ALLOWED_STATES)})")
        
        else:
            return (False, [], f"❌ No locations in allowed states {', '.join(config.ALLOWED_STATES)} (found: {', '.join(non_matching_states[:3])})")

