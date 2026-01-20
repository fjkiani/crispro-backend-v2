"""
⚔️ MANAGER'S PLAN - Concern B (R1): Incremental Refresh Queue

R1 — Incremental refresh queue:
- Input: NCT IDs (from candidate discovery + recently viewed + pinned)
- Output: refreshed trial fields in SQLite

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
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta, timezone

# Add parent directory to path for imports
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from api.services.trial_refresh import refresh_trial_status_with_retry
from api.services.database_connections import get_db_connections

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


async def refresh_trials_incremental(
    nct_ids: List[str],
    update_sqlite: bool = True,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    ⚔️ MANAGER'S PLAN - R1: Incremental refresh queue
    
    Refresh trial status and locations for a list of NCT IDs.
    Optionally update SQLite with refreshed data.
    
    Args:
        nct_ids: List of NCT IDs to refresh
        update_sqlite: Whether to update SQLite with refreshed data (default True)
        batch_size: Number of trials to refresh per batch (default 100)
    
    Returns:
        Refresh results dict with stats
    """
    if not nct_ids:
        return {
            "status": "skipped",
            "reason": "No NCT IDs provided",
            "trials_refreshed": 0,
            "trials_failed": 0
        }
    
    logger.info(f"🔄 Starting incremental refresh for {len(nct_ids)} trials")
    
    # Refresh in batches
    all_refreshed = {}
    failed = []
    
    for i in range(0, len(nct_ids), batch_size):
        batch = nct_ids[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(nct_ids) + batch_size - 1) // batch_size
        
        logger.info(f"   Processing batch {batch_num}/{total_batches} ({len(batch)} trials)")
        
        try:
            refreshed = await refresh_trial_status_with_retry(batch)
            all_refreshed.update(refreshed)
            logger.info(f"   ✅ Refreshed {len(refreshed)}/{len(batch)} trials in batch {batch_num}")
        except Exception as e:
            logger.error(f"   ❌ Batch {batch_num} failed: {e}")
            failed.extend(batch)
        
        # Small delay between batches
        if i + batch_size < len(nct_ids):
            await asyncio.sleep(1.0)
    
    # Update SQLite if requested
    if update_sqlite and all_refreshed:
        try:
            db_conn = get_db_connections()
            conn = db_conn.get_sqlite_connection()
            
            if conn:
                cur = conn.cursor()
                updated_count = 0
                
                for nct_id, refreshed_data in all_refreshed.items():
                    try:
                        # Update trial in SQLite
                        status = refreshed_data.get('status', 'UNKNOWN')
                        locations_json = json.dumps(refreshed_data.get('locations', []))
                        last_refreshed_at = refreshed_data.get('last_updated', datetime.now(timezone.utc).isoformat())
                        
                        # Check if trial exists
                        cur.execute("SELECT id FROM trials WHERE id = ?", (nct_id,))
                        if cur.fetchone():
                            # Update existing trial
                            cur.execute("""
                                UPDATE trials
                                SET status = ?,
                                    locations_full_json = ?,
                                    scraped_at = ?
                                WHERE id = ?
                            """, (status, locations_json, last_refreshed_at, nct_id))
                            updated_count += 1
                    except Exception as e:
                        logger.warning(f"   ⚠️ Failed to update SQLite for {nct_id}: {e}")
                
                conn.commit()
                logger.info(f"   💾 Updated {updated_count} trials in SQLite")
            else:
                logger.warning("   ⚠️ SQLite connection unavailable - skipping update")
        except Exception as e:
            logger.error(f"   ❌ SQLite update failed: {e}")
    
    results = {
        "status": "completed",
        "trials_refreshed": len(all_refreshed),
        "trials_failed": len(failed),
        "failed_nct_ids": failed[:20],  # First 20 failures
        "refresh_timestamp": datetime.now(timezone.utc).isoformat()
    }
    
    logger.info(f"✅ Incremental refresh complete: {results['trials_refreshed']}/{len(nct_ids)} refreshed")
    if failed:
        logger.warning(f"   ⚠️ {len(failed)} trials failed to refresh")
    
    return results


async def refresh_displayed_trials(
    days_back: int = 7,
    update_sqlite: bool = True
) -> Dict[str, Any]:
    """
    Refresh trials that were displayed to Ayesha in the last N days.
    
    ⚔️ MANAGER'S PLAN - R1: Refresh jobs for displayed/pinned trials
    
    Args:
        days_back: Number of days to look back for displayed trials (default 7)
        update_sqlite: Whether to update SQLite (default True)
    
    Returns:
        Refresh results dict
    """
    # TODO: Track "displayed" trials in a separate table or log
    # For now, we'll refresh top ovarian/gynecologic trials from SQLite
    # In production, this should track actual displayed trials from API logs
    
    logger.info(f"🔄 Refreshing displayed trials (last {days_back} days)")
    
    db_conn = get_db_connections()
    conn = db_conn.get_sqlite_connection()
    
    if not conn:
        return {
            "status": "failed",
            "reason": "SQLite connection unavailable",
            "trials_refreshed": 0
        }
    
    # Get top ovarian/gynecologic recruiting/active trials (likely displayed)
    cur = conn.cursor()
    cur.execute("""
        SELECT id
        FROM trials
        WHERE (
          lower(coalesce(conditions,'')) LIKE '%ovarian%'
          OR lower(coalesce(conditions,'')) LIKE '%fallopian%'
          OR lower(coalesce(conditions,'')) LIKE '%peritoneal%'
          OR lower(coalesce(title,'')) LIKE '%ovarian%'
        )
        AND (
          lower(coalesce(status,'')) LIKE '%recruiting%'
          OR lower(coalesce(status,'')) LIKE '%active%'
        )
        ORDER BY 
          CASE
            WHEN lower(coalesce(status,'')) LIKE '%recruiting%' THEN 0
            WHEN lower(coalesce(status,'')) LIKE '%active%' THEN 1
            ELSE 2
          END
        LIMIT 100  -- Top 100 likely displayed trials
    """)
    
    displayed_nct_ids = [row[0] for row in cur.fetchall()]
    
    if not displayed_nct_ids:
        logger.warning("⚠️ No displayed trials found")
        return {
            "status": "skipped",
            "reason": "No displayed trials found",
            "trials_refreshed": 0
        }
    
    logger.info(f"   Found {len(displayed_nct_ids)} likely displayed trials")
    
    return await refresh_trials_incremental(displayed_nct_ids, update_sqlite=update_sqlite)


async def refresh_pinned_trials(
    pinned_nct_ids: List[str],
    update_sqlite: bool = True
) -> Dict[str, Any]:
    """
    Refresh pinned trials for Ayesha.
    
    ⚔️ MANAGER'S PLAN - R1: Refresh jobs for displayed/pinned trials
    
    Args:
        pinned_nct_ids: List of pinned NCT IDs
        update_sqlite: Whether to update SQLite (default True)
    
    Returns:
        Refresh results dict
    """
    if not pinned_nct_ids:
        return {
            "status": "skipped",
            "reason": "No pinned trials",
            "trials_refreshed": 0
        }
    
    logger.info(f"🔄 Refreshing {len(pinned_nct_ids)} pinned trials")
    
    return await refresh_trials_incremental(pinned_nct_ids, update_sqlite=update_sqlite)


async def scheduled_refresh_job(
    refresh_displayed: bool = True,
    refresh_pinned: bool = True,
    pinned_nct_ids: Optional[List[str]] = None,
    days_back: int = 7
) -> Dict[str, Any]:
    """
    ⚔️ MANAGER'S PLAN - Background (continuous freshness + enrichment)
    
    Scheduled refresh job for displayed/pinned trials.
    Should be run nightly (or more frequently).
    
    Args:
        refresh_displayed: Whether to refresh displayed trials (default True)
        refresh_pinned: Whether to refresh pinned trials (default True)
        pinned_nct_ids: List of pinned NCT IDs (default None)
        days_back: Days to look back for displayed trials (default 7)
    
    Returns:
        Combined refresh results
    """
    logger.info("=" * 60)
    logger.info("🚀 Scheduled Refresh Job (Manager's Plan - Concern B)")
    logger.info("=" * 60)
    
    results = {
        "job_status": "completed",
        "job_timestamp": datetime.now(timezone.utc).isoformat(),
        "displayed_refresh": None,
        "pinned_refresh": None,
        "total_refreshed": 0
    }
    
    # Refresh displayed trials
    if refresh_displayed:
        try:
            displayed_results = await refresh_displayed_trials(days_back=days_back)
            results["displayed_refresh"] = displayed_results
            results["total_refreshed"] += displayed_results.get("trials_refreshed", 0)
        except Exception as e:
            logger.error(f"❌ Displayed refresh failed: {e}")
            results["displayed_refresh"] = {"status": "failed", "error": str(e)}
    
    # Refresh pinned trials
    if refresh_pinned and pinned_nct_ids:
        try:
            pinned_results = await refresh_pinned_trials(pinned_nct_ids)
            results["pinned_refresh"] = pinned_results
            results["total_refreshed"] += pinned_results.get("trials_refreshed", 0)
        except Exception as e:
            logger.error(f"❌ Pinned refresh failed: {e}")
            results["pinned_refresh"] = {"status": "failed", "error": str(e)}
    
    logger.info(f"✅ Scheduled refresh job complete: {results['total_refreshed']} total trials refreshed")
    logger.info("=" * 60)
    
    return results


def main():
    """Main execution for scheduled refresh job."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Scheduled refresh job for displayed/pinned trials (Manager's Plan - Concern B)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh displayed trials (last 7 days):
  python scheduled_refresh_job.py --refresh-displayed
  
  # Refresh pinned trials:
  python scheduled_refresh_job.py --refresh-pinned --pinned NCT12345 NCT67890
  
  # Full refresh (displayed + pinned):
  python scheduled_refresh_job.py --refresh-displayed --refresh-pinned --pinned NCT12345
        """
    )
    parser.add_argument("--refresh-displayed", action="store_true", help="Refresh displayed trials")
    parser.add_argument("--refresh-pinned", action="store_true", help="Refresh pinned trials")
    parser.add_argument("--pinned", nargs="+", help="Pinned NCT IDs to refresh")
    parser.add_argument("--days-back", type=int, default=7, help="Days to look back for displayed trials (default: 7)")
    args = parser.parse_args()
    
    # Run async function
    results = asyncio.run(scheduled_refresh_job(
        refresh_displayed=args.refresh_displayed or (not args.refresh_pinned and not args.pinned),
        refresh_pinned=args.refresh_pinned,
        pinned_nct_ids=args.pinned,
        days_back=args.days_back
    ))
    
    # Print results
    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()

