#!/usr/bin/env python3
"""
⚔️ FIND BEST TRIALS FOR AYESHA - COMPLETE PIPELINE ⚔️

Runs the complete modular pipeline:
1. Stage 1-4: Progressive filtering
2. Stage 5: LLM deep analysis (top 5-10 only)
3. Stage 6: Generate Commander-grade dossiers

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

import asyncio
import json
import os
from pathlib import Path

# Set API key
os.environ['GEMINI_API_KEY'] = 'AIzaSyDqlcmojJjbr4jv7XUxNpkL3VlUJs2zSCI'

# Import modules
from api.services.trial_intelligence import TrialIntelligencePipeline
from api.services.trial_intelligence.stage6_dossier import assembler
from ayesha_patient_profile import get_ayesha_complete_profile

# File paths
CANDIDATES_FILE = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "50_vector_candidates_for_jr2.json"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "zo_modular_pipeline_dossiers"

async def main():
    print("⚔️ FINDING BEST TRIALS FOR AYESHA - COMPLETE PIPELINE ⚔️\n")
    
    # Load Ayesha's complete profile
    ayesha = get_ayesha_complete_profile()
    print(f"✅ Loaded patient: {ayesha['demographics']['name']}")
    print(f"   Disease: {ayesha['disease']['primary_diagnosis']}")
    print(f"   Stage: {ayesha['disease']['figo_stage']}")
    print(f"   BRCA: {ayesha['biomarkers']['germline_status']}")
    print(f"   HER2: {ayesha['biomarkers']['her2_status']}")
    print(f"   HRD: {ayesha['biomarkers']['hrd_status']}")
    print(f"   CA-125: {ayesha['biomarkers']['ca125']['value']} U/mL")
    
    # Load candidates
    with open(CANDIDATES_FILE) as f:
        data = json.load(f)
    candidates = data['candidates']
    print(f"✅ Loaded {len(candidates)} candidates from vector search\n")
    
    # === STAGE 1-4: Progressive Filtering ===
    print("🔍 STAGE 1-4: PROGRESSIVE FILTERING\n")
    pipeline = TrialIntelligencePipeline(ayesha, use_llm=True, verbose=True)
    results = await pipeline.execute(candidates)
    
    print(f"\n\n📊 FILTERING COMPLETE:")
    print(f"   Top-Tier: {len(results['top_tier'])}")
    print(f"   Good-Tier: {len(results['good_tier'])}")
    print(f"   Rejected: {len(results['rejected'])}")
    
    # === STAGE 5: LLM DEEP ANALYSIS ===
    print(f"\n\n🤖 STAGE 5: LLM DEEP ANALYSIS (Top {min(5, len(results['top_tier']))} trials)")
    
    from api.services.trial_intelligence.stage5_llm_analysis import trial_fit_analyzer
    
    top_trials = results['top_tier'][:5]  # Top 5 only
    
    for i, trial in enumerate(top_trials, 1):
        nct_id = trial.get('nct_id')
        title = trial.get('title', 'N/A')[:60]
        print(f"\n   {i}. {nct_id}: {title}...")
        print(f"      🤖 Analyzing with Gemini...")
        
        # Run LLM analysis
        analysis = await trial_fit_analyzer.analyze(trial, ayesha)
        
        # Store in metadata
        if '_filter_metadata' not in trial:
            trial['_filter_metadata'] = {}
        
        trial['_filter_metadata']['stage5'] = type('obj', (object,), {
            'passed': True,
            'stage': 'STAGE_5',
            'score': 1.0,
            'reasons': [],
            'metadata': {'llm_analysis': analysis}
        })()
        
        print(f"      ✅ Analysis complete ({len(analysis)} chars)")
    
    # === STAGE 6: GENERATE DOSSIERS ===
    print(f"\n\n📝 STAGE 6: GENERATING COMMANDER-GRADE DOSSIERS\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for i, trial in enumerate(top_trials, 1):
        nct_id = trial.get('nct_id')
        metadata = trial.get('_filter_metadata', {})
        composite_score = metadata.get('composite_score', 0.0)
        
        # Determine tier
        if composite_score >= 0.8:
            tier = 'TOP_TIER'
        elif composite_score >= 0.6:
            tier = 'GOOD_TIER'
        else:
            tier = 'OK_TIER'
        
        # Generate dossier
        markdown = assembler.assemble(trial, ayesha)
        
        # Save
        filename = f"INTELLIGENCE_{nct_id}_{tier}.md"
        filepath = OUTPUT_DIR / filename
        with open(filepath, 'w') as f:
            f.write(markdown)
        
        print(f"   {i}. {nct_id} - {tier} ({composite_score:.2f}) - ✅ Dossier generated")
    
    print(f"\n✅ Generated {len(top_trials)} intelligence dossiers")
    print(f"📁 Output: {OUTPUT_DIR}")
    
    # === SUMMARY ===
    print(f"\n\n⚔️ MISSION COMPLETE! ⚔️")
    print(f"\n📊 FINAL SUMMARY:")
    print(f"   Input: {len(candidates)} candidates")
    print(f"   Survived filtering: {len(results['top_tier']) + len(results['good_tier'])}")
    print(f"   Top-tier trials: {len(results['top_tier'])}")
    print(f"   Dossiers generated: {len(top_trials)}")
    
    print(f"\n✅ BEST TRIALS FOR AYESHA:")
    for i, trial in enumerate(top_trials, 1):
        nct_id = trial.get('nct_id')
        title = trial.get('title', 'N/A')
        score = trial['_filter_metadata']['composite_score']
        prob = trial['_filter_metadata']['stage4'].metadata.get('eligibility_probability', 0.0)
        print(f"   {i}. {nct_id}: {title[:60]}...")
        print(f"      Score: {score:.2f}, Eligibility: ~{prob*100:.0f}%")
    
    print(f"\n📋 REJECTION BREAKDOWN:")
    stats = results['statistics']['rejection_breakdown']
    for stage, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {stage}: {count}")
    
    print(f"\n⚔️ FOR AYESHA! ⚔️")

if __name__ == "__main__":
    asyncio.run(main())


