#!/usr/bin/env python3
"""
Test ClinicalTrialSearchService Cohere Switch

This test demonstrates that we successfully switched ClinicalTrialSearchService
from Google Generative AI (which had the "403 API key leaked" error) to Cohere.

Before the fix: ClinicalTrialSearchService used direct Google AI calls
After the fix: ClinicalTrialSearchService uses LLM abstraction layer with Cohere

Error we fixed: "403 Your API key was reported as leaked. Please use another API key."
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import asyncio
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def test_clinical_trial_cohere_switch():
    """Test that ClinicalTrialSearchService now uses Cohere instead of Google AI."""

    print("🔬 Testing ClinicalTrialSearchService Cohere Switch")
    print("=" * 60)

    try:
        # Import the service
        from api.services.clinical_trial_search_service import ClinicalTrialSearchService

        print("✅ Importing ClinicalTrialSearchService...")

        # Initialize the service
        service = ClinicalTrialSearchService()
        print("✅ ClinicalTrialSearchService initialized successfully")

        # Verify it uses LLM provider (not direct Google AI)
        if hasattr(service, 'llm_provider') and service.llm_provider:
            provider_name = service.llm_provider.__class__.__name__.replace('Provider', '')
            print(f"✅ Service uses LLM provider: {provider_name}")

            if provider_name == 'Cohere':
                print("✅ Confirmed: Using Cohere (not Google AI)")
            else:
                print(f"⚠️  Using {provider_name} (not Cohere)")
                return False

            # Test embedding generation (this would have failed with Google AI)
            test_text = "breast cancer HER2+ clinical trial"
            print(f"⏳ Testing embedding generation for: '{test_text}'")

            # Run the embedding generation (this would have thrown 403 error before)
            embedding = service._generate_embedding(test_text)

            print("✅ Embedding generated successfully!")
            print(f"   - Embedding dimension: {len(embedding)}")
            print(f"   - First 3 values: {embedding[:3]}")
            print(f"   - Value range: [{min(embedding):.3f}, {max(embedding):.3f}]")

            # Verify it's a proper embedding
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding[:10])

            print("✅ Embedding format validated")

            print("\n🎉 SUCCESS!")
            print("✅ ClinicalTrialSearchService successfully switched to Cohere")
            print("✅ No more '403 Your API key was reported as leaked' errors")
            print("✅ Embedding generation works with Cohere")

            return True

        else:
            print("❌ Service missing LLM provider - still using direct Google AI?")
            return False

    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

def check_environment():
    """Check environment variables."""
    print("🔍 Checking environment...")

    cohere_key = os.getenv("COHERE_API_KEY")
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if cohere_key:
        print("✅ COHERE_API_KEY is set")
    else:
        print("❌ COHERE_API_KEY not set - set it in .env file")
        return False

    if gemini_key:
        print("ℹ️  GEMINI_API_KEY is set (still available as fallback)")
    else:
        print("ℹ️  GEMINI_API_KEY not set")

    return True

if __name__ == "__main__":
    print("🔧 Clinical Trial Cohere Switch Test")
    print("=" * 60)

    # Check environment first
    if not check_environment():
        print("\n❌ Environment check failed. Set COHERE_API_KEY in .env")
        sys.exit(1)

    print()

    # Run the test
    success = test_clinical_trial_cohere_switch()

    print("\n" + "=" * 60)
    if success:
        print("🎯 RESULT: ClinicalTrialSearchService successfully switched to Cohere!")
        print("   - Fixed: 403 'API key leaked' error from Google AI")
        print("   - Now using: Cohere embeddings")
        print("   - Status: ✅ WORKING")
        sys.exit(0)
    else:
        print("❌ RESULT: Switch to Cohere failed")
        print("   - Still having issues with ClinicalTrialSearchService")
        sys.exit(1)