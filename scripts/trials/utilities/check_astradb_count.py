#!/usr/bin/env python3
"""
Check how many trials are in AstraDB.
"""

import asyncio
from api.services.clinical_trial_search_service import ClinicalTrialSearchService
from api.services.db_connections import get_db_connections

async def main():
    print("🔍 CHECKING ASTRADB TRIAL COUNT\n")
    
    # Initialize service
    search_service = ClinicalTrialSearchService()
    db = get_db_connections()
    
    # Get collection
    vector_db = db.get_vector_db_connection()
    if not vector_db:
        print("❌ Failed to connect to AstraDB")
        return
    
    collection_name = search_service.collection_name
    print(f"Collection: {collection_name}")
    
    try:
        # Check if collection exists
        collection_names = vector_db.list_collection_names()
        print(f"Available collections: {collection_names}")
        
        if collection_name in collection_names:
            collection = vector_db.get_collection(collection_name)
            
            # Count documents
            count = collection.count_documents({}, upper_bound=100000)
            print(f"\n✅ Collection '{collection_name}' has {count} trials")
            
            # Sample a few trials
            print(f"\n📋 SAMPLE TRIALS (first 5):")
            sample_docs = collection.find({}, limit=5, projection={"nct_id": 1, "title": 1, "status": 1})
            for i, doc in enumerate(sample_docs, 1):
                nct_id = doc.get('nct_id', 'N/A')
                title = doc.get('title', 'N/A')[:60]
                status = doc.get('status', 'N/A')
                print(f"   {i}. {nct_id}: {title}... (Status: {status})")
            
        else:
            print(f"❌ Collection '{collection_name}' does not exist")
            print(f"   Run: python scripts/seed_astradb_from_sqlite.py --limit 0")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())


