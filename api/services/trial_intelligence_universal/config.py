"""
⚔️ TRIAL INTELLIGENCE PIPELINE CONFIGURATION ⚔️

DRY, configurable filter settings.
Easy to adjust without touching code.

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

from typing import List, Set, Dict, Any, Optional
from dataclasses import dataclass

class FilterConfig:
    """
    Configuration for trial intelligence pipeline filters.
    
    Modify these values to adjust filtering behavior without code changes.
    """
    
    def __init__(self):
        # === STAGE 1: HARD FILTERS ===
        
        # Status filters
        self.RECRUITING_STATUSES = {
            'RECRUITING',
            'NOT_YET_RECRUITING',
            'ACTIVE_NOT_RECRUITING'  # May accept via protocol
        }
        
        # Disease filters
        self.DISEASE_KEYWORDS = [
            'ovarian', 'gynecologic', 'serous', 'endometrioid',
            'fallopian tube', 'peritoneal'
        ]
    
        # === STAGE 2: TRIAL TYPE ===
        
        # Observational keywords (for rejection)
        self.OBSERVATIONAL_KEYWORDS = [
            'observational', 'non-interventional', 'noninterventional',
            'registry', 'tissue procurement', 'tissue collection',
            'biobank', 'biorepository', 'correlative study',
            'biomarker study', 'imaging study', 'ai model',
            'artificial intelligence', 'machine learning',
            'retrospective', 'archived tissue', 'tumor samples',
            'specimen collection', 'data collection',
            'natural history', 'epidemiology', 'surveillance',
            'chart review', 'database study', 'cohort study',
            'tumor infiltrating t cells', 'hypoxia imaging',
            'pet/ct imaging', 'mri study', 'ct features'
        ]
        
        # Interventional keywords (for acceptance)
        self.INTERVENTIONAL_KEYWORDS = [
            'randomized', 'placebo', 'double-blind', 'single-blind',
            'treatment', 'therapy', 'drug', 'medication',
            'intervention', 'experimental', 'investigational',
            'phase i', 'phase ii', 'phase iii', 'phase 1', 'phase 2', 'phase 3',
            'clinical trial', 'dosing', 'dose escalation',
            'safety and efficacy', 'response rate', 'survival',
            'maintenance therapy', 'combination therapy',
            'adverse events', 'toxicity', 'maximum tolerated dose',
            'pharmacokinetics', 'pharmacodynamics'
        ]
    
        # === STAGE 3: LOCATION ===
        
        # NYC Metro configuration
        self.PATIENT_ZIP = "10029"  # Ayesha's ZIP (East Harlem)
        self.MAX_TRAVEL_MILES = 50  # Maximum travel distance
        
        # Location filtering behavior
        self.ALLOW_TRIALS_WITHOUT_LOCATION = True  # Allow trials with no location data (flag them for manual review)
        self.REQUIRE_LOCATION_DATA = False  # If False, trials without location data can pass Stage 3
        
        # Allowed states (expandable)
        self.ALLOWED_STATES = {'NY', 'NJ', 'CT'}  # Default: NYC metro only
        
        # NYC Metro cities
        self.NYC_METRO_CITIES = [
            # NYC 5 Boroughs
            'New York', 'Manhattan', 'Brooklyn', 'Bronx', 'Queens', 'Staten Island',
            # Major NYC medical centers
            'East Harlem', 'Upper East Side', 'Midtown', 'Lower Manhattan',
            # Northern NJ (within 50 miles)
            'Jersey City', 'Newark', 'Hoboken', 'Paterson', 'Elizabeth',
            'Edison', 'Woodbridge', 'New Brunswick', 'Trenton',
            'Hackensack', 'Englewood', 'Fort Lee', 'Morristown',
            # Southwest CT (within 50 miles)
            'Stamford', 'Norwalk', 'Bridgeport', 'New Haven', 'Danbury',
            'Westport', 'Greenwich', 'Fairfield'
        ]
        
        # Major cancer centers (for exact matching)
        self.MAJOR_CANCER_CENTERS = [
            'Memorial Sloan Kettering', 'MSK', 'Sloan Kettering',
            'Mount Sinai', 'Icahn School of Medicine',
            'NYU Langone', 'New York University',
            'Weill Cornell', 'Cornell',
            'Columbia University', 'Columbia Presbyterian',
            'Montefiore', 'Albert Einstein',
            'Hackensack Meridian', 'Hackensack University Medical Center',
            'Rutgers Cancer Institute',
            'Yale Cancer Center', 'Yale-New Haven Hospital'
        ]
    
        # === STAGE 4: ELIGIBILITY ===
        
        # Treatment line preferences
        self.PREFERRED_TREATMENT_LINES = ['frontline', 'first-line', 'first line', 'primary', '1l']
        
        # Treatment line scoring weights
        self.LINE_SCORE_WEIGHTS = {
            'frontline': 1.0,      # Perfect match
            'first-line': 1.0,     # Perfect match
            'first line': 1.0,     # Perfect match
            'primary': 1.0,        # Perfect match
            '1l': 1.0,             # Perfect match
            'maintenance': 0.7,    # Good (after frontline)
            'recurrent': 0.2,      # Low (patient is first-line)
            'relapsed': 0.2,       # Low (patient is first-line)
            'platinum-resistant': 0.1,  # Very low
            'platinum-refractory': 0.1   # Very low
        }
        
        # Stage matching
        self.PATIENT_STAGE = "IVB"  # Ayesha's stage
        self.STAGE_IV_KEYWORDS = [
            'stage iv', 'stage 4', 'advanced', 'metastatic'
        ]
        
        # Biomarker probability estimates (literature-based)
        self.HER2_POS_PROB = 0.50  # 40-60% of ovarian cancers
        self.HRD_NEG_PROB = 0.60   # If HRD+ is 40%, then HRD- is 60%
        self.HRD_POS_PROB = 0.40   # 40% of BRCA- are HRD+
        
        # === STAGE 5: LLM ===
        
        # LLM configuration
        self.USE_LLM = True
        self.LLM_MODEL = "gemini-2.5-pro"
        self.MAX_LLM_ANALYSES = 10  # Only analyze top N trials
        
        # === STAGE 6: DOSSIER ===
        
        # Tier thresholds
        self.TOP_TIER_THRESHOLD = 0.8
        self.GOOD_TIER_THRESHOLD = 0.6
        
        # Composite score weights
        self.COMPOSITE_WEIGHTS = {
            'stage1': 0.15,  # Hard filters (low weight - binary)
            'stage2': 0.35,  # Trial type (critical - treatment vs observational)
            'stage3': 0.25,  # Location (critical - NYC access)
            'stage4': 0.25   # Eligibility (important - probability)
        }


# === PRESET CONFIGURATIONS ===

def get_nyc_metro_config() -> FilterConfig:
    """Default: NYC metro only (NY, NJ, CT)"""
    config = FilterConfig()
    config.ALLOWED_STATES = {'NY', 'NJ', 'CT'}
    return config

def get_expanded_states_config(allowed_states: Set[str] = None) -> FilterConfig:
    """
    Expanded states configuration.
    
    Args:
        allowed_states: Set of state codes (default: Northeast + Mid-Atlantic)
    
    Example:
        config = get_expanded_states_config({'NY', 'NJ', 'CT', 'PA', 'MA', 'RI'})
    """
    config = FilterConfig()
    if allowed_states is None:
        # Default: Expand to Northeast + Mid-Atlantic
        config.ALLOWED_STATES = {'NY', 'NJ', 'CT', 'PA', 'MA', 'RI', 'MD', 'DE', 'NH', 'VT'}
    else:
        config.ALLOWED_STATES = allowed_states
    return config

def get_frontline_only_config() -> FilterConfig:
    """Frontline trials only (no maintenance)"""
    config = FilterConfig()
    config.PREFERRED_TREATMENT_LINES = ['frontline', 'first-line', 'first line', 'primary', '1l']
    config.LINE_SCORE_WEIGHTS = {
        'frontline': 1.0,
        'first-line': 1.0,
        'first line': 1.0,
        'primary': 1.0,
        '1l': 1.0,
        'maintenance': 0.0,  # Reject maintenance
        'recurrent': 0.0,
        'relapsed': 0.0
    }
    return config

def get_maintenance_allowed_config() -> FilterConfig:
    """Allow maintenance trials (default)"""
    return FilterConfig()  # Default already allows maintenance


# === ZIP TO STATE MAPPING (US Only) ===

# Simple ZIP prefix to state mapping (first 3 digits)
# This is a simplified mapping - can be expanded with full ZIP database
ZIP_PREFIX_TO_STATE = {
    # New York: 100-149
    **{str(i): 'NY' for i in range(100, 150)},
    # New Jersey: 070-089
    **{str(i).zfill(3): 'NJ' for i in range(70, 90)},
    # Connecticut: 060-069
    **{str(i).zfill(3): 'CT' for i in range(60, 70)},
    # California: 900-961
    **{str(i): 'CA' for i in range(900, 962)},
    # Texas: 733, 750-799, 770-799
    **{str(i): 'TX' for i in range(750, 800)},
    '733': 'TX',
    # Florida: 320-349
    **{str(i): 'FL' for i in range(320, 350)},
    # Illinois: 600-629
    **{str(i): 'IL' for i in range(600, 630)},
    # Pennsylvania: 150-199
    **{str(i): 'PA' for i in range(150, 200)},
    # Ohio: 430-459
    **{str(i): 'OH' for i in range(430, 460)},
    # Massachusetts: 010-027, 055
    **{str(i).zfill(3): 'MA' for i in range(10, 28)},
    '055': 'MA',
    # Add more as needed...
}

# Adjacent states mapping
ADJACENT_STATES = {
    'NY': {'NJ', 'CT', 'PA', 'MA', 'VT'},
    'NJ': {'NY', 'PA', 'DE'},
    'CT': {'NY', 'MA', 'RI'},
    'CA': {'OR', 'NV', 'AZ'},
    'TX': {'OK', 'AR', 'LA', 'NM'},
    'FL': {'GA', 'AL'},
    'IL': {'WI', 'IN', 'MO', 'IA', 'KY'},
    'PA': {'NY', 'NJ', 'DE', 'MD', 'WV', 'OH'},
    'OH': {'PA', 'WV', 'KY', 'IN', 'MI'},
    'MA': {'NH', 'VT', 'NY', 'CT', 'RI'},
}

# Major cancer centers by state/region (for config derivation)
MAJOR_CANCER_CENTERS_BY_REGION = {
    'NY': [
        'Memorial Sloan Kettering', 'MSK', 'Sloan Kettering',
        'Mount Sinai', 'Icahn School of Medicine',
        'NYU Langone', 'New York University',
        'Weill Cornell', 'Cornell',
        'Columbia University', 'Columbia Presbyterian',
        'Montefiore', 'Albert Einstein',
    ],
    'NJ': [
        'Hackensack Meridian', 'Hackensack University Medical Center',
        'Rutgers Cancer Institute',
    ],
    'CT': [
        'Yale Cancer Center', 'Yale-New Haven Hospital',
    ],
    'CA': [
        'UCLA Medical Center', 'UCLA', 'UCLA Health',
        'Stanford Cancer Center', 'Stanford',
        'UCSF Medical Center', 'UCSF',
        'Cedars-Sinai', 'Cedars Sinai',
        'City of Hope',
        'USC Norris Comprehensive Cancer Center',
    ],
    'TX': [
        'MD Anderson', 'MD Anderson Cancer Center',
        'UT Southwestern',
    ],
    'FL': [
        'Moffitt Cancer Center',
        'Sylvester Comprehensive Cancer Center',
    ],
    'IL': [
        'University of Chicago Medicine',
        'Northwestern Medicine',
    ],
    'PA': [
        'University of Pennsylvania', 'Penn Medicine',
        'Fox Chase Cancer Center',
    ],
    'MA': [
        'Dana-Farber Cancer Institute',
        'Massachusetts General Hospital', 'MGH',
    ],
}

def get_major_cancer_centers_for_state(state: str) -> List[str]:
    """Get major cancer centers for a given state."""
    centers = []
    # Get centers for the state
    centers.extend(MAJOR_CANCER_CENTERS_BY_REGION.get(state, []))
    # Also include adjacent states' major centers (for metro areas)
    adjacent = get_adjacent_states(state)
    for adj_state in adjacent:
        centers.extend(MAJOR_CANCER_CENTERS_BY_REGION.get(adj_state, []))
    return list(set(centers))  # Deduplicate

def zip_to_state(zip_code: str) -> Optional[str]:
    """Convert ZIP code to state code using 3-digit prefix."""
    if not zip_code:
        return None
    # Extract first 3 digits
    zip_clean = ''.join(c for c in zip_code if c.isdigit())
    if len(zip_clean) >= 3:
        zip_prefix_3 = zip_clean[:3]
        return ZIP_PREFIX_TO_STATE.get(zip_prefix_3)
    return None

def get_adjacent_states(state: str) -> Set[str]:
    """Get adjacent states for a given state."""
    return ADJACENT_STATES.get(state, set())

def extract_disease_keywords(diagnosis: str) -> List[str]:
    """Extract disease keywords from diagnosis string."""
    diagnosis_lower = diagnosis.lower()
    keywords = []
    
    # Common cancer types
    if 'ovarian' in diagnosis_lower:
        keywords.extend(['ovarian', 'gynecologic', 'serous', 'endometrioid', 'fallopian tube', 'peritoneal'])
    if 'breast' in diagnosis_lower:
        keywords.extend(['breast', 'mammary'])
    if 'lung' in diagnosis_lower:
        keywords.extend(['lung', 'pulmonary', 'non-small cell', 'nsclc', 'small cell', 'sclc'])
    if 'colorectal' in diagnosis_lower or 'colon' in diagnosis_lower:
        keywords.extend(['colorectal', 'colon', 'rectal'])
    if 'prostate' in diagnosis_lower:
        keywords.extend(['prostate', 'prostatic'])
    if 'pancreatic' in diagnosis_lower:
        keywords.extend(['pancreatic', 'pancreas'])
    if 'melanoma' in diagnosis_lower:
        keywords.extend(['melanoma', 'skin'])
    if 'lymphoma' in diagnosis_lower:
        keywords.extend(['lymphoma', 'hodgkin', 'non-hodgkin'])
    if 'leukemia' in diagnosis_lower:
        keywords.extend(['leukemia', 'leukemic'])
    
    # If no specific keywords found, use the diagnosis itself
    if not keywords:
        keywords = [diagnosis_lower]
    
    return keywords

def create_config_from_patient_profile(patient_profile: Dict[str, Any]) -> FilterConfig:
    """
    Create FilterConfig from patient profile.
    
    Derives location, disease, and treatment settings from patient data.
    """
    config = FilterConfig()
    
    # Extract location
    logistics = patient_profile.get('logistics', {})
    zip_code = logistics.get('zip_code') or logistics.get('home_zip')
    if zip_code:
        config.PATIENT_ZIP = str(zip_code)
        # Convert ZIP to state
        state = zip_to_state(zip_code)
        if state:
            config.ALLOWED_STATES = {state}  # Start with patient's state
            # Expand to adjacent states
            adjacent = get_adjacent_states(state)
            config.ALLOWED_STATES.update(adjacent)
            # Special case: NYC metro (NY, NJ, CT)
            if state in ['NY', 'NJ', 'CT']:
                config.ALLOWED_STATES = {'NY', 'NJ', 'CT'}
            
            # Add major cancer centers for patient's region
            regional_centers = get_major_cancer_centers_for_state(state)
            if regional_centers:
                # Merge with default centers (keep NYC centers as fallback)
                config.MAJOR_CANCER_CENTERS = list(set(config.MAJOR_CANCER_CENTERS + regional_centers))
    
    # Extract disease
    disease = patient_profile.get('disease', {})
    primary_diagnosis = disease.get('primary_diagnosis', '')
    if primary_diagnosis:
        config.DISEASE_KEYWORDS = extract_disease_keywords(primary_diagnosis)
    config.PATIENT_STAGE = disease.get('figo_stage') or disease.get('stage', '')
    
    # Extract treatment line
    treatment = patient_profile.get('treatment', {})
    treatment_line = treatment.get('line', 'first-line')
    if treatment_line:
        config.PREFERRED_TREATMENT_LINES = [treatment_line]
        # Also add common variations
        if 'first' in treatment_line.lower():
            config.PREFERRED_TREATMENT_LINES.extend(['frontline', 'first-line', 'first line', 'primary', '1l'])
    
    # Extract travel radius
    travel_radius = logistics.get('travel_radius_miles', 50)
    if travel_radius:
        config.MAX_TRAVEL_MILES = travel_radius
    
    return config

