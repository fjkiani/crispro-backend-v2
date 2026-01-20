#!/usr/bin/env python3
"""
⚔️ PRODUCTION - Entry Point: Refresh (Concern B)

Purpose: Ensure trial status and locations are fresh (last_refreshed_at + stale flags).

Source: production/core/refresh_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

# Import from core module
from scripts.trials.production.core.refresh_agent import (
    refresh_trials_incremental,
    refresh_displayed_trials,
    refresh_pinned_trials,
    bounded_refresh_on_login,
    scheduled_refresh_job
)

def main():
    """Main entry point for refresh."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="⚔️ Trial Refresh Agent (Production - Concern B)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--refresh-displayed", action="store_true", help="Refresh displayed trials")
    parser.add_argument("--refresh-pinned", action="store_true", help="Refresh pinned trials")
    parser.add_argument("--pinned", nargs="+", help="Pinned NCT IDs to refresh")
    parser.add_argument("--days-back", type=int, default=7, help="Days to look back for displayed trials (default: 7)")
    parser.add_argument("--limit", type=int, default=100, help="Maximum trials to refresh (default: 100)")
    parser.add_argument("--bounded", action="store_true", help="Bounded refresh on login (top K displayed)")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to refresh")
    
    args = parser.parse_args()
    
    # Run appropriate refresh function
    if args.bounded and args.nct_ids:
        results = asyncio.run(bounded_refresh_on_login(
            displayed_nct_ids=args.nct_ids,
            limit=args.limit
        ))
    elif args.nct_ids:
        results = asyncio.run(refresh_trials_incremental(
            nct_ids=args.nct_ids
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

if __name__ == "__main__":
    main()
