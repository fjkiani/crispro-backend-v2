#!/usr/bin/env python3
"""
Trial MoA Batch Tagging v2 - Clean, Efficient, Modular
=======================================================

Usage:
    python tag_trials_v2.py --limit 200 --tier tier1
    python tag_trials_v2.py --limit 50 --tier free
    python tag_trials_v2.py --nct-ids NCT123 NCT456 NCT789

Key improvements over v1:
- 5-10x faster (batch multiple trials per API call)
- Modular architecture (easy to test/maintain)
- Smart rate limiting (adapts to tier)
- Progress saving (resume on failure)
- Better logging and statistics
"""

import asyncio
import argparse
import logging
import sys
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Load .env from project root
try:
    from dotenv import load_dotenv
    # Try multiple possible locations
    script_dir = Path(__file__).resolve().parent
    possible_envs = [
        Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/.env"),  # Absolute root
        script_dir.parent.parent.parent.parent / ".env",  # Relative root
        script_dir.parent.parent / ".env",  # Backend root
    ]
    for env_path in possible_envs:
        if env_path.exists():
            load_dotenv(env_path, override=True)
            print(f"✅ Loaded .env from: {env_path}")
            break
except ImportError:
    pass

from trial_tagger.runner import run_tagging
from trial_tagger.db import load_existing_vectors, get_untagged_trials

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


def show_status():
    """Show current tagging status."""
    vectors = load_existing_vectors()
    
    print("\n📊 CURRENT STATUS")
    print("=" * 50)
    print(f"Total trials tagged: {len(vectors)}")
    
    # Count by source
    sources = {}
    for v in vectors.values():
        src = v.get("source", "unknown")
        sources[src] = sources.get(src, 0) + 1
    
    print("\nBy source:")
    for src, count in sorted(sources.items(), key=lambda x: -x[1]):
        print(f"  {src}: {count}")
    
    # Count by confidence
    high = sum(1 for v in vectors.values() if v.get("confidence", 0) >= 0.8)
    med = sum(1 for v in vectors.values() if 0.5 <= v.get("confidence", 0) < 0.8)
    low = sum(1 for v in vectors.values() if v.get("confidence", 0) < 0.5)
    
    print(f"\nBy confidence:")
    print(f"  High (≥0.8): {high}")
    print(f"  Medium (0.5-0.8): {med}")
    print(f"  Low (<0.5): {low}")
    
    # Untagged
    try:
        untagged = get_untagged_trials(limit=1000)
        print(f"\nUntagged trials available: {len(untagged)}")
    except Exception as e:
        print(f"\nCouldn't check untagged: {e}")
    
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(
        description="Efficient trial MoA tagging with Gemini",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Tag 200 trials with tier 1 settings (fast)
  python tag_trials_v2.py --limit 200 --tier tier1
  
  # Tag 50 trials with free tier settings (slower, safer)
  python tag_trials_v2.py --limit 50 --tier free
  
  # Tag specific trials
  python tag_trials_v2.py --nct-ids NCT123 NCT456
  
  # Show current status
  python tag_trials_v2.py --status
"""
    )
    
    parser.add_argument("--limit", type=int, default=200, help="Max trials to tag")
    parser.add_argument("--tier", choices=["free", "tier1", "auto"], default="auto",
                        help="API tier (affects rate limiting)")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to tag")
    parser.add_argument("--status", action="store_true", help="Show current status and exit")
    
    args = parser.parse_args()
    
    if args.status:
        show_status()
        return
    
    print("\n" + "=" * 60)
    print("🚀 Trial MoA Batch Tagging v2")
    print("=" * 60)
    print(f"   Limit: {args.limit}")
    print(f"   Tier: {args.tier}")
    if args.nct_ids:
        print(f"   NCT IDs: {args.nct_ids}")
    print("=" * 60 + "\n")
    
    # Run tagging
    try:
        results = asyncio.run(run_tagging(
            limit=args.limit,
            tier=args.tier,
            nct_ids=args.nct_ids
        ))
        
        print(f"\n✅ Complete: {len(results)} trials tagged")
        
    except KeyboardInterrupt:
        print("\n⚠️ Interrupted - progress saved")
    except Exception as e:
        logger.error(f"Error: {e}")
        raise


if __name__ == "__main__":
    main()

