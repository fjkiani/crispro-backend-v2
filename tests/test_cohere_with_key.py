#!/usr/bin/env python3
"""
Test Cohere integration with API key verification
"""

import asyncio
import sys
import os
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load .env
load_dotenv()

print("=" * 80)
print("COHERE API KEY VERIFICATION")
print("=" * 80)

cohere_key = os.getenv("COHERE_API_KEY")
if not cohere_key:
    print("❌ COHERE_API_KEY not found in .env file")
    print("\n📝 To add it:")
    print("   1. Open: oncology-coPilot/oncology-backend-minimal/.env")
    print("   2. Find the line: COHERE_API_KEY=")
    print("   3. Add your key: COHERE_API_KEY=your-key-here")
    print("   4. Save the file")
    sys.exit(1)

print(f"✅ COHERE_API_KEY found ({len(cohere_key)} characters)")
print(f"   First 10 chars: {cohere_key[:10]}...")

print("\n" + "=" * 80)
print("TESTING COHERE PROVIDER")
print("=" * 80)

async def test_cohere():
    try:
        from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider
        
        # Get Cohere provider
        provider = get_llm_provider(provider=LLMProvider.COHERE)
        
        if not provider:
            print("❌ Failed to get Cohere provider")
            return
        
        if not provider.is_available():
            print("❌ Cohere provider not available")
            print("   - Check COHERE_API_KEY is correct")
            print("   - Check 'cohere' library is installed: pip install cohere")
            return
        
        print(f"✅ Cohere provider initialized")
        print(f"   - Provider: Cohere")
        print(f"   - Model: {provider.get_default_model()}")
        
        print("\n⏳ Testing Cohere API call...")
        
        response = await provider.chat(
            message="Say 'Hello from Cohere' if you can read this. Then explain what you are in one sentence.",
            max_tokens=100,
            temperature=0.0
        )
        
        print(f"\n✅ Cohere API call successful!")
        print(f"   - Response: {response.text}")
        print(f"   - Provider: {response.provider}")
        print(f"   - Model: {response.model}")
        print(f"   - Tokens used: {response.tokens_used}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Cohere test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Run test
success = asyncio.run(test_cohere())

if success:
    print("\n" + "=" * 80)
    print("✅ ALL TESTS PASSED - Cohere is working!")
    print("=" * 80)
    print("\nNext: Test Research Intelligence endpoint:")
    print("  python3 tests/test_research_intelligence_e2e.py")
else:
    print("\n" + "=" * 80)
    print("❌ TESTS FAILED")
    print("=" * 80)

