#!/usr/bin/env python3
"""Direct test script with immediate output"""

import sys
import os
from pathlib import Path

# Setup paths
BACKEND_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_ROOT))
os.environ['PYTHONPATH'] = str(BACKEND_ROOT)

print("Starting LLM test...", flush=True)

import asyncio
from api.services.food_llm_enhancement_service import get_food_llm_enhancement_service

async def main():
    print("Getting service...", flush=True)
    service = get_food_llm_enhancement_service()
    
    print(f"Model: {service.model}", flush=True)
    print(f"Provider: {service.provider}", flush=True)
    print(f"LLM Available: {service.llm_available}", flush=True)
    
    if not service.llm_available:
        print("\n❌ LLM not available - check API keys", flush=True)
        return
    
    print("\n🧪 Testing personalized rationale...", flush=True)
    
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
        
        print("\n" + "="*80, flush=True)
        print("📝 PERSONALIZED RATIONALE:", flush=True)
        print("="*80, flush=True)
        print(result, flush=True)
        print("="*80, flush=True)
        print("\n✅ Test completed!", flush=True)
        
    except Exception as e:
        print(f"\n❌ Error: {e}", flush=True)
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())


