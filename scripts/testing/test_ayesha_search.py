#!/usr/bin/env python3
"""
Test Ayesha search directly to debug why no trials are found.
"""
import sys
import os
import asyncio

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.hybrid_trial_search import HybridTrialSearchService
from api.services.clinical_trial_search_service import ClinicalTrialSearchService

async def test_search():
    """Test the search services directly."""
    print("🔍 Testing Ayesha search...")
    
    # Test 1: Direct AstraDB search
    print("\n1️⃣ Testing ClinicalTrialSearchService directly...")
    astradb_service = ClinicalTrialSearchService()
    query = "ovarian cancer first_line IVB"
    
    try:
        result = await astradb_service.search_trials(
            query=query,
            disease_category="ovarian_cancer",
            top_k=10
        )
        
        print(f"   Response structure: {type(result)}")
        print(f"   Success: {result.get('success', False)}")
        print(f"   Found trials: {len(result.get('data', {}).get('found_trials', []))}")
        
        if result.get('data', {}).get('found_trials'):
            first_trial = result['data']['found_trials'][0]
            print(f"   First trial NCT: {first_trial.get('nct_id', 'N/A')}")
            print(f"   First trial title: {first_trial.get('title', 'N/A')[:50]}...")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()
    
    # Test 2: Hybrid search
    print("\n2️⃣ Testing HybridTrialSearchService...")
    hybrid_service = HybridTrialSearchService()
    patient_context = {
        "condition": "ovarian_cancer_high_grade_serous",
        "disease_category": "ovarian_cancer",
        "location_state": "NY"
    }
    
    try:
        results = await hybrid_service.search_optimized(
            query=query,
            patient_context=patient_context,
            germline_status="negative",
            tumor_context={},
            top_k=10
        )
        
        print(f"   Results: {len(results)} trials")
        if results:
            print(f"   First trial: {results[0].get('nct_id', 'N/A')}")
    except Exception as e:
        print(f"   ❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_search())


