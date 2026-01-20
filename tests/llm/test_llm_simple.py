#!/usr/bin/env python3
"""Simple test to verify LLM service works"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend root to path
BACKEND_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_ROOT))
os.environ['PYTHONPATH'] = str(BACKEND_ROOT)

async def test_simple():
    from api.services.food_llm_enhancement_service import get_food_llm_enhancement_service
    
    service = get_food_llm_enhancement_service()
    print(f"✅ Service initialized")
    print(f"   Model: {service.model}")
    print(f"   Provider: {service.provider}")
    print(f"   LLM Available: {service.llm_available}")
    
    if not service.llm_available:
        print("\n❌ LLM not available - check API keys")
        return
    
    print("\n🧪 Testing personalized rationale...")
    try:
        result = await service.generate_personalized_rationale(
            compound="Vitamin D",
            disease="ovarian_cancer_hgs",
            cancer_type="High-Grade Serous Ovarian Cancer",
            treatment_line="L1",
            biomarkers={"HRD": "POSITIVE", "TMB": 8},
            pathways=["dna_repair", "hrd_ddr"],
            sae_features={
                "line_fitness": {"score": 0.9, "status": "appropriate"},
                "cross_resistance": {"risk": "LOW", "score": 0.0},
                "sequencing_fitness": {"score": 0.85, "optimal": True}
            },
            evidence_grade="MODERATE",
            total_papers=15,
            rct_count=2
        )
        print("\n📝 RESULT:")
        print("-" * 80)
        print(result)
        print("-" * 80)
        print("\n✅ Test passed!")
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_simple())


