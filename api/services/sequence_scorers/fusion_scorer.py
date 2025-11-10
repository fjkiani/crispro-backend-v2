"""
Fusion AlphaMissense Scorer: AlphaMissense Fusion Engine integration.
"""
import os
import httpx
from typing import Dict, Any, List, Optional

from .models import SeqScore
from .utils import percentile_like, classify_impact_level, safe_str, safe_int
from ..cache_service import get_cache, set_cache
from api.config import get_feature_flags


class FusionAMScorer:
    """AlphaMissense Fusion Engine scorer.

    If FUSION_AM_URL is not provided, falls back to local router
    POST /api/fusion/score_variant when available to obtain a
    fused or AlphaMissense score in a demo-friendly way.
    """
    
    def __init__(self, fusion_url: Optional[str] = None, api_base: str = "http://127.0.0.1:8000"):
        self.fusion_url = fusion_url or os.getenv("FUSION_AM_URL")
        self.api_base = api_base
    
    def _get_cache_key(self, mutations: List[Dict[str, Any]]) -> str:
        """Generate cache key for fusion scoring."""
        mutation_keys = []
        for m in mutations:
            hgvs_p = m.get("hgvs_p", "")
            if hgvs_p:
                mutation_keys.append(hgvs_p)
            else:
                chrom = m.get("chrom", "")
                pos = m.get("pos", "")
                ref = m.get("ref", "")
                alt = m.get("alt", "")
                mutation_keys.append(f"{chrom}:{pos}:{ref}:{alt}")
        return f"fusion_am:{hash(tuple(mutation_keys))}"
    
    async def score(self, mutations: List[Dict[str, Any]]) -> List[SeqScore]:
        """
        Score variants using Fusion Engine AlphaMissense.
        
        Args:
            mutations: List of variant dictionaries
            
        Returns:
            List of SeqScore objects
        """
        # If neither external nor local fusion is enabled, exit early
        try:
            ff = get_feature_flags()
            if ff.get("disable_fusion", True):
                return []
        except Exception:
            pass
        if not (self.fusion_url or self.api_base):
            return []
        
        # Check cache first
        cache_key = self._get_cache_key(mutations)
        cached_results = await get_cache(cache_key)
        if cached_results:
            return [SeqScore(**result) for result in cached_results]
        
        seq_scores = []
        
        # Try external Fusion Engine first if configured
        if self.fusion_url:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    for m in mutations:
                        chrom = safe_str(m.get("chrom")).lstrip("chr")
                        pos = safe_int(m.get("pos"))
                        ref = safe_str(m.get("ref")).upper()
                        alt = safe_str(m.get("alt")).upper()
                        if not (chrom and pos and ref and alt):
                            continue
                        candidates = [
                            f"chr{chrom}:{pos}:{ref}:{alt}",
                            f"{chrom}:{pos}:{ref}:{alt}",
                            f"chr{chrom}:{pos}:{alt}:{ref}",
                            f"{chrom}:{pos}:{alt}:{ref}",
                        ]
                        for variant_str in candidates:
                            payload = {
                                "protein_sequence": "PLACEHOLDER",
                                "variants": [
                                    {
                                        "variant_id": f"{m.get('gene', '')}:{m.get('hgvs_p', '')}",
                                        "hgvs": str(m.get("hgvs_p") or ""),
                                        "alphamissense_variant_str": variant_str,
                                    }
                                ],
                            }
                            try:
                                r = await client.post(self.fusion_url.rstrip('/') + "/score_variants", json=payload)
                                if r.status_code >= 400:
                                    continue
                                js = r.json() or {}
                                arr = js.get("scored_variants") or js.get("results") or []
                                item = arr[0] if arr else None
                                if item:
                                    fused = item.get("zeta_score")
                                    if isinstance(fused, (int, float)) and fused not in (-999.0,):
                                        sequence_disruption = float(fused)
                                    else:
                                        am = item.get("alphamissense_score")
                                        if isinstance(am, (int, float)) and am not in (-999.0, -998.0):
                                            sequence_disruption = float(am)
                                        else:
                                            continue
                                    seq_scores.append(SeqScore(
                                        variant=m,
                                        sequence_disruption=sequence_disruption,
                                        calibrated_seq_percentile=percentile_like(sequence_disruption),
                                        impact_level=classify_impact_level(sequence_disruption),
                                        scoring_mode="fusion_am",
                                        best_model="fusion_am",
                                        scoring_strategy={"approach": "alphamissense_fusion", "source": "fusion_engine"}
                                    ))
                                    break
                            except Exception:
                                continue
            except Exception:
                pass

        # Fallback: use local fusion router if external unavailable
        if not seq_scores and self.api_base:
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    for m in mutations:
                        chrom = safe_str(m.get("chrom"))
                        pos = safe_int(m.get("pos"))
                        ref = safe_str(m.get("ref")).upper()
                        alt = safe_str(m.get("alt")).upper()
                        if not (chrom and pos and ref and alt):
                            continue
                        r = await client.post(
                            f"{self.api_base}/api/fusion/score_variant",
                            json={"chrom": chrom, "pos": pos, "ref": ref, "alt": alt},
                            headers={"Content-Type": "application/json"}
                        )
                        if r.status_code >= 400:
                            continue
                        js = r.json() or {}
                        fused = js.get("fused_score")
                        am = js.get("alphamissense_score")
                        score = None
                        if isinstance(fused, (int, float)):
                            score = float(fused)
                        elif isinstance(am, (int, float)):
                            score = float(am)
                        if score is None:
                            continue
                        seq_scores.append(SeqScore(
                            variant=m,
                            sequence_disruption=score,
                            calibrated_seq_percentile=percentile_like(score),
                            impact_level=classify_impact_level(score),
                            scoring_mode="fusion_am_local",
                            best_model="fusion_am",
                            scoring_strategy={"approach": "fusion_router_mock", "source": "local_router"}
                        ))
            except Exception:
                pass
        
        # Fallback: if fusion failed and seq_scores is empty, create minimal placeholder
        if not seq_scores and mutations:
            for m in mutations:
                seq_scores.append(SeqScore(
                    variant=m,
                    sequence_disruption=0.0,
                    calibrated_seq_percentile=0.0,
                    impact_level="no_impact",
                    scoring_mode="fusion_fallback",
                    best_model="fusion_am",
                    scoring_strategy={
                        "approach": "fusion_failed_fallback",
                        "source": "placeholder"
                    }
                ))
        
        # Cache the results
        if seq_scores:
            cache_key = self._get_cache_key(mutations)
            await set_cache(cache_key, [score.__dict__ for score in seq_scores], ttl=3600)
        
        return seq_scores

