#!/usr/bin/env python3
"""Quick test - prints immediately"""

import sys
import os
sys.path.insert(0, '.')

print("=" * 80, flush=True)
print("QUICK LLM TEST", flush=True)
print("=" * 80, flush=True)

try:
    from api.services.food_llm_enhancement_service import get_food_llm_enhancement_service
    print("✅ Import successful", flush=True)
    
    service = get_food_llm_enhancement_service()
    print(f"✅ Service created", flush=True)
    print(f"   Model: {service.model}", flush=True)
    print(f"   Provider: {service.provider}", flush=True)
    print(f"   LLM Available: {service.llm_available}", flush=True)
    
    if service.llm_available:
        print("\n✅ LLM is available - ready to test!", flush=True)
    else:
        print("\n❌ LLM not available - check API keys", flush=True)
        print("   Set GEMINI_API_KEY, ANTHROPIC_API_KEY, or OPENAI_API_KEY", flush=True)
        
except Exception as e:
    print(f"\n❌ ERROR: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("=" * 80, flush=True)


