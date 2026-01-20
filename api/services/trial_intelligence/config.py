"""
⚔️ TRIAL INTELLIGENCE PIPELINE CONFIGURATION ⚔️

DRY, configurable filter settings.
Easy to adjust without touching code.

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

from typing import List, Set, Dict, Any
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

