#!/usr/bin/env python3
"""
Quick script to check if AstraDB has trials and verify search works.
"""
import sys
import os
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.clinical_trial_search_service import ClinicalTrialSearchService

async def check_astradb():
    """Check AstraDB for trials."""
    print("🔍 Testing AstraDB trial search...")
    
    try:
        # Test search
        print("\n🔍 Testing semantic search for 'ovarian cancer first line'...")
        search_service = ClinicalTrialSearchService()
        
        result = await search_service.search_trials(
            query="ovarian cancer first line",
            disease_category="ovarian_cancer",
            top_k=10
        )
        
        if result.get("success"):
            found_trials = result.get("data", {}).get("found_trials", [])
            print(f"✅ Search returned {len(found_trials)} trials")
            
            if found_trials:
                print("\n📋 Sample trials:")
                for i, trial in enumerate(found_trials[:3], 1):
                    print(f"\n   Trial {i}:")
                    print(f"   - NCT ID: {trial.get('nct_id', 'N/A')}")
                    print(f"   - Title: {trial.get('title', 'N/A')[:70]}...")
                    print(f"   - Status: {trial.get('status', 'N/A')}")
                    print(f"   - Phase: {trial.get('phase', 'N/A')}")
                    print(f"   - Similarity: {trial.get('similarity_score', 'N/A')}")
            else:
                print("⚠️  No trials found - AstraDB may be empty or search query didn't match")
        else:
            print(f"❌ Search failed: {result.get('error', 'Unknown error')}")
            print(f"   Response: {result}")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_astradb())

