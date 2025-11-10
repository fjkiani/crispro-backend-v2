"""
Evo2 Scorer: Evo2 sequence scoring with adaptive windows and ensemble support.
"""
import os
import httpx
from typing import Dict, Any, List, Optional

from .models import SeqScore
from .utils import percentile_like, classify_impact_level, safe_str, safe_int
from ..cache_service import get_cache, set_cache
from api.config import get_feature_flags


class Evo2Scorer:
    """Evo2 sequence scorer with adaptive windows and ensemble support."""
    
    def __init__(self, api_base: str = "http://127.0.0.1:8000"):
        self.api_base = api_base
    
    def _get_cache_key(self, mutation: Dict[str, Any], model_id: str, window_flanks: List[int], ensemble: bool) -> str:
        """Generate cache key for mutation scoring."""
        hgvs_p = mutation.get("hgvs_p", "")
        if hgvs_p:
            return f"evo2:{model_id}:{hgvs_p}:{hash(tuple(window_flanks))}:{ensemble}"
        else:
            chrom = mutation.get("chrom", "")
            pos = mutation.get("pos", "")
            ref = mutation.get("ref", "")
            alt = mutation.get("alt", "")
            return f"evo2:{model_id}:{chrom}:{pos}:{ref}:{alt}:{hash(tuple(window_flanks))}:{ensemble}"
    
    async def score(self, mutations: List[Dict[str, Any]], model_id: str = "evo2_7b", 
                   window_flanks: List[int] = None, ensemble: bool = True) -> List[SeqScore]:
        """
        Score variants using Evo2 with adaptive windows.
        
        Args:
            mutations: List of variant dictionaries
            model_id: Evo2 model to use
            window_flanks: List of flank sizes to test
            ensemble: Whether to use ensemble scoring
            
        Returns:
            List of SeqScore objects
        """
        if window_flanks is None:
            window_flanks = [4096, 8192, 16384, 25000]
        
        seq_scores = []
        
        try:
            feature_flags = get_feature_flags()
            disable_evo2 = feature_flags.get("disable_evo2", False)
            if disable_evo2:
                return []
        except Exception:
            pass
        
        # Check cache for all mutations first
        cached_results = []
        uncached_mutations = []
        
        for m in mutations:
            cache_key = self._get_cache_key(m, model_id, window_flanks, ensemble)
            cached_result = await get_cache(cache_key)
            if cached_result:
                cached_results.append(SeqScore(**cached_result))
            else:
                uncached_mutations.append(m)
        
        # If all results are cached, return them
        if not uncached_mutations:
            return cached_results
        
        # Process uncached mutations
        async with httpx.AsyncClient(timeout=180.0) as client:
            for m in uncached_mutations:
                chrom, pos, ref, alt = (
                    safe_str(m.get("chrom")), 
                    safe_int(m.get("pos")), 
                    safe_str(m.get("ref")).upper(), 
                    safe_str(m.get("alt")).upper()
                )
                
                best = {
                    "model": None,
                    "min_delta": None,
                    "exon_delta": None,
                    "best_window_bp": None,
                    "windows_tested": [],
                    "forward_reverse_meta": None
                }
                
                # Test multiple models if ensemble is enabled, but respect EVO_ALLOWED_MODELS if set
                default_candidates = ["evo2_1b", "evo2_7b", "evo2_40b"] if ensemble else [model_id]
                allowed = os.getenv("EVO_ALLOWED_MODELS", "").strip()
                if allowed:
                    allow_list = [m.strip() for m in allowed.split(",") if m.strip()]
                    model_candidates = [m for m in default_candidates if m in allow_list]
                    if not model_candidates:
                        model_candidates = [model_id]
                else:
                    model_candidates = default_candidates
                
                for model in model_candidates:
                    try:
                        result = await self._score_variant_with_symmetry(
                            client, chrom, pos, ref, alt, model, window_flanks
                        )
                        
                        # Keep the best result across models
                        if result.get("min_delta") is not None:
                            if (best["min_delta"] is None or 
                                abs(float(result["min_delta"])) > abs(float(best["min_delta"] or 0))):
                                best.update(result)
                                best["model"] = model
                    except Exception:
                        continue
                
                if best["min_delta"] is not None:
                    sequence_disruption = abs(float(best["min_delta"]))
                    # Heuristic truncation/frameshift lift: if hgvs_p indicates stop (*) or fs, enforce high disruption
                    try:
                        hgvs_p = str(m.get("hgvs_p") or "").upper()
                        if ("*" in hgvs_p) or ("FS" in hgvs_p):
                            sequence_disruption = max(sequence_disruption, 1.0)
                    except Exception:
                        pass
                    seq_score = SeqScore(
                        variant=m,
                        sequence_disruption=sequence_disruption,
                        min_delta=best["min_delta"],
                        exon_delta=best["exon_delta"],
                        calibrated_seq_percentile=percentile_like(sequence_disruption),
                        impact_level=classify_impact_level(sequence_disruption),
                        scoring_mode="evo2_adaptive",
                        best_model=best["model"],
                        best_window_bp=best["best_window_bp"],
                        scoring_strategy={
                            "approach": "evo2_adaptive_windows",
                            "models_tested": model_candidates,
                            "windows_tested": best["windows_tested"]
                        },
                        forward_reverse_meta=best["forward_reverse_meta"]
                    )
                    seq_scores.append(seq_score)
                    
                    # Cache the result
                    cache_key = self._get_cache_key(m, model_id, window_flanks, ensemble)
                    await set_cache(cache_key, seq_score.__dict__, ttl=3600)
        
        # Combine cached and newly computed results
        return cached_results + seq_scores
    
    async def _score_variant_adaptive(self, client: httpx.AsyncClient, chrom: str, pos: int, 
                                    ref: str, alt: str, model_id: str, 
                                    window_flanks: List[int]) -> Dict[str, Any]:
        """Probe multiple exon flanks and return best exon_delta."""
        # Multi-window (model default) for min_delta
        j_multi = {}
        try:
            multi = await client.post(
                f"{self.api_base}/api/evo/score_variant_multi",
                json={
                    "assembly": "GRCh38", 
                    "chrom": chrom, 
                    "pos": pos, 
                    "ref": ref, 
                    "alt": alt, 
                    "model_id": model_id
                },
                headers={"Content-Type": "application/json"}
            )
            if multi.status_code < 400:
                j_multi = multi.json() or {}
        except Exception:
            j_multi = {}
        
        # Spam-safe: if delta-only mode is enabled, skip exon loop entirely
        try:
            feature_flags = get_feature_flags()
            if feature_flags.get("evo_use_delta_only", False):
                return {
                    "min_delta": (j_multi or {}).get("min_delta"),
                    "exon_delta": None,
                    "best_window_bp": None,
                    "windows_tested": [],
                }
        except Exception:
            pass
        
        # Exon windows
        best_exon_delta = None
        best_flank = None
        tested = []
        
        for flank in window_flanks:
            try:
                exon = await client.post(
                    f"{self.api_base}/api/evo/score_variant_exon",
                    json={
                        "assembly": "GRCh38", 
                        "chrom": chrom, 
                        "pos": pos, 
                        "ref": ref, 
                        "alt": alt, 
                        "flank": int(flank), 
                        "model_id": model_id
                    },
                    headers={"Content-Type": "application/json"}
                )
                j_exon = exon.json() if exon.status_code < 400 else {}
                ex_delta = (j_exon or {}).get("exon_delta")
                tested.append({"flank": int(flank), "exon_delta": ex_delta})
                
                if ex_delta is not None:
                    if (best_exon_delta is None or 
                        abs(float(ex_delta)) > abs(float(best_exon_delta))):
                        best_exon_delta = ex_delta
                        best_flank = int(flank)
            except Exception:
                tested.append({"flank": int(flank), "error": True})
                continue
        
        return {
            "min_delta": (j_multi or {}).get("min_delta"),
            "exon_delta": best_exon_delta,
            "best_window_bp": int(best_flank or 0) * 2 if best_flank else None,
            "windows_tested": tested,
        }
    
    async def _score_variant_with_symmetry(self, client: httpx.AsyncClient, chrom: str, 
                                         pos: int, ref: str, alt: str, model_id: str, 
                                         window_flanks: List[int]) -> Dict[str, Any]:
        """Score variant with forward/reverse averaging for symmetry."""
        # Score forward direction (ref > alt)
        forward_result = await self._score_variant_adaptive(
            client, chrom, pos, ref, alt, model_id, window_flanks
        )
        
        # Score reverse direction (alt > ref) for symmetry
        try:
            feature_flags = get_feature_flags()
            if feature_flags.get("evo_disable_symmetry", True):
                reverse_result = {
                    "min_delta": 0.0, 
                    "exon_delta": 0.0, 
                    "best_window_bp": forward_result.get("best_window_bp"), 
                    "windows_tested": forward_result.get("windows_tested", [])
                }
            else:
                reverse_result = await self._score_variant_adaptive(
                    client, chrom, pos, alt, ref, model_id, window_flanks
                )
        except Exception:
            reverse_result = {
                "min_delta": 0.0, 
                "exon_delta": 0.0, 
                "best_window_bp": forward_result.get("best_window_bp"), 
                "windows_tested": forward_result.get("windows_tested", [])
            }
        
        # Average the delta scores for symmetry
        forward_min = forward_result.get("min_delta") or 0.0
        reverse_min = reverse_result.get("min_delta") or 0.0
        avg_min_delta = (forward_min + reverse_min) / 2.0
        
        forward_exon = forward_result.get("exon_delta") or 0.0
        reverse_exon = reverse_result.get("exon_delta") or 0.0
        avg_exon_delta = (forward_exon + reverse_exon) / 2.0
        
        # Use the best window from either direction
        best_window_bp = (forward_result.get("best_window_bp") or 
                         reverse_result.get("best_window_bp"))
        
        return {
            "min_delta": avg_min_delta,
            "exon_delta": avg_exon_delta,
            "best_window_bp": best_window_bp,
            "windows_tested": forward_result.get("windows_tested", []),
            "forward_reverse_meta": {
                "forward_min": forward_min,
                "reverse_min": reverse_min,
                "forward_exon": forward_exon,
                "reverse_exon": reverse_exon,
                "symmetry_enabled": True
            }
        }

