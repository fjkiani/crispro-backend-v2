"""
Seed 'trials' table with ovarian cancer trials from ClinicalTrials.gov

This script:
1. Fetches ovarian trials from ClinicalTrials.gov API
2. Parses them using the existing parser
3. Transforms to match 'trials' table schema
4. Inserts into 'trials' table (not 'clinical_trials')
"""
import sys
import asyncio
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add backend to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
backend_path = project_root / "oncology-coPilot" / "oncology-backend"
sys.path.insert(0, str(backend_path))

# Import from agent_1_seeding - add to path first
agent_1_path = backend_path / "scripts" / "agent_1_seeding"
sys.path.insert(0, str(agent_1_path.parent))  # Add 'scripts' to path

# Now import directly
from agent_1_seeding.api.ctgov_client import fetch_ovarian_trials
from agent_1_seeding.parsers.study_parser import parse_ctgov_study

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def transform_to_trials_schema(parsed_trial: Dict[str, Any], raw_study: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform parsed trial (clinical_trials schema) to trials table schema.
    
    Mapping:
    - nct_id → id
    - title → title
    - status → status
    - phase → phases (convert format)
    - description_text → summary
    - disease_category → conditions (convert to JSON array string)
    - interventions (from metadata) → interventions
    - source_url → source
    - inclusion_criteria_text → inclusion_criteria and inclusion_criteria_full
    - exclusion_criteria_text → exclusion_criteria and exclusion_criteria_full
    - primary_endpoint → primary_endpoint
    - interventions (from metadata) → interventions_json
    - locations_data → locations_full_json
    - raw_study → scraped_data_json
    - current timestamp → scraped_at
    """
    # Extract interventions from metadata
    metadata = json.loads(parsed_trial.get('metadata_json', '{}'))
    interventions_list = metadata.get('interventions', [])
    
    # Extract locations from metadata or locations_data
    locations_data = parsed_trial.get('locations_data', '[]')
    if isinstance(locations_data, str):
        try:
            locations = json.loads(locations_data)
        except:
            locations = []
    else:
        locations = locations_data
    
    # Convert disease_category to conditions (JSON array string)
    conditions = parsed_trial.get('disease_category', 'ovarian cancer')
    if isinstance(conditions, str):
        conditions_json = json.dumps([conditions])
    else:
        conditions_json = json.dumps(conditions) if conditions else json.dumps(['ovarian cancer'])
    
    # Convert phase to phases format
    phase = parsed_trial.get('phase', 'N/A')
    phases = phase if isinstance(phase, str) else ', '.join(phase) if phase else 'N/A'
    
    return {
        'id': parsed_trial.get('nct_id', ''),
        'title': parsed_trial.get('title', ''),
        'status': parsed_trial.get('status', 'Unknown'),
        'phases': phases,
        'summary': parsed_trial.get('description_text', ''),
        'conditions': conditions_json,  # JSON array string
        'interventions': ', '.join(interventions_list) if interventions_list else '',
        'source': parsed_trial.get('source_url', ''),
        'inclusion_criteria': parsed_trial.get('inclusion_criteria_text', ''),
        'exclusion_criteria': parsed_trial.get('exclusion_criteria_text', ''),
        'inclusion_criteria_full': parsed_trial.get('inclusion_criteria_text', ''),
        'exclusion_criteria_full': parsed_trial.get('exclusion_criteria_text', ''),
        'primary_endpoint': parsed_trial.get('primary_endpoint', ''),
        'interventions_json': json.dumps(interventions_list) if interventions_list else '[]',
        'locations_full_json': json.dumps(locations) if locations else '[]',
        'scraped_data_json': json.dumps(raw_study),  # Full raw study object
        'scraped_at': datetime.now().isoformat()
    }


def insert_trials_batched(trials: List[Dict[str, Any]], batch_size: int = 50) -> None:
    """
    Insert trials into 'trials' table in batches.
    """
    # Use the correct database path
    db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        for i in range(0, len(trials), batch_size):
            batch = trials[i:i + batch_size]
            
            for trial in batch:
                # Use INSERT OR REPLACE for idempotency
                cursor.execute("""
                    INSERT OR REPLACE INTO trials (
                        id, title, status, phases, summary, conditions, interventions,
                        source, inclusion_criteria, exclusion_criteria,
                        inclusion_criteria_full, exclusion_criteria_full,
                        primary_endpoint, interventions_json, locations_full_json,
                        scraped_data_json, scraped_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trial.get('id', ''),
                    trial.get('title', ''),
                    trial.get('status', 'Unknown'),
                    trial.get('phases', 'N/A'),
                    trial.get('summary', ''),
                    trial.get('conditions', '[]'),
                    trial.get('interventions', ''),
                    trial.get('source', ''),
                    trial.get('inclusion_criteria', ''),
                    trial.get('exclusion_criteria', ''),
                    trial.get('inclusion_criteria_full', ''),
                    trial.get('exclusion_criteria_full', ''),
                    trial.get('primary_endpoint', ''),
                    trial.get('interventions_json', '[]'),
                    trial.get('locations_full_json', '[]'),
                    trial.get('scraped_data_json', '{}'),
                    trial.get('scraped_at', datetime.now().isoformat())
                ))
            
            conn.commit()
            logger.info(f"   Inserted batch {i//batch_size + 1} ({min(i+batch_size, len(trials))}/{len(trials)} trials)")
        
    finally:
        conn.close()


async def seed_trials_table(limit: int = 500):
    """
    Seed 'trials' table with ovarian cancer trials.
    
    Args:
        limit: Maximum number of trials to fetch and seed
    """
    db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"
    
    logger.info(f"🚀 Seeding {limit} ovarian trials to 'trials' table in {db_path}")
    
    try:
        # 1. Fetch trials from API
        logger.info(f"Fetching {limit} trials from ClinicalTrials.gov API v2...")
        raw_trials = await fetch_ovarian_trials(limit=limit)
        logger.info(f"✅ Fetched {len(raw_trials)} raw trials")
        
        if len(raw_trials) == 0:
            logger.error("No trials fetched - exiting")
            return 0
        
        # 2. Parse trials
        logger.info("Parsing trials...")
        parsed_trials = [parse_ctgov_study(s) for s in raw_trials]
        logger.info(f"✅ Parsed {len(parsed_trials)} trials")
        
        # 3. Transform to trials table schema
        logger.info("Transforming to 'trials' table schema...")
        transformed_trials = [
            transform_to_trials_schema(parsed, raw)
            for parsed, raw in zip(parsed_trials, raw_trials)
        ]
        logger.info(f"✅ Transformed {len(transformed_trials)} trials")
        
        # 4. Insert into SQLite
        logger.info("Inserting into 'trials' table...")
        insert_trials_batched(transformed_trials)
        logger.info("✅ SQLite insertion complete")
        
        # 5. Verify
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM trials")
        count = cursor.fetchone()[0]
        
        # Check recruiting status
        cursor.execute("SELECT COUNT(*) FROM trials WHERE status LIKE '%RECRUITING%'")
        recruiting_count = cursor.fetchone()[0]
        
        conn.close()
        
        logger.info(f"✅ SEEDING COMPLETE - {count} total trials in 'trials' table")
        logger.info(f"   Recruiting trials: {recruiting_count}")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=500, help="Number of trials to seed")
    args = parser.parse_args()
    
    result = asyncio.run(seed_trials_table(limit=args.limit))
    sys.exit(0 if result > 0 else 1)

