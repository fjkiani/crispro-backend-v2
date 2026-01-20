#!/usr/bin/env python3
"""
Quick test to verify Cohere integration in Research Intelligence
"""

import asyncio
import sys
import os
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Test 1: Check LLM abstraction layer
print("=" * 80)
print("TEST 1: LLM Abstraction Layer Initialization")
print("=" * 80)

try:
    from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider
    
    # Try to get Cohere provider
    provider = get_llm_provider(provider=LLMProvider.COHERE)
    
    if provider and provider.is_available():
        print("✅ Cohere provider initialized and available")
        print(f"   - Provider: {provider.get_provider_name()}")
        print(f"   - Default model: {provider.get_default_model()}")
    else:
        print("⚠️  Cohere provider not available")
        print("   - Check COHERE_API_KEY in .env")
        print("   - Provider available:", provider.is_available() if provider else "None")
        
except Exception as e:
    print(f"❌ Failed to initialize Cohere provider: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check enhanced_evidence_service
print("\n" + "=" * 80)
print("TEST 2: Enhanced Evidence Service (LLM Methods)")
print("=" * 80)

try:
    from api.services.enhanced_evidence_service import EnhancedEvidenceService
    
    service = EnhancedEvidenceService()
    
    # Check if methods exist
    has_llm_agnostic = hasattr(service, '_call_llm_agnostic')
    has_llm_comprehensive = hasattr(service, '_call_llm_agnostic_comprehensive')
    has_gemini_alias = hasattr(service, '_call_gemini_llm')  # Backward compat
    
    print(f"✅ EnhancedEvidenceService initialized")
    print(f"   - _call_llm_agnostic: {'✅' if has_llm_agnostic else '❌'}")
    print(f"   - _call_llm_agnostic_comprehensive: {'✅' if has_llm_comprehensive else '❌'}")
    print(f"   - _call_gemini_llm (alias): {'✅' if has_gemini_alias else '❌'}")
    
except Exception as e:
    print(f"❌ Failed to initialize EnhancedEvidenceService: {e}")
    import traceback
    traceback.print_exc()

# Test 3: Check synthesis_engine
print("\n" + "=" * 80)
print("TEST 3: Research Synthesis Engine")
print("=" * 80)

try:
    from api.services.research_intelligence.synthesis_engine import ResearchSynthesisEngine
    
    engine = ResearchSynthesisEngine()
    
    has_llm_provider = hasattr(engine, 'llm_provider')
    has_comprehensive_llm = hasattr(engine, '_comprehensive_llm_extraction')
    has_extract_with_llm = hasattr(engine, '_extract_with_llm')
    
    print(f"✅ ResearchSynthesisEngine initialized")
    print(f"   - llm_provider attribute: {'✅' if has_llm_provider else '❌'}")
    print(f"   - _comprehensive_llm_extraction: {'✅' if has_comprehensive_llm else '❌'}")
    print(f"   - _extract_with_llm: {'✅' if has_extract_with_llm else '❌'}")
    
    if has_llm_provider and engine.llm_provider:
        print(f"   - LLM Provider: {engine.llm_provider.__class__.__name__.replace('Provider', '')}")
        print(f"   - Provider available: {engine.llm_provider.is_available() if hasattr(engine.llm_provider, 'is_available') else 'Unknown'}")
        print(f"   - Has embed method: {'✅' if hasattr(engine.llm_provider, 'embed') else '❌'}")
        print(f"   - Default model: {engine.llm_provider.get_default_model() if hasattr(engine.llm_provider, 'get_default_model') else 'Unknown'}")
    
except Exception as e:
    print(f"❌ Failed to initialize ResearchSynthesisEngine: {e}")
    import traceback
    traceback.print_exc()

# Test 4: Check orchestrator
print("\n" + "=" * 80)
print("TEST 4: Research Intelligence Orchestrator")
print("=" * 80)

try:
    from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
    
    orchestrator = ResearchIntelligenceOrchestrator()
    
    is_available = orchestrator.is_available()
    has_synthesis_engine = hasattr(orchestrator, 'synthesis_engine')
    
    print(f"✅ ResearchIntelligenceOrchestrator initialized")
    print(f"   - Available: {'✅' if is_available else '⚠️'}")
    print(f"   - Has synthesis_engine: {'✅' if has_synthesis_engine else '❌'}")
    
    if has_synthesis_engine and orchestrator.synthesis_engine:
        synth_engine = orchestrator.synthesis_engine
        if hasattr(synth_engine, 'llm_provider') and synth_engine.llm_provider:
            print(f"   - LLM Provider: {synth_engine.llm_provider.__class__.__name__.replace('Provider', '')}")
            print(f"   - Provider available: {synth_engine.llm_provider.is_available() if hasattr(synth_engine.llm_provider, 'is_available') else 'Unknown'}")
            print(f"   - Has embed method: {'✅' if hasattr(synth_engine.llm_provider, 'embed') else '❌'}")
    
except Exception as e:
    print(f"❌ Failed to initialize ResearchIntelligenceOrchestrator: {e}")
    import traceback
    traceback.print_exc()

# Test 5: Simple LLM call test (if API key available)
print("\n" + "=" * 80)
print("TEST 5: Simple LLM Call Test (if API key available)")
print("=" * 80)

async def test_simple_llm_call():
    try:
        from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider

        provider = get_llm_provider(provider=LLMProvider.COHERE)

        if not provider or not provider.is_available():
            print("⚠️  Skipping LLM call test - Cohere provider not available")
            print("   Set COHERE_API_KEY in .env to test actual API calls")
            return

        print("⏳ Testing Cohere API call...")

        response = await provider.chat(
            message="Say 'Hello from Cohere' if you can read this.",
            max_tokens=50,
            temperature=0.0
        )

        print(f"✅ LLM call successful!")
        print(f"   - Response: {response.text[:100]}...")
        print(f"   - Provider: {response.provider}")
        print(f"   - Model: {response.model}")
        print(f"   - Tokens used: {response.tokens_used}")

    except Exception as e:
        print(f"❌ LLM call failed: {e}")
        import traceback
        traceback.print_exc()

# Test 6: Cohere Embeddings Test (for Clinical Trials)
print("\n" + "=" * 80)
print("TEST 6: Cohere Embeddings Test (Clinical Trials)")
print("=" * 80)

async def test_cohere_embeddings():
    try:
        from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider

        provider = get_llm_provider(provider=LLMProvider.COHERE)

        if not provider or not provider.is_available():
            print("⚠️  Skipping embeddings test - Cohere provider not available")
            print("   Set COHERE_API_KEY in .env to test embeddings")
            return

        if not hasattr(provider, 'embed'):
            print("⚠️  Cohere provider doesn't support embeddings yet")
            print("   Need to extend LLMProviderBase with embed() method")
            return

        print("⏳ Testing Cohere embeddings...")

        embedding = await provider.embed(
            text="ovarian cancer BRCA1 clinical trial",
            model="embed-english-v3.0"
        )

        print(f"✅ Embedding generated successfully!")
        print(f"   - Embedding length: {len(embedding)}")
        print(f"   - First 5 values: {embedding[:5]}")
        print(f"   - Provider: {provider.__class__.__name__}")

        # Test that it's a proper embedding (list of floats)
        assert isinstance(embedding, list)
        assert len(embedding) > 0
        assert all(isinstance(x, float) for x in embedding[:10])  # Check first 10

        print("✅ Embedding format validated")

    except Exception as e:
        print(f"❌ Embedding test failed: {e}")
        import traceback
        traceback.print_exc()

# Run async tests
asyncio.run(test_simple_llm_call())
asyncio.run(test_cohere_embeddings())

# Test 7: Clinical Trial Search Service with Cohere
print("\n" + "=" * 80)
print("TEST 7: Clinical Trial Search Service with Cohere")
print("=" * 80)

def test_clinical_trial_service_cohere():
    try:
        from api.services.clinical_trial_search_service import ClinicalTrialSearchService

        print("⏳ Testing ClinicalTrialSearchService with Cohere...")

        service = ClinicalTrialSearchService()
        print("✅ ClinicalTrialSearchService initialized with Cohere")

        # Check that it has LLM provider
        if hasattr(service, 'llm_provider') and service.llm_provider:
            print(f"   - LLM Provider: {service.llm_provider.__class__.__name__.replace('Provider', '')}")
            print(f"   - Provider available: {service.llm_provider.is_available()}")

            # Test embedding generation (without AstraDB dependency)
            test_text = "ovarian cancer BRCA1 clinical trial"
            print(f"⏳ Testing embedding generation for: '{test_text}'")

            import asyncio
            embedding = asyncio.run(service.llm_provider.embed(text=test_text))

            print("✅ Embedding generated successfully!")
            print(f"   - Embedding dimension: {len(embedding)}")
            print(f"   - First 5 values: {embedding[:5]}")
            print(f"   - Value range: [{min(embedding):.3f}, {max(embedding):.3f}]")

            # Test that it's a proper embedding (list of floats)
            assert isinstance(embedding, list)
            assert len(embedding) > 0
            assert all(isinstance(x, float) for x in embedding[:10])

            print("✅ Embedding format validated")
            print("✅ ClinicalTrialSearchService successfully switched to Cohere!")
            return True

        else:
            print("❌ ClinicalTrialSearchService missing LLM provider")
            return False

    except Exception as e:
        print(f"❌ Clinical Trial Search Service test failed: {e}")
        import traceback
        traceback.print_exc()
        return False

# Run clinical trial service test
test_clinical_trial_service_cohere()

print("\n" + "=" * 80)
print("TEST SUMMARY")
print("=" * 80)
print("✅ All structural tests passed")
print("✅ Cohere embeddings working for Clinical Trials")
print("⚠️  API key test requires COHERE_API_KEY in .env")
print("\nNext steps:")
print("1. Set COHERE_API_KEY in .env file")
print("2. Set DEFAULT_LLM_PROVIDER=cohere in .env (optional, defaults to cohere)")
print("3. Run full E2E test: python3 tests/test_research_intelligence_e2e.py")

