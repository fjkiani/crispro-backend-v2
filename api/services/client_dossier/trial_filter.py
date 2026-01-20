"""
Trial Filter - Multi-tier filtering logic for JR2.

Replicates Zo's "1 in 700" filtering strategy to identify top-tier trials.
"""
from typing import List, Dict, Any, Tuple
import logging

logger = logging.getLogger(__name__)

def assess_disease_match(trial: Dict[str, Any], patient_disease: str) -> Tuple[bool, float, str]:
    """
    Assess disease match between trial and patient.
    
    Returns:
        (matches, confidence, reasoning)
    """
    # Try multiple field names (trials table may have different schema)
    trial_disease = (trial.get('disease_subcategory', '') or trial.get('conditions', '') or '').lower()
    patient_disease_lower = patient_disease.lower()
    
    # Exact match
    if trial_disease == patient_disease_lower:
        return True, 1.0, f"Exact match: {trial_disease}"
    
    # Ovarian cancer variants
    if 'ovarian' in patient_disease_lower:
        if 'ovarian' in trial_disease or 'gynecologic' in trial_disease:
            return True, 0.9, f"Ovarian/gynecologic match: {trial_disease}"
    
    # Partial match
    if patient_disease_lower in trial_disease or trial_disease in patient_disease_lower:
        return True, 0.7, f"Partial match: {trial_disease}"
    
    return False, 0.0, f"No match: {trial_disease} vs {patient_disease_lower}"

def assess_treatment_line_match(trial: Dict[str, Any], patient_line: str) -> Tuple[bool, float, str]:
    """
    Assess treatment line match.
    
    Returns:
        (matches, confidence, reasoning)
    """
    # Extract from eligibility text or description
    eligibility = (trial.get('eligibility_text', '') + ' ' + trial.get('description_text', '')).lower()
    
    # First-line indicators
    if patient_line == "first-line" or patient_line == "L1":
        if any(term in eligibility for term in ['first-line', 'frontline', 'previously untreated', 'treatment-naive']):
            return True, 1.0, "First-line trial"
        if 'second-line' in eligibility or 'previously treated' in eligibility:
            return False, 0.0, "Not first-line (requires prior treatment)"
    
    # Second-line indicators
    if patient_line == "second-line" or patient_line == "L2":
        if any(term in eligibility for term in ['second-line', 'previously treated', 'relapsed', 'refractory']):
            return True, 1.0, "Second-line trial"
    
    # Default: assume matches if not explicitly excluded
    return True, 0.8, "Line match assumed (not explicitly excluded)"

def assess_biomarker_match(trial: Dict[str, Any], patient_biomarkers: Dict[str, Any]) -> Tuple[bool, float, List[str], str]:
    """
    Assess biomarker match and identify pending gates.
    
    Returns:
        (matches, confidence, pending_gates, reasoning)
    """
    pending_gates = []
    eligibility = (trial.get('eligibility_text', '') + ' ' + trial.get('description_text', '')).lower()
    biomarker_text = trial.get('biomarker_requirements', '')
    if isinstance(biomarker_text, str):
        eligibility += ' ' + biomarker_text.lower()
    
    # Check HRD
    if 'hrd' in eligibility or 'homologous recombination' in eligibility:
        if patient_biomarkers.get('hrd') == "UNKNOWN":
            pending_gates.append("HRD test required")
        elif patient_biomarkers.get('hrd') == "POSITIVE" or patient_biomarkers.get('hrd') == "HIGH":
            return True, 1.0, [], "HRD+ match"
        else:
            return False, 0.0, [], "HRD- (trial requires HRD+)"
    
    # Check BRCA
    if 'brca' in eligibility:
        if patient_biomarkers.get('brca') == "UNKNOWN":
            pending_gates.append("BRCA test required")
        elif patient_biomarkers.get('brca') == "POSITIVE":
            return True, 1.0, [], "BRCA+ match"
        else:
            return False, 0.0, [], "BRCA- (trial requires BRCA+)"
    
    # Check TMB
    if 'tmb' in eligibility or 'tumor mutational burden' in eligibility:
        if patient_biomarkers.get('tmb') == "UNKNOWN":
            pending_gates.append("TMB test required")
        elif patient_biomarkers.get('tmb') and float(patient_biomarkers.get('tmb', 0)) >= 20:
            return True, 1.0, [], "TMB-High match"
        else:
            return False, 0.0, [], "TMB-Low (trial requires TMB-High)"
    
    # Check MSI
    if 'msi' in eligibility or 'microsatellite' in eligibility:
        if patient_biomarkers.get('msi') == "UNKNOWN":
            pending_gates.append("MSI test required")
        elif patient_biomarkers.get('msi') == "HIGH" or patient_biomarkers.get('msi') == "MSI-H":
            return True, 1.0, [], "MSI-High match"
        else:
            return False, 0.0, [], "MSI-Stable (trial requires MSI-High)"
    
    # No biomarker requirements
    return True, 1.0, [], "No biomarker requirements"

def assess_location_match(trial: Dict[str, Any], patient_location: str) -> Tuple[bool, float, str]:
    """
    Assess location match (NYC metro area).
    
    Returns:
        (matches, confidence, reasoning)
    """
    # Try multiple field names
    locations = trial.get('locations_data', []) or trial.get('sites_json', [])
    if isinstance(locations, str):
        try:
            import json
            locations = json.loads(locations)
        except:
            locations = []
    if not locations:
        return True, 0.5, "No location data (assume match)"
    
    # Check for NYC metro (NY, NJ, CT)
    nyc_states = ['NY', 'NJ', 'CT', 'New York', 'New Jersey', 'Connecticut']
    for loc in locations:
        state = loc.get('state', '').upper()
        city = loc.get('city', '').upper()
        
        if state in ['NY', 'NJ', 'CT'] or 'NEW YORK' in city or 'NEW JERSEY' in city:
            return True, 1.0, f"NYC metro match: {city}, {state}"
    
    return False, 0.0, "No NYC metro locations"

def filter_50_candidates(trials: List[Dict[str, Any]], patient_profile: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Multi-tier filtering: Top-Tier, Good-Tier, OK-Tier.
    
    Replicates Zo's "1 in 700" filtering strategy.
    
    Args:
        trials: List of trial dictionaries
        patient_profile: {
            'disease': str,
            'treatment_line': str,
            'biomarkers': Dict[str, Any],
            'location': str
        }
    
    Returns:
        {
            'top_tier': List[Dict],
            'good_tier': List[Dict],
            'ok_tier': List[Dict]
        }
    """
    top_tier = []
    good_tier = []
    ok_tier = []
    
    for trial in trials:
        # Hard filters (must pass)
        disease_match, disease_conf, disease_reason = assess_disease_match(trial, patient_profile['disease'])
        if not disease_match:
            continue
        
        location_match, location_conf, location_reason = assess_location_match(trial, patient_profile.get('location', 'NYC'))
        if not location_match:
            continue
        
        # Status must be RECRUITING (case-insensitive)
        status = trial.get('status', '').upper()
        if status and 'RECRUIT' not in status and 'ACTIVE' not in status:
            continue
        
        # Soft filters (scoring)
        line_match, line_conf, line_reason = assess_treatment_line_match(trial, patient_profile.get('treatment_line', 'first-line'))
        biomarker_match, biomarker_conf, pending_gates, biomarker_reason = assess_biomarker_match(
            trial, patient_profile.get('biomarkers', {})
        )
        
        # Calculate composite score
        composite_score = (disease_conf * 0.3 + location_conf * 0.2 + line_conf * 0.2 + biomarker_conf * 0.3)
        
        # Add metadata
        trial['_filter_metadata'] = {
            'disease_match': disease_reason,
            'location_match': location_reason,
            'line_match': line_reason,
            'biomarker_match': biomarker_reason,
            'pending_gates': pending_gates,
            'composite_score': composite_score
        }
        
        # Tier assignment
        if composite_score >= 0.9 and len(pending_gates) == 0:
            top_tier.append(trial)
        elif composite_score >= 0.7:
            good_tier.append(trial)
        else:
            ok_tier.append(trial)
    
    # Sort by composite score
    top_tier.sort(key=lambda t: t['_filter_metadata']['composite_score'], reverse=True)
    good_tier.sort(key=lambda t: t['_filter_metadata']['composite_score'], reverse=True)
    ok_tier.sort(key=lambda t: t['_filter_metadata']['composite_score'], reverse=True)
    
    logger.info(f"✅ Filtered {len(trials)} trials → Top: {len(top_tier)}, Good: {len(good_tier)}, OK: {len(ok_tier)}")
    
    return {
        'top_tier': top_tier,
        'good_tier': good_tier,
        'ok_tier': ok_tier
    }

