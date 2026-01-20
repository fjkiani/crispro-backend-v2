#!/usr/bin/env python3
"""
End-to-End Tests for Research Intelligence Framework

Tests various research questions to verify production readiness.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator


# Test queries covering different scenarios
TEST_QUERIES = [
    {
        "name": "Food-based compound query",
        "question": "How do purple potatoes help with ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L2",
            "biomarkers": {"HRD": "POSITIVE"}
        }
    },
    {
        "name": "Vitamin/supplement query",
        "question": "How does vitamin D help with ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L1",
            "biomarkers": {"HRD": "POSITIVE", "TMB": 8}
        }
    },
    {
        "name": "Mechanism-focused query",
        "question": "What mechanisms does curcumin target in breast cancer?",
        "context": {
            "disease": "breast_cancer",
            "treatment_line": "L1",
            "biomarkers": {"HER2": "NEGATIVE", "ER": "POSITIVE"}
        }
    },
    {
        "name": "Treatment line specific query",
        "question": "What foods help with platinum resistance in ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L3",
            "biomarkers": {"HRD": "POSITIVE"},
            "prior_therapies": ["carboplatin", "paclitaxel"]
        }
    },
    {
        "name": "Biomarker-specific query",
        "question": "How does green tea help BRCA1-mutant ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L1",
            "biomarkers": {"BRCA": "MUTANT", "HRD": "POSITIVE"}
        }
    },
    {
        "name": "General cancer prevention query",
        "question": "What compounds prevent cancer metastasis?",
        "context": {
            "disease": "general_cancer",
            "treatment_line": "prevention",
            "biomarkers": {}
        }
    }
]


async def run_single_test(test_case: Dict[str, Any], test_num: int, total: int) -> Dict[str, Any]:
    """Run a single test case."""
    print(f"\n{'='*80}")
    print(f"TEST {test_num}/{total}: {test_case['name']}")
    print(f"{'='*80}")
    print(f"Question: {test_case['question']}")
    print(f"Context: {json.dumps(test_case['context'], indent=2)}")
    print("\n⏳ Running research intelligence...")
    
    start_time = datetime.now()
    
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        
        result = await orchestrator.research_question(
            question=test_case['question'],
            context=test_case['context']
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Extract key metrics
        research_plan = result.get('research_plan', {})
        portal_results = result.get('portal_results', {})
        synthesized = result.get('synthesized_findings', {})
        moat_analysis = result.get('moat_analysis', {})
        
        pubmed_articles = portal_results.get('pubmed', {}).get('articles', [])
        top_keywords = portal_results.get('top_keywords', [])
        mechanisms = synthesized.get('mechanisms', [])
        
        print(f"\n✅ Test completed in {elapsed:.2f}s")
        print(f"   - Articles found: {len(pubmed_articles)}")
        print(f"   - Top keywords: {', '.join(top_keywords[:5])}")
        print(f"   - Mechanisms identified: {len(mechanisms)}")
        print(f"   - Overall confidence: {synthesized.get('overall_confidence', 'N/A')}")
        
        return {
            "test_name": test_case['name'],
            "question": test_case['question'],
            "context": test_case['context'],
            "status": "SUCCESS",
            "elapsed_seconds": elapsed,
            "metrics": {
                "articles_found": len(pubmed_articles),
                "top_keywords_count": len(top_keywords),
                "mechanisms_count": len(mechanisms),
                "overall_confidence": synthesized.get('overall_confidence', 0.5)
            },
            "result": result
        }
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        
        return {
            "test_name": test_case['name'],
            "question": test_case['question'],
            "context": test_case['context'],
            "status": "FAILED",
            "elapsed_seconds": elapsed,
            "error": str(e),
            "traceback": traceback.format_exc()
        }


async def run_all_tests():
    """Run all test cases."""
    print("="*80)
    print("RESEARCH INTELLIGENCE FRAMEWORK - END-TO-END TEST SUITE")
    print("="*80)
    print(f"Total tests: {len(TEST_QUERIES)}")
    print(f"Start time: {datetime.now().isoformat()}")
    
    results = []
    
    for i, test_case in enumerate(TEST_QUERIES, 1):
        result = await run_single_test(test_case, i, len(TEST_QUERIES))
        results.append(result)
        
        # Small delay between tests to avoid rate limits
        if i < len(TEST_QUERIES):
            await asyncio.sleep(2)
    
    # Generate summary
    total_tests = len(results)
    successful = sum(1 for r in results if r['status'] == 'SUCCESS')
    failed = total_tests - successful
    total_elapsed = sum(r['elapsed_seconds'] for r in results)
    avg_elapsed = total_elapsed / total_tests if total_tests > 0 else 0
    
    total_articles = sum(r.get('metrics', {}).get('articles_found', 0) for r in results if r['status'] == 'SUCCESS')
    total_mechanisms = sum(r.get('metrics', {}).get('mechanisms_count', 0) for r in results if r['status'] == 'SUCCESS')
    
    summary = {
        "test_suite": "Research Intelligence Framework E2E Tests",
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "successful": successful,
            "failed": failed,
            "success_rate": f"{(successful/total_tests*100):.1f}%" if total_tests > 0 else "0%",
            "total_elapsed_seconds": round(total_elapsed, 2),
            "average_elapsed_seconds": round(avg_elapsed, 2),
            "total_articles_found": total_articles,
            "total_mechanisms_identified": total_mechanisms
        },
        "test_results": results
    }
    
    # Print summary
    print("\n" + "="*80)
    print("TEST SUMMARY")
    print("="*80)
    print(f"Total tests: {total_tests}")
    print(f"Successful: {successful} ✅")
    print(f"Failed: {failed} ❌")
    print(f"Success rate: {summary['summary']['success_rate']}")
    print(f"Total elapsed: {total_elapsed:.2f}s")
    print(f"Average per test: {avg_elapsed:.2f}s")
    print(f"Total articles found: {total_articles}")
    print(f"Total mechanisms identified: {total_mechanisms}")
    
    # Save results
    output_file = Path(__file__).parent / f"research_intelligence_e2e_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(output_file, 'w') as f:
        json.dump(summary, f, indent=2, default=str)
    
    print(f"\n💾 Results saved to: {output_file}")
    
    return summary


if __name__ == "__main__":
    asyncio.run(run_all_tests())























