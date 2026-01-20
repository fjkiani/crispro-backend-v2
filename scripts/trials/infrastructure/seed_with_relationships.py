"""
Seed Trials with Relationship Data - Direct implementation
Fetches from API, parses with relationship extraction, inserts to SQLite
Avoids ChromaDB dependency
"""
import sys
import asyncio
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Direct imports to avoid ChromaDB
project_root = Path(__file__).resolve().parent.parent.parent.parent
backend_path = project_root / "oncology-coPilot" / "oncology-backend"
sys.path.insert(0, str(backend_path))

# Import modules directly (bypass __init__ that imports chromadb)
import importlib.util

# Import ctgov_client
spec1 = importlib.util.spec_from_file_location(
    "ctgov_client",
    backend_path / "scripts" / "agent_1_seeding" / "api" / "ctgov_client.py"
)
ctgov = importlib.util.module_from_spec(spec1)
sys.modules["ctgov_client"] = ctgov
spec1.loader.exec_module(ctgov)

# Import study_parser (which imports relationship_parser)
spec2 = importlib.util.spec_from_file_location(
    "study_parser",
    backend_path / "scripts" / "agent_1_seeding" / "parsers" / "study_parser.py"
)
parser = importlib.util.module_from_spec(spec2)
sys.modules["study_parser"] = parser

# Temporarily mock chromadb for relationship_parser imports
sys.modules["chromadb"] = type(sys)('chromadb')

spec2.loader.exec_module(parser)

fetch_ovarian_trials = ctgov.fetch_ovarian_trials
parse_ctgov_study = parser.parse_ctgov_study

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def insert_trials(trials: List[Dict[str, Any]]) -> None:
    """Insert trials into SQLite."""
    db_path = project_root / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        for trial in trials:
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
        logger.info(f"✅ Inserted {len(trials)} trials")
        
    finally:
        conn.close()


async def main(limit: int = 50):
    """Main seeding function."""
    logger.info(f"🚀 Seeding {limit} trials with relationship data...")
    
    try:
        # Fetch from API
        logger.info("Fetching trials from ClinicalTrials.gov API v2...")
        trials = await fetch_ovarian_trials(limit=limit)
        logger.info(f"✅ Fetched {len(trials)} trials")
        
        # Parse with relationship extraction
        logger.info("Parsing trials (includes relationship extraction)...")
        parsed = [parse_ctgov_study(s) for s in trials]
        logger.info(f"✅ Parsed {len(parsed)} trials")
        
        # Check relationship data
        sample = parsed[0] if parsed else {}
        if sample.get('pis_json'):
            pis = json.loads(sample['pis_json'])
            logger.info(f"   Sample: {len(pis)} PIs")
        if sample.get('orgs_json'):
            orgs = json.loads(sample['orgs_json'])
            logger.info(f"   Sample lead sponsor: {orgs.get('lead_sponsor', 'N/A')}")
        
        # Insert
        logger.info("Inserting into SQLite...")
        insert_trials(parsed)
        
        # Verify
        db_path = project_root / "oncology-coPilot" / "oncology-backend" / "backend" / "data" / "clinical_trials.db"
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM clinical_trials")
        count = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM clinical_trials WHERE pis_json IS NOT NULL")
        with_pis = cursor.fetchone()[0]
        conn.close()
        
        logger.info(f"✅ SEEDING COMPLETE - {count} trials, {with_pis} with PI data")
        return count
        
    except Exception as e:
        logger.error(f"❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return 0


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=50)
    args = parser.parse_args()
    
    result = asyncio.run(main(limit=args.limit))
    sys.exit(0 if result > 0 else 1)










