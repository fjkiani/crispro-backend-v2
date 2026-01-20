"""
Ayesha Targeted Trial Fetch

Fetch 50 ovarian cancer trials using targeted queries from disease module config.
Compare with existing trials to measure quality improvements.
"""

import sys
import asyncio
import json
import yaml
import sqlite3
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query

# Initialize logging
import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DB_PATH = backend_root / "data" / "clinical_trials.db"
DISEASE_MODULE_PATH = backend_root / "api" / "resources" / "disease_modules" / "ovarian.yaml"


async def fetch_targeted_trials(max_trials_per_query: int = 10, total_target: int = 50) -> List[Dict[str, Any]]:
    """
    Fetch trials using targeted queries from disease module config.
    
    Args:
        max_trials_per_query: Max trials to fetch per query template
        total_target: Total number of unique trials to fetch
    
    Returns:
        List of unique trials (deduped)
    """
    # Load ovarian disease module
    if not DISEASE_MODULE_PATH.exists():
        raise FileNotFoundError(f"Disease module not found: {DISEASE_MODULE_PATH}")
    
    with open(DISEASE_MODULE_PATH) as f:
        disease_module = yaml.safe_load(f)
    
    query_templates = disease_module.get('query_templates', [])
    
    # Filter to high-priority templates
    high_priority_templates = [t for t in query_templates if t.get('priority') == 'high']
    
    logger.info(f"📋 Using {len(high_priority_templates)} high-priority query templates")
    
    all_trials = []
    nct_ids_seen = set()
    
    # Execute each query template
    for i, template in enumerate(high_priority_templates, 1):
        query_text = template.get('query', '')
        template_name = template.get('name', f'Template {i}')
        
        logger.info(f"🔍 Query {i}/{len(high_priority_templates)}: {template_name}")
        logger.info(f"   Query: {query_text[:100]}...")
        
        try:
            # Build CT.gov query
            builder = CTGovQueryBuilder()
            
            # Parse query text (simple approach - split by AND/OR)
            # For now, use add_condition for ovarian cancer
            if "ovarian cancer" in query_text.lower() or "ovarian" in query_text.lower():
                builder.add_condition("ovarian cancer")
            
            # Add status filter
            builder.add_status(["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING"])
            
            # Execute query
            trials = await execute_query(builder, max_results=max_trials_per_query)
            
            # Dedupe
            new_trials = []
            for trial in trials:
                nct_id = trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                if nct_id and nct_id not in nct_ids_seen:
                    nct_ids_seen.add(nct_id)
                    new_trials.append(trial)
                    all_trials.append(trial)
            
            logger.info(f"   ✅ Found {len(new_trials)} new trials (total: {len(all_trials)})")
            
            # Stop if we have enough
            if len(all_trials) >= total_target:
                logger.info(f"✅ Reached target of {total_target} trials")
                break
                
        except Exception as e:
            logger.error(f"   ❌ Error executing query: {e}")
            continue
    
    logger.info(f"✅ Total unique trials fetched: {len(all_trials)}")
    return all_trials[:total_target]


async def compare_quality(new_trials: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compare new trials with existing trials in database.
    
    Returns comparison metrics.
    """
    # Get existing trials
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, conditions, interventions, status
        FROM trials 
        WHERE status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING')
        AND (LOWER(conditions) LIKE '%ovarian%' OR LOWER(title) LIKE '%ovarian%')
    """)
    existing_trials = cursor.fetchall()
    existing_nct_ids = {t[0] for t in existing_trials}
    
    # Extract NCT IDs from new trials
    new_nct_ids = set()
    for trial in new_trials:
        nct_id = trial.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
        if nct_id:
            new_nct_ids.add(nct_id)
    
    # Compare
    overlap = new_nct_ids.intersection(existing_nct_ids)
    truly_new = new_nct_ids - existing_nct_ids
    
    # Keyword analysis
    keywords = ["PARP", "TP53", "PD-L1", "MBD4", "BER", "DDR", "ATR", "WEE1", "olaparib", "pembrolizumab"]
    
    new_keyword_counts = {}
    existing_keyword_counts = {}
    
    # Count keywords in new trials (titles)
    for trial in new_trials:
        title = trial.get("protocolSection", {}).get("identificationModule", {}).get("briefTitle", "").upper()
        for keyword in keywords:
            if keyword.upper() in title:
                new_keyword_counts[keyword] = new_keyword_counts.get(keyword, 0) + 1
    
    # Count keywords in existing trials
    for trial in existing_trials:
        title = (trial[1] or "").upper()
        for keyword in keywords:
            if keyword.upper() in title:
                existing_keyword_counts[keyword] = existing_keyword_counts.get(keyword, 0) + 1
    
    comparison = {
        "existing_total": len(existing_trials),
        "new_total": len(new_trials),
        "overlap": len(overlap),
        "truly_new": len(truly_new),
        "keyword_counts_new": new_keyword_counts,
        "keyword_counts_existing": existing_keyword_counts,
    }
    
    conn.close()
    return comparison


async def main():
    """Main entry point."""
    logger.info("🚀 Starting Ayesha targeted trial fetch (50 trials)")
    logger.info("=" * 80)
    
    try:
        # Fetch targeted trials
        new_trials = await fetch_targeted_trials(max_trials_per_query=10, total_target=50)
        
        logger.info(f"✅ Fetched {len(new_trials)} trials")
        
        # Compare quality
        comparison = await compare_quality(new_trials)
        
        logger.info("=" * 80)
        logger.info("📊 QUALITY COMPARISON")
        logger.info("=" * 80)
        logger.info(f"Existing trials: {comparison['existing_total']}")
        logger.info(f"New trials: {comparison['new_total']}")
        logger.info(f"Overlap: {comparison['overlap']}")
        logger.info(f"Truly new: {comparison['truly_new']}")
        logger.info("")
        logger.info("Keyword counts (new vs existing):")
        for keyword in ["PARP", "TP53", "PD-L1", "MBD4", "BER", "DDR", "ATR", "WEE1"]:
            new_count = comparison['keyword_counts_new'].get(keyword, 0)
            existing_count = comparison['keyword_counts_existing'].get(keyword, 0)
            new_pct = (new_count / len(new_trials) * 100) if new_trials else 0
            existing_pct = (existing_count / comparison['existing_total'] * 100) if comparison['existing_total'] else 0
            logger.info(f"  {keyword:10s}: New={new_count:2d} ({new_pct:4.1f}%) | Existing={existing_count:2d} ({existing_pct:4.1f}%)")
        
        logger.info("=" * 80)
        logger.info("✅ Comparison complete!")
        
    except Exception as e:
        logger.error(f"❌ Error: {e}", exc_info=True)


if __name__ == "__main__":
    asyncio.run(main())
