"""
Trial Querier - Read trials from SQLite database.

JR2 uses this to get trials for filtering and dossier generation.
"""
import sqlite3
import json
from typing import List, Dict, Any
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

def get_trials_from_sqlite(limit: int = 0) -> List[Dict[str, Any]]:
    """
    Get trials from SQLite for JR2's filtering pipeline.
    
    Uses the 'trials' table which has 1000 trials (not 'clinical_trials' which has 30).
    
    Args:
        limit: Max trials to return (0 = all)
    
    Returns:
        List of trial dictionaries with all fields
    """
    # Get absolute path to database
    # From: api/services/client_dossier/trial_querier.py
    # To: oncology-backend-minimal/data/clinical_trials.db
    current_file = Path(__file__).resolve()
    # Go up: client_dossier -> services -> api -> oncology-backend-minimal
    backend_root = current_file.parent.parent.parent.parent
    db_path = backend_root / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # Use 'trials' table (has 1000 trials, not 'clinical_trials' which has 30)
    if limit > 0:
        cursor.execute("SELECT * FROM trials LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT * FROM trials")
    
    trials = [dict(row) for row in cursor.fetchall()]
    
    # Parse JSON fields if they exist
    for trial in trials:
        for json_field in ['pis_json', 'orgs_json', 'sites_json', 'biomarker_requirements', 'locations_data', 'mechanism_tags']:
            if trial.get(json_field) and isinstance(trial[json_field], str):
                try:
                    trial[json_field] = json.loads(trial[json_field])
                except (json.JSONDecodeError, TypeError):
                    trial[json_field] = []
    
    conn.close()
    logger.info(f"✅ Retrieved {len(trials)} trials from SQLite")
    return trials

