#!/usr/bin/env python3
"""
⚔️ FIND BEST TRIALS FOR AYESHA - EXPANDED STATES ⚔️

EXPANDED GEOGRAPHY: Northeast + Mid-Atlantic (10 states)
Allows travel up to ~300 miles for rare, excellent trials

States: NY, NJ, CT, PA, MA, RI, MD, DE, NH, VT

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

import asyncio
import json
import os
import sys
from pathlib import Path

# Set API key
os.environ['GEMINI_API_KEY'] = 'AIzaSyDqlcmojJjbr4jv7XUxNpkL3VlUJs2zSCI'

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import modules
from api.services.trial_intelligence import TrialIntelligencePipeline
from api.services.trial_intelligence.config import get_expanded_states_config
from api.services.trial_intelligence.stage6_dossier import assembler
from api.services.clinical_trial_search_service import ClinicalTrialSearchService
from ayesha_patient_profile import get_ayesha_complete_profile

# Output directory
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "zo_expanded_states_dossiers"

async def search_astradb_for_ayesha(ayesha, top_k: int = 200, min_score: float = 0.5):
    """Search AstraDB with patient-specific query"""
    print(f"\n🔍 SEARCHING ASTRADB FOR AYESHA")
    print(f"   Query parameters: top_k={top_k}, min_score={min_score}")
    
    # Build patient-specific query
    disease = ayesha['disease']['primary_diagnosis']
    stage = ayesha['disease']['figo_stage']
    treatment_line = ayesha['treatment']['line']
    brca_status = ayesha['biomarkers']['germline_status']
    
    query = f"""
    Stage {stage} {disease}, {treatment_line}, BRCA {brca_status}.
    Patient is treatment-naive, ECOG 1, extensive tumor burden with pleural metastases.
    Looking for recruiting trials in USA (Northeast/Mid-Atlantic preferred).
    Interested in frontline or maintenance therapy.
    """.strip()
    
    print(f"   Query: {query[:100]}...")
    
    # Search AstraDB
    search_service = ClinicalTrialSearchService()
    
    try:
        result = await search_service.search_trials(
            query=query,
            disease_category="gynecologic_oncology",
            top_k=top_k,
            min_score=min_score
        )
        
        if result['success']:
            trials = result['data']['found_trials']
            print(f"   ✅ Found {len(trials)} trials from AstraDB")
            return trials
        else:
            print(f"   ❌ Search failed: {result.get('error', 'Unknown error')}")
            return []
    
    except Exception as e:
        print(f"   ❌ AstraDB search error: {e}")
        import traceback
        traceback.print_exc()
        return []

async def main():
    print("⚔️ FINDING BEST TRIALS FOR AYESHA - EXPANDED STATES ⚔️\n")
    
    # Load Ayesha's complete profile
    ayesha = get_ayesha_complete_profile()
    print(f"✅ Loaded patient: {ayesha['demographics']['name']}")
    print(f"   Disease: {ayesha['disease']['primary_diagnosis']}")
    print(f"   Stage: {ayesha['disease']['figo_stage']}")
    print(f"   Location: NYC Metro (ZIP 10029)")
    print(f"   CA-125: {ayesha['biomarkers']['ca125']['value']} U/mL")
    
    # === STEP 1: SEARCH ASTRADB ===
    candidates = await search_astradb_for_ayesha(ayesha, top_k=200, min_score=0.5)
    
    if not candidates:
        print(f"\n❌ No candidates found in AstraDB")
        return
    
    # === STEP 2: CONFIGURE FILTERS ===
    print(f"\n⚙️ CONFIGURING FILTERS - EXPANDED GEOGRAPHY")
    
    # EXPANDED CONFIG: Northeast + Mid-Atlantic (10 states)
    config = get_expanded_states_config()  # Defaults to 10 states
    
    print(f"   📍 Allowed states: {sorted(config.ALLOWED_STATES)}")
    print(f"   🚗 Max travel: {config.MAX_TRAVEL_MILES} miles")
    print(f"   ⚕️ Major centers: {len(config.MAJOR_CANCER_CENTERS)} tracked")
    print(f"   🏥 Metro cities: {len(config.NYC_METRO_CITIES)} tracked")
    
    # === STEP 3: RUN MODULAR PIPELINE ===
    print(f"\n🔍 STAGE 1-4: PROGRESSIVE FILTERING\n")
    pipeline = TrialIntelligencePipeline(ayesha, config=config, use_llm=True, verbose=True)
    results = await pipeline.execute(candidates)
    
    print(f"\n\n📊 FILTERING COMPLETE:")
    print(f"   Top-Tier: {len(results['top_tier'])}")
    print(f"   Good-Tier: {len(results['good_tier'])}")
    print(f"   Rejected: {len(results['rejected'])}")
    
    # === STEP 4: LLM DEEP ANALYSIS ===
    print(f"\n\n🤖 STAGE 5: LLM DEEP ANALYSIS (Top {min(config.MAX_LLM_ANALYSES, len(results['top_tier']))} trials)")
    
    from api.services.trial_intelligence.stage5_llm_analysis import trial_fit_analyzer
    
    top_trials = results['top_tier'][:config.MAX_LLM_ANALYSES]
    good_trials = results['good_tier'][:max(0, config.MAX_LLM_ANALYSES - len(top_trials))]
    all_to_analyze = top_trials + good_trials
    
    for i, trial in enumerate(all_to_analyze, 1):
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
    
    # === STEP 5: GENERATE DOSSIERS ===
    print(f"\n\n📝 STAGE 6: GENERATING COMMANDER-GRADE DOSSIERS\n")
    
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    for i, trial in enumerate(all_to_analyze, 1):
        nct_id = trial.get('nct_id')
        metadata = trial.get('_filter_metadata', {})
        composite_score = metadata.get('composite_score', 0.0)
        
        # Determine tier
        if composite_score >= config.TOP_TIER_THRESHOLD:
            tier = 'TOP_TIER'
        elif composite_score >= config.GOOD_TIER_THRESHOLD:
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
    
    print(f"\n✅ Generated {len(all_to_analyze)} intelligence dossiers")
    print(f"📁 Output: {OUTPUT_DIR}")
    
    # === SUMMARY ===
    print(f"\n\n⚔️ MISSION COMPLETE! ⚔️")
    print(f"\n📊 FINAL SUMMARY:")
    print(f"   AstraDB query: {len(candidates)} candidates retrieved")
    print(f"   After filtering: {len(results['top_tier']) + len(results['good_tier'])} survivors")
    print(f"   Top-tier: {len(results['top_tier'])}")
    print(f"   Good-tier: {len(results['good_tier'])}")
    print(f"   Dossiers generated: {len(all_to_analyze)}")
    
    print(f"\n✅ TOP-TIER TRIALS FOR AYESHA:")
    for i, trial in enumerate(results['top_tier'], 1):
        nct_id = trial.get('nct_id')
        title = trial.get('title', 'N/A')
        score = trial['_filter_metadata']['composite_score']
        locations = trial['_filter_metadata']['stage3'].metadata.get('matching_locations', [])
        loc_states = list(set([loc.get('state', '?') for loc in locations]))
        print(f"   {i}. {nct_id}: {title[:60]}...")
        print(f"      Score: {score:.2f}, States: {', '.join(loc_states)}")
    
    print(f"\n✅ GOOD-TIER TRIALS:")
    for i, trial in enumerate(results['good_tier'][:5], 1):  # Top 5 good-tier
        nct_id = trial.get('nct_id')
        title = trial.get('title', 'N/A')
        score = trial['_filter_metadata']['composite_score']
        locations = trial['_filter_metadata']['stage3'].metadata.get('matching_locations', [])
        loc_states = list(set([loc.get('state', '?') for loc in locations]))
        print(f"   {i}. {nct_id}: {title[:60]}...")
        print(f"      Score: {score:.2f}, States: {', '.join(loc_states)}")
    
    print(f"\n📋 REJECTION BREAKDOWN:")
    stats = results['statistics']['rejection_breakdown']
    for stage, count in sorted(stats.items(), key=lambda x: x[1], reverse=True):
        print(f"   {stage}: {count}")
    
    print(f"\n⚙️ FILTER CONFIGURATION USED:")
    print(f"   Allowed states: {sorted(config.ALLOWED_STATES)} (EXPANDED)")
    print(f"   Max LLM analyses: {config.MAX_LLM_ANALYSES}")
    print(f"   Top-tier threshold: {config.TOP_TIER_THRESHOLD}")
    print(f"   Line weight (maintenance): {config.LINE_SCORE_WEIGHTS['maintenance']}")
    print(f"   Line weight (frontline): {config.LINE_SCORE_WEIGHTS['frontline']}")
    
    print(f"\n⚔️ FOR AYESHA! ⚔️")

if __name__ == "__main__":
    asyncio.run(main())


