#!/usr/bin/env python3
"""
⚔️ PRODUCTION - Entry Point: Patient Matching + Dossier (Concern D)

Purpose: Compute eligibility, mechanism fit ranking, and generate reasoning/dossiers.

Source: production/core/matching_agent.py
"""

import asyncio
import sys
import os
from pathlib import Path

# ⚔️ FIX: Add parent directories to path for imports (works from any directory)
current_file = Path(__file__).resolve()
root_dir = current_file.parent.parent.parent.parent.parent  # Go up to project root
backend_dir = root_dir / "oncology-coPilot" / "oncology-backend-minimal"

# Add both root and backend to path
sys.path.insert(0, str(root_dir))
sys.path.insert(0, str(backend_dir))

# Change to backend directory to ensure relative imports work
os.chdir(str(backend_dir))

# Import from core module
try:
    from scripts.trials.production.core.matching_agent import match_patient_to_trials
except ImportError as e:
    print(f"❌ Import failed: {e}")
    print(f"   Root dir: {root_dir}")
    print(f"   Backend dir: {backend_dir}")
    print(f"   Current dir: {os.getcwd()}")
    print(f"   Python path: {sys.path[:3]}")
    sys.exit(1)

async def main():
    """Main entry point for patient matching + dossier."""
    print("⚔️ Patient Matching + Dossier (Production - Concern D)")
    
    # Example usage:
    patient_profile = {
        "disease": "Ovarian Cancer",
        "stage": "IV",
        "location_state": "NY",
        "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0],  # DDR-high
        "germline_variants": [{"gene": "DPYD", "variant": "*2A"}],
        "age": 65,
        "mutations": [{"gene": "BRCA1"}, {"gene": "TP53"}]
    }
    
    result = await match_patient_to_trials(patient_profile, max_results=10)
    print(f"✅ Found {len(result['matches'])} matches")
    print(f"   Total candidates: {result['total_candidates']}")
    print(f"   MoA coverage: {result['moa_coverage']}")
    print(f"   Holistic scoring: {result['provenance']['holistic_scoring']}")
    
    # Display top matches
    for i, match in enumerate(result['matches'][:5], 1):
        print(f"\n{i}. {match.get('nct_id')}: {match.get('title', 'Unknown')}")
        print(f"   Holistic Score: {match.get('holistic_score', 'N/A')}")
        print(f"   Mechanism Fit: {match.get('mechanism_fit_score', 'N/A')}")
        print(f"   Eligibility: {match.get('eligibility_score', 'N/A')}")
        print(f"   PGx Safety: {match.get('pgx_safety_score', 'N/A')}")

if __name__ == "__main__":
    asyncio.run(main())
