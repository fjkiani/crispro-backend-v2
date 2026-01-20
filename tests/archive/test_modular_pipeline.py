#!/usr/bin/env python3
"""
⚔️ TEST MODULAR PIPELINE ⚔️

Test the new modular pipeline on the 5 bad dossiers.

Expected Results:
- NCT01000259: REJECTED at STAGE_2 (observational: tissue procurement)
- NCT06331130: REJECTED at STAGE_3 (location: Italy 🇮🇹)
- NCT04001023: REJECTED at STAGE_2 (observational: hypoxia imaging)
- NCT02655016: PASS (PRIMA niraparib - legitimate trial)
- NCT04284969: TBD (need to check)
"""

import asyncio
import json
from pathlib import Path

# Import modular pipeline
from api.services.trial_intelligence import TrialIntelligencePipeline
from ayesha_patient_profile import get_ayesha_complete_profile

# Load candidates
CANDIDATES_FILE = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "50_vector_candidates_for_jr2.json"

async def main():
    print("⚔️ TESTING MODULAR PIPELINE\n")
    
    # Load Ayesha's profile
    ayesha = get_ayesha_complete_profile()
    print(f"✅ Loaded patient: {ayesha['demographics']['name']}")
    print(f"   Disease: {ayesha['disease']['primary_diagnosis']}")
    print(f"   Stage: {ayesha['disease']['figo_stage']}")
    
    # Load candidates
    with open(CANDIDATES_FILE) as f:
        data = json.load(f)
    candidates = data['candidates']
    print(f"✅ Loaded {len(candidates)} candidates")
    
    # Create pipeline
    pipeline = TrialIntelligencePipeline(ayesha, use_llm=False, verbose=True)  # No LLM for quick test
    
    # Execute
    results = await pipeline.execute(candidates)
    
    print(f"\n\n📊 FINAL RESULTS:")
    print(f"   Top-Tier: {len(results['top_tier'])}")
    print(f"   Good-Tier: {len(results['good_tier'])}")
    print(f"   Rejected: {len(results['rejected'])}")
    
    print(f"\n✅ TOP-TIER TRIALS:")
    for trial in results['top_tier']:
        nct_id = trial.get('nct_id')
        title = trial.get('title', 'N/A')[:60]
        score = trial['_filter_metadata']['composite_score']
        print(f"   {nct_id}: {title}... (score: {score:.2f})")
    
    print(f"\n❌ REJECTION AUDIT TRAIL (Top 10):")
    for i, rejection in enumerate(results['audit_trail'][:10], 1):
        nct_id = rejection['nct_id']
        stage = rejection['rejected_at']
        reason = rejection['reason']
        print(f"   {i}. {nct_id} - {stage}: {reason}")
    
    print(f"\n⚔️ TEST COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main())


