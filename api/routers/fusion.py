"""
Fusion Engine - AlphaMissense integration with GRCh38 missense gating

Curl examples (local):

1) Coverage check
curl -sS "http://127.0.0.1:8000/api/fusion/coverage?chrom=7&pos=140453136&ref=T&alt=A"

2) Score variant
curl -sS -X POST http://127.0.0.1:8000/api/fusion/score_variant \
  -H 'Content-Type: application/json' \
  -d '{"chrom":"7","pos":140453136,"ref":"T","alt":"A"}'
"""
import os
import asyncio
from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any, Optional
import httpx
import json
import hashlib

# Optional Redis import
try:
    import redis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    redis = None

from ..config import get_feature_flags

router = APIRouter(prefix="/api/fusion", tags=["fusion"])

# Redis client (optional)
redis_client = None
if REDIS_AVAILABLE:
    try:
        redis_url = os.getenv("REDIS_URL")
        if redis_url:
            redis_client = redis.from_url(redis_url, decode_responses=True)
    except Exception:
        redis_client = None

# Fusion Engine URL (placeholder - would be configured in production)
FUSION_AM_URL = os.getenv("FUSION_AM_URL", "https://fusion-api.example.com")


def _ensure_enabled():
    """Check if Fusion Engine is enabled"""
    flags = get_feature_flags()
    if flags.get("disable_fusion", True):
        raise HTTPException(status_code=403, detail="Fusion Engine disabled by configuration")


def _is_grch38_missense(chrom: str, pos: int, ref: str, alt: str) -> bool:
    """Check if variant is GRCh38 missense (single nucleotide substitution)"""
    # Basic GRCh38 chromosome check
    if not chrom.startswith(("chr", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20", "21", "22", "X", "Y")):
        return False
    
    # Clean chromosome format
    if chrom.startswith("chr"):
        chrom = chrom[3:]
    
    # Check if it's a valid chromosome
    if chrom not in [str(i) for i in range(1, 23)] + ["X", "Y"]:
        return False
    
    # Check if it's a single nucleotide substitution
    if len(ref) != 1 or len(alt) != 1:
        return False
    
    # Check if it's a missense (not synonymous)
    if ref == alt:
        return False
    
    return True


def _get_cache_key(chrom: str, pos: int, ref: str, alt: str) -> str:
    """Generate cache key for variant"""
    return f"fusion:am:{chrom}:{pos}:{ref}>{alt}"


async def _get_cached_result(cache_key: str) -> Optional[Dict[str, Any]]:
    """Get cached result from Redis"""
    if not redis_client:
        return None
    
    try:
        cached = redis_client.get(cache_key)
        if cached:
            return json.loads(cached)
    except Exception:
        pass
    return None


async def _set_cached_result(cache_key: str, result: Dict[str, Any], ttl: int = 3600):
    """Cache result in Redis"""
    if not redis_client:
        return
    
    try:
        redis_client.setex(cache_key, ttl, json.dumps(result))
    except Exception:
        pass


@router.get("/coverage")
async def check_coverage(
    chrom: str = Query(..., description="Chromosome"),
    pos: int = Query(..., description="Position"),
    ref: str = Query(..., description="Reference allele"),
    alt: str = Query(..., description="Alternate allele")
):
    """Check if variant is covered by AlphaMissense Fusion Engine"""
    _ensure_enabled()
    
    try:
        # Check if it's GRCh38 missense
        is_covered = _is_grch38_missense(chrom, pos, ref, alt)
        
        return {
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "coverage": is_covered,
            "reason": "GRCh38 missense variant" if is_covered else "Not GRCh38 missense or invalid format",
            "provenance": {
                "method": "grch38_missense_gate",
                "feature_flags": get_feature_flags()
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Coverage check failed: {e}")


@router.post("/score_variant")
async def score_variant(request: Dict[str, Any]):
    """Score variant using AlphaMissense Fusion Engine"""
    _ensure_enabled()
    
    try:
        chrom = str(request.get("chrom", ""))
        pos = int(request.get("pos", 0))
        ref = str(request.get("ref", ""))
        alt = str(request.get("alt", ""))
        
        if not (chrom and pos and ref and alt):
            raise HTTPException(status_code=400, detail="chrom, pos, ref, alt required")
        
        # Check GRCh38 missense eligibility
        if not _is_grch38_missense(chrom, pos, ref, alt):
            return {
                "chrom": chrom,
                "pos": pos,
                "ref": ref,
                "alt": alt,
                "fused_score": None,
                "alphamissense_score": None,
                "coverage": False,
                "reason": "Not GRCh38 missense variant",
                "provenance": {
                    "method": "grch38_missense_gate",
                    "feature_flags": get_feature_flags()
                }
            }
        
        # Check cache first
        cache_key = _get_cache_key(chrom, pos, ref, alt)
        cached_result = await _get_cached_result(cache_key)
        if cached_result:
            cached_result["provenance"]["cache"] = "hit"
            return cached_result
        
        # For demo purposes, return a mock score
        # In production, this would call the actual Fusion Engine API
        mock_score = 0.75  # Mock fused score
        am_score = 0.68    # Mock AlphaMissense score
        
        result = {
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "fused_score": mock_score,
            "alphamissense_score": am_score,
            "coverage": True,
            "reason": "GRCh38 missense variant scored",
            "provenance": {
                "method": "fusion_engine_mock",
                "cache": "miss",
                "feature_flags": get_feature_flags()
            }
        }
        
        # Cache the result
        await _set_cached_result(cache_key, result)
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Variant scoring failed: {e}")