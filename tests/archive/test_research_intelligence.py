"""
Test Research Intelligence Framework

Tests the full research intelligence pipeline:
- pubmearch (PubMed search + keyword analysis)
- pubmed_parser (deep parsing)
- LLM synthesis
- MOAT integration
"""

import asyncio
import sys
from pathlib import Path
import os
import json

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator

async def test_research_intelligence():
    """Test the full research intelligence pipeline."""
    print("=" * 80)
    print("🔬 RESEARCH INTELLIGENCE FRAMEWORK TEST")
    print("=" * 80)
    
    # Check environment
    print("\n📋 Environment Check:")
    print(f"   NCBI_USER_EMAIL: {'✅ Set' if os.getenv('NCBI_USER_EMAIL') else '❌ Not set'}")
    print(f"   NCBI_USER_API_KEY: {'✅ Set' if os.getenv('NCBI_USER_API_KEY') else '⚠️ Optional'}")
    print(f"   OPENAI_API_KEY: {'✅ Set' if os.getenv('OPENAI_API_KEY') else '❌ Not set (needed for LLM)'}")
    
    # Initialize orchestrator
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        print("\n✅ Orchestrator initialized")
    except Exception as e:
        print(f"\n❌ Orchestrator initialization failed: {e}")
        print("   Note: Some components may not be available")
        return
    
    # Test question
    question = "How do purple potatoes help with ovarian cancer?"
    context = {
        "disease": "ovarian_cancer_hgs",
        "treatment_line": "L2",
        "biomarkers": {"HRD": "POSITIVE", "TMB": 8.2}
    }
    
    print("\n" + "=" * 80)
    print("📊 TEST: Research Intelligence Pipeline")
    print("=" * 80)
    print(f"\nQuestion: {question}")
    print(f"Context: {json.dumps(context, indent=2)}")
    
    try:
        result = await orchestrator.research_question(question, context)
        
        print("\n✅ Research completed!")
        
        # Display results
        print("\n📋 Research Plan:")
        plan = result.get("research_plan", {})
        print(f"   Primary Question: {plan.get('primary_question', 'N/A')}")
        print(f"   Entities: {plan.get('entities', {})}")
        print(f"   Sub-questions: {len(plan.get('sub_questions', []))}")
        
        print("\n📚 Portal Results:")
        portal_results = result.get("portal_results", {})
        pubmed = portal_results.get("pubmed", {})
        print(f"   Articles Found: {pubmed.get('article_count', 0)}")
        top_keywords = portal_results.get("top_keywords", [])
        print(f"   Top Keywords: {', '.join(top_keywords[:10])}")
        
        print("\n📄 Parsed Content:")
        parsed = result.get("parsed_content", {})
        print(f"   Full-text Articles Parsed: {parsed.get('parsed_count', 0)}")
        
        print("\n🧠 Synthesized Findings:")
        synthesized = result.get("synthesized_findings", {})
        mechanisms = synthesized.get("mechanisms", [])
        print(f"   Mechanisms Found: {len(mechanisms)}")
        for mech in mechanisms[:5]:
            print(f"      - {mech.get('mechanism', 'N/A')}: {mech.get('target', 'N/A')} (confidence: {mech.get('confidence', 0):.2f})")
        print(f"   Overall Confidence: {synthesized.get('overall_confidence', 0):.2f}")
        
        print("\n🎯 MOAT Analysis:")
        moat = result.get("moat_analysis", {})
        pathways = moat.get("pathways", [])
        print(f"   Pathways Identified: {', '.join(pathways)}")
        treatment_line = moat.get("treatment_line_analysis", {})
        print(f"   Treatment Line Score: {treatment_line.get('score', 0):.2f} ({treatment_line.get('status', 'N/A')})")
        biomarker = moat.get("biomarker_analysis", {})
        print(f"   Biomarker Matches: {biomarker.get('total_matches', 0)}")
        
        print("\n" + "=" * 80)
        print("✅ TEST COMPLETE")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ Research failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_research_intelligence())










