"""
⚔️ MANAGER'S PLAN - Plumber Execution Script

Combines all Plumber tasks into a single executable script:
1. Incremental tagging via checksum + batch prompting (T1)
2. Automated QA (T4)
3. Scheduled refresh jobs (R1)

Background (continuous freshness + enrichment):
- Nightly (or more frequent) jobs:
  - Refresh jobs for displayed/pinned trials
  - Tagging jobs for curated corpora and changed trials
  - Optional: reseed corpora from CT.gov on schedule

Author: Zo (for Plumber)
Date: January 9, 2025
"""

import asyncio
import json
import logging
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api.services.database_connections import get_db_connections

# Import Plumber modules
try:
    from tagging_incremental import get_incremental_tagging_candidates, run_automated_qa
    from scheduled_refresh_job import scheduled_refresh_job, refresh_trials_incremental
    from tag_trials_moa_batch import tag_trials_moa_batch
except ImportError:
    # Fallback for direct execution
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from tagging_incremental import get_incremental_tagging_candidates, run_automated_qa
    from scheduled_refresh_job import scheduled_refresh_job, refresh_trials_incremental
    from tag_trials_moa_batch import tag_trials_moa_batch

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def plumber_nightly_job(
    refresh_trials: bool = True,
    tag_trials: bool = True,
    tag_limit: int = 200,
    corpus_nct_ids: Optional[List[str]] = None,
    pinned_nct_ids: Optional[List[str]] = None,
    days_back: int = 7
) -> Dict[str, Any]:
    """
    ⚔️ MANAGER'S PLAN - Background (continuous freshness + enrichment)
    
    Nightly (or more frequent) job that:
    - Refreshes displayed/pinned trials (R1)
    - Tags curated corpora and changed trials (T1 + T4)
    
    Args:
        refresh_trials: Whether to refresh trials (default True)
        tag_trials: Whether to tag trials (default True)
        tag_limit: Maximum trials to tag (default 200)
        corpus_nct_ids: Corpus NCT IDs for priority tagging (e.g., Ayesha corpus)
        pinned_nct_ids: Pinned NCT IDs to refresh
        days_back: Days to look back for displayed trials (default 7)
    
    Returns:
        Combined execution results
    """
    logger.info("=" * 60)
    logger.info("🚀 Plumber Nightly Job (Manager's Plan)")
    logger.info("=" * 60)
    
    results = {
        "job_status": "completed",
        "job_timestamp": datetime.now(timezone.utc).isoformat(),
        "refresh_results": None,
        "tagging_results": None
    }
    
    # Step 1: Refresh trials (R1)
    if refresh_trials:
        logger.info("\n📋 Step 1: Refreshing trials (R1 - Incremental refresh queue)")
        try:
            refresh_results = await scheduled_refresh_job(
                refresh_displayed=True,
                refresh_pinned=bool(pinned_nct_ids),
                pinned_nct_ids=pinned_nct_ids,
                days_back=days_back
            )
            results["refresh_results"] = refresh_results
            logger.info(f"✅ Refresh complete: {refresh_results.get('total_refreshed', 0)} trials refreshed")
        except Exception as e:
            logger.error(f"❌ Refresh failed: {e}")
            results["refresh_results"] = {"status": "failed", "error": str(e)}
    
    # Step 2: Tag trials (T1 + T4)
    if tag_trials:
        logger.info("\n📋 Step 2: Tagging trials (T1 - Incremental tagging + T4 - Automated QA)")
        try:
            # Get incremental candidates
            db_path = str(Path(__file__).resolve().parent.parent.parent / "data" / "clinical_trials.db")
            vectors_path = str(Path(__file__).resolve().parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json")
            
            candidates, selection_stats = get_incremental_tagging_candidates(
                db_path=db_path,
                existing_vectors_path=vectors_path,
                corpus_nct_ids=corpus_nct_ids,
                confidence_threshold=0.7,
                max_candidates=tag_limit
            )
            
            if candidates:
                # Tag candidates using batch tagging script
                tagged = await tag_trials_moa_batch(
                    trial_nct_ids=[c.get('nct_id') for c in candidates[:tag_limit]],
                    limit=tag_limit,
                    batch_size=50,
                    use_incremental=True,  # Already selected incrementally
                    corpus_nct_ids=corpus_nct_ids,
                    confidence_threshold=0.7,
                    run_qa=True
                )
                
                results["tagging_results"] = {
                    "status": "completed",
                    "candidates_selected": len(candidates),
                    "selection_stats": selection_stats,
                    "trials_tagged": len(tagged),
                    "tagged_nct_ids": list(tagged.keys())
                }
                logger.info(f"✅ Tagging complete: {len(tagged)} trials tagged")
            else:
                logger.info("ℹ️  No trials need tagging (all up-to-date)")
                results["tagging_results"] = {
                    "status": "skipped",
                    "reason": "No candidates need tagging",
                    "selection_stats": selection_stats
                }
        except Exception as e:
            logger.error(f"❌ Tagging failed: {e}")
            results["tagging_results"] = {"status": "failed", "error": str(e)}
    
    logger.info("\n" + "=" * 60)
    logger.info(f"✅ Plumber nightly job complete")
    logger.info("=" * 60)
    
    return results


def main():
    """Main execution for Plumber nightly job."""
    parser = argparse.ArgumentParser(
        description="Plumber Nightly Job - Refresh + Tagging (Manager's Plan)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Full nightly job (refresh + tag):
  python plumber_execution.py
  
  # Refresh only:
  python plumber_execution.py --no-tag
  
  # Tag only:
  python plumber_execution.py --no-refresh
  
  # With Ayesha corpus:
  python plumber_execution.py --corpus NCT04284969 NCT04001023
  
  # With pinned trials:
  python plumber_execution.py --pinned NCT12345 NCT67890
        """
    )
    parser.add_argument("--no-refresh", action="store_true", help="Skip refresh step")
    parser.add_argument("--no-tag", action="store_true", help="Skip tagging step")
    parser.add_argument("--tag-limit", type=int, default=200, help="Maximum trials to tag (default: 200)")
    parser.add_argument("--corpus", nargs="+", help="Corpus NCT IDs for priority tagging (e.g., Ayesha corpus)")
    parser.add_argument("--pinned", nargs="+", help="Pinned NCT IDs to refresh")
    parser.add_argument("--days-back", type=int, default=7, help="Days to look back for displayed trials (default: 7)")
    args = parser.parse_args()
    
    # Run async function
    results = asyncio.run(plumber_nightly_job(
        refresh_trials=not args.no_refresh,
        tag_trials=not args.no_tag,
        tag_limit=args.tag_limit,
        corpus_nct_ids=args.corpus,
        pinned_nct_ids=args.pinned,
        days_back=args.days_back
    ))
    
    # Print results
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

