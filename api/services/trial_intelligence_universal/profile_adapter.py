"""
Profile Adapter - Converts simple profile to full profile format.

Supports both simple and full profile formats for easier adoption.
"""

from typing import Dict, Any

def adapt_simple_to_full_profile(simple_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert simple profile to full Ayesha-style profile.
    
    Simple profile format:
    {
        'patient_id': str,
        'disease': str,
        'treatment_line': str,
        'location': str,
        'biomarkers': Dict[str, Any],
        'zip_code': Optional[str],
        'age': Optional[int],
        'sex': Optional[str],
        'stage': Optional[str],
    }
    
    Returns full profile format with sensible defaults.
    """
    # Extract from simple profile
    patient_id = simple_profile.get('patient_id', 'unknown')
    disease_name = simple_profile.get('disease', '')
    treatment_line = simple_profile.get('treatment_line', 'first-line')
    location = simple_profile.get('location', 'Unknown')
    biomarkers = simple_profile.get('biomarkers', {})
    zip_code = simple_profile.get('zip_code')
    age = simple_profile.get('age')
    sex = simple_profile.get('sex')
    stage = simple_profile.get('stage')
    
    # Build full profile with defaults
    full_profile = {
        'demographics': {
            'patient_id': patient_id,
            'name': simple_profile.get('name', f'Patient {patient_id}'),
            'age': age,
            'sex': sex,
            'location': location,
        },
        'disease': {
            'primary_diagnosis': disease_name,
            'stage': stage or 'Unknown',
            'figo_stage': stage or 'Unknown',
            'tumor_burden': simple_profile.get('tumor_burden', 'Unknown'),
            'performance_status': simple_profile.get('performance_status', None),
        },
        'treatment': {
            'line': treatment_line,
            'line_number': _parse_treatment_line_number(treatment_line),
            'status': 'treatment_naive' if treatment_line == 'first-line' else 'on_treatment',
            'prior_therapies': simple_profile.get('prior_therapies', []),
        },
        'biomarkers': biomarkers,
        'eligibility': {
            'age_eligible': True,
            'performance_status': 'ECOG 0-2',
            'organ_function': {
                'hepatic': 'normal',
                'renal': 'normal',
                'cardiac': 'normal',
                'pulmonary': 'normal',
            },
            'exclusions': {
                'bowel_obstruction': False,
                'active_infection': False,
                'brain_metastases': False,
                'other_malignancy': False,
            },
            'tissue_availability': {
                'has_tissue': simple_profile.get('has_tissue', True),
                'tissue_type': simple_profile.get('tissue_type', 'Unknown'),
                'sufficient_for_testing': True,
            },
        },
        'logistics': {
            'location': location,
            'zip_code': zip_code,
            'home_zip': zip_code,
            'travel_radius_miles': simple_profile.get('travel_radius_miles', 50),
            'willing_to_travel': simple_profile.get('willing_to_travel', True),
        },
        'labs': {},
        'screening': {
            'recist_measurable_disease': True,
            'target_lesions_present': True,
        },
        'critical_gates': simple_profile.get('critical_gates', {}),
        'probability_estimates': {},
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


