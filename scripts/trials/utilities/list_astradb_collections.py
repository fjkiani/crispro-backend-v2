#!/usr/bin/env python3
"""
List all collections in AstraDB to verify which one has trials.
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.database_connections import get_db_connections

def list_collections():
    """List all collections in AstraDB."""
    print("🔍 Listing AstraDB collections...")
    
    try:
        db = get_db_connections()
        vector_db = db.get_vector_db_connection()
        
        if not vector_db:
            print("❌ Failed to get AstraDB connection")
            return
        
        collections = vector_db.list_collection_names()
        print(f"\n✅ Found {len(collections)} collections:")
        
        for coll_name in collections:
            try:
                collection = vector_db.get_collection(coll_name)
                # Try to count documents (approximate)
                try:
                    count = collection.count_documents({}, upper_bound=1000000)
                    print(f"   - {coll_name}: ~{count} documents")
                except:
                    print(f"   - {coll_name}: (unable to count)")
            except Exception as e:
                print(f"   - {coll_name}: (error accessing: {e})")
    
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    list_collections()


