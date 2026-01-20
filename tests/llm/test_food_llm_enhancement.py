"""
Test script for LLM Food Enhancement Service

Run this to see actual LLM outputs for food validation.
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))

# Set PYTHONPATH
os.environ['PYTHONPATH'] = str(BACKEND_ROOT)

from api.services.food_llm_enhancement_service import get_food_llm_enhancement_service


async def test_personalized_rationale():
    """Test personalized rationale generation."""
    print("\n" + "="*80)
    print("TEST 1: Personalized Rationale Generation")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    result = await service.generate_personalized_rationale(
        compound="Vitamin D",
        disease="ovarian_cancer_hgs",
        cancer_type="High-Grade Serous Ovarian Cancer",
        treatment_line="L1",
        biomarkers={
            "HRD": "POSITIVE",
            "TMB": 8,
            "germline_BRCA": "NEGATIVE"
        },
        pathways=["dna_repair", "hrd_ddr", "immune_modulation"],
        sae_features={
            "line_fitness": {"score": 0.9, "status": "appropriate"},
            "cross_resistance": {"risk": "LOW", "score": 0.0},
            "sequencing_fitness": {"score": 0.85, "optimal": True}
        },
        evidence_grade="MODERATE",
        total_papers=15,
        rct_count=2
    )
    
    print("\n📝 PERSONALIZED RATIONALE:")
    print("-" * 80)
    print(result)
    print("-" * 80)


async def test_mechanism_synthesis():
    """Test mechanism synthesis."""
    print("\n" + "="*80)
    print("TEST 2: Mechanism Synthesis (Beyond Keywords)")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    # Mock papers
    papers = [
        {
            "pmid": "25489052",
            "title": "Vitamin D and survival in ovarian cancer: a systematic review",
            "abstract": "Patients with serum 25(OH)D >30 ng/mL had HR 0.77 for mortality. Vitamin D enhances BRCA1 function through VDR activation and supports DNA repair pathways. In vitro studies show Vitamin D receptor (VDR) transcriptional control of DNA repair genes."
        },
        {
            "pmid": "23456789",
            "title": "Vitamin D receptor signaling in homologous recombination repair",
            "abstract": "VDR activation upregulates BRCA1 and RAD51 expression, enhancing homologous recombination repair capacity. This is particularly relevant for HRD+ patients where DNA repair is compromised."
        },
        {
            "pmid": "34567890",
            "title": "Immune modulation by Vitamin D in cancer patients",
            "abstract": "Vitamin D modulates immune function through VDR-mediated cytokine regulation, supporting immune surveillance in cancer patients."
        }
    ]
    
    result = await service.synthesize_mechanisms_llm(
        compound="Vitamin D",
        disease="ovarian cancer",
        pathways=["dna_repair", "hrd_ddr", "immune_modulation"],
        papers=papers,
        max_mechanisms=5
    )
    
    print("\n🔬 LLM-SYNTHESIZED MECHANISMS:")
    print("-" * 80)
    for i, mechanism in enumerate(result, 1):
        print(f"{i}. {mechanism}")
    print("-" * 80)
    print(f"\nTotal mechanisms discovered: {len(result)}")


async def test_evidence_interpretation():
    """Test evidence interpretation for treatment line."""
    print("\n" + "="*80)
    print("TEST 3: Evidence Interpretation (Treatment Line Context)")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    papers = [
        {
            "pmid": "25489052",
            "title": "Vitamin D supplementation in first-line ovarian cancer therapy",
            "abstract": "Randomized controlled trial of Vitamin D in first-line chemotherapy for ovarian cancer..."
        },
        {
            "pmid": "23456789",
            "title": "Vitamin D and frontline treatment outcomes",
            "abstract": "Prospective study of Vitamin D levels during primary chemotherapy..."
        }
    ]
    
    result = await service.interpret_evidence_for_treatment_line(
        compound="Vitamin D",
        disease="ovarian cancer",
        treatment_line="L1",
        evidence_grade="MODERATE",
        papers=papers,
        total_papers=15,
        rct_count=2
    )
    
    print("\n📊 EVIDENCE INTERPRETATION:")
    print("-" * 80)
    print(f"Interpretation: {result.get('interpretation', 'N/A')}")
    print(f"\nTreatment Line Relevance: {result.get('treatment_line_relevance', 'N/A')}")
    print(f"Confidence Note: {result.get('confidence_note', 'N/A')}")
    print("-" * 80)


async def test_patient_recommendations():
    """Test patient-specific recommendations."""
    print("\n" + "="*80)
    print("TEST 4: Patient-Specific Recommendations")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    result = await service.generate_patient_specific_recommendations(
        compound="Vitamin D",
        disease="ovarian_cancer_hgs",
        cancer_type="High-Grade Serous Ovarian Cancer",
        treatment_line="L1",
        biomarkers={
            "HRD": "POSITIVE",
            "TMB": 8
        },
        sae_features={
            "line_fitness": {"score": 0.9, "status": "appropriate"},
            "cross_resistance": {"risk": "LOW", "score": 0.0},
            "sequencing_fitness": {"score": 0.85, "optimal": True}
        },
        dosage="2000-4000 IU daily",
        evidence={
            "evidence_grade": "MODERATE",
            "total_papers": 15,
            "rct_count": 2
        }
    )
    
    print("\n👤 PATIENT-SPECIFIC RECOMMENDATIONS:")
    print("-" * 80)
    print(f"⏰ TIMING:")
    print(f"   {result.get('timing', 'N/A')}")
    print(f"\n📊 MONITORING:")
    print(f"   {result.get('monitoring', 'N/A')}")
    print(f"\n⚠️ SAFETY NOTES:")
    print(f"   {result.get('safety_notes', 'N/A')}")
    print(f"\n📋 PATIENT INSTRUCTIONS:")
    print(f"   {result.get('patient_instructions', 'N/A')}")
    print("-" * 80)


async def test_green_tea_maintenance():
    """Test Green Tea for maintenance therapy."""
    print("\n" + "="*80)
    print("TEST 5: Green Tea for Maintenance Therapy (L3)")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    result = await service.generate_personalized_rationale(
        compound="Green Tea (EGCG)",
        disease="ovarian_cancer_hgs",
        cancer_type="High-Grade Serous Ovarian Cancer",
        treatment_line="L3",
        biomarkers={
            "HRD": "POSITIVE",
            "TMB": 8
        },
        pathways=["angiogenesis", "nfkb_signaling", "inflammation"],
        sae_features={
            "line_fitness": {"score": 0.85, "status": "appropriate"},
            "cross_resistance": {"risk": "LOW", "score": 0.1},
            "sequencing_fitness": {"score": 0.85, "optimal": True}
        },
        evidence_grade="MODERATE",
        total_papers=12,
        rct_count=1
    )
    
    print("\n📝 PERSONALIZED RATIONALE (Maintenance Therapy):")
    print("-" * 80)
    print(result)
    print("-" * 80)


async def test_curcumin_tmb_high():
    """Test Curcumin for TMB-high patient."""
    print("\n" + "="*80)
    print("TEST 6: Curcumin for TMB-High Patient (L2)")
    print("="*80)
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("⚠️ LLM not available - check API keys")
        return
    
    result = await service.generate_personalized_rationale(
        compound="Curcumin",
        disease="ovarian_cancer_hgs",
        cancer_type="High-Grade Serous Ovarian Cancer",
        treatment_line="L2",
        biomarkers={
            "TMB": 15,
            "HRD": "NEGATIVE"
        },
        pathways=["nfkb_signaling", "inflammation", "immune_surveillance"],
        sae_features={
            "line_fitness": {"score": 0.75, "status": "moderate"},
            "cross_resistance": {"risk": "LOW", "score": 0.2},
            "sequencing_fitness": {"score": 0.70, "optimal": False}
        },
        evidence_grade="MODERATE",
        total_papers=18,
        rct_count=2
    )
    
    print("\n📝 PERSONALIZED RATIONALE (TMB-High, Second-Line):")
    print("-" * 80)
    print(result)
    print("-" * 80)


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*80)
    print("🧪 LLM FOOD ENHANCEMENT SERVICE - TEST SUITE")
    print("="*80)
    print("\nTesting LLM-enhanced food validation outputs...")
    print("Note: Requires GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY")
    
    service = get_food_llm_enhancement_service()
    
    if not service.llm_available:
        print("\n❌ LLM NOT AVAILABLE")
        print("Please set one of:")
        print("  - GEMINI_API_KEY")
        print("  - ANTHROPIC_API_KEY")
        print("  - OPENAI_API_KEY")
        return
    
    print(f"\n✅ LLM Available (Provider: {service.provider}, Model: {service.model})")
    
    try:
        await test_personalized_rationale()
        await test_mechanism_synthesis()
        await test_evidence_interpretation()
        await test_patient_recommendations()
        await test_green_tea_maintenance()
        await test_curcumin_tmb_high()
        
        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETE")
        print("="*80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(run_all_tests())


