"""
⚔️ PRODUCTION - Concern B: Refresh Agent (R1)

Purpose: Ensure trial status and locations are fresh (last_refreshed_at + stale flags).

Non-negotiables (Manager's Plan):
- R1: Incremental refresh queue (bounded, prioritized)
- SLA policies (displayed/pinned trials refreshed nightly)
- last_refreshed_at + stale flags (explicit freshness tracking)
- Bounded refresh on login (top K displayed trials)

Consolidated from:
- scheduled_refresh_job.py (R1)
- extract_fresh_recruiting_trials.py (if applicable)

Source of Truth: .cursor/ayesha/TRIAL_TAGGING_ANALYSIS_AND_NEXT_ROADBLOCK.md (lines 491-537)
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
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent.parent.parent))

# Try to import refresh service
try:
    from api.services.trial_refresh import refresh_trial_status_with_retry
    REFRESH_AVAILABLE = True
except ImportError:
    REFRESH_AVAILABLE = False
    logger.warning("⚠️ Trial refresh service not available")

# Try to import database connections
try:
    from api.services.database_connections import get_db_connections
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logger.warning("⚠️ Database connections not available")

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ⚔️ FIX: Paths - Correct calculation
# File: scripts/trials/production/core/refresh_agent.py
# From: oncology-backend-minimal/
SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent  # scripts/trials/
BACKEND_ROOT = SCRIPT_DIR.parent.parent  # Correct: oncology-backend-minimal/ (not oncology-coPilot/)
DB_PATH = BACKEND_ROOT / "data" / "clinical_trials.db"

# SLA thresholds
STALE_THRESHOLD_DAYS = 7  # Trials older than 7 days are considered stale
PRIORITY_REFRESH_THRESHOLD_DAYS = 1  # Priority trials (displayed/pinned) refreshed daily


async def refresh_trials_incremental(
    nct_ids: List[str],
    update_sqlite: bool = True,
    batch_size: int = 100
) -> Dict[str, Any]:
    """
    ⚔️ R1: Incremental refresh queue
    
    Refresh trial status and locations for a list of NCT IDs.
    Updates last_refreshed_at and stale flags in SQLite.
    
    Args:
        nct_ids: List of NCT IDs to refresh
        update_sqlite: Whether to update SQLite (default True)
        batch_size: Number of trials per batch (default 100)
    
    Returns:
        Refresh results dict with stats
    """
    if not REFRESH_AVAILABLE:
        return {
            "status": "failed",
            "reason": "Trial refresh service not available",
            "trials_refreshed": 0
        }
    
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
        updated_count = _update_sqlite_with_refreshed_data(all_refreshed)
        logger.info(f"   💾 Updated {updated_count} trials in SQLite")
    
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


def _update_sqlite_with_refreshed_data(refreshed_data: Dict[str, Dict[str, Any]]) -> int:
    """
    Update SQLite with refreshed trial data (status, locations, last_refreshed_at, stale flags).
    
    Args:
        refreshed_data: Dict mapping NCT ID to refreshed trial data
    
    Returns:
        Number of trials updated
    """
    if not DB_AVAILABLE:
        return 0
    
    try:
        db_conn = get_db_connections()
        conn = db_conn.get_sqlite_connection()
        
        if not conn:
            logger.warning("   ⚠️ SQLite connection unavailable - skipping update")
            return 0
        
        cur = conn.cursor()
        updated_count = 0
        now_utc = datetime.now(timezone.utc)
        
        for nct_id, refreshed_trial in refreshed_data.items():
            try:
                status = refreshed_trial.get('status', 'UNKNOWN')
                locations = refreshed_trial.get('locations', [])
                locations_json = json.dumps(locations) if locations else None
                last_refreshed_at = refreshed_trial.get('last_updated') or now_utc.isoformat()
                
                # Compute stale flag (trials older than STALE_THRESHOLD_DAYS are stale)
                try:
                    last_refreshed_dt = datetime.fromisoformat(last_refreshed_at.replace('Z', '+00:00'))
                    age_days = (now_utc.replace(tzinfo=timezone.utc) - last_refreshed_dt.replace(tzinfo=timezone.utc)).days
                    is_stale = age_days > STALE_THRESHOLD_DAYS
                except Exception:
                    is_stale = True  # If we can't parse date, assume stale
                
                # Check if trial exists
                cur.execute("SELECT id FROM trials WHERE id = ?", (nct_id,))
                if cur.fetchone():
                    # Update existing trial
                    cur.execute("""
                        UPDATE trials
                        SET status = ?,
                            locations_full_json = ?,
                            scraped_at = ?,
                            last_refreshed_at = ?,
                            is_stale = ?
                        WHERE id = ?
                    """, (status, locations_json, last_refreshed_at, last_refreshed_at, 1 if is_stale else 0, nct_id))
                    updated_count += 1
                else:
                    # Insert new trial (if needed)
                    logger.warning(f"   ⚠️ Trial {nct_id} not found in SQLite - skipping insert (not in scope)")
            
            except Exception as e:
                logger.warning(f"   ⚠️ Failed to update SQLite for {nct_id}: {e}")
        
        conn.commit()
        return updated_count
    
    except Exception as e:
        logger.error(f"   ❌ SQLite update failed: {e}")
        return 0


def get_stale_trials(
    nct_ids: Optional[List[str]] = None,
    threshold_days: int = STALE_THRESHOLD_DAYS
) -> List[str]:
    """
    Get list of stale NCT IDs (older than threshold_days or missing last_refreshed_at).
    
    Args:
        nct_ids: Optional list of NCT IDs to check (if None, checks all trials)
        threshold_days: Stale threshold in days (default STALE_THRESHOLD_DAYS)
    
    Returns:
        List of stale NCT IDs
    """
    if not DB_AVAILABLE:
        return []
    
    try:
        db_conn = get_db_connections()
        conn = db_conn.get_sqlite_connection()
        
        if not conn:
            return []
        
        cur = conn.cursor()
        now_utc = datetime.now(timezone.utc)
        threshold_date = (now_utc - timedelta(days=threshold_days)).isoformat()
        
        if nct_ids:
            # Check specific NCT IDs
            placeholders = ','.join(['?'] * len(nct_ids))
            cur.execute(f"""
                SELECT id
                FROM trials
                WHERE id IN ({placeholders})
                AND (
                    last_refreshed_at IS NULL
                    OR last_refreshed_at < ?
                    OR is_stale = 1
                )
            """, (*nct_ids, threshold_date))
        else:
            # Check all trials
            cur.execute("""
                SELECT id
                FROM trials
                WHERE (
                    last_refreshed_at IS NULL
                    OR last_refreshed_at < ?
                    OR is_stale = 1
                )
            """, (threshold_date,))
        
        stale_nct_ids = [row[0] for row in cur.fetchall()]
        return stale_nct_ids
    
    except Exception as e:
        logger.error(f"❌ Failed to get stale trials: {e}")
        return []


async def refresh_displayed_trials(
    days_back: int = 7,
    limit: int = 100,
    update_sqlite: bool = True
) -> Dict[str, Any]:
    """
    ⚔️ R1: Refresh jobs for displayed/pinned trials
    
    Refresh trials that were likely displayed to users in the last N days.
    
    Args:
        days_back: Days to look back for displayed trials (default 7)
        limit: Maximum trials to refresh (default 100)
        update_sqlite: Whether to update SQLite (default True)
    
    Returns:
        Refresh results dict
    """
    logger.info(f"🔄 Refreshing displayed trials (last {days_back} days, limit {limit})")
    
    if not DB_AVAILABLE:
        return {
            "status": "failed",
            "reason": "Database connection unavailable",
            "trials_refreshed": 0
        }
    
    try:
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
            LIMIT ?
        """, (limit,))
        
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
    
    except Exception as e:
        logger.error(f"❌ Displayed refresh failed: {e}")
        return {
            "status": "failed",
            "reason": str(e),
            "trials_refreshed": 0
        }


async def refresh_pinned_trials(
    pinned_nct_ids: List[str],
    update_sqlite: bool = True
) -> Dict[str, Any]:
    """
    ⚔️ R1: Refresh jobs for displayed/pinned trials
    
    Refresh pinned trials for specific patients (e.g., Ayesha).
    
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


async def bounded_refresh_on_login(
    displayed_nct_ids: List[str],
    limit: int = 50,
    update_sqlite: bool = True
) -> Dict[str, Any]:
    """
    ⚔️ R1: Bounded refresh on login (top K displayed trials)
    
    Refresh top K displayed trials when user logs in (fast path).
    
    Args:
        displayed_nct_ids: List of NCT IDs currently displayed
        limit: Maximum trials to refresh (default 50)
        update_sqlite: Whether to update SQLite (default True)
    
    Returns:
        Refresh results dict
    """
    # Prioritize stale trials
    stale_nct_ids = get_stale_trials(displayed_nct_ids, threshold_days=PRIORITY_REFRESH_THRESHOLD_DAYS)
    
    # Limit to top K
    nct_ids_to_refresh = (stale_nct_ids + [n for n in displayed_nct_ids if n not in stale_nct_ids])[:limit]
    
    if not nct_ids_to_refresh:
        return {
            "status": "skipped",
            "reason": "No trials to refresh",
            "trials_refreshed": 0
        }
    
    logger.info(f"🔄 Bounded refresh on login: {len(nct_ids_to_refresh)} trials (limit: {limit})")
    
    return await refresh_trials_incremental(nct_ids_to_refresh, update_sqlite=update_sqlite)


async def scheduled_refresh_job(
    refresh_displayed: bool = True,
    refresh_pinned: bool = True,
    pinned_nct_ids: Optional[List[str]] = None,
    days_back: int = 7,
    limit: int = 100
) -> Dict[str, Any]:
    """
    ⚔️ Background (continuous freshness + enrichment)
    
    Scheduled refresh job for displayed/pinned trials (nightly or more frequent).
    
    Args:
        refresh_displayed: Whether to refresh displayed trials (default True)
        refresh_pinned: Whether to refresh pinned trials (default True)
        pinned_nct_ids: List of pinned NCT IDs (default None)
        days_back: Days to look back for displayed trials (default 7)
        limit: Maximum displayed trials to refresh (default 100)
    
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
            displayed_results = await refresh_displayed_trials(days_back=days_back, limit=limit)
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


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description="⚔️ Trial Refresh Agent (Production - Concern B)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Refresh displayed trials (last 7 days):
  python refresh_agent.py --refresh-displayed
  
  # Refresh pinned trials:
  python refresh_agent.py --refresh-pinned --pinned NCT12345 NCT67890
  
  # Full refresh (displayed + pinned):
  python refresh_agent.py --refresh-displayed --refresh-pinned --pinned NCT12345
  
  # Bounded refresh on login:
  python refresh_agent.py --bounded --nct-ids NCT12345 NCT67890 --limit 50
        """
    )
    parser.add_argument("--refresh-displayed", action="store_true", help="Refresh displayed trials")
    parser.add_argument("--refresh-pinned", action="store_true", help="Refresh pinned trials")
    parser.add_argument("--pinned", nargs="+", help="Pinned NCT IDs to refresh")
    parser.add_argument("--days-back", type=int, default=7, help="Days to look back for displayed trials (default: 7)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum trials to refresh (default: 100)")
    parser.add_argument("--bounded", action="store_true", help="Bounded refresh on login (top K displayed)")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to refresh (for bounded refresh)")
    
    args = parser.parse_args()
    
    # Run appropriate refresh function
    if args.bounded and args.nct_ids:
        results = asyncio.run(bounded_refresh_on_login(
            displayed_nct_ids=args.nct_ids,
            limit=args.limit
        ))
    else:
        results = asyncio.run(scheduled_refresh_job(
            refresh_displayed=args.refresh_displayed or (not args.refresh_pinned and not args.pinned),
            refresh_pinned=args.refresh_pinned,
            pinned_nct_ids=args.pinned,
            days_back=args.days_back,
            limit=args.limit
        ))
    
    # Print results
    print(json.dumps(results, indent=2))
