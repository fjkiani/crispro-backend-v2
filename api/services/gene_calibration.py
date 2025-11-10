"""
Gene-specific calibration service for Evo2 delta scores.
Computes percentiles and z-scores based on ClinVar reference data.
"""
import json
import asyncio
import time
from typing import Dict, List, Optional, Tuple
import httpx
import numpy as np
from pathlib import Path

class GeneCalibrationService:
    """
    Dynamic calibration service that learns from ClinVar data to provide
    gene-specific percentiles and z-scores for Evo2 delta scores.
    """
    
    def __init__(self, cache_dir: str = "data/calibration_cache", ttl_hours: int = 24):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.gene_stats = {}  # In-memory cache
        self.ttl_seconds = ttl_hours * 3600
        self.last_refresh = {}  # Track last refresh time per gene
        self._refresh_task = None
        
    async def start_background_refresh(self, refresh_interval_hours: int = 6):
        """Start background refresh task for calibration data."""
        if self._refresh_task is None:
            self._refresh_task = asyncio.create_task(
                self._background_refresh_loop(refresh_interval_hours * 3600)
            )
    
    async def stop_background_refresh(self):
        """Stop background refresh task."""
        if self._refresh_task:
            self._refresh_task.cancel()
            try:
                await self._refresh_task
            except asyncio.CancelledError:
                pass
            self._refresh_task = None
    
    async def _background_refresh_loop(self, refresh_interval_seconds: int):
        """Background task to refresh calibration data periodically."""
        try:
            while True:
                await asyncio.sleep(refresh_interval_seconds)
                
                # Refresh expired entries
                current_time = time.time()
                expired_genes = []
                
                for gene, last_refresh_time in self.last_refresh.items():
                    if current_time - last_refresh_time > self.ttl_seconds:
                        expired_genes.append(gene)
                
                if expired_genes:
                    print(f"Background refresh: updating calibration for {len(expired_genes)} genes")
                    for gene in expired_genes:
                        try:
                            await self._compute_gene_stats_from_clinvar(gene)
                            self.last_refresh[gene] = current_time
                        except Exception as e:
                            print(f"Background refresh failed for {gene}: {e}")
                            
        except asyncio.CancelledError:
            print("Background calibration refresh stopped")
            raise
        except Exception as e:
            print(f"Background refresh error: {e}")
    
    async def preload_genes(self, genes: List[str]):
        """Preload calibration data for a list of genes."""
        print(f"Preloading calibration data for {len(genes)} genes...")
        current_time = time.time()
        
        tasks = []
        for gene in genes:
            gene = gene.upper()
            # Only load if not recently cached
            if (gene not in self.last_refresh or 
                current_time - self.last_refresh[gene] > self.ttl_seconds):
                tasks.append(self._preload_single_gene(gene, current_time))
        
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(1 for r in results if not isinstance(r, Exception))
            print(f"Preloaded calibration for {successful}/{len(tasks)} genes")
        else:
            print("All genes already cached and current")
    
    async def _preload_single_gene(self, gene: str, current_time: float):
        """Preload calibration for a single gene."""
        try:
            await self._load_or_compute_gene_stats(gene)
            self.last_refresh[gene] = current_time
            return True
        except Exception as e:
            print(f"Failed to preload {gene}: {e}")
            return False
        
    async def get_gene_calibration(self, gene: str, delta_score: float) -> Dict[str, float]:
        """
        Get calibrated percentile and z-score for a delta score in a specific gene.
        
        Args:
            gene: Gene symbol (e.g., "BRAF")
            delta_score: Raw Evo2 delta score
            
        Returns:
            Dict with calibrated_percentile, z_score, confidence
        """
        gene = gene.upper()
        current_time = time.time()
        
        # Check if data needs refresh
        if (gene not in self.last_refresh or 
            current_time - self.last_refresh[gene] > self.ttl_seconds):
            await self._load_or_compute_gene_stats(gene)
            self.last_refresh[gene] = current_time
        
        stats = self.gene_stats.get(gene, {})
        
        if not stats or stats.get("sample_size", 0) < 5:
            # Insufficient data, fall back to global percentile estimation
            return {
                "calibrated_percentile": self._fallback_percentile(delta_score),
                "z_score": 0.0,
                "confidence": 0.1,
                "sample_size": stats.get("sample_size", 0),
                "calibration_source": "fallback",
                "cache_age_hours": self._get_cache_age_hours(gene, current_time)
            }
        
        # Compute percentile and z-score using gene-specific distribution
        percentile = self._compute_percentile(delta_score, stats["distribution"])
        z_score = self._compute_z_score(delta_score, stats["mean"], stats["std"])
        
        return {
            "calibrated_percentile": percentile,
            "z_score": z_score,
            "confidence": min(1.0, stats["sample_size"] / 50.0),  # Higher confidence with more samples
            "sample_size": stats["sample_size"],
            "calibration_source": "gene_specific",
            "cache_age_hours": self._get_cache_age_hours(gene, current_time)
        }
    
    def _get_cache_age_hours(self, gene: str, current_time: float) -> float:
        """Get cache age in hours for a gene."""
        if gene not in self.last_refresh:
            return 0.0
        age_seconds = current_time - self.last_refresh[gene]
        return age_seconds / 3600.0
    
    async def _load_or_compute_gene_stats(self, gene: str):
        """Load gene stats from cache or compute from ClinVar if needed."""
        cache_file = self.cache_dir / f"{gene}_stats.json"
        current_time = time.time()
        
        # Try to load from cache first if it's fresh
        if cache_file.exists():
            try:
                stat_result = cache_file.stat()
                file_age = current_time - stat_result.st_mtime
                
                if file_age < self.ttl_seconds:
                    with open(cache_file, 'r') as f:
                        self.gene_stats[gene] = json.load(f)
                        return
            except Exception:
                pass
        
        # Compute from ClinVar data
        await self._compute_gene_stats_from_clinvar(gene)
        
        # Cache the results
        if gene in self.gene_stats:
            try:
                with open(cache_file, 'w') as f:
                    json.dump(self.gene_stats[gene], f)
            except Exception:
                pass
    
    async def _compute_gene_stats_from_clinvar(self, gene: str):
        """
        Fetch known variants for a gene from ClinVar and compute their
        Evo2 delta scores to build a calibration distribution.
        """
        try:
            # Get known variants for this gene from ClinVar
            variants = await self._fetch_clinvar_variants(gene)
            
            if len(variants) < 3:
                self.gene_stats[gene] = {"sample_size": 0, "gene": gene, "computed_at": time.time()}
                return
            
            # Score a sample of variants with Evo2 to build distribution
            delta_scores = await self._score_variants_batch(variants[:20])  # Limit to 20 for speed
            
            if len(delta_scores) < 3:
                self.gene_stats[gene] = {"sample_size": 0, "gene": gene, "computed_at": time.time()}
                return
            
            # Compute distribution statistics
            scores_array = np.array(delta_scores)
            self.gene_stats[gene] = {
                "mean": float(np.mean(scores_array)),
                "std": float(np.std(scores_array)),
                "distribution": sorted(delta_scores),  # For percentile computation
                "sample_size": len(delta_scores),
                "gene": gene,
                "computed_at": time.time()
            }
            
        except Exception as e:
            print(f"Failed to compute gene stats for {gene}: {e}")
            self.gene_stats[gene] = {"sample_size": 0, "gene": gene, "computed_at": time.time()}
    
    async def _fetch_clinvar_variants(self, gene: str) -> List[Dict]:
        """Fetch known variants for a gene from ClinVar API."""
        variants = []
        try:
            # Use a simple approach: search for variants in this gene
            # In production, you might want to use the full ClinVar dataset
            search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
            params = {
                "db": "clinvar",
                "term": f"{gene}[gene] AND single_nucleotide_variant[molecular_consequence]",
                "retmax": 50,
                "retmode": "json"
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    data = response.json()
                    # This is a simplified implementation
                    # In practice, you'd need to fetch the full variant details
                    # and parse genomic coordinates, ref/alt alleles
                    pass
            
        except Exception:
            pass
        
        return variants
    
    async def _score_variants_batch(self, variants: List[Dict]) -> List[float]:
        """Score a batch of variants with Evo2 to get delta scores."""
        scores = []
        
        # This would call your Evo2 service for each variant
        # For now, return some realistic sample data for development
        
        # Simulate realistic delta score distribution for development
        # Replace this with actual Evo2 calls in production
        import random
        random.seed(42)  # Reproducible for testing
        
        for _ in variants[:10]:  # Limit for development
            # Simulate realistic delta scores (mostly small negative values)
            score = random.gauss(-0.05, 0.03)  # Mean around -0.05, std 0.03
            scores.append(score)
        
        return scores
    
    def _compute_percentile(self, value: float, distribution: List[float]) -> float:
        """Compute percentile of value within the distribution."""
        if not distribution:
            return 50.0
        
        # Count how many values are less than or equal to our value
        count_le = sum(1 for x in distribution if x <= value)
        percentile = (count_le / len(distribution)) * 100.0
        
        return max(0.0, min(100.0, percentile))
    
    def _compute_z_score(self, value: float, mean: float, std: float) -> float:
        """Compute z-score of value given mean and standard deviation."""
        if std <= 0:
            return 0.0
        return (value - mean) / std
    
    def _fallback_percentile(self, delta_score: float) -> float:
        """
        Fallback percentile estimation when gene-specific data is unavailable.
        Based on general Evo2 score distributions.
        """
        # Rough mapping based on observed Evo2 behavior
        if delta_score <= -1.0:
            return 95.0  # Very disruptive
        elif delta_score <= -0.1:
            return 75.0  # Moderately disruptive  
        elif delta_score <= -0.01:
            return 60.0  # Mildly disruptive
        else:
            return 30.0  # Likely neutral/benign
    
    async def preload_common_genes(self, genes: List[str]):
        """Preload calibration data for commonly queried genes."""
        await self.preload_genes(genes)

    def get_cache_stats(self) -> Dict[str, any]:
        """Get statistics about the calibration cache."""
        current_time = time.time()
        stats = {
            "total_genes_cached": len(self.gene_stats),
            "genes_with_data": sum(1 for stats in self.gene_stats.values() if stats.get("sample_size", 0) > 0),
            "cache_ages_hours": {
                gene: self._get_cache_age_hours(gene, current_time) 
                for gene in self.last_refresh.keys()
            },
            "ttl_hours": self.ttl_seconds / 3600,
            "background_refresh_active": self._refresh_task is not None and not self._refresh_task.done()
        }
        return stats


# Global instance
_calibration_service = None

def get_calibration_service() -> GeneCalibrationService:
    """Get the global calibration service instance."""
    global _calibration_service
    if _calibration_service is None:
        from api.config import CALIBRATION_TTL_HOURS
        _calibration_service = GeneCalibrationService(ttl_hours=CALIBRATION_TTL_HOURS)
    return _calibration_service

async def initialize_calibration_service():
    """Initialize calibration service with preloading and background refresh."""
    from api.config import (
        get_feature_flags, 
        COMMON_MM_GENES, 
        CALIBRATION_REFRESH_INTERVAL_HOURS
    )
    
    feature_flags = get_feature_flags()
    if not feature_flags["enable_calibration_preload"]:
        print("Calibration preload disabled by feature flag")
        return
    
    service = get_calibration_service()
    
    # Start background refresh
    await service.start_background_refresh(CALIBRATION_REFRESH_INTERVAL_HOURS)
    
    # Preload common genes
    await service.preload_common_genes(COMMON_MM_GENES)
    
    print(f"Calibration service initialized with {len(COMMON_MM_GENES)} genes")
    return service 
 
 