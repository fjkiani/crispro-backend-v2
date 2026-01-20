#!/usr/bin/env python3
"""Simple LLM test that prints everything"""

import sys
import os
import asyncio

# Force unbuffered output
sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
sys.stderr = os.fdopen(sys.stderr.fileno(), 'w', 0)

print("Starting test...", flush=True)

# Load .env
try:
    from dotenv import load_dotenv
    from pathlib import Path
    env_path = Path(__file__).resolve().parent.parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}", flush=True)
    else:
        print(f"⚠️ .env not found at: {env_path}", flush=True)
except Exception as e:
    print(f"⚠️ Could not load .env: {e}", flush=True)

# Check API key
api_key = os.getenv("GEMINI_API_KEY")
print(f"🔑 GEMINI_API_KEY set: {bool(api_key)}", flush=True)

# Test import
sys.path.insert(0, '.')
print("Importing service...", flush=True)

try:
    from api.services.food_llm_enhancement_service import get_food_llm_enhancement_service
    print("✅ Import successful", flush=True)
    
    service = get_food_llm_enhancement_service()
    print(f"✅ Service created", flush=True)
    print(f"   Model: {service.model}", flush=True)
    print(f"   LLM Available: {service.llm_available}", flush=True)
    
    if service.llm_available:
        print("\n🧪 Testing LLM call...", flush=True)
        
        async def test():
            result = await service.generate_personalized_rationale(
                compound="Vitamin D",
                disease="ovarian_cancer_hgs",
                cancer_type="High-Grade Serous Ovarian Cancer",
                treatment_line="L1",
                biomarkers={"HRD": "POSITIVE"},
                pathways=["dna_repair"],
                sae_features={"line_fitness": {"score": 0.9}},
                evidence_grade="MODERATE",
                total_papers=15,
                rct_count=2
            )
            print("\n" + "="*80, flush=True)
            print("RESULT:", flush=True)
            print("="*80, flush=True)
            print(result, flush=True)
            print("="*80, flush=True)
        
        asyncio.run(test())
    else:
        print("❌ LLM not available", flush=True)
        
except Exception as e:
    print(f"❌ ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\nTest complete!", flush=True)


