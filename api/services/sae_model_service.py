"""
SAE Model Service: Client helper for extracting SAE features from Evo2 activations.
Provides a Python interface to the SAE Modal service.
"""
import httpx
import os
from typing import Dict, Any, List, Optional
from loguru import logger

SAE_SERVICE_URL = os.getenv("SAE_SERVICE_URL", "https://your-modal-url-here.modal.run")
SAE_TIMEOUT = 120.0

class SAEModelService:
    """Client for SAE feature extraction service."""
    
    def __init__(self, service_url: Optional[str] = None):
        """
        Initialize SAE model service client.
        
        Args:
            service_url: Optional custom SAE service URL. Defaults to SAE_SERVICE_URL env var.
        """
        self.service_url = service_url or SAE_SERVICE_URL
        if not self.service_url or self.service_url == "https://your-modal-url-here.modal.run":
            logger.warning("SAE service URL not configured. Set SAE_SERVICE_URL environment variable.")
            self.configured = False
        else:
            self.configured = True
    
    async def extract_features_from_activations(
        self,
        activations: List[List[List[float]]],
        provenance: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Extract SAE features from pre-computed Evo2 layer 26 activations.
        
        Args:
            activations: Layer 26 activations [batch, seq_len, 4096]
            provenance: Optional provenance metadata to attach
        
        Returns:
            {
                "features": List[...],  # 32K-dim feature vector
                "top_features": List[{"index": int, "value": float}],  # Top k=64
                "layer": "blocks.26",
                "stats": {...},
                "provenance": {...}
            }
        """
        if not self.configured:
            raise ValueError("SAE service not configured. Set SAE_SERVICE_URL.")
        
        payload = {"activations": activations}
        
        async with httpx.AsyncClient(timeout=SAE_TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{self.service_url}/extract_features",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                result = response.json()
                
                # Attach additional provenance if provided
                if provenance:
                    if "provenance" not in result:
                        result["provenance"] = {}
                    result["provenance"].update(provenance)
                
                return result
            
            except httpx.HTTPStatusError as e:
                logger.error(f"SAE service HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"SAE service error: {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"SAE service connection error: {e}")
                raise RuntimeError(f"Failed to connect to SAE service: {str(e)}")
    
    async def extract_features_from_variant(
        self,
        chrom: str,
        pos: int,
        ref: str,
        alt: str,
        model_id: str = "evo2_1b",
        assembly: str = "GRCh38",
        window: int = 8192
    ) -> Dict[str, Any]:
        """
        Extract SAE features from a genomic variant.
        The SAE service will score the variant with Evo2 and extract activations internally.
        
        Args:
            chrom: Chromosome (e.g., "7", "chr7", "X")
            pos: Position (1-based)
            ref: Reference allele
            alt: Alternate allele
            model_id: Evo2 model to use (default: "evo2_1b")
            assembly: Genome assembly (default: "GRCh38")
            window: Window size for sequence context (default: 8192)
        
        Returns:
            {
                "features": List[...],  # 32K-dim feature vector
                "top_features": List[{"index": int, "value": float}],  # Top k=64
                "layer": "blocks.26",
                "stats": {...},
                "provenance": {...}
            }
        """
        if not self.configured:
            raise ValueError("SAE service not configured. Set SAE_SERVICE_URL.")
        
        payload = {
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "model_id": model_id,
            "assembly": assembly,
            "window": window
        }
        
        async with httpx.AsyncClient(timeout=SAE_TIMEOUT) as client:
            try:
                response = await client.post(
                    f"{self.service_url}/extract_features",
                    json=payload,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
            
            except httpx.HTTPStatusError as e:
                logger.error(f"SAE service HTTP error: {e.response.status_code} - {e.response.text}")
                raise RuntimeError(f"SAE service error: {e.response.text}")
            except httpx.RequestError as e:
                logger.error(f"SAE service connection error: {e}")
                raise RuntimeError(f"Failed to connect to SAE service: {str(e)}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check if SAE service is healthy and reachable.
        
        Returns:
            {
                "status": "healthy" | "unhealthy" | "not_configured",
                "url": str,
                ...
            }
        """
        if not self.configured:
            return {
                "status": "not_configured",
                "url": None,
                "message": "SAE_SERVICE_URL not set"
            }
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                response = await client.get(f"{self.service_url}/health")
                return {
                    "status": "healthy" if response.status_code == 200 else "unhealthy",
                    "url": self.service_url,
                    "response": response.json() if response.status_code == 200 else response.text
                }
            except Exception as e:
                return {
                    "status": "error",
                    "url": self.service_url,
                    "error": str(e)
                }

# Global singleton instance
_sae_service = None

def get_sae_service() -> SAEModelService:
    """Get the global SAE model service instance."""
    global _sae_service
    if _sae_service is None:
        _sae_service = SAEModelService()
    return _sae_service



