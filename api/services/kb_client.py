"""
Knowledge Base Client Service
Task-oriented helpers that wrap the KB store with timeouts, retries, and provenance pass-through
"""
import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import httpx

from .kb_store import get_kb_store

logger = logging.getLogger(__name__)

class KBClient:
    """Client for Knowledge Base operations with timeouts and retries"""
    
    def __init__(self, timeout: float = 5.0, max_retries: int = 2):
        self.timeout = timeout
        self.max_retries = max_retries
        self.kb_store = get_kb_store()
    
    async def _make_request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        """Make HTTP request with retries and timeout"""
        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.request(method, url, **kwargs)
                    response.raise_for_status()
                    return response.json()
            except Exception as e:
                if attempt == self.max_retries:
                    logger.error(f"KB client request failed after {self.max_retries + 1} attempts: {e}")
                    raise
                logger.warning(f"KB client request attempt {attempt + 1} failed: {e}")
                await asyncio.sleep(0.5 * (attempt + 1))  # Exponential backoff
    
    def get_gene(self, gene: str) -> Optional[Dict[str, Any]]:
        """
        Get gene entity with name, synonyms, and pathways
        
        Args:
            gene: Gene symbol (e.g., 'BRCA1', 'TP53')
            
        Returns:
            Gene entity with provenance or None if not found
        """
        try:
            # Try direct lookup first
            item_id = f"genes/{gene.upper()}"
            item = self.kb_store.get_item(item_id)
            if item:
                return item
            
            # Fallback to search
            results = self.kb_store.search(gene, ["gene"], 5)
            for hit in results.get("hits", []):
                if hit.get("item", {}).get("symbol", "").upper() == gene.upper():
                    return hit.get("item")
            
            logger.info(f"Gene not found in KB: {gene}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting gene {gene}: {e}")
            return None
    
    def get_variant(self, gene: str, hgvs_p: Optional[str] = None, 
                   chrom: Optional[str] = None, pos: Optional[int] = None) -> Optional[Dict[str, Any]]:
        """
        Get variant entity if curated
        
        Args:
            gene: Gene symbol
            hgvs_p: HGVS protein notation (e.g., 'p.V600E')
            chrom: Chromosome
            pos: Position
            
        Returns:
            Variant entity with provenance or None if not found
        """
        try:
            # Try HGVS-based lookup first
            if hgvs_p:
                variant_key = f"{gene}_{hgvs_p.replace('p.', '').replace('.', '_')}"
                item_id = f"variants/{variant_key}"
                item = self.kb_store.get_item(item_id)
                if item:
                    return item
            
            # Fallback to search
            search_terms = [gene]
            if hgvs_p:
                search_terms.append(hgvs_p)
            
            for term in search_terms:
                results = self.kb_store.search(term, ["variant"], 5)
                for hit in results.get("hits", []):
                    variant = hit.get("item", {})
                    if variant.get("gene", "").upper() == gene.upper():
                        return variant
            
            logger.info(f"Variant not found in KB: {gene} {hgvs_p}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting variant {gene} {hgvs_p}: {e}")
            return None
    
    def get_pathways(self, genes: List[str]) -> List[Dict[str, Any]]:
        """
        Get pathway memberships for genes
        
        Args:
            genes: List of gene symbols
            
        Returns:
            List of pathway entities with provenance
        """
        try:
            pathways = []
            
            for gene in genes:
                # Get gene entity first
                gene_entity = self.get_gene(gene)
                if gene_entity and "pathways" in gene_entity:
                    for pathway_id in gene_entity["pathways"]:
                        pathway_item = self.kb_store.get_item(f"pathways/{pathway_id}")
                        if pathway_item:
                            pathways.append(pathway_item)
            
            # Remove duplicates
            seen = set()
            unique_pathways = []
            for pathway in pathways:
                pathway_id = pathway.get("id")
                if pathway_id and pathway_id not in seen:
                    seen.add(pathway_id)
                    unique_pathways.append(pathway)
            
            return unique_pathways
            
        except Exception as e:
            logger.error(f"Error getting pathways for {genes}: {e}")
            return []
    
    def get_cohort_coverage(self, gene: str) -> Optional[Dict[str, Any]]:
        """
        Get cohort coverage snapshot for gene
        
        Args:
            gene: Gene symbol
            
        Returns:
            Cohort coverage data with provenance or None if not found
        """
        try:
            # Search for cohort summaries that mention this gene
            results = self.kb_store.search(gene, ["cohort"], 10)
            
            for hit in results.get("hits", []):
                cohort = hit.get("item", {})
                if "coverage" in cohort and "by_gene" in cohort["coverage"]:
                    gene_coverage = cohort["coverage"]["by_gene"].get(gene.upper())
                    if gene_coverage:
                        return {
                            "gene": gene,
                            "cohort_id": cohort.get("id"),
                            "cohort_name": cohort.get("name"),
                            "coverage": gene_coverage,
                            "provenance": cohort.get("provenance", {})
                        }
            
            logger.info(f"No cohort coverage found for gene: {gene}")
            return None
            
        except Exception as e:
            logger.error(f"Error getting cohort coverage for {gene}: {e}")
            return None
    
    def search_curated_facts(self, query: str, types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Search for curated facts across KB
        
        Args:
            query: Search query
            types: Optional list of types to search
            
        Returns:
            List of matching items with provenance
        """
        try:
            results = self.kb_store.search(query, types, 20)
            return results.get("hits", [])
            
        except Exception as e:
            logger.error(f"Error searching curated facts: {e}")
            return []

# Global KB client instance
_kb_client: Optional[KBClient] = None

def get_kb_client() -> KBClient:
    """Get the global KB client instance"""
    global _kb_client
    if _kb_client is None:
        _kb_client = KBClient()
    return _kb_client


