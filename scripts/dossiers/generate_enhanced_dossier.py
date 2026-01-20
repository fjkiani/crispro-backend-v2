#!/usr/bin/env python3
"""
Generate an enhanced dossier in the Zo-style format using LLM.
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime
import os
import sys
import subprocess

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))
# Add project root for tools
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.services.client_dossier.dossier_generator import generate_dossier
from api.services.client_dossier.dossier_renderer import render_dossier_markdown
from api.services.client_dossier.trial_querier import get_trials_from_sqlite
from api.services.client_dossier.trial_filter import filter_50_candidates

# LLM helper
def enhance_dossier_with_llm(dossier_data: dict, patient_profile: dict) -> str:
    """Use LLM to transform dossier into Zo-style intelligence report."""
    # Build the prompt
    prompt_text = f"""Transform this clinical trial dossier into a comprehensive intelligence report in the style of Zo's trial analysis.

PATIENT PROFILE:
- Patient ID: {patient_profile.get('patient_id', 'unknown')}
- Disease: {patient_profile.get('disease', 'unknown')}
- Treatment Line: {patient_profile.get('treatment_line', 'unknown')}
- Location: {patient_profile.get('location', 'unknown')}
- Biomarkers: {json.dumps(patient_profile.get('biomarkers', {}), indent=2)}

DOSSIER DATA:
{json.dumps(dossier_data, indent=2)}

REQUIRED OUTPUT FORMAT:
1. TRIAL INTELLIGENCE REPORT: [NCT ID]
   - Trial Name, Full Title, Phase, Sponsor, Status, Enrollment, Primary Completion, Link

2. 🔥 WHY THIS MATTERS FOR AYESHA - CRITICAL ANALYSIS
   - Disease Match (with match score %)
   - Treatment Line Match
   - Biomarker Requirements (with gates and actions)
   - Location Match
   - Overall match assessment

3. 🧬 CLINICAL MECHANISM - [Drug Name]
   - What the drug is (drug class, mechanism)
   - Why it's groundbreaking for ovarian cancer
   - The strategy (if combination)

4. 📊 ELIGIBILITY ASSESSMENT FOR AYESHA
   - Table format: Criterion | Ayesha's Status | Match | Action Required

5. 🚨 CRITICAL DECISION TREE FOR AYESHA
   - Visual decision flowchart

6. 💡 STRATEGIC IMPLICATIONS
   - Best-Case Scenario
   - Most Likely Scenario
   - Challenge Scenario

7. ⚔️ ZO'S TACTICAL RECOMMENDATIONS
   - IMMEDIATE ACTIONS (THIS WEEK)
   - Decision flowchart for oncologist

8. 📈 CLINICAL EVIDENCE SUPPORTING THIS TRIAL
   - Track record, key insights

9. 🎯 COMPETITIVE POSITIONING
   - Table comparing this trial vs other options

10. ⚔️ COMMANDER - MY FINAL RECOMMENDATION
    - Priority rank
    - Action plan
    - Expected timeline
    - Probability of eligibility
    - Value proposition

Use emojis, clear sections, actionable recommendations, and match the style of the example provided.
Be specific about biomarker gates, testing requirements, and decision points."""

    try:
        # Call LLM via subprocess (using the tools/llm_api.py script)
        llm_script = project_root / "src" / "tools" / "llm_api.py"
        if not llm_script.exists():
            raise FileNotFoundError(f"LLM script not found: {llm_script}")
        
        result = subprocess.run(
            [sys.executable, str(llm_script), 
             "--prompt", prompt_text, 
             "--provider", "gemini"],  # Use Gemini (more likely to be installed)
            capture_output=True,
            text=True,
            timeout=180,
            cwd=str(project_root)
        )
        
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            raise Exception(f"LLM call failed: {result.stderr}")
    except Exception as e:
        print(f"⚠️ LLM enhancement failed: {e}")
        return render_dossier_markdown(dossier_data)  # Fallback to standard format

async def main():
    """Generate enhanced dossier for Ayesha."""
    print("⚔️ Generating Enhanced Dossier for Ayesha\n")
    
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
    
    # Find a good ovarian cancer trial
    print("1. Finding ovarian cancer trial...")
    all_trials = get_trials_from_sqlite()
    
    # Filter for ovarian cancer
    ovarian_trials = [
        t for t in all_trials 
        if 'ovarian' in (t.get('conditions', '') or t.get('title', '') or '').lower()
    ]
    
    if not ovarian_trials:
        print("   ⚠️ No ovarian cancer trials found, using known trial: NCT03916679")
        test_nct_id = 'NCT03916679'
    else:
        test_nct_id = ovarian_trials[0].get('id') or ovarian_trials[0].get('nct_id', 'NCT03916679')
        print(f"   ✅ Found trial: {test_nct_id}")
        print(f"   Title: {ovarian_trials[0].get('title', 'N/A')[:80]}...")
    
    # Generate dossier
    print(f"\n2. Generating dossier for {test_nct_id}...")
    try:
        dossier_data = await generate_dossier(test_nct_id, AYESHA_PROFILE)
        print(f"   ✅ Dossier generated ({len(dossier_data.get('sections', {}))} sections)")
    except Exception as e:
        print(f"   ❌ Failed: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # Enhance with LLM
    print("\n3. Enhancing dossier with LLM (this may take 30-60 seconds)...")
    try:
        enhanced_markdown = enhance_dossier_with_llm(dossier_data, AYESHA_PROFILE)
        print(f"   ✅ Enhanced dossier generated ({len(enhanced_markdown)} chars)")
    except Exception as e:
        print(f"   ⚠️ LLM enhancement failed: {e}")
        enhanced_markdown = render_dossier_markdown(dossier_data)
        print(f"   ✅ Using standard format ({len(enhanced_markdown)} chars)")
    
    # Save outputs
    output_dir = Path(".cursor/ayesha/generated_dossiers") / test_nct_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    
    # Save enhanced markdown
    md_file = output_dir / f"enhanced_dossier_{test_nct_id}_{timestamp}.md"
    md_file.write_text(enhanced_markdown)
    print(f"\n   ✅ Enhanced markdown saved: {md_file}")
    
    # Save JSON
    json_file = output_dir / f"dossier_{test_nct_id}_{timestamp}.json"
    json_file.write_text(json.dumps(dossier_data, indent=2))
    print(f"   ✅ JSON saved: {json_file}")
    
    # Also save to test_output for easy access
    test_output_dir = Path(".cursor/ayesha/test_output")
    test_output_dir.mkdir(parents=True, exist_ok=True)
    (test_output_dir / "enhanced_dossier.md").write_text(enhanced_markdown)
    (test_output_dir / "enhanced_dossier.json").write_text(json.dumps(dossier_data, indent=2))
    print(f"   ✅ Also saved to: {test_output_dir}/enhanced_dossier.md")
    
    print(f"\n⚔️ Dossier generation COMPLETE!")
    print(f"\n📄 View the enhanced dossier:")
    print(f"   {md_file}")
    print(f"\n📄 Or quick access:")
    print(f"   {test_output_dir}/enhanced_dossier.md")
    
    # Show preview
    print(f"\n📋 PREVIEW (first 500 chars):")
    print("=" * 80)
    print(enhanced_markdown[:500])
    print("=" * 80)

if __name__ == "__main__":
    asyncio.run(main())
