"""
Enformer Client - Backend Integration

Client for calling Enformer service from backend API endpoints.
Handles service discovery, retries, fallbacks, and provenance tracking.

Author: Zo
Date: October 13, 2025
"""

import os
import httpx
import asyncio
from typing import Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)

ENFORMER_URL = os.environ.get("ENFORMER_URL", None)
ENFORMER_TIMEOUT = int(os.environ.get("ENFORMER_TIMEOUT", 30))
ENFORMER_RETRIES = int(os.environ.get("ENFORMER_RETRIES", 2))


async def predict_chromatin_accessibility(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    context_bp: int = 32000,
    use_cache: bool = True
) -> Dict[str, Any]:
    """
    Predict chromatin accessibility using Enformer service
    
    Args:
        chrom: Chromosome (e.g., "chr7")
        pos: Position (1-based, GRCh38)
        ref: Reference allele
        alt: Alternate allele
        context_bp: Context window (±32kb default)
        use_cache: Use service cache if available
    
    Returns:
        {
            "accessibility_score": float [0,1],
            "dnase_signal": float,
            "cage_signal": float,
            "atac_signal": float,
            "provenance": {...}
        }
    """
    
    # Check if service is configured
    if ENFORMER_URL is None:
        logger.warning("ENFORMER_URL not set. Using deterministic stub.")
        return _stub_prediction(chrom, pos, ref, alt, context_bp, "service_not_configured")
    
    # Prepare request
    payload = {
        "chrom": chrom,
        "pos": pos,
        "ref": ref,
        "alt": alt,
        "context_bp": context_bp,
        "use_cache": use_cache
    }
    
    # Retry logic
    for attempt in range(ENFORMER_RETRIES):
        try:
            async with httpx.AsyncClient(timeout=ENFORMER_TIMEOUT) as client:
                response = await client.post(
                    f"{ENFORMER_URL}/predict",
                    json=payload
                )
                response.raise_for_status()
                result = response.json()
                
                # Add client-side provenance
                result["provenance"]["client_version"] = "v1"
                result["provenance"]["attempt"] = attempt + 1
                
                return result
        
        except httpx.TimeoutException:
            logger.warning(f"Enformer timeout (attempt {attempt + 1}/{ENFORMER_RETRIES})")
            if attempt == ENFORMER_RETRIES - 1:
                return _stub_prediction(chrom, pos, ref, alt, context_bp, "timeout")
            await asyncio.sleep(1)  # Brief backoff
        
        except httpx.HTTPStatusError as e:
            logger.error(f"Enformer HTTP error: {e.response.status_code}")
            return _stub_prediction(chrom, pos, ref, alt, context_bp, f"http_{e.response.status_code}")
        
        except Exception as e:
            logger.error(f"Enformer unexpected error: {e}")
            return _stub_prediction(chrom, pos, ref, alt, context_bp, "unexpected_error")
    
    # Fallback if all retries fail
    return _stub_prediction(chrom, pos, ref, alt, context_bp, "retries_exhausted")


def _stub_prediction(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    context_bp: int,
    reason: str
) -> Dict[str, Any]:
    """Deterministic stub for when Enformer service unavailable"""
    
    # Deterministic value based on position (for reproducibility)
    import hashlib
    seed = hashlib.md5(f"{chrom}:{pos}".encode()).hexdigest()
    seed_int = int(seed[:8], 16)
    
    # Generate deterministic but varied scores in [0.4, 0.7] range
    base = 0.4 + (seed_int % 1000) / 1000 * 0.3
    
    return {
        "accessibility_score": round(base, 3),
        "dnase_signal": round(base + 0.01, 3),
        "cage_signal": round(base - 0.01, 3),
        "atac_signal": round(base, 3),
        "provenance": {
            "model": "enformer-stub-v1",
            "method": "deterministic_fallback",
            "context_bp": context_bp,
            "tracks": ["DNase_stub", "CAGE_stub", "ATAC_stub"],
            "fallback_reason": reason,
            "warning": "⚠️ Using deterministic stub. Enformer service unavailable."
        }
    }


def get_service_status() -> Dict[str, Any]:
    """Check Enformer service status"""
    if ENFORMER_URL is None:
        return {
            "available": False,
            "reason": "ENFORMER_URL not configured"
        }
    
    try:
        with httpx.Client(timeout=5) as client:
            response = client.get(f"{ENFORMER_URL}/health_check")
            response.raise_for_status()
            health = response.json()
            return {
                "available": True,
                "health": health
            }
    except Exception as e:
        return {
            "available": False,
            "reason": str(e)
        }


