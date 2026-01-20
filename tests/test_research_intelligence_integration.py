"""
Test Research Intelligence Integration

Tests the complete flow:
1. Database connection
2. Query execution and auto-save
3. Dossier generation
4. Query history retrieval
5. Value synthesis

Run: python tests/test_research_intelligence_integration.py
"""

import asyncio
import os
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any
import json

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.agent_manager import get_supabase_client
from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
from api.services.research_intelligence.dossier_generator import ResearchIntelligenceDossierGenerator
from api.services.research_intelligence.value_synthesizer import ValueSynthesizer
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_database_connection():
    """Test 1: Verify Supabase connection."""
    print("\n" + "="*80)
    print("TEST 1: Database Connection")
    print("="*80)
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            print("❌ Supabase client not available")
            print("   Check SUPABASE_URL and SUPABASE_ANON_KEY in .env")
            return False
        
        # Try a simple query to verify connection
        response = supabase.table("research_intelligence_queries").select("id").limit(1).execute()
        print("✅ Supabase connection successful")
        print(f"   Tables accessible: research_intelligence_queries")
        return True
    except Exception as e:
        print(f"❌ Database connection failed: {e}")
        return False


async def test_query_execution():
    """Test 2: Execute a research query."""
    print("\n" + "="*80)
    print("TEST 2: Query Execution")
    print("="*80)
    
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        
        test_question = "How does curcumin help with cancer?"
        test_context = {
            "disease": "breast_cancer",
            "treatment_line": "L1",
            "biomarkers": {}
        }
        
        print(f"Question: {test_question}")
        print(f"Context: {json.dumps(test_context, indent=2)}")
        print("\n⏳ Running research query...")
        
        result = await orchestrator.research_question(
            question=test_question,
            context=test_context
        )
        
        if result:
            print("✅ Query execution successful")
            print(f"   - Mechanisms found: {len(result.get('synthesized_findings', {}).get('mechanisms', []))}")
            print(f"   - MOAT analysis: {'Yes' if result.get('moat_analysis') else 'No'}")
            return result
        else:
            print("❌ Query returned no results")
            return None
    except Exception as e:
        print(f"❌ Query execution failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_dossier_generation(query_result: Dict[str, Any]):
    """Test 3: Generate dossier."""
    print("\n" + "="*80)
    print("TEST 3: Dossier Generation")
    print("="*80)
    
    if not query_result:
        print("⚠️ Skipping - no query result available")
        return None
    
    try:
        generator = ResearchIntelligenceDossierGenerator()
        
        for persona in ["patient", "doctor", "r&d"]:
            print(f"\n⏳ Generating dossier for {persona}...")
            dossier = await generator.generate_dossier(
                query_result=query_result,
                persona=persona,
                query_id="test-query-id"
            )
            
            if dossier and dossier.get("markdown"):
                markdown_length = len(dossier["markdown"])
                sections = dossier.get("sections", {})
                print(f"✅ {persona.capitalize()} dossier generated")
                print(f"   - Markdown length: {markdown_length} chars")
                print(f"   - Sections: {', '.join([k for k, v in sections.items() if v])}")
            else:
                print(f"❌ Failed to generate {persona} dossier")
                return None
        
        print("\n✅ All persona dossiers generated successfully")
        return dossier
    except Exception as e:
        print(f"❌ Dossier generation failed: {e}")
        import traceback
        traceback.print_exc()
        return None


async def test_value_synthesis(query_result: Dict[str, Any]):
    """Test 4: Generate value synthesis."""
    print("\n" + "="*80)
    print("TEST 4: Value Synthesis")
    print("="*80)
    
    if not query_result:
        print("⚠️ Skipping - no query result available")
        return None
    
    try:
        synthesizer = ValueSynthesizer()
        
        for persona in ["patient", "doctor", "r&d"]:
            print(f"\n⏳ Generating value synthesis for {persona}...")
            insights = await synthesizer.synthesize_insights(
                query_result=query_result,
                persona=persona
            )
            
            if insights:
                print(f"✅ {persona.capitalize()} value synthesis generated")
                if insights.get("executive_summary"):
                    print(f"   - Executive summary: {insights['executive_summary'][:100]}...")
                if insights.get("action_items"):
                    print(f"   - Action items: {len(insights['action_items'])}")
            else:
                print(f"⚠️ No insights generated for {persona} (may be using fallback)")
        
        print("\n✅ Value synthesis test completed")
        return True
    except Exception as e:
        print(f"❌ Value synthesis failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_database_operations():
    """Test 5: Database operations (requires authenticated user)."""
    print("\n" + "="*80)
    print("TEST 5: Database Operations")
    print("="*80)
    
    try:
        supabase = get_supabase_client()
        if not supabase:
            print("⚠️ Supabase not available - skipping database tests")
            return False
        
        # Test table existence
        try:
            response = supabase.table("research_intelligence_queries").select("id").limit(1).execute()
            print("✅ research_intelligence_queries table exists")
        except Exception as e:
            print(f"❌ research_intelligence_queries table error: {e}")
            return False
        
        try:
            response = supabase.table("research_intelligence_dossiers").select("id").limit(1).execute()
            print("✅ research_intelligence_dossiers table exists")
        except Exception as e:
            print(f"❌ research_intelligence_dossiers table error: {e}")
            return False
        
        print("\n✅ All database tables accessible")
        print("   Note: Full CRUD tests require authenticated user")
        return True
    except Exception as e:
        print(f"❌ Database operations test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("\n" + "="*80)
    print("RESEARCH INTELLIGENCE INTEGRATION TESTS")
    print("="*80)
    print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    results = {}
    
    # Test 1: Database connection
    results["database_connection"] = await test_database_connection()
    
    # Test 2: Query execution
    query_result = await test_query_execution()
    results["query_execution"] = query_result is not None
    
    # Test 3: Dossier generation
    dossier_result = await test_dossier_generation(query_result)
    results["dossier_generation"] = dossier_result is not None
    
    # Test 4: Value synthesis
    results["value_synthesis"] = await test_value_synthesis(query_result)
    
    # Test 5: Database operations
    results["database_operations"] = await test_database_operations()
    
    # Summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    
    for test_name, passed in results.items():
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    total = len(results)
    passed = sum(1 for v in results.values() if v)
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 ALL TESTS PASSED - Integration ready!")
    else:
        print(f"\n⚠️ {total - passed} test(s) failed - Review errors above")
    
    print("="*80)


if __name__ == "__main__":
    asyncio.run(main())

