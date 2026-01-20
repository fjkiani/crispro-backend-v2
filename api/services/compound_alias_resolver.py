"""
Compound Alias Resolver Service

Dynamically resolves compound names to canonical chemical names using PubChem API.

Features:
- In-memory caching for speed
- Exponential backoff retry logic
- Rate limit handling (429 errors)
- Graceful fallback to original name on failure

Author: CrisPRO Platform
Date: November 5, 2025
"""

import requests
import time
import logging
from typing import Optional, Dict

logger = logging.getLogger(__name__)


class CompoundAliasResolver:
    """
    Dynamically resolve compound aliases using PubChem API.
    
    This service replaces hardcoded compound aliases with dynamic resolution,
    supporting 110M+ compounds in PubChem database.
    
    Examples:
        >>> resolver = CompoundAliasResolver()
        >>> resolver.resolve_compound_alias("Vitamin D")
        'Cholecalciferol'
        >>> resolver.resolve_compound_alias("Turmeric")
        'Curcumin'
    """
    
    def __init__(self, base_url: str = "https://pubchem.ncbi.nlm.nih.gov/rest/pug"):
        """
        Initialize the compound alias resolver.
        
        Args:
            base_url: PubChem REST API base URL
        """
        self._cache: Dict[str, str] = {}  # In-memory cache
        self.base_url = base_url
        self.cache_hits = 0
        self.cache_misses = 0
        self.resolution_failures = 0
        
        logger.info(f"CompoundAliasResolver initialized with base URL: {base_url}")
    
    def resolve_compound_alias(
        self, 
        compound: str, 
        retries: int = 2,
        timeout: int = 5
    ) -> str:
        """
        Query PubChem for compound synonyms with retry logic.
        
        This method attempts to resolve a common compound name (e.g., "Vitamin D")
        to its canonical chemical name (e.g., "Cholecalciferol") using PubChem's
        synonyms endpoint.
        
        Features:
        - In-memory caching (fast path for repeated queries)
        - Exponential backoff on rate limits (429 errors)
        - Graceful fallback to original name on failure
        - Comprehensive logging for debugging
        
        Args:
            compound: Compound name (e.g., "Vitamin D", "Curcumin", "Green Tea Extract")
            retries: Number of retry attempts on failure (default: 2)
            timeout: Request timeout in seconds (default: 5)
            
        Returns:
            Canonical compound name (or original if resolution fails)
            
        Examples:
            >>> resolver = CompoundAliasResolver()
            >>> resolver.resolve_compound_alias("Vitamin D")
            'Cholecalciferol'
            >>> resolver.resolve_compound_alias("UnknownCompound123")
            'UnknownCompound123'  # Fallback to original
        """
        # Normalize input (lowercase, strip whitespace)
        compound_normalized = compound.lower().strip()
        
        # Check cache first (FAST PATH)
        if compound_normalized in self._cache:
            self.cache_hits += 1
            cached_result = self._cache[compound_normalized]
            logger.info(f"✅ Cache hit for compound: '{compound}' → '{cached_result}'")
            return cached_result
        
        self.cache_misses += 1
        logger.info(f"⚡ Cache miss for compound: '{compound}' - querying PubChem...")
        
        # Retry with exponential backoff
        for attempt in range(retries + 1):
            try:
                # PubChem synonyms endpoint
                # Example: https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/Vitamin%20D/synonyms/JSON
                url = f"{self.base_url}/compound/name/{compound}/synonyms/JSON"
                
                logger.debug(f"Attempt {attempt + 1}/{retries + 1}: Querying {url}")
                response = requests.get(url, timeout=timeout)
                
                # SUCCESS CASE
                if response.ok:
                    data = response.json()
                    
                    # Extract synonyms list
                    # Structure: {"InformationList": {"Information": [{"Synonym": ["name1", "name2", ...]}]}}
                    synonyms = data['InformationList']['Information'][0]['Synonym']
                    
                    # Return first canonical name (most specific)
                    canonical_name = synonyms[0]
                    
                    # Cache result for future queries
                    self._cache[compound_normalized] = canonical_name
                    
                    logger.info(f"✅ Resolved '{compound}' → '{canonical_name}' (cached)")
                    return canonical_name
                
                # RATE LIMIT HIT - exponential backoff
                if response.status_code == 429:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"⚠️ Rate limited (429) on attempt {attempt + 1}, "
                        f"waiting {wait_time}s before retry..."
                    )
                    time.sleep(wait_time)
                    continue
                
                # NOT FOUND - compound doesn't exist in PubChem
                if response.status_code == 404:
                    logger.warning(
                        f"⚠️ Compound '{compound}' not found in PubChem (404) - "
                        f"using original name"
                    )
                    # Cache the original name to avoid repeated lookups
                    self._cache[compound_normalized] = compound
                    return compound
                
                # OTHER ERRORS - log and continue
                logger.warning(
                    f"⚠️ PubChem returned {response.status_code} for '{compound}'"
                )
                
            except requests.exceptions.Timeout:
                logger.warning(
                    f"⏱️ Timeout on attempt {attempt + 1}/{retries + 1} for '{compound}'"
                )
                if attempt < retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    
            except requests.exceptions.RequestException as e:
                logger.error(
                    f"🔥 Network error on attempt {attempt + 1}: {e}"
                )
                if attempt < retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
                    
            except (KeyError, IndexError, ValueError) as e:
                logger.error(
                    f"🔥 PubChem response parsing error for '{compound}': {e}"
                )
                # Don't retry on parsing errors - data structure issue
                break
                
            except Exception as e:
                logger.error(
                    f"🔥 Unexpected error resolving '{compound}': {e}"
                )
                if attempt < retries:
                    wait_time = 2 ** attempt
                    time.sleep(wait_time)
        
        # ALL RETRIES FAILED - fallback to original name
        self.resolution_failures += 1
        logger.warning(
            f"❌ Failed to resolve '{compound}' after {retries + 1} attempts, "
            f"using original name. Total failures: {self.resolution_failures}"
        )
        
        # Cache the original name to avoid repeated failed lookups
        self._cache[compound_normalized] = compound
        return compound
    
    def resolve_batch(
        self, 
        compounds: list[str], 
        max_parallel: int = 5,
        delay_between_requests: float = 0.2
    ) -> Dict[str, str]:
        """
        Resolve multiple compounds with rate limit control.
        
        This method processes a batch of compounds sequentially to avoid
        overwhelming the PubChem API with concurrent requests. A small delay
        is added between requests to respect rate limits.
        
        Args:
            compounds: List of compound names to resolve
            max_parallel: Reserved for future async implementation (currently unused)
            delay_between_requests: Delay in seconds between requests (default: 0.2)
            
        Returns:
            Dictionary of {original_name: canonical_name} mappings
            
        Examples:
            >>> resolver = CompoundAliasResolver()
            >>> compounds = ["Vitamin D", "Curcumin", "Resveratrol"]
            >>> results = resolver.resolve_batch(compounds)
            >>> results
            {'Vitamin D': 'Cholecalciferol', 'Curcumin': 'Curcumin', 'Resveratrol': 'Resveratrol'}
        """
        results = {}
        total = len(compounds)
        
        logger.info(f"🔄 Starting batch resolution for {total} compounds...")
        
        for idx, compound in enumerate(compounds, 1):
            logger.debug(f"Processing {idx}/{total}: {compound}")
            
            # Resolve compound
            canonical = self.resolve_compound_alias(compound)
            results[compound] = canonical
            
            # Add delay to avoid rate limits (except for last item)
            if idx < total:
                time.sleep(delay_between_requests)
        
        logger.info(
            f"✅ Batch resolution complete: {total} compounds processed, "
            f"{self.cache_hits} cache hits, {self.cache_misses} cache misses, "
            f"{self.resolution_failures} failures"
        )
        
        return results
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache performance statistics.
        
        Returns:
            Dictionary with cache hits, misses, failures, and size
        """
        return {
            "cache_size": len(self._cache),
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "resolution_failures": self.resolution_failures,
            "hit_rate": (
                self.cache_hits / (self.cache_hits + self.cache_misses)
                if (self.cache_hits + self.cache_misses) > 0
                else 0.0
            )
        }
    
    def clear_cache(self):
        """Clear the in-memory cache."""
        cache_size = len(self._cache)
        self._cache.clear()
        logger.info(f"🗑️ Cache cleared ({cache_size} entries removed)")
    
    def warm_cache(self, common_compounds: list[str]):
        """
        Pre-populate cache with common compounds.
        
        Args:
            common_compounds: List of commonly queried compounds to pre-resolve
        """
        logger.info(f"🔥 Warming cache with {len(common_compounds)} common compounds...")
        self.resolve_batch(common_compounds)
        logger.info(f"✅ Cache warmed: {len(self._cache)} entries")


# Singleton instance for application-wide use
_resolver_instance: Optional[CompoundAliasResolver] = None


def get_resolver() -> CompoundAliasResolver:
    """
    Get or create the singleton CompoundAliasResolver instance.
    
    Returns:
        CompoundAliasResolver singleton instance
    """
    global _resolver_instance
    if _resolver_instance is None:
        _resolver_instance = CompoundAliasResolver()
    return _resolver_instance

