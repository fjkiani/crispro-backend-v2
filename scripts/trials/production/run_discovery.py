#!/usr/bin/env python3
"""
⚔️ PRODUCTION - Entry Point: Candidate Discovery (Concern A)

Purpose: Turn a patient profile into a bounded candidate set of NCTs (200-1000 trials).

Source: production/core/discovery_agent.py
"""

import asyncio
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
root_dir = Path(__file__).resolve().parent.parent.parent.parent.parent
sys.path.insert(0, str(root_dir))

# Import from core module
from scripts.trials.production.core.discovery_agent import discover_candidates

def main():
    """Main entry point for candidate discovery."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="⚔️ Candidate Discovery Agent (Production - Concern A)",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--profile", type=str, help="Profile name (e.g., 'ayesha')")
    parser.add_argument("--profile-file", type=str, help="Path to profile JSON file")
    parser.add_argument("--min", type=int, default=200, help="Minimum candidates (default: 200)")
    parser.add_argument("--max", type=int, default=1000, help="Maximum candidates (default: 1000)")
    
    args = parser.parse_args()
    
    # Load profile
    if args.profile == "ayesha":
        try:
            from ayesha_patient_profile import get_ayesha_complete_profile
            patient_profile = get_ayesha_complete_profile()
        except ImportError:
            print("❌ Ayesha profile not available", file=sys.stderr)
            sys.exit(1)
    elif args.profile_file:
        patient_profile = json.loads(Path(args.profile_file).read_text())
    else:
        print("❌ Must specify --profile or --profile-file", file=sys.stderr)
        sys.exit(1)
    
    # Run discovery
    results = asyncio.run(discover_candidates(
        patient_profile=patient_profile,
        min_candidates=args.min,
        max_candidates=args.max
    ))
    
    # Print results
    print(json.dumps(results, indent=2))

if __name__ == "__main__":
    main()
