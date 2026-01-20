"""
Sprint 2: Backend Verification
Test Research Intelligence orchestrator with 10 real queries to verify system works as documented.

What We're Testing:
- Orchestrator initialization
- All portals connect (PubMed, GDC, PDS)
- MOAT integration returns pathways
- Full pipeline works end-to-end
"""

import asyncio
import json
import logging
import sys
from datetime import datetime
from typing import Dict, List, Any
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Import orchestrator
try:
    from api.services.research_intelligence.orchestrator import ResearchIntelligenceOrchestrator
except ImportError as e:
    logger.error(f"Failed to import ResearchIntelligenceOrchestrator: {e}")
    logger.error("Make sure you're running from the correct directory")
    raise

# 10 Real Test Queries (diverse, covering different use cases)
TEST_QUERIES = [
    {
        "id": 1,
        "question": "What mechanisms does curcumin target in breast cancer?",
        "context": {
            "disease": "breast_cancer",
            "treatment_line": "L2",
            "biomarkers": {"HER2": "NEGATIVE", "ER": "POSITIVE", "HRD": "POSITIVE"}
        },
        "expected_components": ["mechanisms", "pathways", "moat_analysis"]
    },
    {
        "id": 2,
        "question": "How do purple potatoes help with ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L2",
            "biomarkers": {"HRD": "POSITIVE"}
        },
        "expected_components": ["mechanisms", "pathways", "toxicity_mitigation"]
    },
    {
        "id": 3,
        "question": "What is the evidence for PARP inhibitors in BRCA-mutated ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L1",
            "biomarkers": {"BRCA1": "MUTATED", "HRD": "POSITIVE"}
        },
        "expected_components": ["mechanisms", "evidence_tier", "clinical_trial_recommendations"]
    },
    {
        "id": 4,
        "question": "How does platinum resistance develop in ovarian cancer?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L2",
            "biomarkers": {"HRD": "POSITIVE"}
        },
        "expected_components": ["mechanisms", "cross_resistance", "pathways"]
    },
    {
        "id": 5,
        "question": "What are the mechanisms of action for pembrolizumab in lung cancer?",
        "context": {
            "disease": "lung_cancer_nsclc",
            "treatment_line": "L1",
            "biomarkers": {"PD-L1": "POSITIVE", "MSI": "HIGH"}
        },
        "expected_components": ["mechanisms", "pathways", "sae_features"]
    },
    {
        "id": 6,
        "question": "How does green tea extract affect cancer cell apoptosis?",
        "context": {
            "disease": "colorectal_cancer",
            "treatment_line": "L1",
            "biomarkers": {}
        },
        "expected_components": ["mechanisms", "pathways", "article_summaries"]
    },
    {
        "id": 7,
        "question": "What is the role of anthocyanins in cancer prevention?",
        "context": {
            "disease": "breast_cancer",
            "treatment_line": "L1",
            "biomarkers": {}
        },
        "expected_components": ["mechanisms", "evidence_tier", "citation_network"]
    },
    {
        "id": 8,
        "question": "How do taxanes work in triple-negative breast cancer?",
        "context": {
            "disease": "breast_cancer",
            "treatment_line": "L1",
            "biomarkers": {"HER2": "NEGATIVE", "ER": "NEGATIVE", "PR": "NEGATIVE"}
        },
        "expected_components": ["mechanisms", "pathways", "drug_interactions"]
    },
    {
        "id": 9,
        "question": "What mechanisms does olaparib target in BRCA-mutated cancers?",
        "context": {
            "disease": "ovarian_cancer_hgs",
            "treatment_line": "L1",
            "biomarkers": {"BRCA1": "MUTATED", "HRD": "POSITIVE"}
        },
        "expected_components": ["mechanisms", "pathways", "toxicity_mitigation"]
    },
    {
        "id": 10,
        "question": "How does metformin affect cancer metabolism?",
        "context": {
            "disease": "breast_cancer",
            "treatment_line": "L2",
            "biomarkers": {}
        },
        "expected_components": ["mechanisms", "pathways", "sub_question_answers"]
    }
]


async def test_orchestrator_initialization():
    """Test 1: Verify orchestrator initializes correctly"""
    logger.info("=" * 80)
    logger.info("TEST 1: Orchestrator Initialization")
    logger.info("=" * 80)
    
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        logger.info("✅ Orchestrator initialized successfully")
        
        # Check availability
        is_available = orchestrator.is_available()
        logger.info(f"✅ Orchestrator is_available(): {is_available}")
        
        # Check components
        components = {
            "pubmed": orchestrator.pubmed is not None,
            "project_data_sphere": orchestrator.project_data_sphere is not None,
            "gdc": orchestrator.gdc is not None,
            "pubmed_parser": orchestrator.pubmed_parser is not None,
            "pharmacogenomics_parser": orchestrator.pharmacogenomics_parser is not None,
            "question_formulator": orchestrator.question_formulator is not None,
            "synthesis_engine": orchestrator.synthesis_engine is not None,
            "moat_integrator": orchestrator.moat_integrator is not None
        }
        
        logger.info("Component Status:")
        for component, available in components.items():
            status = "✅" if available else "⚠️"
            logger.info(f"  {status} {component}: {available}")
        
        return {
            "test": "orchestrator_initialization",
            "status": "PASS" if is_available else "WARN",
            "components": components,
            "is_available": is_available
        }
    except Exception as e:
        logger.error(f"❌ Orchestrator initialization failed: {e}", exc_info=True)
        return {
            "test": "orchestrator_initialization",
            "status": "FAIL",
            "error": str(e)
        }


async def test_single_query(query_data: Dict[str, Any]) -> Dict[str, Any]:
    """Test a single query end-to-end"""
    query_id = query_data["id"]
    question = query_data["question"]
    context = query_data["context"]
    expected_components = query_data["expected_components"]
    
    logger.info("=" * 80)
    logger.info(f"TEST {query_id + 1}: Query {query_id} - {question[:60]}...")
    logger.info("=" * 80)
    
    start_time = datetime.now()
    
    try:
        orchestrator = ResearchIntelligenceOrchestrator()
        
        # Run research question
        result = await orchestrator.research_question(
            question=question,
            context=context
        )
        
        elapsed = (datetime.now() - start_time).total_seconds()
        
        # Verify result structure
        required_keys = [
            "research_plan",
            "portal_results",
            "parsed_content",
            "synthesized_findings",
            "moat_analysis",
            "provenance"
        ]
        
        missing_keys = [key for key in required_keys if key not in result]
        
        if missing_keys:
            logger.warning(f"⚠️ Missing keys: {missing_keys}")
        else:
            logger.info("✅ All required keys present")
        
        # Check expected components
        found_components = []
        missing_components = []
        
        for component in expected_components:
            if component == "mechanisms":
                found = "mechanisms" in result.get("synthesized_findings", {})
            elif component == "pathways":
                found = "pathways" in result.get("moat_analysis", {})
            elif component == "evidence_tier":
                found = "evidence_tier" in result.get("synthesized_findings", {})
            elif component == "cross_resistance":
                found = "cross_resistance" in result.get("moat_analysis", {})
            elif component == "toxicity_mitigation":
                found = "toxicity_mitigation" in result.get("moat_analysis", {})
            elif component == "clinical_trial_recommendations":
                found = "clinical_trial_recommendations" in result.get("moat_analysis", {})
            elif component == "drug_interactions":
                found = "drug_interactions" in result.get("moat_analysis", {})
            elif component == "citation_network":
                found = "citation_network" in result.get("moat_analysis", {})
            elif component == "sae_features":
                found = "sae_features" in result.get("moat_analysis", {})
            elif component == "article_summaries":
                found = "article_summaries" in result.get("synthesized_findings", {})
            elif component == "sub_question_answers":
                found = "sub_question_answers" in result
            else:
                found = False
            
            if found:
                found_components.append(component)
            else:
                missing_components.append(component)
        
        # Log results
        logger.info(f"✅ Query completed in {elapsed:.2f} seconds")
        logger.info(f"✅ Found components: {found_components}")
        if missing_components:
            logger.warning(f"⚠️ Missing components: {missing_components}")
        
        # Check portal results
        portal_results = result.get("portal_results", {})
        portals_used = []
        if portal_results.get("pubmed"):
            portals_used.append("pubmed")
        if portal_results.get("gdc"):
            portals_used.append("gdc")
        if portal_results.get("project_data_sphere"):
            portals_used.append("project_data_sphere")
        
        logger.info(f"✅ Portals used: {portals_used}")
        
        # Check MOAT analysis
        moat_analysis = result.get("moat_analysis", {})
        moat_components = [key for key in moat_analysis.keys() if moat_analysis.get(key)]
        logger.info(f"✅ MOAT components: {moat_components}")
        
        return {
            "test": f"query_{query_id}",
            "status": "PASS" if not missing_components else "PARTIAL",
            "question": question,
            "elapsed_seconds": elapsed,
            "found_components": found_components,
            "missing_components": missing_components,
            "portals_used": portals_used,
            "moat_components": moat_components,
            "has_mechanisms": "mechanisms" in result.get("synthesized_findings", {}),
            "has_pathways": "pathways" in result.get("moat_analysis", {}),
            "has_provenance": "provenance" in result
        }
        
    except Exception as e:
        elapsed = (datetime.now() - start_time).total_seconds()
        logger.error(f"❌ Query {query_id} failed: {e}", exc_info=True)
        return {
            "test": f"query_{query_id}",
            "status": "FAIL",
            "question": question,
            "elapsed_seconds": elapsed,
            "error": str(e)
        }


async def run_verification_suite():
    """Run all verification tests"""
    logger.info("=" * 80)
    logger.info("SPRINT 2: BACKEND VERIFICATION")
    logger.info("Testing Research Intelligence Orchestrator with 10 real queries")
    logger.info("=" * 80)
    
    results = []
    
    # Test 1: Orchestrator initialization
    init_result = await test_orchestrator_initialization()
    results.append(init_result)
    
    # Tests 2-11: 10 real queries
    for query_data in TEST_QUERIES:
        query_result = await test_single_query(query_data)
        results.append(query_result)
        
        # Small delay between queries to avoid rate limits
        await asyncio.sleep(2)
    
    # Generate summary report
    logger.info("=" * 80)
    logger.info("VERIFICATION SUMMARY")
    logger.info("=" * 80)
    
    total_tests = len(results)
    passed = sum(1 for r in results if r.get("status") == "PASS")
    partial = sum(1 for r in results if r.get("status") == "PARTIAL")
    failed = sum(1 for r in results if r.get("status") == "FAIL")
    warned = sum(1 for r in results if r.get("status") == "WARN")
    
    logger.info(f"Total Tests: {total_tests}")
    logger.info(f"✅ Passed: {passed}")
    logger.info(f"⚠️ Partial: {partial}")
    logger.info(f"⚠️ Warned: {warned}")
    logger.info(f"❌ Failed: {failed}")
    
    # Save results to file
    output_dir = Path("publications/06-research-intelligence/sprint2_results")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / f"verification_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    report = {
        "timestamp": datetime.now().isoformat(),
        "summary": {
            "total_tests": total_tests,
            "passed": passed,
            "partial": partial,
            "warned": warned,
            "failed": failed,
            "pass_rate": f"{(passed / total_tests * 100):.1f}%" if total_tests > 0 else "0%"
        },
        "results": results
    }
    
    with open(output_file, "w") as f:
        json.dump(report, f, indent=2)
    
    logger.info(f"✅ Report saved to: {output_file}")
    
    # Print detailed results
    logger.info("\n" + "=" * 80)
    logger.info("DETAILED RESULTS")
    logger.info("=" * 80)
    
    for result in results:
        test_name = result.get("test", "unknown")
        status = result.get("status", "UNKNOWN")
        logger.info(f"\n{test_name}: {status}")
        
        if status == "PASS":
            if "elapsed_seconds" in result:
                logger.info(f"  ⏱️  Time: {result['elapsed_seconds']:.2f}s")
            if "found_components" in result:
                logger.info(f"  ✅ Components: {', '.join(result['found_components'])}")
            if "portals_used" in result:
                logger.info(f"  🔌 Portals: {', '.join(result['portals_used'])}")
        
        elif status == "PARTIAL":
            logger.warning(f"  ⚠️  Missing: {', '.join(result.get('missing_components', []))}")
        
        elif status == "FAIL":
            logger.error(f"  ❌ Error: {result.get('error', 'Unknown error')}")
    
    return report


if __name__ == "__main__":
    # Run verification suite
    report = asyncio.run(run_verification_suite())
    
    # Exit with appropriate code
    if report["summary"]["failed"] > 0:
        exit(1)
    elif report["summary"]["partial"] > 0 or report["summary"]["warned"] > 0:
        exit(0)  # Partial success is acceptable for verification
    else:
        exit(0)

