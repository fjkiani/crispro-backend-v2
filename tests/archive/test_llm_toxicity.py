"""
Test LLM Enhancement for Toxicity Mitigation

Tests Phase 3 implementation from TOXICITY_MOAT_IMPLEMENTATION_TASKS.md
Validates LLM-enhanced rationales for toxicity mitigation.

Created: 2025-01-28
Status: Phase 3 Testing
"""

import asyncio
import sys
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent.parent / '.env')
except:
    pass

sys.path.insert(0, str(Path(__file__).parent))


async def test_llm_enhancement():
    print("=" * 60)
    print("LLM TOXICITY ENHANCEMENT TEST")
    print("=" * 60)
    
    from api.services.llm_toxicity_service import (
        generate_toxicity_rationale, 
        generate_mitigation_dossier,
        LLM_AVAILABLE
    )
    
    print(f"\n[CHECK] LLM Available: {LLM_AVAILABLE}")
    
    if not LLM_AVAILABLE:
        print("⚠️  LLM not available - using static rationales")
        print("    To enable: Set GEMINI_API_KEY in .env")
    
    # Test 1: Single rationale generation
    print("\n[TEST 1] Single Rationale Generation")
    print("-" * 40)
    
    result = await generate_toxicity_rationale(
        compound="NAC (N-Acetyl Cysteine)",
        drug_name="carboplatin",
        drug_moa="platinum_agent",
        toxicity_pathway="dna_repair",
        germline_genes=["BRCA1"],
        cancer_type="ovarian cancer (HGSOC)",
        treatment_phase="first-line chemotherapy",
        base_mechanism="Glutathione precursor, supports DNA repair enzymes",
        timing="post-chemo (not during infusion)",
        dose="600mg twice daily"
    )
    
    print(f"   LLM Enhanced: {result['llm_enhanced']}")
    print(f"   Confidence: {result['confidence']}")
    print(f"\n   Rationale:")
    print(f"   {result['rationale']}")
    print(f"\n   Patient Summary:")
    print(f"   {result['patient_summary']}")
    
    # Test 2: Cardiotoxicity scenario
    print("\n[TEST 2] Cardiotoxicity Mitigation")
    print("-" * 40)
    
    result2 = await generate_toxicity_rationale(
        compound="CoQ10 (Ubiquinol)",
        drug_name="doxorubicin",
        drug_moa="anthracycline",
        toxicity_pathway="cardiometabolic",
        germline_genes=["KCNQ1"],
        cancer_type="breast cancer",
        treatment_phase="adjuvant chemotherapy",
        base_mechanism="Mitochondrial support, cardioprotective",
        timing="with fatty meal, continuous during treatment",
        dose="200-400mg daily"
    )
    
    print(f"   LLM Enhanced: {result2['llm_enhanced']}")
    print(f"\n   Rationale: {result2['rationale'][:200]}...")
    
    # Test 3: Full dossier generation
    print("\n[TEST 3] Full Mitigation Dossier")
    print("-" * 40)
    
    from api.services.toxicity_pathway_mappings import get_mitigating_foods
    
    mitigating_foods = get_mitigating_foods({"dna_repair": 1.0})
    
    dossier = await generate_mitigation_dossier(
        patient_context={
            "cancer_type": "ovarian cancer",
            "germline_genes": ["BRCA1"],
            "treatment_line": "first-line"
        },
        medications=["carboplatin"],
        mitigating_foods=mitigating_foods
    )
    
    print(f"   Dossier Generated: {bool(dossier)}")
    print(f"   LLM Enhanced: {dossier.get('llm_enhanced', False)}")
    print(f"   Food Recommendations: {len(dossier.get('food_recommendations', []))}")
    
    if dossier.get("executive_summary"):
        print(f"\n   Executive Summary:")
        print(f"   {dossier['executive_summary'][:300]}...")
    
    # Test 4: Edge cases
    print("\n[TEST 4] Edge Cases")
    print("-" * 40)
    
    # Empty germline genes
    result_empty = await generate_toxicity_rationale(
        compound="NAC",
        drug_name="carboplatin",
        drug_moa="platinum_agent",
        toxicity_pathway="dna_repair",
        germline_genes=[],  # EMPTY
        cancer_type="ovarian cancer"
    )
    print(f"   ✅ Empty genes handled: {bool(result_empty.get('rationale'))}")
    
    # Unknown drug
    result_unknown = await generate_toxicity_rationale(
        compound="NAC",
        drug_name="made_up_drug_xyz",
        drug_moa="unknown",
        toxicity_pathway="dna_repair",
        germline_genes=["BRCA1"],
        cancer_type="cancer"
    )
    print(f"   ✅ Unknown drug handled: {bool(result_unknown.get('rationale'))}")
    
    print("\n" + "=" * 60)
    print("✅ LLM TOXICITY ENHANCEMENT TEST COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_llm_enhancement())






