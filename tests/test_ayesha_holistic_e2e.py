#!/usr/bin/env python3
"""
End-to-End Test: Ayesha Holistic Score Pipeline

Tests the complete holistic scoring workflow with Ayesha's DDR-high profile
against candidate trials with MoA vectors.
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv()


async def test_ayesha_holistic_e2e():
    print("🧬 AYESHA END-TO-END HOLISTIC SCORE TEST")
    print("=" * 60)
    
    from api.services.holistic_score_service import get_holistic_score_service
    
    service = get_holistic_score_service()
    
    # Ayesha's DDR-high profile (MBD4 + TP53)
    ayesha_profile = {
        "disease": "ovarian_cancer_hgs",
        "mechanism_vector": [0.88, 0.12, 0.15, 0.10, 0.05, 0.20, 0.0],  # DDR-high
        "age": 40,
        "mutations": [
            {"gene": "MBD4", "variant": "c.1239delA"},
            {"gene": "TP53", "variant": "p.R273H"}
        ],
        "germline_variants": [],
        "tumor_context": {
            "hrd_score": 42,
            "stage": "IVB",
            "p53_status": "mutant"
        },
        "location": {"state": "NY"}
    }
    
    print("\n📋 Patient Profile: Ayesha (MBD4+TP53, DDR-high)")
    print(f"   Mechanism Vector: DDR={ayesha_profile['mechanism_vector'][0]}, IO={ayesha_profile['mechanism_vector'][5]}")
    
    # Ayesha's candidate trials with MoA vectors
    ayesha_trials = [
        {
            "nct_id": "NCT04284969",
            "title": "Olaparib + Ceralasertib (PARP+ATR)",
            "moa_vector": [0.95, 0.10, 0.20, 0.15, 0.05, 0.0, 0.0],  # DDR-high
            "overall_status": "RECRUITING",
            "phase": "Phase 2",
            "conditions": ["Ovarian Cancer"]
        },
        {
            "nct_id": "NCT01891344",
            "title": "Niraparib + Bevacizumab (PARP+VEGF)",
            "moa_vector": [0.80, 0.0, 0.10, 0.40, 0.0, 0.0, 0.0],  # DDR + VEGF
            "overall_status": "RECRUITING",
            "phase": "Phase 3"
        },
        {
            "nct_id": "NCT02657889",
            "title": "Pembrolizumab + Olaparib (IO+PARP)",
            "moa_vector": [0.70, 0.0, 0.0, 0.0, 0.0, 0.60, 0.0],  # DDR + IO
            "overall_status": "RECRUITING",
            "phase": "Phase 2"
        },
        {
            "nct_id": "NCT-MAPK-001",
            "title": "MEK Inhibitor Trial (MAPK pathway)",
            "moa_vector": [0.10, 0.90, 0.10, 0.0, 0.0, 0.0, 0.0],  # MAPK-focused (bad fit)
            "overall_status": "RECRUITING",
            "phase": "Phase 2"
        },
        {
            "nct_id": "NCT-CHEMO-001",
            "title": "Standard Carboplatin + Paclitaxel",
            "moa_vector": [0.30, 0.10, 0.10, 0.10, 0.0, 0.10, 0.0],  # Neutral
            "overall_status": "RECRUITING",
            "phase": "Phase 3"
        }
    ]
    
    print(f"\n🔬 Testing {len(ayesha_trials)} trials with Holistic Score...")
    print("-" * 60)
    
    # Run batch scoring
    results = await service.compute_batch(
        patient_profile=ayesha_profile,
        trials=ayesha_trials,
        pharmacogenes=[]
    )
    
    print("\n📊 HOLISTIC SCORE RESULTS (Ranked by Score):")
    print("=" * 60)
    
    for i, r in enumerate(results, 1):
        title = r.get("title", "N/A")[:42]
        print(f"\n#{i} {r['nct_id']}")
        print(f"   Title: {title}")
        print(f"   ✨ Holistic: {r['holistic_score']:.2f} | 🧬 Mech: {r['mechanism_fit_score']:.2f} | 📋 Elig: {r['eligibility_score']:.2f} | 💊 PGx: {r['pgx_safety_score']:.2f}")
        print(f"   📈 Interpretation: {r['interpretation']}")
    
    print("\n" + "=" * 60)
    
    # Validate DDR trials ranked higher than MAPK trials
    ddr_trial = next((r for r in results if r["nct_id"] == "NCT04284969"), None)
    mapk_trial = next((r for r in results if r["nct_id"] == "NCT-MAPK-001"), None)
    
    print("\n🎯 VALIDATION:")
    if ddr_trial and mapk_trial:
        print(f"   DDR Trial (NCT04284969) Mechanism Fit: {ddr_trial['mechanism_fit_score']:.2f}")
        print(f"   MAPK Trial (NCT-MAPK-001) Mechanism Fit: {mapk_trial['mechanism_fit_score']:.2f}")
        
        if ddr_trial["mechanism_fit_score"] > mapk_trial["mechanism_fit_score"]:
            print("   ✅ PASS: DDR trials correctly ranked higher than MAPK trials!")
        else:
            print("   ⚠️ FAIL: DDR trials should rank higher")
            
        if ddr_trial["holistic_score"] > mapk_trial["holistic_score"]:
            print("   ✅ PASS: DDR trials have higher holistic score!")
        else:
            print("   ⚠️ FAIL: Holistic score ranking incorrect")
    
    # Check top trial is DDR-focused
    top_trial = results[0] if results else None
    if top_trial:
        print(f"\n   Top Ranked Trial: {top_trial['nct_id']}")
        if "PARP" in top_trial.get("title", "") or top_trial["nct_id"] == "NCT04284969":
            print("   ✅ PASS: Top trial is PARP/DDR-focused (correct for DDR-high patient)")
        else:
            print("   ⚠️ Top trial is not DDR-focused")
    
    print("\n" + "=" * 60)
    print("✅ E2E TEST COMPLETE")
    
    return results


if __name__ == "__main__":
    results = asyncio.run(test_ayesha_holistic_e2e())
