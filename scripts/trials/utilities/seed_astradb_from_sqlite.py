"""
Seed AstraDB from SQLite clinical trials database.

This script:
1. Reads all trials from SQLite (populated by Agent 1)
2. Generates embeddings using Google Embedding API
3. Upserts trials to AstraDB vector store

Run this AFTER Agent 1 has populated SQLite.

Usage:
    cd oncology-coPilot/oncology-backend-minimal
    venv/bin/python scripts/seed_astradb_from_sqlite.py [--batch-size 50] [--limit 0]
"""
import asyncio
import argparse
import logging
from pathlib import Path
import json
import sys

# Fix Python path for imports
backend_dir = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(backend_dir))

from api.services.database_connections import get_db_connections
from api.services.clinical_trial_search_service import ClinicalTrialSearchService

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def truncate_string_to_bytes(text: str, max_bytes: int = 7500) -> str:
    """
    Truncate string to fit within byte limit (AstraDB indexed string limit is 8000 bytes).
    Uses 7500 as safe margin.
    
    Args:
        text: String to truncate
        max_bytes: Maximum bytes allowed (default: 7500)
        
    Returns:
        Truncated string (with ellipsis if truncated)
    """
    if not text:
        return text
    
    # Encode to bytes to check actual size
    text_bytes = text.encode('utf-8')
    if len(text_bytes) <= max_bytes:
        return text
    
    # Truncate to max_bytes, ensuring we don't break UTF-8 characters
    truncated_bytes = text_bytes[:max_bytes]
    # Remove any incomplete UTF-8 sequences at the end
    while truncated_bytes and (truncated_bytes[-1] & 0xC0) == 0x80:
        truncated_bytes = truncated_bytes[:-1]
    
    truncated_text = truncated_bytes.decode('utf-8', errors='ignore')
    # Add ellipsis if truncated
    if len(text_bytes) > max_bytes:
        truncated_text = truncated_text.rstrip() + "..."
    
    return truncated_text


async def seed_astradb(batch_size: int = 50, limit: int = 0):
    """
    Seed AstraDB from SQLite clinical trials database.
    
    Args:
        batch_size: Number of trials to process per batch (default: 50)
        limit: Max trials to process (0 = all)
    """
    logger.info(f"🚀 Starting AstraDB seeding (batch_size={batch_size}, limit={limit})")
    
    # Initialize connections
    db = get_db_connections()
    service = ClinicalTrialSearchService()
    
    # Get SQLite connection
    conn = db.get_sqlite_connection()
    if not conn:
        logger.error("❌ Failed to connect to SQLite")
        return
    
    # Get or create AstraDB collection
    vector_db = db.get_vector_db_connection()
    if not vector_db:
        logger.error("❌ Failed to get AstraDB connection")
        return
    
    # Check if collection exists, create if not
    collection_name = service.collection_name
    try:
        collection_names = vector_db.list_collection_names()
        if collection_name in collection_names:
            logger.info(f"✅ Collection '{collection_name}' already exists")
            collection = vector_db.get_collection(collection_name)
        else:
            logger.info(f"📦 Creating collection '{collection_name}' with vector dimension 768...")
            # AstraDB API v2.x uses definition parameter
            # Try with string metric first, VectorMetric enum if available
            try:
                from astrapy.constants import VectorMetric
                metric_value = VectorMetric.COSINE
            except ImportError:
                metric_value = "cosine"
            collection = vector_db.create_collection(
                collection_name,
                definition={"vector": {"dimension": 768, "metric": metric_value}}
            )
            logger.info(f"✅ Collection '{collection_name}' created successfully")
    except Exception as e:
        logger.error(f"❌ Failed to get/create collection: {e}", exc_info=True)
        return
    
    # Read trials from SQLite
    # Use 'clinical_trials' table (Ayesha's 30 curated ovarian cancer trials)
    cursor = conn.cursor()
    if limit > 0:
        cursor.execute("SELECT * FROM clinical_trials LIMIT ?", (limit,))
    else:
        cursor.execute("SELECT * FROM clinical_trials")
    
    trials = cursor.fetchall()
    total_trials = len(trials)
    logger.info(f"📚 Found {total_trials} trials in SQLite")
    
    if total_trials == 0:
        logger.warning("⚠️ No trials found. Run Agent 1 seeding first!")
        return
    
    # Process in batches
    processed = 0
    errors = 0
    
    for i in range(0, total_trials, batch_size):
        batch = trials[i:i+batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (total_trials + batch_size - 1) // batch_size
        
        logger.info(f"⚙️ Processing batch {batch_num}/{total_batches} ({len(batch)} trials)")
        
        # Rate limiting: Cohere trial key is limited to 40 calls/minute
        # Calculate: 40 calls/minute = 1.5 seconds per call
        # With batch_size calls per batch, we need: batch_size × 1.5 seconds + buffer
        # Example: batch_size=10 → 15 seconds + 3 second buffer = 18 seconds minimum
        if batch_num > 1:
            min_delay = batch_size * 1.5 + 3  # Minimum delay based on batch size
            await asyncio.sleep(min_delay)
            logger.debug(f"⏱️ Rate limit delay: {min_delay:.1f}s between batches")
        
        # Build batch of documents for batch insert (like working example)
        documents_to_insert = []
        texts_to_embed = []
        trial_metadata = []  # Store trial dicts for building documents after embedding
        
        # First pass: collect texts for batch embedding
        for trial in batch:
            try:
                trial_dict = dict(trial)
                eligibility_text = (
                    trial_dict.get('eligibility_text') or 
                    trial_dict.get('inclusion_criteria_text') or 
                    trial_dict.get('inclusion_criteria') or 
                    trial_dict.get('description_text') or
                    trial_dict.get('objectives_text') or
                    ''
                )
                if not eligibility_text or len(eligibility_text.strip()) < 50:
                    continue
                texts_to_embed.append(eligibility_text)
                trial_metadata.append(trial_dict)
            except Exception as e:
                logger.debug(f"Skipping trial in batch prep: {e}")
                continue
        
        # Generate embeddings with retry logic for rate limits
        if texts_to_embed:
            try:
                embeddings = []
                for idx, text in enumerate(texts_to_embed):
                    # Add small delay between embedding calls (0.25 seconds = 4 calls/second max)
                    if idx > 0:
                        await asyncio.sleep(0.25)
                    
                    # Retry logic for rate limit errors
                    max_retries = 3
                    retry_delay = 5.0  # Start with 5 second delay
                    embedding = None
                    
                    for attempt in range(max_retries):
                        try:
                            embedding = await service._generate_embedding(text)
                            if embedding and len(embedding) > 0:
                                embeddings.append(embedding)
                                break  # Success, exit retry loop
                            else:
                                embeddings.append(None)
                                break  # Invalid embedding, don't retry
                        except Exception as e:
                            error_str = str(e).lower()
                            # Check if it's a rate limit error
                            if 'rate limit' in error_str or '429' in error_str or 'quota' in error_str:
                                if attempt < max_retries - 1:
                                    wait_time = retry_delay * (2 ** attempt)  # Exponential backoff: 5s, 10s, 20s
                                    logger.warning(f"⚠️ Rate limit hit (attempt {attempt + 1}/{max_retries}), waiting {wait_time:.1f}s...")
                                    await asyncio.sleep(wait_time)
                                else:
                                    logger.error(f"❌ Rate limit exceeded after {max_retries} retries. Skipping embedding.")
                                    embeddings.append(None)
                                    break
                            else:
                                # Non-rate-limit error, log and skip
                                logger.error(f"❌ Embedding generation failed (non-rate-limit): {e}")
                                embeddings.append(None)
                                break
                    
                    # If we still don't have an embedding after retries, add None
                    if embedding is None and len(embeddings) <= idx:
                        embeddings.append(None)
                
                # Build documents with vectors
                for i, trial_dict in enumerate(trial_metadata):
                    if embeddings[i] is None:
                        continue
                    
                    nct_id = trial_dict.get('nct_id') or trial_dict.get('id', 'UNKNOWN')
                    doc_id = trial_dict.get('source_url') or f"nct_{nct_id}"
                    
                    # Truncate text fields
                    eligibility_text = truncate_string_to_bytes(texts_to_embed[i], max_bytes=7500)
                    description_text = truncate_string_to_bytes(trial_dict.get('description_text', ''), max_bytes=7500)
                    
                    # Parse JSON fields
                    biomarker_requirements = trial_dict.get('biomarker_requirements')
                    if biomarker_requirements and isinstance(biomarker_requirements, str):
                        try:
                            biomarker_requirements = json.loads(biomarker_requirements)
                        except:
                            biomarker_requirements = None
                    
                    locations_data = trial_dict.get('locations_data')
                    if locations_data and isinstance(locations_data, str):
                        try:
                            locations_data = json.loads(locations_data)
                        except:
                            locations_data = None
                    
                    mechanism_tags = trial_dict.get('mechanism_tags')
                    if mechanism_tags and isinstance(mechanism_tags, str):
                        try:
                            mechanism_tags = json.loads(mechanism_tags)
                        except:
                            mechanism_tags = None
                    
                    biomarker_requirements_gtm = trial_dict.get('biomarker_requirements_gtm')
                    if biomarker_requirements_gtm and isinstance(biomarker_requirements_gtm, str):
                        try:
                            biomarker_requirements_gtm = json.loads(biomarker_requirements_gtm)
                        except:
                            biomarker_requirements_gtm = None
                    
                    document = {
                        "_id": doc_id,
                        "$vector": embeddings[i],  # Vector field - MUST be included for vector search
                        "nct_id": nct_id,
                        "title": trial_dict.get('title', ''),
                        "status": trial_dict.get('status', 'UNKNOWN'),
                        "phase": trial_dict.get('phase') or trial_dict.get('phases', 'N/A'),
                        "disease_category": trial_dict.get('disease_category'),
                        "disease_subcategory": trial_dict.get('disease_subcategory'),
                        "biomarker_requirements": biomarker_requirements,
                        "locations_data": locations_data,
                        "eligibility_text": eligibility_text,
                        "description_text": description_text,
                        "source_url": trial_dict.get('source_url') or trial_dict.get('source', ''),
                        "sponsor_name": trial_dict.get('sponsor_name'),
                        "principal_investigator_name": trial_dict.get('principal_investigator_name'),
                        "pi_contact_email": trial_dict.get('pi_contact_email'),
                        "study_coordinator_email": trial_dict.get('study_coordinator_email'),
                        "primary_endpoint": trial_dict.get('primary_endpoint'),
                        "site_count": trial_dict.get('site_count', 0),
                        "estimated_enrollment": trial_dict.get('estimated_enrollment'),
                        "mechanism_tags": mechanism_tags,
                        "biomarker_requirements_gtm": biomarker_requirements_gtm
                    }
                    documents_to_insert.append(document)
            
            except Exception as e:
                logger.error(f"❌ Error building batch documents: {e}", exc_info=True)
                errors += len(trial_metadata)
                continue
        
        # Batch insert using insert_many (like working example)
        if documents_to_insert:
            try:
                # Delete existing documents first (for upsert behavior)
                doc_ids = [doc["_id"] for doc in documents_to_insert]
                for doc_id in doc_ids:
                    try:
                        collection.delete_one({"_id": doc_id})
                    except:
                        pass  # Ignore if document doesn't exist
                
                # Insert all documents with vectors
                collection.insert_many(documents_to_insert)
                processed += len(documents_to_insert)
                logger.info(f"✅ Inserted batch of {len(documents_to_insert)} documents with vectors")
            except Exception as e:
                logger.error(f"❌ Error batch inserting: {e}", exc_info=True)
                errors += len(documents_to_insert)
        
        logger.info(f"✅ Batch {batch_num}/{total_batches} complete ({processed}/{total_trials} trials)")
        
        # Rate limiting between batches
        if i + batch_size < total_trials:
            await asyncio.sleep(1.0)
    
    logger.info(f"🎉 Seeding complete! Processed: {processed}, Errors: {errors}")
    
    # Count documents (AstraDB uses count_documents with filter)
    try:
        doc_count = collection.count_documents({}, upper_bound=1000000)
        logger.info(f"✅ AstraDB collection '{service.collection_name}' now has {doc_count} documents")
    except Exception as e:
        logger.warning(f"⚠️ Could not count documents: {e}")

def parse_args():
    parser = argparse.ArgumentParser(description="Seed AstraDB from SQLite clinical trials")
    parser.add_argument("--batch-size", type=int, default=50, help="Batch size for processing (default: 50)")
    parser.add_argument("--limit", type=int, default=0, help="Max trials to process (0 = all, default: 0)")
    return parser.parse_args()

if __name__ == "__main__":
    args = parse_args()
    asyncio.run(seed_astradb(batch_size=args.batch_size, limit=args.limit))

