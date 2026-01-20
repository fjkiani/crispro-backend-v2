"""
ClinicalTrialSearchService - Lightweight search for minimal backend.
Extracted core logic from ClinicalTrialAgent, removing AgentInterface bloat.
Uses AstraDB vector store + LLM embeddings for semantic search.
"""
import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone as tz

from api.services.database_connections import get_db_connections
from api.services.llm_provider.llm_abstract import get_llm_provider, LLMProvider

# Configure logging
logger = logging.getLogger(__name__)

class ClinicalTrialSearchService:
    """
    Lightweight clinical trial search service using Astra

DB + Google embeddings.
    No AgentInterface dependencies - pure service logic.
    """
    
    def __init__(self):
        """Initialize service with database connections and LLM provider."""
        self.db = get_db_connections()

        # Initialize LLM provider for embeddings (auto-detects from environment)
        # Priority: Cohere > Gemini > OpenAI > Anthropic
        try:
            self.llm_provider = get_llm_provider()
            logger.info(f"✅ ClinicalTrialSearchService using LLM provider: {self.llm_provider.__class__.__name__}")
        except Exception as e:
            raise ValueError(f"LLM provider initialization failed: {e}. "
                           "Please set COHERE_API_KEY, GEMINI_API_KEY, or OPENAI_API_KEY in environment.")

        # Collection name for clinical trials (matching Agent 1 seeding)
        # Note: Check environment for collection name, default to clinical_trials_eligibility
        # If using clinical_trials_eligibility2, set ASTRA_COLLECTION_NAME env var
        self.collection_name = os.getenv("ASTRA_COLLECTION_NAME", "clinical_trials_eligibility2")

        logger.info(f"✅ ClinicalTrialSearchService initialized (collection: {self.collection_name})")
    
    async def _generate_embedding(self, text: str) -> List[float]:
        """
        Generate embedding vector using LLM abstraction layer.
        Auto-detects provider (Cohere > Gemini > OpenAI > Anthropic).
        
        IMPORTANT: AstraDB collection expects 768-dimensional vectors.
        Truncate embeddings to match collection schema.
        """
        try:
            # Use await since embed() is async and we're in an async context
            embedding = await self.llm_provider.embed(
                text=text,
                task_type="retrieval_query"  # Pass through to provider if supported
            )
            
            # CRITICAL: Truncate to 768 dimensions to match AstraDB collection schema
            # Collection 'clinical_trials_eligibility2' expects vector<float, 768>
            # Cohere embed-english-v3.0 produces 1024-dim, so we need to truncate
            if len(embedding) > 768:
                logger.warning(f"⚠️ Embedding dimension mismatch: {len(embedding)} > 768. Truncating to 768 dimensions.")
                embedding = embedding[:768]
            elif len(embedding) < 768:
                logger.warning(f"⚠️ Embedding dimension mismatch: {len(embedding)} < 768. Padding with zeros.")
                embedding = embedding + [0.0] * (768 - len(embedding))
            
            return embedding
        except Exception as e:
            logger.error(f"❌ Embedding generation failed: {e}", exc_info=True)
            raise
    
    async def search_trials(
        self,
        query: str,
        disease_category: Optional[str] = None,
        top_k: int = 10,
        min_score: float = 0.0  # Lower threshold to see results - AstraDB cosine similarity can be lower
    ) -> Dict[str, Any]:
        """
        Search clinical trials using semantic vector search.
        
        Args:
            query: Natural language search query
            disease_category: Optional filter (e.g., "gynecologic_oncology", "breast_cancer")
            top_k: Number of results to return (default: 10)
            min_score: Minimum similarity score threshold (default: 0.5)
            
        Returns:
            Dict with search results and metadata
        """
        try:
            # Generate query embedding
            query_embedding = await self._generate_embedding(query)
            
            # Get AstraDB collection
            collection = self.db.get_vector_db_collection(self.collection_name)
            if not collection:
                logger.error(f"❌ AstraDB collection '{self.collection_name}' not available")
                return {"success": False, "error": "Vector store unavailable", "data": {"found_trials": []}}
            
            logger.info(f"✅ Using collection: {self.collection_name}, embedding dimension: {len(query_embedding)}")
            
            # Build filter for metadata (if disease category specified)
            # Note: AstraDB requires empty dict {} for filter, not None
            filter_dict = {}
            if disease_category:
                filter_dict["disease_category"] = disease_category
            
            # Prepare find parameters (matching main backend pattern)
            find_params = {
                "filter": filter_dict,  # Empty dict if no filter, or disease_category filter
                "sort": {"$vector": query_embedding},  # Vector search via sort parameter
                "limit": top_k,
                "include_similarity": True
            }
            
            logger.debug(f"Vector search params: filter={filter_dict}, limit={top_k}, embedding_dim={len(query_embedding)}")
            
            # Execute vector search (AstraDB API uses sort with $vector, not direct vector param)
            similar_trials_cursor = collection.find(**find_params)
            
            # Convert cursor to list (this populates the cursor for metadata access)
            similar_trials = list(similar_trials_cursor)
            
            logger.info(f"✅ Found {len(similar_trials)} trials from vector search (before similarity filtering)")
            
            # Process results
            found_trials = []
            for doc in similar_trials:
                # Extract similarity score (cosine similarity from AstraDB)
                # Note: AstraDB returns similarity as a value between -1 and 1, but typically 0-1 for normalized vectors
                similarity = doc.get('$similarity', 0.0)
                
                # Log similarity for debugging
                logger.debug(f"Trial {doc.get('nct_id', 'UNKNOWN')} similarity: {similarity:.4f}")
                
                # Filter by minimum score
                if similarity < min_score:
                    logger.debug(f"Skipping trial {doc.get('nct_id')} - similarity {similarity:.4f} < min_score {min_score}")
                    continue
                
                # Parse trial data from document
                trial_data = {
                    "nct_id": doc.get("nct_id", "N/A"),
                    "title": doc.get("title", "No Title"),
                    "status": doc.get("status", "Unknown"),
                    "source_url": doc.get("source_url", ""),
                    "disease_category": doc.get("disease_category", ""),
                    "phase": self._parse_phase_from_metadata(doc),
                    "biomarker_requirements": self._parse_biomarkers(doc),
                    "locations_data": self._parse_locations(doc),
                    "eligibility_text": doc.get("eligibility_text", ""),
                    "description_text": doc.get("description_text", ""),
                    "similarity_score": round(similarity, 3)
                }
                
                found_trials.append(trial_data)
            
            logger.info(f"✅ Found {len(found_trials)} trials matching query: '{query[:50]}...'")
            
            return {
                "success": True,
                "data": {
                    "found_trials": found_trials,
                    "query": query,
                    "disease_category": disease_category,
                    "total_results": len(found_trials)
                },
                "provenance": {
                    "service": "ClinicalTrialSearchService",
                    "collection": self.collection_name,
                    "embedding_model": "models/embedding-001",
                    "timestamp": datetime.now(tz.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e),
                "data": {"found_trials": []}
            }
    
    def _parse_phase_from_metadata(self, doc: Dict[str, Any]) -> str:
        """Extract phase from metadata JSON (backwards compatible)."""
        try:
            metadata = doc.get("metadata_json", {})
            if isinstance(metadata, str):
                import json
                metadata = json.loads(metadata)
            return metadata.get("phase", "N/A")
        except:
            return "N/A"
    
    def _parse_biomarkers(self, doc: Dict[str, Any]) -> List[str]:
        """Parse biomarker requirements from JSON field."""
        try:
            biomarkers = doc.get("biomarker_requirements", [])
            if isinstance(biomarkers, str):
                import json
                biomarkers = json.loads(biomarkers)
            return biomarkers if isinstance(biomarkers, list) else []
        except:
            return []
    
    def _parse_locations(self, doc: Dict[str, Any]) -> List[Dict[str, str]]:
        """Parse locations data from JSON field."""
        try:
            locations = doc.get("locations_data", [])
            if isinstance(locations, str):
                import json
                locations = json.loads(locations)
            return locations if isinstance(locations, list) else []
        except:
            return []
    
    async def get_trial_details(self, nct_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve full trial details from SQLite by NCT ID.
        Useful for drill-down after vector search.
        """
        try:
            conn = self.db.get_sqlite_connection()
            if not conn:
                logger.error("❌ SQLite connection unavailable")
                return None
            
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM clinical_trials WHERE nct_id = ?
            """, (nct_id,))
            
            row = cursor.fetchone()
            if row:
                # Convert Row to dict
                trial_dict = dict(row)
                logger.info(f"✅ Retrieved details for {nct_id}")
                return trial_dict
            else:
                logger.warning(f"⚠️ No trial found with NCT ID: {nct_id}")
                return None
                
        except Exception as e:
            logger.error(f"❌ Failed to get trial details: {e}", exc_info=True)
            return None
    
    async def filter_by_state(
        self,
        trials: List[Dict[str, Any]],
        state_code: str
    ) -> List[Dict[str, Any]]:
        """
        Filter trials by state (for refresh_status integration).
        
        Args:
            trials: List of trial dicts with locations_data
            state_code: Two-letter state code (e.g., "NY", "CA")
            
        Returns:
            Filtered list of trials with locations in specified state
        """
        filtered = []
        for trial in trials:
            locations = trial.get("locations_data", [])
            if isinstance(locations, str):
                import json
                locations = json.loads(locations)
            
            # Check if any location matches state
            has_state = any(
                loc.get("state", "").upper() == state_code.upper()
                for loc in locations
            )
            
            if has_state:
                filtered.append(trial)
        
        logger.info(f"✅ Filtered {len(trials)} → {len(filtered)} trials in state {state_code}")
        return filtered

