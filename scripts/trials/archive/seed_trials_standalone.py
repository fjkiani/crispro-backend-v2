"""
Standalone Trial Seeding Script - Seeds SQLite with relationship data
Directly uses parsing and SQLite insertion without ChromaDB dependencies
"""
import sys
import asyncio
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any

# Add backend to path
project_root = Path(__file__).resolve().parent.parent.parent.parent
backend_path = project_root / "oncology-coPilot" / "oncology-backend"
sys.path.insert(0, str(backend_path))

# Import from agent_1_seeding
import importlib.util
spec = importlib.util.spec_from_file_location("ctgov_client", backend_path / "scripts" / "agent_1_seeding" / "api" / "ctgov_client.py")
ctgov_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ctgov_module)
fetch_ovarian_trials = ctgov_module.fetch_ovarian_trials

spec2 = importlib.util.spec_from_file_location("study_parser", backend_path / "scripts" / "agent_1_seeding" / "parsers" / "study_parser.py")
parser_module = importlib.util.module_from_spec(spec2)
spec2.loader.exec_module(parser_module)
parse_ctgov_study = parser_module.parse_ctgov_study

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def insert_trials_batched(trials: List[Dict[str, Any]], batch_size: int = 50) -> None:
    """
    Insert trials into SQLite in batches.
    Adapted from sqlite_client.py to avoid chromadb dependency.
    """
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    db_path = project_root / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        for i in range(0, len(trials), batch_size):
            batch = trials[i:i + batch_size]
            
            for trial in batch:
                # Use INSERT OR REPLACE for idempotency
                cursor.execute("""
                    INSERT OR REPLACE INTO clinical_trials (
                        source_url, nct_id, primary_id, title, status, phase,
                        description_text, inclusion_criteria_text, exclusion_criteria_text,
                        objectives_text, eligibility_text, raw_markdown, metadata_json,
                        ai_summary, pis_json, orgs_json, sites_json
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trial.get('source_url', ''),
                    trial.get('nct_id', ''),
                    trial.get('primary_id', ''),
                    trial.get('title', ''),
                    trial.get('status', 'Unknown'),
                    trial.get('phase', 'N/A'),
                    trial.get('description_text', ''),
                    trial.get('inclusion_criteria_text', ''),
                    trial.get('exclusion_criteria_text', ''),
                    trial.get('objectives_text', ''),
                    trial.get('eligibility_text', ''),
                    trial.get('raw_markdown', ''),
                    trial.get('metadata_json', '{}'),
                    trial.get('ai_summary'),
                    trial.get('pis_json'),
                    trial.get('orgs_json'),
                    trial.get('sites_json')
                ))
            
            conn.commit()
            logger.info(f"   Inserted batch {i//batch_size + 1} ({min(i+batch_size, len(trials))}/{len(trials)} trials)")
        
    finally:
        conn.close()


async def seed_trials(limit: int = 100):
    """Seed SQLite database with trials (includes relationship data from Component 1)."""
    
    project_root = Path(__file__).resolve().parent.parent.parent.parent
    db_path = project_root / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
    
    logger.info(f"🚀 Seeding {limit} trials to {db_path}")
    
    try:
        # 1. Fetch trials from API
        logger.info(f"Fetching {limit} trials from ClinicalTrials.gov API v2...")
        trials = await fetch_ovarian_trials(limit=limit)
        logger.info(f"✅ Fetched {len(trials)} trials")
        
        if len(trials) == 0:
            logger.error("No trials fetched - exiting")
            return 0
        
        # 2. Parse trials (includes relationship data from relationship_parser)
        logger.info("Parsing trials with relationship extraction...")
        parsed_trials = [parse_ctgov_study(s) for s in trials]
        logger.info(f"✅ Parsed {len(parsed_trials)} trials")
        
        # Check relationship data
        sample = parsed_trials[0] if parsed_trials else {}
        if sample.get('pis_json'):
            pis = json.loads(sample['pis_json'])
            logger.info(f"   Sample trial has {len(pis)} PIs")
        if sample.get('orgs_json'):
            orgs = json.loads(sample['orgs_json'])
            logger.info(f"   Sample trial lead sponsor: {orgs.get('lead_sponsor', 'N/A')}")
        if sample.get('sites_json'):
            sites = json.loads(sample['sites_json'])
            logger.info(f"   Sample trial has {len(sites)} sites")
        
        # 3. Insert into SQLite
        logger.info("Inserting into SQLite...")
        insert_trials_batched(parsed_trials)
        logger.info("✅ SQLite insertion complete")
        
        # 4. Verify
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clinical_trials")
        count = cursor.fetchone()[0]
        
        # Check relationship data in DB
        cursor.execute("SELECT COUNT(*) FROM clinical_trials WHERE pis_json IS NOT NULL")
        with_pis = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clinical_trials WHERE orgs_json IS NOT NULL")
        with_orgs = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clinical_trials WHERE sites_json IS NOT NULL")
        with_sites = cursor.fetchone()[0]
        
        conn.close()
        
        logger.info(f"✅ SEEDING COMPLETE - {count} trials in database")
        logger.info(f"   Trials with PI data: {with_pis}")
        logger.info(f"   Trials with org data: {with_orgs}")
        logger.info(f"   Trials with site data: {with_sites}")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50, help="Number of trials to seed")
    args = parser.parse_args()
    
    result = asyncio.run(seed_trials(limit=args.limit))
    sys.exit(0 if result > 0 else 1)

