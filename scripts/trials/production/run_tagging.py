#!/usr/bin/env python3
"""
⚔️ PRODUCTION - Entry Point: Offline Tagging (Concern C)

Purpose: Attach mechanism vectors (7D) to trials without runtime LLM calls.

Source: production/core/tagging_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

# Import from core module
from scripts.trials.production.core.tagging_agent import run_tagging_pipeline

def main():
    """Main entry point for offline tagging."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="⚔️ Trial Tagging Agent (Production - Concern C)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--limit", type=int, default=500, help="Maximum candidates to tag (default: 500)")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size (10-25, default: 25)")
    parser.add_argument("--corpus", type=str, help="Corpus name (e.g., 'ayesha')")
    parser.add_argument("--provider", type=str, help="LLM provider (openai/gemini/cohere)")
    parser.add_argument("--no-qa", action="store_true", help="Skip automated QA")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to tag")
    
    args = parser.parse_args()
    
    # Get corpus NCT IDs if specified
    corpus_nct_ids = None
    if args.corpus == "ayesha":
        # TODO: Load Ayesha corpus NCT IDs from config
        corpus_nct_ids = []
    
    # Run pipeline
    results = asyncio.run(run_tagging_pipeline(
        corpus_nct_ids=corpus_nct_ids or args.nct_ids,
        batch_size=args.batch_size,
        max_candidates=args.limit,
        provider=args.provider,
        run_qa=not args.no_qa
    ))
    
    # Print results
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
