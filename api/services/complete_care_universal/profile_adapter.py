"""
Profile Adapter - Converts simple profile to full profile format.

Reuses pattern from trial_intelligence_universal.
Supports both simple and full profile formats for easier adoption.

Sprint 1: Integrated PGx extraction for germline variant detection.
"""

from typing import Dict, Any, List
from api.services.pgx_extraction_service import get_pgx_extraction_service


def adapt_simple_to_full_profile(simple_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert simple profile to full profile format.
    
    Simple profile format:
    {
        'patient_id': str,
        'name': Optional[str],
        'disease': str | Dict[str, Any],  # Can be string or dict with type/stage
        'treatment_line': str,
        'location': str,
        'biomarkers': Dict[str, Any],
        'zip_code': Optional[str],
        'age': Optional[int],
        'sex': Optional[str],
        'stage': Optional[str],
        'tumor_context': Optional[Dict[str, Any]],
        'germline_variants': Optional[List[Dict]],  # NEW: Sprint 1
        'germline_panel': Optional[Dict],  # NEW: Sprint 1
        'mutations': Optional[List[Dict]],  # May contain germline mutations
    }
    
    Returns full profile format compatible with universal orchestrator.
    """
    # Extract from simple profile
    patient_id = simple_profile.get('patient_id', 'unknown')
    name = simple_profile.get('name', f'Patient {patient_id}')
    
    # Handle disease (can be string or dict)
    disease_input = simple_profile.get('disease', {})
    if isinstance(disease_input, str):
        disease_type = disease_input
        disease_stage = simple_profile.get('stage', 'Unknown')
    else:
        disease_type = disease_input.get('type', '')
        disease_stage = disease_input.get('stage', simple_profile.get('stage', 'Unknown'))
    
    treatment_line = simple_profile.get('treatment_line', 'first-line')
    location = simple_profile.get('location', 'Unknown')
    biomarkers = simple_profile.get('biomarkers', {})
    zip_code = simple_profile.get('zip_code')
    age = simple_profile.get('age')
    sex = simple_profile.get('sex')
    tumor_context = simple_profile.get('tumor_context')
    
    # Sprint 1: Extract PGx variants if present
    pgx_service = get_pgx_extraction_service()
    germline_variants = []
    
    # Check if germline_variants already provided
    if 'germline_variants' in simple_profile:
        germline_variants = pgx_service.extract_from_patient_profile({
            'germline_variants': simple_profile['germline_variants']
        })
    # Check if germline_panel provided
    elif 'germline_panel' in simple_profile:
        germline_variants = pgx_service.extract_from_patient_profile({
            'germline_panel': simple_profile['germline_panel']
        })
    # Check if mutations list provided (may contain germline)
    elif 'mutations' in simple_profile:
        # Filter for germline mutations if sample_type field exists
        germline_mutations = [
            m for m in simple_profile.get('mutations', [])
            if m.get('sample_type') == 'germline' or 'germline' in str(m.get('source', '')).lower()
        ]
        if germline_mutations:
            germline_variants = pgx_service.extract_from_mutations_list(germline_mutations, sample_type='germline')
    
    # Build full profile
    full_profile = {
        'demographics': {
            'patient_id': patient_id,
            'name': name,
            'age': age,
            'sex': sex,
            'location': location,
            'zip_code': zip_code,
        },
        'disease': {
            'type': disease_type,
            'stage': disease_stage,
            'histology': disease_input.get('histology') if isinstance(disease_input, dict) else None,
            'diagnosis_date': disease_input.get('diagnosis_date') if isinstance(disease_input, dict) else None,
        },
        'treatment': {
            'line': treatment_line,
            'line_number': _parse_treatment_line_number(treatment_line),
            'history': simple_profile.get('treatment_history', []),
            'current_medications': simple_profile.get('current_medications', []),
        },
        'biomarkers': biomarkers,
        'tumor_context': tumor_context,
        'germline_variants': germline_variants,  # NEW: Sprint 1 - PGx variants extracted
        'logistics': {
            'zip_code': zip_code,
            'location': location,
            'travel_radius_miles': simple_profile.get('travel_radius_miles', 50),
            'preferred_locations': simple_profile.get('preferred_locations', []),
        },
    }
    
    return full_profile


def _parse_treatment_line_number(treatment_line: str) -> int:
    """Parse treatment line string to number."""
    treatment_lower = treatment_line.lower()
    if 'first' in treatment_lower or '1' in treatment_lower or 'frontline' in treatment_lower:
        return 1
    elif 'second' in treatment_lower or '2' in treatment_lower:
        return 2
    elif 'third' in treatment_lower or '3' in treatment_lower:
        return 3
    return 1  # Default to first-line


def is_simple_profile(profile: Dict[str, Any]) -> bool:
    """Check if profile is simple format."""
    return 'demographics' not in profile and 'patient_id' in profile


