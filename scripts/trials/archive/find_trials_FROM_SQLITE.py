#!/usr/bin/env python3
"""
⚔️ FIND BEST TRIALS FOR AYESHA - FROM SQLITE (1,000 TRIALS) ⚔️

Uses SQLite database directly (not AstraDB vector search).
Queries all 1,000 trials and filters with modular pipeline.

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

import asyncio
import json
import os
import sys
from pathlib import Path
import sqlite3

# Set API key
os.environ['GEMINI_API_KEY'] = 'AIzaSyDqlcmojJjbr4jv7XUxNpkL3VlUJs2zSCI'

# Add project root to path
project_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(project_root))

# Import modules
from api.services.trial_intelligence import TrialIntelligencePipeline
from api.services.trial_intelligence.config import FilterConfig, get_expanded_states_config
from api.services.trial_intelligence.stage6_dossier import assembler
from ayesha_patient_profile import get_ayesha_complete_profile

# Output directory
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "zo_sqlite_dossiers"

def get_all_trials_from_sqlite() -> list:
    """
    Get ALL 1,000 trials from SQLite 'trials' table.
    
    Returns:
        List of trial dictionaries (normalized to match pipeline expectations)
    """
    db_path = Path(__file__).resolve().parent / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    cursor = conn.cursor()
    
    # Get ALL trials from 'trials' table (1,000 trials)
    cursor.execute("SELECT * FROM trials")
    rows = cursor.fetchall()
    
    trials = []
    for row in rows:
        trial = dict(row)
        
        # Normalize field names to match pipeline expectations
        # SQLite uses 'id' for NCT ID, pipeline expects 'nct_id'
        if 'id' in trial and 'nct_id' not in trial:
            trial['nct_id'] = trial['id']
        
        # Normalize 'conditions' to 'disease_category'
        # SQLite 'conditions' might be JSON array string or plain text
        if 'conditions' in trial:
            conditions = trial['conditions']
            if isinstance(conditions, str):
                # Try to parse as JSON first
                try:
                    conditions_list = json.loads(conditions)
                    if isinstance(conditions_list, list):
                        conditions = ' '.join(conditions_list).lower()
                    else:
                        conditions = str(conditions_list).lower()
                except (json.JSONDecodeError, TypeError):
                    # Not JSON, use as-is
                    conditions = conditions.lower()
            else:
                conditions = str(conditions).lower()
            
            trial['disease_category'] = conditions
            trial['conditions'] = conditions  # Keep original too
        
        # Normalize 'summary' to 'description_text'
        if 'summary' in trial and 'description_text' not in trial:
            trial['description_text'] = trial['summary'] or ''
        
        # Parse locations_full_json to locations_data
        if 'locations_full_json' in trial and trial['locations_full_json']:
            try:
                locations = json.loads(trial['locations_full_json'])
                if isinstance(locations, list):
                    trial['locations_data'] = locations
                else:
                    trial['locations_data'] = []
            except (json.JSONDecodeError, TypeError):
                trial['locations_data'] = []
        else:
            trial['locations_data'] = []
        
        # Parse other JSON fields if they exist
        for json_field in ['biomarker_requirements', 'mechanism_tags', 'interventions_json']:
            if trial.get(json_field) and isinstance(trial[json_field], str):
                try:
                    trial[json_field] = json.loads(trial[json_field])
                except (json.JSONDecodeError, TypeError):
                    trial[json_field] = []
        
        # Ensure eligibility_text exists (for stage filters)
        if 'eligibility_text' not in trial:
            # Combine inclusion + exclusion criteria
            inclusion = trial.get('inclusion_criteria', '') or trial.get('inclusion_criteria_full', '')
            exclusion = trial.get('exclusion_criteria', '') or trial.get('exclusion_criteria_full', '')
            trial['eligibility_text'] = f"{inclusion} {exclusion}".strip()
        
        trials.append(trial)
    
    conn.close()
    print(f"✅ Retrieved {len(trials)} trials from SQLite")
    return trials

async def main():
    print("⚔️ FINDING BEST TRIALS FOR AYESHA - FROM SQLITE (1,000 TRIALS) ⚔️\n")
    
    # Load Ayesha's complete profile
    ayesha = get_ayesha_complete_profile()
    print(f"✅ Loaded patient: {ayesha['demographics']['name']}")
    print(f"   Disease: {ayesha['disease']['primary_diagnosis']}")
    print(f"   Stage: {ayesha['disease']['figo_stage']}")
    print(f"   Location: NYC Metro (ZIP 10029)")
    print(f"   CA-125: {ayesha['biomarkers']['ca125']['value']} U/mL")
    
    # === STEP 1: GET ALL TRIALS FROM SQLITE ===
    print(f"\n🔍 LOADING ALL TRIALS FROM SQLITE\n")
    candidates = get_all_trials_from_sqlite()
    
    if not candidates:
        print(f"\n❌ No candidates found in SQLite")
        return
    
    print(f"   ✅ Loaded {len(candidates)} trials from SQLite")
    
    # Count by status
    status_counts = {}
    for trial in candidates:
        status = trial.get('status', 'UNKNOWN')
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print(f"\n📊 STATUS BREAKDOWN:")
    for status, count in sorted(status_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"   {status}: {count}")
    
    recruiting_count = sum(count for status, count in status_counts.items() 
                          if status in ['RECRUITING', 'NOT_YET_RECRUITING', 'ACTIVE_NOT_RECRUITING'])
    print(f"\n✅ RECRUITING: {recruiting_count} trials")
    
    # === STEP 2: CONFIGURE FILTERS ===
    print(f"\n⚙️ CONFIGURING FILTERS")
    
    # Use expanded config (10 states) for more options
    config = get_expanded_states_config()  # Defaults to 10 states
    
    print(f"   📍 Allowed states: {sorted(config.ALLOWED_STATES)} (EXPANDED)")
    print(f"   🚗 Max travel: {config.MAX_TRAVEL_MILES} miles")
    print(f"   ⚕️ Major centers: {len(config.MAJOR_CANCER_CENTERS)} tracked")
    print(f"   🏥 Metro cities: {len(config.NYC_METRO_CITIES)} tracked")
    print(f"   📊 Max LLM analyses: {config.MAX_LLM_ANALYSES}")
    
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
        nct_id = trial.get('nct_id', trial.get('id', 'UNKNOWN'))
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
        nct_id = trial.get('nct_id', trial.get('id', 'UNKNOWN'))
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
    print(f"   SQLite query: {len(candidates)} candidates retrieved")
    print(f"   After filtering: {len(results['top_tier']) + len(results['good_tier'])} survivors")
    print(f"   Top-tier: {len(results['top_tier'])}")
    print(f"   Good-tier: {len(results['good_tier'])}")
    print(f"   Dossiers generated: {len(all_to_analyze)}")
    
    print(f"\n✅ TOP-TIER TRIALS FOR AYESHA:")
    for i, trial in enumerate(results['top_tier'], 1):
        nct_id = trial.get('nct_id', trial.get('id', 'UNKNOWN'))
        title = trial.get('title', 'N/A')
        score = trial['_filter_metadata']['composite_score']
        locations = trial['_filter_metadata']['stage3'].metadata.get('matching_locations', [])
        loc_states = list(set([loc.get('state', '?') for loc in locations]))
        print(f"   {i}. {nct_id}: {title[:60]}...")
        print(f"      Score: {score:.2f}, States: {', '.join(loc_states) if loc_states else 'N/A'}")
    
    print(f"\n✅ GOOD-TIER TRIALS (Top 5):")
    for i, trial in enumerate(results['good_tier'][:5], 1):
        nct_id = trial.get('nct_id', trial.get('id', 'UNKNOWN'))
        title = trial.get('title', 'N/A')
        score = trial['_filter_metadata']['composite_score']
        locations = trial['_filter_metadata']['stage3'].metadata.get('matching_locations', [])
        loc_states = list(set([loc.get('state', '?') for loc in locations]))
        print(f"   {i}. {nct_id}: {title[:60]}...")
        print(f"      Score: {score:.2f}, States: {', '.join(loc_states) if loc_states else 'N/A'}")
    
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

