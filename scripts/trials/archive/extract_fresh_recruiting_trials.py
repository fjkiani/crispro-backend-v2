"""
Extract FRESH recruiting ovarian trials from ClinicalTrials.gov API

Strategy:
1. Fetch ALL recruiting ovarian trials (simple filter - works reliably)
2. Store in 'trials_fresh' table (preserve old data)
3. Let our modular pipeline handle type/location/stage filtering

Target: ~777 recruiting trials (from reconnaissance)
"""
import sys
import asyncio
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add paths
project_root = Path(__file__).resolve().parent.parent.parent.parent
backend_path = project_root / "oncology-coPilot" / "oncology-backend"
sys.path.insert(0, str(backend_path))
agent_1_path = backend_path / "scripts" / "agent_1_seeding"
sys.path.insert(0, str(agent_1_path.parent))

from agent_1_seeding.parsers.study_parser import parse_ctgov_study
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "https://clinicaltrials.gov/api/v2/studies"


async def fetch_trials_by_criteria(
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    status: List[str] = None,
    phases: List[str] = None,
    study_type: str = "INTERVENTIONAL",
    keyword: Optional[str] = None,
    limit: int = 1000
) -> List[Dict[str, Any]]:
    """
    Fetch trials from ClinicalTrials.gov API v2 by criteria.
    
    Args:
        condition: Condition query (e.g., "ovarian cancer")
        intervention: Intervention query (e.g., "PARP inhibitor")
        status: List of status filters (e.g., ["RECRUITING", "NOT_YET_RECRUITING"])
        phases: List of phase filters (e.g., ["PHASE1", "PHASE2", "PHASE3"])
        study_type: Study type (default: "INTERVENTIONAL")
        keyword: Additional keyword (e.g., "basket", "rare disease")
        limit: Maximum number of trials to fetch (default: 1000)
        
    Returns:
        List of study objects from API
    """
    # Use CTGovQueryBuilder for flexible query building
    from api.services.ctgov_query_builder import CTGovQueryBuilder
    
    builder = CTGovQueryBuilder()
    
    # Add condition (default to "ovarian cancer" for backward compatibility)
    if condition:
        builder.add_condition(condition)
    else:
        builder.add_condition("ovarian cancer")  # Default for backward compatibility
    
    # Add intervention
    if intervention:
        builder.add_intervention(intervention)
    
    # Add status (default to RECRUITING for backward compatibility)
    if status:
        builder.add_status(status)
    else:
        builder.add_status(["RECRUITING"])
    
    # Add phases
    if phases:
        builder.add_phase(phases)
    
    # Add study type
    if study_type:
        builder.add_study_type(study_type)
    
    # Add keyword
    if keyword:
        builder.add_keyword(keyword)
    
    # Build and execute query
    from api.services.ctgov_query_builder import execute_query
    trials = await execute_query(builder, max_results=limit)
    
    logger.info(f"✅ Total fetched: {len(trials)} trials")
    return trials


def create_fresh_table():
    """Create 'trials_fresh' table with same schema as 'trials'"""
    db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    # Create table (same schema as 'trials')
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS trials_fresh (
            id TEXT PRIMARY KEY,
            title TEXT,
            status TEXT,
            phases TEXT,
            summary TEXT,
            conditions TEXT,
            interventions TEXT,
            source TEXT,
            inclusion_criteria TEXT,
            exclusion_criteria TEXT,
            inclusion_criteria_full TEXT,
            exclusion_criteria_full TEXT,
            primary_endpoint TEXT,
            interventions_json TEXT,
            locations_full_json TEXT,
            scraped_data_json TEXT,
            scraped_at TEXT
        )
    """)
    
    conn.commit()
    conn.close()
    logger.info("✅ Created 'trials_fresh' table")


def transform_to_trials_schema(parsed_trial: Dict[str, Any], raw_study: Dict[str, Any]) -> Dict[str, Any]:
    """Transform parsed trial to trials table schema"""
    metadata = json.loads(parsed_trial.get('metadata_json', '{}'))
    interventions_list = metadata.get('interventions', [])
    
    locations_data = parsed_trial.get('locations_data', '[]')
    if isinstance(locations_data, str):
        try:
            locations = json.loads(locations_data)
        except:
            locations = []
    else:
        locations = locations_data
    
    conditions = parsed_trial.get('disease_category', 'ovarian cancer')
    if isinstance(conditions, str):
        conditions_json = json.dumps([conditions])
    else:
        conditions_json = json.dumps(conditions) if conditions else json.dumps(['ovarian cancer'])
    
    phase = parsed_trial.get('phase', 'N/A')
    phases = phase if isinstance(phase, str) else ', '.join(phase) if phase else 'N/A'
    
    return {
        'id': parsed_trial.get('nct_id', ''),
        'title': parsed_trial.get('title', ''),
        'status': parsed_trial.get('status', 'Unknown'),
        'phases': phases,
        'summary': parsed_trial.get('description_text', ''),
        'conditions': conditions_json,
        'interventions': ', '.join(interventions_list) if interventions_list else '',
        'source': parsed_trial.get('source_url', ''),
        'inclusion_criteria': parsed_trial.get('inclusion_criteria_text', ''),
        'exclusion_criteria': parsed_trial.get('exclusion_criteria_text', ''),
        'inclusion_criteria_full': parsed_trial.get('inclusion_criteria_text', ''),
        'exclusion_criteria_full': parsed_trial.get('exclusion_criteria_text', ''),
        'primary_endpoint': parsed_trial.get('primary_endpoint', ''),
        'interventions_json': json.dumps(interventions_list) if interventions_list else '[]',
        'locations_full_json': json.dumps(locations) if locations else '[]',
        'scraped_data_json': json.dumps(raw_study),
        'scraped_at': datetime.now().isoformat()
    }


def insert_trials_batched(trials: List[Dict[str, Any]], table_name: str = "trials_fresh", batch_size: int = 50) -> None:
    """Insert trials into specified table in batches"""
    db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        for i in range(0, len(trials), batch_size):
            batch = trials[i:i + batch_size]
            
            for trial in batch:
                cursor.execute(f"""
                    INSERT OR REPLACE INTO {table_name} (
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


async def extract_and_seed(
    condition: Optional[str] = None,
    intervention: Optional[str] = None,
    status: List[str] = None,
    phases: List[str] = None,
    study_type: str = "INTERVENTIONAL",
    keyword: Optional[str] = None,
    limit: int = 777
):
    """
    Extract fresh trials by criteria and seed to trials_fresh table
    
    Args:
        condition: Condition query (e.g., "ovarian cancer")
        intervention: Intervention query (e.g., "PARP inhibitor")
        status: List of status filters
        phases: List of phase filters
        study_type: Study type
        keyword: Additional keyword
        limit: Maximum number of trials to fetch
    """
    logger.info(f"🚀 EXTRACTING FRESH RECRUITING OVARIAN TRIALS")
    logger.info(f"   Target: {limit} trials")
    logger.info(f"   Filter: RECRUITING status only")
    logger.info(f"   Post-processing: Will filter type/location/stage")
    
    # 1. Create fresh table
    create_fresh_table()
    
    # 2. Fetch trials
    logger.info("\n📥 FETCHING FROM CLINICALTRIALS.GOV API...")
    raw_trials = await fetch_trials_by_criteria(
        condition=condition,
        intervention=intervention,
        status=status,
        phases=phases,
        study_type=study_type,
        keyword=keyword,
        limit=limit
    )
    logger.info(f"✅ Fetched {len(raw_trials)} raw trials")
    
    if len(raw_trials) == 0:
        logger.error("❌ No trials fetched - API may be down")
        return 0
    
    # 3. Parse trials
    logger.info("\n⚙️ PARSING TRIALS...")
    parsed_trials = []
    for i, raw_trial in enumerate(raw_trials):
        try:
            parsed = parse_ctgov_study(raw_trial)
            parsed_trials.append(parsed)
            if (i + 1) % 100 == 0:
                logger.info(f"   Parsed {i + 1}/{len(raw_trials)} trials...")
        except Exception as e:
            nct_id = raw_trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "UNKNOWN")
            logger.warning(f"   Failed to parse {nct_id}: {e}")
    
    logger.info(f"✅ Parsed {len(parsed_trials)}/{len(raw_trials)} trials")
    
    # 4. Transform to trials schema
    logger.info("\n🔄 TRANSFORMING TO TRIALS SCHEMA...")
    transformed_trials = [
        transform_to_trials_schema(parsed, raw)
        for parsed, raw in zip(parsed_trials, raw_trials)
    ]
    logger.info(f"✅ Transformed {len(transformed_trials)} trials")
    
    # 5. Insert into trials_fresh
    logger.info("\n💾 INSERTING INTO 'trials_fresh' TABLE...")
    insert_trials_batched(transformed_trials, table_name="trials_fresh")
    
    # 6. Verify
    db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    cursor.execute("SELECT COUNT(*) FROM trials_fresh")
    count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM trials_fresh WHERE status LIKE '%RECRUITING%'")
    recruiting_count = cursor.fetchone()[0]
    
    # Sample interventions and locations
    cursor.execute("""
        SELECT COUNT(*) FROM trials_fresh 
        WHERE interventions_json IS NOT NULL 
        AND interventions_json != '[]'
    """)
    with_interventions = cursor.fetchone()[0]
    
    cursor.execute("""
        SELECT COUNT(*) FROM trials_fresh 
        WHERE locations_full_json IS NOT NULL 
        AND locations_full_json != '[]'
    """)
    with_locations = cursor.fetchone()[0]
    
    conn.close()
    
    logger.info(f"\n✅ EXTRACTION COMPLETE")
    logger.info(f"   Total in 'trials_fresh': {count}")
    logger.info(f"   Recruiting: {recruiting_count}")
    logger.info(f"   With interventions data: {with_interventions}")
    logger.info(f"   With location data: {with_locations}")
    
    logger.info(f"\n⚔️ NEXT STEP:")
    logger.info(f"   python3 find_trials_FROM_FRESH_TABLE.py")
    
    return count


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Extract clinical trials from ClinicalTrials.gov API")
    parser.add_argument('--condition', type=str, help='Condition query (e.g., "ovarian cancer")')
    parser.add_argument('--intervention', type=str, help='Intervention query (e.g., "PARP inhibitor")')
    parser.add_argument('--status', nargs='+', default=['RECRUITING'], help='Status filters (e.g., RECRUITING NOT_YET_RECRUITING)')
    parser.add_argument('--phase', nargs='+', help='Phase filters (e.g., PHASE1 PHASE2 PHASE3)')
    parser.add_argument('--study-type', type=str, default='INTERVENTIONAL', help='Study type')
    parser.add_argument('--keyword', type=str, help='Additional keyword (e.g., "basket", "rare disease")')
    parser.add_argument('--limit', type=int, default=1000, help='Max trials to fetch')
    args = parser.parse_args()
    
    result = asyncio.run(extract_and_seed(
        condition=args.condition,
        intervention=args.intervention,
        status=args.status,
        phases=args.phase,
        study_type=args.study_type,
        keyword=args.keyword,
        limit=args.limit
    ))
    sys.exit(0 if result > 0 else 1)


