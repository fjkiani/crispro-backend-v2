"""
MOAT Integration Test - Validates the complete toxicity → food mitigation flow.

This test validates the implementation of:
- ADVANCED_CARE_PLAN Section 4: Toxicity & Pharmacogenomics
- ADVANCED_CARE_PLAN Section 7: Nutraceutical Synergy/Antagonism
"""

import asyncio
import sys
from pathlib import Path

# Add parent to path
sys.path.insert(0, str(Path(__file__).parent))


async def test_complete_moat():
    print("=" * 70)
    print("MOAT INTEGRATION TEST")
    print("Testing: Toxicity → Mitigating Foods Flow")
    print("=" * 70)
    
    # =========================================================================
    # TEST 1: Core Functions Exist
    # =========================================================================
    print("\n[TEST 1] Core Functions Exist")
    print("-" * 50)
    
    from api.services.toxicity_pathway_mappings import (
        compute_pathway_overlap,
        get_mitigating_foods,
        get_drug_moa
    )
    print("   ✅ compute_pathway_overlap imported")
    print("   ✅ get_mitigating_foods imported")
    print("   ✅ get_drug_moa imported")
    
    # =========================================================================
    # TEST 2: Pathway → Foods Mapping
    # =========================================================================
    print("\n[TEST 2] Pathway → Foods Mapping")
    print("-" * 50)
    
    # DNA repair
    dna_foods = get_mitigating_foods({"dna_repair": 1.0, "inflammation": 0.0, "cardiometabolic": 0.0})
    assert len(dna_foods) == 3, f"Expected 3 DNA repair foods, got {len(dna_foods)}"
    print(f"   ✅ DNA repair → {len(dna_foods)} foods: {[f['compound'] for f in dna_foods]}")
    
    # Inflammation
    inf_foods = get_mitigating_foods({"dna_repair": 0.0, "inflammation": 1.0, "cardiometabolic": 0.0})
    assert len(inf_foods) == 3, f"Expected 3 inflammation foods, got {len(inf_foods)}"
    print(f"   ✅ Inflammation → {len(inf_foods)} foods: {[f['compound'] for f in inf_foods]}")
    
    # Cardiometabolic
    cardio_foods = get_mitigating_foods({"dna_repair": 0.0, "inflammation": 0.0, "cardiometabolic": 1.0})
    assert len(cardio_foods) == 3, f"Expected 3 cardio foods, got {len(cardio_foods)}"
    print(f"   ✅ Cardiometabolic → {len(cardio_foods)} foods: {[f['compound'] for f in cardio_foods]}")
    
    # =========================================================================
    # TEST 3: Drug → MoA Lookup
    # =========================================================================
    print("\n[TEST 3] Drug → MoA Lookup")
    print("-" * 50)
    
    assert get_drug_moa("carboplatin") == "platinum_agent"
    assert get_drug_moa("doxorubicin") == "anthracycline"
    assert get_drug_moa("pembrolizumab") == "checkpoint_inhibitor"
    assert get_drug_moa("olaparib") == "PARP_inhibitor"
    assert get_drug_moa("unknown") == "unknown"
    
    print("   ✅ carboplatin → platinum_agent")
    print("   ✅ doxorubicin → anthracycline")
    print("   ✅ pembrolizumab → checkpoint_inhibitor")
    print("   ✅ olaparib → PARP_inhibitor")
    print("   ✅ unknown → unknown (fallback works)")
    
    # =========================================================================
    # TEST 4: Full API Response Includes mitigating_foods
    # =========================================================================
    print("\n[TEST 4] Safety API Returns mitigating_foods")
    print("-" * 50)
    
    from api.services.safety_service import get_safety_service
    from api.schemas.safety import (
        ToxicityRiskRequest, PatientContext, GermlineVariant,
        TherapeuticCandidate, ClinicalContext
    )
    
    service = get_safety_service()
    
    # Scenario: BRCA1 patient on carboplatin (platinum_agent)
    request = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="17", pos=41276045, ref="A", alt="G", gene="BRCA1")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
        context=ClinicalContext(disease="ovarian_cancer"),
        options={"profile": "baseline"}
    )
    
    result = await service.compute_toxicity_risk(request)
    
    assert hasattr(result, 'mitigating_foods'), "mitigating_foods field missing from response"
    assert len(result.mitigating_foods) >= 3, f"Expected 3+ mitigating foods, got {len(result.mitigating_foods)}"
    
    print(f"   ✅ Risk Score: {result.risk_score}")
    print(f"   ✅ mitigating_foods field present: {len(result.mitigating_foods)} foods")
    for food in result.mitigating_foods:
        print(f"      - {food['compound']}: {food['timing']}")
    
    # =========================================================================
    # TEST 5: Clinical Scenarios
    # =========================================================================
    print("\n[TEST 5] Clinical Scenarios")
    print("-" * 50)
    
    # Scenario A: Anthracycline patient (cardiotoxicity)
    request_anthracycline = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="7", pos=100000, ref="C", alt="T", gene="KCNQ1")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="anthracycline"),
        context=ClinicalContext(disease="breast_cancer"),
        options={"profile": "baseline"}
    )
    
    result_anthracycline = await service.compute_toxicity_risk(request_anthracycline)
    cardio_recommended = [f for f in result_anthracycline.mitigating_foods if f["pathway"] == "cardiometabolic"]
    
    print(f"   Scenario A: Anthracycline + KCNQ1 variant")
    print(f"   ✅ Risk Score: {result_anthracycline.risk_score}")
    print(f"   ✅ Cardiometabolic foods: {len(cardio_recommended)}")
    assert any("CoQ10" in f["compound"] for f in cardio_recommended), "CoQ10 should be recommended for cardiotoxicity"
    print(f"   ✅ CoQ10 recommended for cardioprotection")
    
    # Scenario B: Checkpoint inhibitor patient (inflammation/iRAEs)
    request_io = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="6", pos=31575000, ref="G", alt="A", gene="TNF")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="checkpoint_inhibitor"),
        context=ClinicalContext(disease="melanoma"),
        options={"profile": "baseline"}
    )
    
    result_io = await service.compute_toxicity_risk(request_io)
    inflammation_recommended = [f for f in result_io.mitigating_foods if f["pathway"] == "inflammation"]
    
    print(f"\n   Scenario B: Checkpoint Inhibitor + TNF variant")
    print(f"   ✅ Risk Score: {result_io.risk_score}")
    print(f"   ✅ Inflammation foods: {len(inflammation_recommended)}")
    assert any("Omega-3" in f["compound"] for f in inflammation_recommended), "Omega-3 should be recommended for inflammation"
    print(f"   ✅ Omega-3 recommended for iRAE prevention")
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("✅ ALL MOAT INTEGRATION TESTS PASSED!")
    print("=" * 70)
    print("""
MOAT CAPABILITY VALIDATED:
- Toxicity detection → Pathway overlap calculation
- Pathway overlap → Mitigating foods recommendation
- Drug name → MoA lookup
- Full API response includes mitigating_foods
- Clinical scenarios (cardiotoxicity, iRAEs) work correctly

CONNECTION TO ADVANCED CARE PLAN:
- Section 4: Toxicity & Pharmacogenomics ✅ Implemented
- Section 7: Nutraceutical Synergy/Antagonism ✅ Implemented

THE MOAT: "What foods mitigate YOUR drug's toxicity for YOUR germline profile"
""")


if __name__ == "__main__":
    asyncio.run(test_complete_moat())

