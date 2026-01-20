"""
Bulk Seed Clinical Trials - Scale from 1,200 to 5,000-10,000 trials

Strategy:
1. Use multiple query strategies to get diverse trials
2. Seed across different cancer types, not just ovarian
3. Handle rate limiting (2 req/sec)
4. Track progress and avoid duplicates
5. Run in batches to reach target

Target: 5,000-10,000 trials by tomorrow
Current: ~1,200 trials
Needed: 3,800-8,800 more trials
"""
import sys
import asyncio
import sqlite3
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import time

# Add paths
project_root = Path(__file__).resolve().parent.parent.parent.parent
backend_path = project_root / "oncology-coPilot" / "oncology-backend"
sys.path.insert(0, str(backend_path))
agent_1_path = backend_path / "scripts" / "agent_1_seeding"
sys.path.insert(0, str(agent_1_path.parent))

# Add minimal backend to path for CTGovQueryBuilder
minimal_backend_path = project_root / "oncology-coPilot" / "oncology-backend-minimal"
sys.path.insert(0, str(minimal_backend_path))

from agent_1_seeding.parsers.study_parser import parse_ctgov_study
from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Database path
DB_PATH = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"

# Query strategies for diverse trial collection
QUERY_STRATEGIES = [
    # Ovarian cancer (existing focus)
    {
        "name": "Ovarian Cancer - Recruiting",
        "condition": "ovarian cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 2000
    },
    {
        "name": "Ovarian Cancer - All Status",
        "condition": "ovarian cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING", "ACTIVE_NOT_RECRUITING", "COMPLETED"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 1500
    },
    # Breast cancer (high volume)
    {
        "name": "Breast Cancer - Recruiting",
        "condition": "breast cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 2000
    },
    # Lung cancer (high volume)
    {
        "name": "Lung Cancer - Recruiting",
        "condition": "lung cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 2000
    },
    # Colorectal cancer
    {
        "name": "Colorectal Cancer - Recruiting",
        "condition": "colorectal cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 1000
    },
    # Pancreatic cancer
    {
        "name": "Pancreatic Cancer - Recruiting",
        "condition": "pancreatic cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 800
    },
    # DNA repair focused
    {
        "name": "DNA Repair - PARP Inhibitors",
        "condition": "cancer",
        "intervention": "PARP inhibitor",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 1000
    },
    {
        "name": "DNA Repair - ATR Inhibitors",
        "condition": "cancer",
        "intervention": "ATR inhibitor",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 500
    },
    # Immunotherapy
    {
        "name": "Immunotherapy - Checkpoint Inhibitors",
        "condition": "cancer",
        "intervention": "checkpoint inhibitor",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 1500
    },
    # Basket trials
    {
        "name": "Basket Trials - Tumor Agnostic",
        "keyword": "basket trial tumor agnostic",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 500
    },
    # Precision medicine
    {
        "name": "Precision Medicine - Biomarker Driven",
        "keyword": "precision medicine biomarker",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 800
    },
    # Rare mutations
    {
        "name": "Rare Mutations - MBD4",
        "keyword": "MBD4 mutation",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 200
    },
    {
        "name": "Rare Mutations - TP53",
        "keyword": "TP53 mutation",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 500
    },
    # High TMB / MSI-H
    {
        "name": "High TMB / MSI-H",
        "keyword": "TMB MSI-H hypermutator",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE1", "PHASE2", "PHASE3"],
        "limit": 400
    },
    # Phase 2/3 only (more mature)
    {
        "name": "Phase 2/3 - All Cancers",
        "condition": "cancer",
        "status": ["RECRUITING", "NOT_YET_RECRUITING"],
        "phases": ["PHASE2", "PHASE3"],
        "limit": 2000
    },
]


def get_existing_nct_ids() -> Set[str]:
    """Get all existing NCT IDs from database to avoid duplicates."""
    if not DB_PATH.exists():
        return set()
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id FROM trials")
        nct_ids = {row[0] for row in cursor.fetchall()}
        logger.info(f"Found {len(nct_ids)} existing trials in database")
        return nct_ids
    finally:
        conn.close()


def transform_to_trials_schema(parsed_trial: Dict[str, Any], raw_study: Dict[str, Any]) -> Dict[str, Any]:
    """Transform parsed trial to trials table schema."""
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
    
    conditions = parsed_trial.get('disease_category', 'cancer')
    if isinstance(conditions, str):
        conditions_json = json.dumps([conditions])
    else:
        conditions_json = json.dumps(conditions) if conditions else json.dumps(['cancer'])
    
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


def insert_trials_batched(trials: List[Dict[str, Any]], batch_size: int = 50) -> int:
    """Insert trials into 'trials' table in batches. Returns count inserted."""
    if not DB_PATH.exists():
        logger.error(f"Database not found: {DB_PATH}")
        return 0
    
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    inserted = 0
    try:
        for i in range(0, len(trials), batch_size):
            batch = trials[i:i + batch_size]
            
            for trial in batch:
                try:
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
                    inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert trial {trial.get('id', 'UNKNOWN')}: {e}")
            
            conn.commit()
            logger.info(f"   Inserted batch {i//batch_size + 1} ({min(i+batch_size, len(trials))}/{len(trials)} trials)")
        
    finally:
        conn.close()
    
    return inserted


async def execute_strategy(strategy: Dict[str, Any], existing_nct_ids: Set[str]) -> int:
    """
    Execute a single query strategy and return number of new trials added.
    
    Uses simplified API queries (no filters) and filters in post-processing,
    as the API v2 may not support complex filter combinations.
    
    Args:
        strategy: Query strategy dictionary
        existing_nct_ids: Set of existing NCT IDs to avoid duplicates
        
    Returns:
        Number of new trials added
    """
    name = strategy.get("name", "Unknown")
    limit = strategy.get("limit", 1000)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"📋 Strategy: {name}")
    logger.info(f"   Target: {limit} trials")
    logger.info(f"{'='*60}")
    
    try:
        # Build simplified query (API v2 doesn't support complex filters reliably)
        # We'll filter in post-processing instead
        builder = CTGovQueryBuilder()
        
        # Build query term from condition/keyword/intervention
        query_terms = []
        if strategy.get("condition"):
            query_terms.append(strategy["condition"])
        if strategy.get("keyword"):
            query_terms.append(strategy["keyword"])
        if strategy.get("intervention"):
            query_terms.append(strategy["intervention"])
        
        if query_terms:
            # Use query.term for simple text search
            builder.add_keyword(" ".join(query_terms))
        else:
            # Fallback to generic cancer search
            builder.add_keyword("cancer")
        
        # Don't add filters to API call - filter in post-processing
        # builder.add_status(strategy.get("status", []))
        # builder.add_phase(strategy.get("phases", []))
        # builder.add_study_type("INTERVENTIONAL")
        
        # Execute query (fetch more than needed, we'll filter)
        fetch_limit = min(limit * 3, 5000)  # Fetch 3x to account for filtering
        logger.info(f"   Fetching up to {fetch_limit} trials from API (will filter to {limit})...")
        raw_trials = await execute_query(builder, max_results=fetch_limit)
        logger.info(f"   ✅ Fetched {len(raw_trials)} raw trials")
        
        if len(raw_trials) == 0:
            logger.warning(f"   ⚠️ No trials fetched for strategy: {name}")
            return 0
        
        # Filter by status, phase, and study type in post-processing
        filtered_trials = []
        status_filter = strategy.get("status", [])
        phases_filter = strategy.get("phases", [])
        
        for raw_trial in raw_trials:
            # Extract trial info
            protocol = raw_trial.get("protocolSection", {})
            ident = protocol.get("identificationModule", {})
            status_module = protocol.get("statusModule", {})
            design_module = protocol.get("designModule", {})
            
            nct_id = ident.get("nctId")
            if not nct_id:
                continue
            
            # Filter by status
            overall_status = status_module.get("overallStatus", "")
            if status_filter and overall_status not in status_filter:
                continue
            
            # Filter by phase
            phase_info = design_module.get("phases", [])
            if phases_filter:
                phase_match = any(phase in phases_filter for phase in phase_info)
                if not phase_match:
                    continue
            
            # Filter by study type
            study_type = design_module.get("studyType", "")
            if study_type != "INTERVENTIONAL":
                continue
            
            # Skip if already exists
            if nct_id in existing_nct_ids:
                continue
            
            filtered_trials.append(raw_trial)
        
        logger.info(f"   📊 Filtered: {len(filtered_trials)}/{len(raw_trials)} match criteria")
        
        # Limit to target
        new_trials = filtered_trials[:limit]
        logger.info(f"   📊 New trials: {len(new_trials)} (limited to {limit})")
        
        if len(new_trials) == 0:
            logger.info(f"   ⏭️ All trials already exist, skipping")
            return 0
        
        # Parse trials
        logger.info(f"   Parsing {len(new_trials)} trials...")
        parsed_trials = []
        for i, raw_trial in enumerate(new_trials):
            try:
                parsed = parse_ctgov_study(raw_trial)
                parsed_trials.append((parsed, raw_trial))
                if (i + 1) % 100 == 0:
                    logger.info(f"      Parsed {i + 1}/{len(new_trials)}...")
            except Exception as e:
                nct_id = raw_trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId", "UNKNOWN")
                logger.warning(f"      Failed to parse {nct_id}: {e}")
        
        logger.info(f"   ✅ Parsed {len(parsed_trials)}/{len(new_trials)} trials")
        
        # Transform to schema
        logger.info(f"   Transforming to trials schema...")
        transformed_trials = [
            transform_to_trials_schema(parsed, raw)
            for parsed, raw in parsed_trials
        ]
        
        # Update existing_nct_ids as we go
        for trial in transformed_trials:
            existing_nct_ids.add(trial.get('id', ''))
        
        # Insert into database
        logger.info(f"   Inserting into database...")
        inserted = insert_trials_batched(transformed_trials)
        logger.info(f"   ✅ Inserted {inserted} new trials")
        
        return inserted
        
    except Exception as e:
        logger.error(f"   ❌ Strategy '{name}' failed: {e}", exc_info=True)
        return 0


async def bulk_seed_trials(target_count: int = 10000, max_strategies: Optional[int] = None):
    """
    Bulk seed trials using multiple query strategies.
    
    Args:
        target_count: Target total number of trials
        max_strategies: Maximum number of strategies to run (None = all)
    """
    logger.info(f"\n{'='*60}")
    logger.info(f"🚀 BULK TRIAL SEEDING")
    logger.info(f"   Target: {target_count} total trials")
    logger.info(f"{'='*60}\n")
    
    # Get existing trials
    existing_nct_ids = get_existing_nct_ids()
    initial_count = len(existing_nct_ids)
    logger.info(f"📊 Current database: {initial_count} trials")
    logger.info(f"📊 Need to add: {target_count - initial_count} more trials\n")
    
    if initial_count >= target_count:
        logger.info(f"✅ Already at target ({initial_count} >= {target_count})")
        return
    
    # Select strategies
    strategies = QUERY_STRATEGIES
    if max_strategies:
        strategies = strategies[:max_strategies]
    
    logger.info(f"📋 Running {len(strategies)} query strategies...\n")
    
    # Track progress
    total_added = 0
    strategy_results = []
    
    start_time = time.time()
    
    # Execute strategies sequentially (rate limiting handled in execute_query)
    for i, strategy in enumerate(strategies, 1):
        logger.info(f"\n[{i}/{len(strategies)}] Processing strategy...")
        
        added = await execute_strategy(strategy, existing_nct_ids)
        total_added += added
        
        strategy_results.append({
            "name": strategy.get("name", "Unknown"),
            "added": added,
            "target": strategy.get("limit", 1000)
        })
        
        # Check if we've reached target
        current_count = initial_count + total_added
        if current_count >= target_count:
            logger.info(f"\n✅ Reached target! ({current_count} >= {target_count})")
            break
        
        # Progress update
        logger.info(f"\n📊 Progress: {current_count}/{target_count} trials ({current_count/target_count*100:.1f}%)")
        logger.info(f"   Added this run: {total_added} new trials")
        
        # Small delay between strategies
        await asyncio.sleep(1)
    
    elapsed = time.time() - start_time
    
    # Final verification
    final_nct_ids = get_existing_nct_ids()
    final_count = len(final_nct_ids)
    
    logger.info(f"\n{'='*60}")
    logger.info(f"✅ BULK SEEDING COMPLETE")
    logger.info(f"{'='*60}")
    logger.info(f"   Initial count: {initial_count}")
    logger.info(f"   Final count: {final_count}")
    logger.info(f"   Added: {total_added} new trials")
    logger.info(f"   Time elapsed: {elapsed/60:.1f} minutes")
    logger.info(f"   Rate: {total_added/(elapsed/60):.1f} trials/minute")
    
    logger.info(f"\n📋 Strategy Results:")
    for result in strategy_results:
        logger.info(f"   {result['name']}: +{result['added']} trials (target: {result['target']})")
    
    # Check recruiting status
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM trials WHERE status LIKE '%RECRUITING%'")
    recruiting_count = cursor.fetchone()[0]
    conn.close()
    
    logger.info(f"\n📊 Final Statistics:")
    logger.info(f"   Total trials: {final_count}")
    logger.info(f"   Recruiting: {recruiting_count}")
    logger.info(f"   Other status: {final_count - recruiting_count}")
    
    if final_count < target_count:
        logger.warning(f"\n⚠️ Did not reach target ({final_count} < {target_count})")
        logger.warning(f"   Consider running additional strategies or increasing limits")
    else:
        logger.info(f"\n🎉 Successfully reached target!")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Bulk seed clinical trials")
    parser.add_argument("--target", type=int, default=10000, help="Target total number of trials")
    parser.add_argument("--max-strategies", type=int, default=None, help="Maximum number of strategies to run")
    args = parser.parse_args()
    
    asyncio.run(bulk_seed_trials(target_count=args.target, max_strategies=args.max_strategies))

