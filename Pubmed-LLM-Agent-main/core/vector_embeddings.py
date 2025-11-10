import os
import json
import numpy as np
from typing import List, Dict, Any, Optional
import hashlib
from datetime import datetime
import requests
from .utils import clean_text

class VectorEmbeddingsService:
    """
    Service for creating and managing vector embeddings for clinical literature.
    Supports multiple embedding providers and vector databases.
    """

    def __init__(self, provider: str = "gemini", api_key: Optional[str] = None):
        self.provider = provider
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")

        # Embedding dimensions for different providers
        self.embedding_dims = {
            "gemini": 768,  # Gemini embedding dimension
            "openai": 1536,  # text-embedding-3-small
            "cohere": 1024,  # Cohere embed-multilingual-v3.0
        }

        # Cache for embeddings to avoid recomputing
        self.embedding_cache = {}
        self.cache_file = "embeddings_cache.json"
        self._load_cache()

    def _load_cache(self):
        """Load cached embeddings from disk"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    self.embedding_cache = json.load(f)
        except Exception as e:
            print(f"Warning: Could not load embedding cache: {e}")
            self.embedding_cache = {}

    def _save_cache(self):
        """Save cached embeddings to disk"""
        try:
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.embedding_cache, f, indent=2)
        except Exception as e:
            print(f"Warning: Could not save embedding cache: {e}")

    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text"""
        return hashlib.md5(text.encode()).hexdigest()

    def embed_text(self, text: str, task: str = "retrieval") -> List[float]:
        """
        Create embeddings for text using the configured provider.

        Args:
            text: Text to embed
            task: Task type ("retrieval", "semantic", "clustering")

        Returns:
            List of float values representing the embedding
        """
        # Check cache first
        cache_key = self._get_cache_key(text)
        if cache_key in self.embedding_cache:
            return self.embedding_cache[cache_key]

        # Clean and prepare text
        clean = clean_text(text)
        if len(clean) < 10:  # Too short for meaningful embedding
            return [0.0] * self.embedding_dims.get(self.provider, 768)

        try:
            if self.provider == "gemini":
                embedding = self._embed_with_gemini(clean, task)
            elif self.provider == "openai":
                embedding = self._embed_with_openai(clean)
            else:
                # Fallback to simple TF-IDF style embedding
                embedding = self._embed_with_fallback(clean)

            # Cache the result
            self.embedding_cache[cache_key] = embedding
            if len(self.embedding_cache) % 100 == 0:  # Save every 100 embeddings
                self._save_cache()

            return embedding

        except Exception as e:
            print(f"Error creating embedding: {e}")
            # Return zero vector as fallback
            return [0.0] * self.embedding_dims.get(self.provider, 768)

    def _embed_with_gemini(self, text: str, task: str) -> List[float]:
        """Create embeddings using Gemini API"""
        import google.genai as genai

        if not self.api_key:
            raise ValueError("GEMINI_API_KEY required for Gemini embeddings")

        genai.configure(api_key=self.api_key)

        try:
            # Use Gemini's text embedding model
            result = genai.embed_content(
                model="models/text-embedding-004",
                content=text,
                task_type="RETRIEVAL_DOCUMENT" if task == "retrieval" else "SEMANTIC_SIMILARITY"
            )

            return result['embedding']
        except Exception as e:
            print(f"Gemini embedding error: {e}")
            raise

    def _embed_with_openai(self, text: str) -> List[float]:
        """Create embeddings using OpenAI API"""
        import openai

        if not self.api_key:
            raise ValueError("OPENAI_API_KEY required for OpenAI embeddings")

        client = openai.OpenAI(api_key=self.api_key)

        try:
            response = client.embeddings.create(
                input=text,
                model="text-embedding-3-small"
            )

            return response.data[0].embedding
        except Exception as e:
            print(f"OpenAI embedding error: {e}")
            raise

    def _embed_with_fallback(self, text: str) -> List[float]:
        """Simple fallback embedding based on word frequency"""
        # This is a very basic embedding - in production, use a proper model
        words = text.lower().split()
        vocab_size = 1000  # Simple vocab size
        embedding = [0.0] * vocab_size

        for i, word in enumerate(words[:100]):  # Limit to first 100 words
            word_hash = hash(word) % vocab_size
            embedding[word_hash] += 1.0

        # Normalize
        norm = np.linalg.norm(embedding)
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def embed_clinical_paper(self, paper: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create comprehensive embeddings for a clinical paper.

        Args:
            paper: Paper data with title, abstract, etc.

        Returns:
            Paper with embeddings added
        """
        # Combine title and abstract for main content embedding
        main_content = f"{paper.get('title', '')} {paper.get('abstract', '')}"
        main_embedding = self.embed_text(main_content, task="retrieval")

        # Create separate embeddings for different aspects
        title_embedding = self.embed_text(paper.get('title', ''), task="semantic")
        abstract_embedding = self.embed_text(paper.get('abstract', ''), task="retrieval")

        # Create embeddings for clinical insights if available
        insights_text = ""
        if 'insights' in paper:
            insights = paper['insights']
            for category, insight_list in insights.items():
                if insight_list:
                    insights_text += f" {category}: {'; '.join(insight_list)}"

        insights_embedding = self.embed_text(insights_text, task="semantic") if insights_text else None

        return {
            **paper,
            'embedding': main_embedding,
            'title_embedding': title_embedding,
            'abstract_embedding': abstract_embedding,
            'insights_embedding': insights_embedding,
            'embedding_provider': self.provider,
            'embedding_created_at': datetime.now().isoformat()
        }

    def embed_query(self, query: str) -> List[float]:
        """
        Create embedding for a search query.

        Args:
            query: Search query text

        Returns:
            Query embedding vector
        """
        return self.embed_text(query, task="retrieval")

    def compute_similarity(self, embedding1: List[float], embedding2: List[float]) -> float:
        """
        Compute cosine similarity between two embeddings.

        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector

        Returns:
            Similarity score between 0 and 1
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)

            dot_product = np.dot(vec1, vec2)
            norm1 = np.linalg.norm(vec1)
            norm2 = np.linalg.norm(vec2)

            if norm1 == 0 or norm2 == 0:
                return 0.0

            return dot_product / (norm1 * norm2)
        except Exception as e:
            print(f"Error computing similarity: {e}")
            return 0.0

    def search_similar(self, query_embedding: List[float], papers: List[Dict[str, Any]],
                      top_k: int = 5, threshold: float = 0.1) -> List[Dict[str, Any]]:
        """
        Find papers similar to query embedding.

        Args:
            query_embedding: Query embedding vector
            papers: List of papers with embeddings
            top_k: Number of top results to return
            threshold: Minimum similarity threshold

        Returns:
            List of similar papers with similarity scores
        """
        results = []

        for paper in papers:
            if 'embedding' not in paper:
                continue

            similarity = self.compute_similarity(query_embedding, paper['embedding'])

            if similarity >= threshold:
                results.append({
                    **paper,
                    'similarity_score': similarity
                })

        # Sort by similarity and return top_k
        results.sort(key=lambda x: x['similarity_score'], reverse=True)
        return results[:top_k]
