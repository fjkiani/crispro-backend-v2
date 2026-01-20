"""
Simple Trial Seeding Script - Seeds SQLite with relationship data
Uses Agent 1 seeding infrastructure but focuses on SQLite only (no ChromaDB)
"""
import sys
import asyncio
import sqlite3
import logging
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent.parent / "oncology-backend"
sys.path.insert(0, str(backend_path))

from scripts.agent_1_seeding.api.ctgov_client import fetch_ovarian_trials
from scripts.agent_1_seeding.parsers.study_parser import parse_ctgov_study
from scripts.agent_1_seeding.database.sqlite_client import insert_trials_batched

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def seed_trials(limit: int = 100):
    """Seed SQLite database with trials (includes relationship data from Component 1)."""
    
    # Database path
    db_path = Path(__file__).resolve().parent.parent.parent / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
    
    logger.info(f"🚀 Seeding {limit} trials to {db_path}")
    
    try:
        # 1. Fetch trials from API
        logger.info(f"Fetching {limit} trials from ClinicalTrials.gov API v2...")
        trials = await fetch_ovarian_trials(limit=limit)
        logger.info(f"✅ Fetched {len(trials)} trials")
        
        if len(trials) == 0:
            logger.error("No trials fetched - exiting")
            return
        
        # 2. Parse trials (includes relationship data from relationship_parser)
        logger.info("Parsing trials with relationship extraction...")
        parsed_trials = [parse_ctgov_study(s) for s in trials]
        logger.info(f"✅ Parsed {len(parsed_trials)} trials")
        
        # Check relationship data
        sample = parsed_trials[0] if parsed_trials else {}
        if sample.get('pis_json'):
            import json
            pis = json.loads(sample['pis_json'])
            logger.info(f"   Sample trial has {len(pis)} PIs")
        
        # 3. Insert into SQLite
        logger.info("Inserting into SQLite...")
        insert_trials_batched(parsed_trials)
        logger.info("✅ SQLite insertion complete")
        
        # 4. Verify
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clinical_trials")
        count = cursor.fetchone()[0]
        conn.close()
        
        logger.info(f"✅ SEEDING COMPLETE - {count} trials in database")
        
        return count
        
    except Exception as e:
        logger.error(f"❌ Seeding failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=100, help="Number of trials to seed")
    args = parser.parse_args()
    
    result = asyncio.run(seed_trials(limit=args.limit))
    sys.exit(0 if result > 0 else 1)










