"""
Food Data Loading Service

Centralized service for loading all food-related data files.
Extracted from hypothesis_validator.py for modularity.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

# Data file paths (relative to project root)
DATA_DIR = Path(__file__).parent.parent.parent.parent.parent / ".cursor/ayesha/hypothesis_validator/data"
DISEASE_AB_FILE = DATA_DIR / "disease_ab_dependencies.json"
FOOD_TARGETS_FILE = DATA_DIR / "food_targets.json"
CANCER_TYPE_FOODS_FILE = DATA_DIR / "cancer_type_food_recommendations.json"
BIOMARKER_FOODS_FILE = DATA_DIR / "biomarker_food_mapping.json"

# Universal pathway database
UNIVERSAL_DB_PATH = Path(__file__).parent.parent / "resources" / "universal_disease_pathway_database.json"

# Cache loaded data
_disease_ab_cache: Optional[Dict[str, Any]] = None
_food_targets_cache: Optional[Dict[str, Any]] = None
_cancer_type_foods_cache: Optional[Dict[str, Any]] = None
_biomarker_foods_cache: Optional[Dict[str, Any]] = None
_universal_db_cache: Optional[Dict[str, Any]] = None


def load_disease_ab_mapping() -> Dict[str, Any]:
    """
    Load disease A→B dependency mapping.
    
    Returns:
        Dictionary mapping disease IDs to their A→B dependencies
    """
    global _disease_ab_cache
    
    if _disease_ab_cache is not None:
        return _disease_ab_cache
    
    try:
        if DISEASE_AB_FILE.exists():
            with open(DISEASE_AB_FILE, 'r') as f:
                _disease_ab_cache = json.load(f)
            logger.debug(f"Loaded disease A→B mapping from {DISEASE_AB_FILE}")
        else:
            logger.warning(f"Disease A→B file not found: {DISEASE_AB_FILE}")
            _disease_ab_cache = {}
    except Exception as e:
        logger.error(f"Failed to load disease A→B mapping: {e}")
        _disease_ab_cache = {}
    
    return _disease_ab_cache


def load_food_targets() -> Dict[str, Any]:
    """
    Load food targets mapping.
    
    Returns:
        Dictionary mapping compounds to their targets
    """
    global _food_targets_cache
    
    if _food_targets_cache is not None:
        return _food_targets_cache
    
    try:
        if FOOD_TARGETS_FILE.exists():
            with open(FOOD_TARGETS_FILE, 'r') as f:
                _food_targets_cache = json.load(f)
            logger.debug(f"Loaded food targets from {FOOD_TARGETS_FILE}")
        else:
            logger.warning(f"Food targets file not found: {FOOD_TARGETS_FILE}")
            _food_targets_cache = {}
    except Exception as e:
        logger.error(f"Failed to load food targets: {e}")
        _food_targets_cache = {}
    
    return _food_targets_cache


def load_cancer_type_foods() -> Dict[str, Any]:
    """
    Load cancer type-specific food recommendations.
    
    Returns:
        Dictionary with cancer_types key containing disease-specific recommendations
    """
    global _cancer_type_foods_cache
    
    if _cancer_type_foods_cache is not None:
        return _cancer_type_foods_cache
    
    try:
        if CANCER_TYPE_FOODS_FILE.exists():
            with open(CANCER_TYPE_FOODS_FILE, 'r') as f:
                _cancer_type_foods_cache = json.load(f)
            logger.debug(f"Loaded cancer type foods from {CANCER_TYPE_FOODS_FILE}")
        else:
            logger.warning(f"Cancer type foods file not found: {CANCER_TYPE_FOODS_FILE}")
            _cancer_type_foods_cache = {"cancer_types": {}}
    except Exception as e:
        logger.warning(f"Failed to load cancer type foods: {e}")
        _cancer_type_foods_cache = {"cancer_types": {}}
    
    return _cancer_type_foods_cache


def load_biomarker_foods() -> Dict[str, Any]:
    """
    Load biomarker-specific food mappings.
    
    Returns:
        Dictionary with biomarker_mappings key containing biomarker-specific recommendations
    """
    global _biomarker_foods_cache
    
    if _biomarker_foods_cache is not None:
        return _biomarker_foods_cache
    
    try:
        if BIOMARKER_FOODS_FILE.exists():
            with open(BIOMARKER_FOODS_FILE, 'r') as f:
                _biomarker_foods_cache = json.load(f)
            logger.debug(f"Loaded biomarker foods from {BIOMARKER_FOODS_FILE}")
        else:
            logger.warning(f"Biomarker foods file not found: {BIOMARKER_FOODS_FILE}")
            _biomarker_foods_cache = {"biomarker_mappings": {}}
    except Exception as e:
        logger.warning(f"Failed to load biomarker foods: {e}")
        _biomarker_foods_cache = {"biomarker_mappings": {}}
    
    return _biomarker_foods_cache


def load_universal_disease_pathway_database() -> Dict[str, Any]:
    """
    Load universal disease pathway database (TCGA-weighted).
    
    Returns:
        Dictionary with diseases key containing pathway weights
    """
    global _universal_db_cache
    
    if _universal_db_cache is not None:
        return _universal_db_cache
    
    try:
        if UNIVERSAL_DB_PATH.exists():
            with open(UNIVERSAL_DB_PATH, 'r') as f:
                _universal_db_cache = json.load(f)
            logger.debug(f"Loaded universal disease pathway database from {UNIVERSAL_DB_PATH}")
        else:
            logger.warning(f"Universal pathway database not found: {UNIVERSAL_DB_PATH}")
            _universal_db_cache = {"diseases": {}}
    except Exception as e:
        logger.error(f"Failed to load universal pathway database: {e}")
        _universal_db_cache = {"diseases": {}}
    
    return _universal_db_cache


def get_disease_data(disease: str) -> Optional[Dict[str, Any]]:
    """
    Get disease data from universal database or DISEASE_AB fallback.
    
    Args:
        disease: Disease ID (e.g., "ovarian_cancer_hgs")
    
    Returns:
        Disease data dictionary or None if not found
    """
    # Try universal database first
    universal_db = load_universal_disease_pathway_database()
    if disease in universal_db.get("diseases", {}):
        return universal_db["diseases"][disease]
    
    # Fallback to DISEASE_AB
    disease_ab = load_disease_ab_mapping()
    return disease_ab.get(disease)


def clear_cache():
    """Clear all cached data (useful for testing or reloading)."""
    global _disease_ab_cache, _food_targets_cache
    global _cancer_type_foods_cache, _biomarker_foods_cache, _universal_db_cache
    
    _disease_ab_cache = None
    _food_targets_cache = None
    _cancer_type_foods_cache = None
    _biomarker_foods_cache = None
    _universal_db_cache = None
    logger.debug("Cleared food data cache")

