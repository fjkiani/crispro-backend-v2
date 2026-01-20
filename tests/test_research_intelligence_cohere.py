#!/usr/bin/env python3
"""
Quick test of Research Intelligence with Cohere
"""

import asyncio
import sys
import json
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator


async def test_research_intelligence():
    print("=" * 80)
    print("TEST: Research Intelligence with Cohere")
    print("=" * 80)
    
    question = "How does olaparib work in ovarian cancer?"
    context = {
        "disease": "ovarian_cancer_hgs",
        "treatment_line": "L1",
        "biomarkers": {"HRD": "POSITIVE"}
    }
    
    print(f"\nQuestion: {question}")
    print(f"Context: {json.dumps(context, indent=2)}")
    print("\n⏳ Running Research Intelligence...")
    
    start_time = datetime.now()
    
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        
        if not orchestrator.is_available():
            print("❌ Orchestrator not available")
            return False
        
        result = await orchestrator.research_question(
            question=question,
            context=context
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Extract key results
        research_plan = result.get('research_plan', {})
        synthesized = result.get('synthesized_findings', {})
        moat_analysis = result.get('moat_analysis', {})
        provenance = result.get('provenance', {})
        
        mechanisms = synthesized.get('mechanisms', [])
        method = synthesized.get('method', 'unknown')
        
        print(f"\n✅ Research Intelligence completed in {elapsed:.2f}s")
        print(f"   - Method used: {method}")
        print(f"   - Mechanisms found: {len(mechanisms)}")
        print(f"   - Overall confidence: {synthesized.get('overall_confidence', 'N/A')}")
        
        if mechanisms:
            print(f"\n   Top mechanisms:")
            for i, mech in enumerate(mechanisms[:3], 1):
                if isinstance(mech, dict):
                    print(f"     {i}. {mech.get('mechanism', 'Unknown')} (confidence: {mech.get('confidence', 'N/A')})")
                else:
                    print(f"     {i}. {mech}")
        
        # Check if Cohere was used
        methods_used = provenance.get('methods', [])
        if 'llm_deep_research' in methods_used:
            print(f"\n   ✅ LLM deep research used (Cohere)")
        elif 'generic_llm_synthesis' in methods_used:
            print(f"\n   ⚠️  Generic LLM synthesis used (fallback)")
        
        return True
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n❌ Test failed after {elapsed:.2f}s: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_research_intelligence())
    
    if success:
        print("\n" + "=" * 80)
        print("✅ RESEARCH INTELLIGENCE WITH COHERE: SUCCESS")
        print("=" * 80)
    else:
        print("\n" + "=" * 80)
        print("❌ RESEARCH INTELLIGENCE WITH COHERE: FAILED")
        print("=" * 80)

