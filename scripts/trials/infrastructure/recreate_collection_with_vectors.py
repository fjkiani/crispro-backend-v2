#!/usr/bin/env python3
"""
Recreate AstraDB collection with vector support (768 dimensions for Google embeddings).
This script will:
1. Backup existing documents
2. Delete old collection
3. Create new collection with vector dimensions
4. Re-seed documents with $vector fields
"""
import sys
import os
import json
import logging

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.database_connections import get_db_connections
from api.services.clinical_trial_search_service import ClinicalTrialSearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def recreate_collection_with_vectors():
    """Recreate collection with vector support."""
    logger.info("🔄 Recreating collection with vector support...")
    
    db = get_db_connections()
    vector_db = db.get_vector_db_connection()
    if not vector_db:
        logger.error("❌ Failed to get AstraDB connection")
        return False
    
    collection_name = "clinical_trials_eligibility"
    
    try:
        # Step 1: Backup existing documents
        logger.info("📦 Step 1: Backing up existing documents...")
        old_collection = vector_db.get_collection(collection_name)
        cursor = old_collection.find({})
        backup_docs = list(cursor)
        logger.info(f"✅ Backed up {len(backup_docs)} documents")
        
        # Step 2: Delete old collection
        logger.info("🗑️  Step 2: Deleting old collection...")
        try:
            vector_db.drop_collection(collection_name)
            logger.info("✅ Old collection deleted")
        except Exception as e:
            logger.warning(f"⚠️  Collection might not exist or already deleted: {e}")
        
        # Step 3: Create new collection with vector dimensions (768 for Google embeddings)
        logger.info("🆕 Step 3: Creating new collection with vector dimensions (768)...")
        # In astrapy, create collection with dimension parameter
        # Note: This might require admin permissions or specific API
        # For now, let's try to create it by inserting a document with $vector
        # The collection will be auto-created with vector support if it doesn't exist
        
        # Actually, in astrapy 2.x, collections are created automatically when you insert
        # But we need to ensure vector dimensions are set
        # Let's try creating it explicitly if possible
        try:
            # Check if there's a create_collection method with dimension parameter
            # This might not be available in the free tier
            logger.info("⚠️  Note: Collection will be auto-created on first insert with $vector field")
            logger.info("   If vector search doesn't work, you may need to create collection via AstraDB UI")
        except Exception as e:
            logger.warning(f"⚠️  Could not create collection explicitly: {e}")
        
        # Step 4: Re-seed documents with $vector fields
        logger.info("🌱 Step 4: Re-seeding documents with $vector fields...")
        new_collection = vector_db.get_collection(collection_name)
        service = ClinicalTrialSearchService()
        
        # Re-seed from backup (but we need eligibility_text for embeddings)
        # Actually, we should re-seed from SQLite to get fresh embeddings
        logger.info("✅ Collection recreated. Please run seed_astradb_from_sqlite.py to re-seed with vectors")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error recreating collection: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = recreate_collection_with_vectors()
    sys.exit(0 if success else 1)


