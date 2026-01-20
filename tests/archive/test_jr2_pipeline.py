"""
Quick test script for JR2's dossier generation pipeline.

Tests:
1. Trial querier (SQLite read)
2. Trial filter (multi-tier filtering)
3. Dossier generation (full pipeline)
"""
import asyncio
import json
from pathlib import Path

from api.services.client_dossier.trial_querier import get_trials_from_sqlite
from api.services.client_dossier.trial_filter import filter_50_candidates
from api.services.client_dossier.dossier_generator import generate_dossier
from api.services.client_dossier.dossier_renderer import render_dossier_markdown

# Ayesha's profile
AYESHA_PROFILE = {
    'patient_id': 'ayesha_001',
    'disease': 'ovarian_cancer_hgs',
    'treatment_line': 'first-line',
    'location': 'NYC',
    'biomarkers': {
        'brca': 'NEGATIVE',
        'hrd': 'UNKNOWN',
        'tmb': 'UNKNOWN',
        'msi': 'UNKNOWN',
        'her2': 'UNKNOWN'
    }
}

async def test_pipeline():
    """Test the complete pipeline."""
    print("⚔️ JR2 Pipeline Test\n")
    
    # Test 1: Trial querier
    print("1. Testing trial querier...")
    try:
        trials = get_trials_from_sqlite(limit=10)
        print(f"   ✅ Retrieved {len(trials)} trials")
        if trials:
            print(f"   Sample: {trials[0].get('nct_id', 'N/A')} - {trials[0].get('title', 'N/A')[:50]}...")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return
    
    # Test 2: Trial filter
    print("\n2. Testing trial filter...")
    try:
        filtered = filter_50_candidates(trials, AYESHA_PROFILE)
        print(f"   ✅ Filtered results:")
        print(f"      Top-Tier: {len(filtered['top_tier'])}")
        print(f"      Good-Tier: {len(filtered['good_tier'])}")
        print(f"      OK-Tier: {len(filtered['ok_tier'])}")
        
        if filtered['top_tier']:
            top_trial = filtered['top_tier'][0]
            print(f"   Top trial: {top_trial.get('id', 'N/A')} - {top_trial.get('title', 'N/A')[:50]}...")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        return
    
    # Test 3: Dossier generation (use ovarian cancer trial specifically)
    print("\n3. Testing dossier generation...")
    try:
        # First, try to find an ovarian cancer trial from filtered results
        test_nct_id = None
        
        # Look for ovarian cancer trial in filtered results
        for tier_name, tier_trials in [('top_tier', filtered['top_tier']), 
                                       ('good_tier', filtered['good_tier']), 
                                       ('ok_tier', filtered['ok_tier'])]:
            for trial in tier_trials:
                conditions = (trial.get('conditions', '') or trial.get('disease_subcategory', '') or '').lower()
                title = (trial.get('title', '') or '').lower()
                if 'ovarian' in conditions or 'ovarian' in title:
                    test_nct_id = trial.get('id') or trial.get('nct_id')
                    print(f"   Found ovarian cancer trial in {tier_name}: {test_nct_id}")
                    break
            if test_nct_id:
                break
        
        # Fallback: Use known ovarian cancer trial
        if not test_nct_id:
            test_nct_id = 'NCT03916679'  # MESO-CAR T Cells for Ovarian Cancer
            print(f"   Using known ovarian cancer trial: {test_nct_id}")
        
        print(f"   Generating dossier for: {test_nct_id}")
        dossier = await generate_dossier(test_nct_id, AYESHA_PROFILE)
        print(f"   ✅ Dossier generated")
        print(f"      Sections: {len(dossier.get('sections', {}))}")
        
        # Test 4: Markdown rendering
        print("\n4. Testing markdown rendering...")
        markdown = render_dossier_markdown(dossier)
        print(f"   ✅ Markdown rendered ({len(markdown)} chars)")
        
        # Save test output
        output_dir = Path(".cursor/ayesha/test_output")
        output_dir.mkdir(parents=True, exist_ok=True)
        
        (output_dir / "test_dossier.md").write_text(markdown)
        (output_dir / "test_dossier.json").write_text(json.dumps(dossier, indent=2))
        
        print(f"\n   ✅ Test outputs saved to {output_dir}")
        print(f"   ✅ Pipeline test COMPLETE!")
        
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return

if __name__ == "__main__":
    asyncio.run(test_pipeline())

