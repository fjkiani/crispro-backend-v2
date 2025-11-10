"""
Evo2 model proxy endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import httpx
import os
import hashlib
import time

from ..config import EVO_URL_7B, EVO_URL_40B, EVO_URL_1B, get_feature_flags, get_model_url
DEFAULT_EVO_MODEL = os.getenv("DEFAULT_EVO_MODEL", "evo2_1b")
# Optional hard guard to force a single model (e.g., evo2_1b)
FORCE_MODEL_ID = os.getenv("EVO_FORCE_MODEL", "").strip().lower()

# Simple in-memory cache to prevent duplicate calls
_evo_cache: Dict[str, Any] = {}
_cache_ttl = 300  # 5 minutes

def _get_cache_key(chrom: str, pos: int, ref: str, alt: str, model_id: str, endpoint: str) -> str:
    """Generate cache key for variant scoring requests."""
    key_data = f"{endpoint}:{model_id}:{chrom}:{pos}:{ref}:{alt}"
    return hashlib.md5(key_data.encode()).hexdigest()

def _get_cached_result(cache_key: str) -> Any:
    """Get cached result if still valid."""
    if cache_key in _evo_cache:
        result, timestamp = _evo_cache[cache_key]
        if time.time() - timestamp < _cache_ttl:
            return result
        else:
            del _evo_cache[cache_key]
    return None

def _cache_result(cache_key: str, result: Any) -> None:
    """Cache a result with timestamp."""
    _evo_cache[cache_key] = (result, time.time())

router = APIRouter(prefix="/api/evo", tags=["evo"])

# Helper to resolve effective model id honoring EVO_FORCE_MODEL
def _effective_model_id(request_model_id: str) -> str:
    try:
        if FORCE_MODEL_ID:
            return FORCE_MODEL_ID
        return (request_model_id or DEFAULT_EVO_MODEL).lower()
    except Exception:
        return (FORCE_MODEL_ID or DEFAULT_EVO_MODEL).lower()

# --- Helpers: coordinate→sequence mapping for upstream /score_delta ---
async def _fetch_reference_window(assembly: str, chrom: str, start: int, end: int) -> str:
    asm = "GRCh38" if str(assembly).lower() in ("grch38","hg38") else "GRCh37"
    region = f"{chrom}:{start}-{end}:1"
    url = f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}"
    async with httpx.AsyncClient(timeout=20.0) as client:
        r = await client.get(url)
        r.raise_for_status()
        return (r.text or "").strip().upper()

def _assemble_ref_alt(window_seq: str, pos: int, window_start: int, ref: str, alt: str) -> Dict[str, str]:
    if not window_seq:
        raise ValueError("empty reference window")
    idx = int(pos) - int(window_start)  # 0-based offset within window
    if idx < 0 or idx >= len(window_seq):
        raise ValueError("variant position outside reference window")
    base_at_pos = window_seq[idx]
    # Accept 'N' or mismatch; prefer not to crash but annotate
    ref_seq = window_seq
    alt_seq = window_seq[:idx] + str(alt or "").upper() + window_seq[idx+1:]
    return {"ref_sequence": ref_seq, "alt_sequence": alt_seq, "observed_ref": base_at_pos}

async def _score_delta_with_flanks(
    base_url: str,
    model_id: str,
    assembly: str,
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    flanks: List[int],
    debug: bool = False,
):
    attempts_info = []
    headers = {"Content-Type": "application/json", "Accept": "application/json"}

    def _revcomp(seq: str) -> str:
        table = str.maketrans("ACGTNacgtn", "TGCANtgcan")
        return (seq or "").translate(table)[::-1]

    # Spam-safety: cap number of flanks and optionally disable reverse-complement retries
    try:
        ff = get_feature_flags()
        max_flanks = int(ff.get("evo_max_flanks", 1))
        disable_rc = bool(ff.get("evo_disable_symmetry", True))
    except Exception:
        max_flanks = 1
        disable_rc = True
    capped_flanks = (flanks or [])[:max_flanks]

    async with httpx.AsyncClient(timeout=180.0) as client:
        for flank in capped_flanks:
            start = max(1, pos - flank)
            end = pos + flank
            try:
                window = await _fetch_reference_window(assembly, chrom, start, end)
                seqs = _assemble_ref_alt(window, pos, start, ref, alt)
                # Provide multiple alias keys to satisfy upstream schema variants
                payload = {
                    "ref_sequence": seqs["ref_sequence"],
                    "alt_sequence": seqs["alt_sequence"],
                    "reference_sequence": seqs["ref_sequence"],
                    "alternate_sequence": seqs["alt_sequence"],
                    "model_id": model_id,
                    "task": "score_delta",
                }
                r = await client.post(f"{base_url}/score_delta", json=payload, headers=headers)
                status = r.status_code
                body_text = r.text[:500] if r.text else ""
                try:
                    js = r.json() or {}
                except Exception:
                    js = {}
                # extract candidate delta fields (include delta_score used by upstream)
                delta = None
                for key in ("delta","min_delta","exon_delta","score","delta_score"):
                    if key in js:
                        try:
                            delta = float(js.get(key))
                            break
                        except Exception:
                            pass
                attempts_info.append({"flank": flank, "status": status, "has_json": bool(js), "delta": delta, "body": body_text if debug else None})
                if status < 400 and delta is not None:
                    return {"ok": True, "delta": delta, "flank": flank, "upstream": (js if debug else None), "attempts": attempts_info if debug else None}

                # Try reverse-complement sequences if allowed and first attempt produced no usable delta
                if not disable_rc:
                    try:
                        rc_ref = _revcomp(seqs["ref_sequence"]) ; rc_alt = _revcomp(seqs["alt_sequence"])
                        rc_payload = {
                            "ref_sequence": rc_ref,
                            "alt_sequence": rc_alt,
                            "reference_sequence": rc_ref,
                            "alternate_sequence": rc_alt,
                            "model_id": model_id,
                            "task": "score_delta",
                        }
                        rr = await client.post(f"{base_url}/score_delta", json=rc_payload, headers=headers)
                        rc_status = rr.status_code
                        rc_body = rr.text[:500] if rr.text else ""
                        try:
                            rj = rr.json() or {}
                        except Exception:
                            rj = {}
                        rc_delta = None
                        for key in ("delta","min_delta","exon_delta","score","delta_score"):
                            if key in rj:
                                try:
                                    rc_delta = float(rj.get(key))
                                    break
                                except Exception:
                                    pass
                        attempts_info.append({"flank": flank, "rc": True, "status": rc_status, "has_json": bool(rj), "delta": rc_delta, "body": rc_body if debug else None})
                        if rc_status < 400 and rc_delta is not None:
                            return {"ok": True, "delta": rc_delta, "flank": flank, "upstream": (rj if debug else None), "attempts": attempts_info if debug else None}
                    except Exception as ee:
                        attempts_info.append({"flank": flank, "rc": True, "error": str(ee)})
            except Exception as e:
                attempts_info.append({"flank": flank, "error": str(e)})
                continue
    return {"ok": False, "attempts": attempts_info}

@router.post("/warmup")
async def warmup_evo_model(request: Dict[str, Any]):
    """Warmup an Evo2 model.
    Input: { model_id: "evo2_1b" | "evo2_7b" | "evo2_40b" }
    """
    try:
        model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
        
        # Use the new get_model_url function with fallback logic
        target_url = get_model_url(model_id)
        
        if not target_url:
            raise HTTPException(status_code=503, detail=f"No Evo service URL configured for {model_id}")
        
        async def _try_warmup(base_url: str, model_choice: str) -> Dict[str, Any]:
            attempts = []
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                # Prefer /score_delta as warmup
                try:
                    payload = {"ref_sequence": "AAAAAA", "alt_sequence": "AAACAA", "model_id": model_choice}
                    r = await client.post(f"{base_url}/score_delta", json=payload, headers={"Content-Type": "application/json"})
                    if r.status_code < 400:
                        js = r.json() if (r.headers.get("content-type") or "").startswith("application/json") else {"message": r.text}
                        return {"ok": True, "path": "/score_delta", "response": js}
                    attempts.append({"path": "/score_delta", "status": r.status_code, "body": r.text})
                except Exception as e:
                    attempts.append({"path": "/score_delta", "error": str(e)})
                # Fallback to /score minimal
                try:
                    payload = {"sequence": "AAAAAA", "model_id": model_choice}
                    r = await client.post(f"{base_url}/score", json=payload, headers={"Content-Type": "application/json"})
                    if r.status_code < 400:
                        js = r.json() if (r.headers.get("content-type") or "").startswith("application/json") else {"message": r.text}
                        return {"ok": True, "path": "/score", "response": js}
                    attempts.append({"path": "/score", "status": r.status_code, "body": r.text})
                except Exception as e:
                    attempts.append({"path": "/score", "error": str(e)})
            return {"ok": False, "attempts": attempts}
        
        # Try requested model
        result = await _try_warmup(target_url, model_id)
        if result.get("ok"):
            out = {"status": "warmed", "model": model_id, "via": result.get("path")}
            if result.get("response"):
                out["response"] = result["response"]
            return out
        
        # Fallback to 40B if 1B/7B fail
        if model_id in ["evo2_1b", "evo2_7b"] and EVO_URL_40B:
            fb = await _try_warmup(EVO_URL_40B, "evo2_40b")
            if fb.get("ok"):
                out = {"status": "warmed", "model": "evo2_40b", "via": fb.get("path"), "warning": f"Requested {model_id} unavailable, fell back to evo2_40b"}
                if fb.get("response"):
                    out["response"] = fb["response"]
                return out
        
        # Nothing worked: return 502 with details
        detail = {"error": "All warmup attempts failed", "model": model_id, "requested_attempts": result.get("attempts")}
        raise HTTPException(status_code=502, detail=detail)
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evo warmup failed: {str(e)}")

@router.post("/score")
async def score_variant(request: Dict[str, Any]):
    """Score a variant using Evo2.
    Input: { sequence: str, model_id?: "evo2_1b" | "evo2_7b" | "evo2_40b" }
    """
    try:
        model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
        
        # Use the new get_model_url function with fallback logic
        target_url = get_model_url(model_id)
        
        if not target_url:
            raise HTTPException(status_code=503, detail=f"No Evo service URL configured for {model_id}")
        
        # Try to score with the requested model
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(
                    f"{target_url}/score",
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            # If 1B or 7B fails, try falling back to 40B
            if model_id in ["evo2_1b", "evo2_7b"] and EVO_URL_40B:
                try:
                    fallback_request = {**request, "model_id": "evo2_40b"}
                    async with httpx.AsyncClient(timeout=120.0) as client:
                        response = await client.post(
                            f"{EVO_URL_40B}/score",
                            json=fallback_request,
                            headers={"Content-Type": "application/json"}
                        )
                        response.raise_for_status()
                        result = response.json()
                        # Add a warning about the fallback
                        result["warning"] = f"Requested {model_id} failed, fell back to evo2_40b"
                        result["actual_model"] = "evo2_40b"
                        return result
                except Exception:
                    pass
            
            # If all else fails, raise the original error
            if isinstance(e, httpx.HTTPStatusError):
                raise HTTPException(status_code=e.response.status_code, detail=f"Evo service error: {e.response.text}")
            else:
                raise HTTPException(status_code=503, detail=f"Failed to connect to Evo service: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evo score failed: {str(e)}")

@router.post("/generate")
async def generate_sequence(request: Dict[str, Any]):
    """Generate sequence using Evo2.
    Input: { prompt: str, max_tokens?: int, model_id?: "evo2_1b" | "evo2_7b" | "evo2_40b" }
    """
    try:
        # Basic safety gate: block viral content prompts
        try:
            text = (request.get("prompt") or "") + " " + (request.get("sequence") or "")
            up = str(text).upper()
            for forbidden in ["HIV","SARS","EBOLA","INFLUENZA"]:
                if forbidden in up:
                    raise HTTPException(status_code=400, detail="forbidden content in request")
        except HTTPException:
            raise
        except Exception:
            pass
        model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
        
        # Use the new get_model_url function with fallback logic
        target_url = get_model_url(model_id)
        
        if not target_url:
            raise HTTPException(status_code=503, detail=f"No Evo service URL configured for {model_id}")
        
        # Try to generate with the requested model
        try:
            async with httpx.AsyncClient(timeout=180.0) as client:
                response = await client.post(
                    f"{target_url}/generate",
                    json=request,
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()
        
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            # If 1B or 7B fails, try falling back to 40B
            if model_id in ["evo2_1b", "evo2_7b"] and EVO_URL_40B:
                try:
                    fallback_request = {**request, "model_id": "evo2_40b"}
                    async with httpx.AsyncClient(timeout=180.0) as client:
                        response = await client.post(
                            f"{EVO_URL_40B}/generate",
                            json=fallback_request,
                            headers={"Content-Type": "application/json"}
                        )
                        response.raise_for_status()
                        result = response.json()
                        # Add a warning about the fallback
                        result["warning"] = f"Requested {model_id} failed, fell back to evo2_40b"
                        result["actual_model"] = "evo2_40b"
                        return result
                except Exception:
                    pass
            
            # If all else fails, raise the original error
            if isinstance(e, httpx.HTTPStatusError):
                raise HTTPException(status_code=e.response.status_code, detail=f"Evo service error: {e.response.text}")
            else:
                raise HTTPException(status_code=503, detail=f"Failed to connect to Evo service: {str(e)}")
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evo generate failed: {str(e)}")

@router.get("/health")
async def evo_health():
    """Check health of Evo2 services."""
    try:
        results = {}
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Check 1B model
            if EVO_URL_1B:
                try:
                    response = await client.get(f"{EVO_URL_1B}/health")
                    results["evo2_1b"] = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "url": EVO_URL_1B,
                        "response": response.json() if response.status_code == 200 else response.text
                    }
                except Exception as e:
                    results["evo2_1b"] = {
                        "status": "error",
                        "url": EVO_URL_1B,
                        "error": str(e)
                    }
            else:
                results["evo2_1b"] = {
                    "status": "not_configured",
                    "url": None
                }
            
            # Check 7B model
            if EVO_URL_7B:
                try:
                    response = await client.get(f"{EVO_URL_7B}/health")
                    results["evo2_7b"] = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "url": EVO_URL_7B,
                        "response": response.json() if response.status_code == 200 else response.text
                    }
                except Exception as e:
                    results["evo2_7b"] = {
                        "status": "error",
                        "url": EVO_URL_7B,
                        "error": str(e)
                    }
            else:
                results["evo2_7b"] = {
                    "status": "not_configured",
                    "url": None
                }
            
            # Check 40B model
            if EVO_URL_40B:
                try:
                    response = await client.get(f"{EVO_URL_40B}/health")
                    results["evo2_40b"] = {
                        "status": "healthy" if response.status_code == 200 else "unhealthy",
                        "url": EVO_URL_40B,
                        "response": response.json() if response.status_code == 200 else response.text
                    }
                except Exception as e:
                    results["evo2_40b"] = {
                        "status": "error",
                        "url": EVO_URL_40B,
                        "error": str(e)
                    }
            else:
                results["evo2_40b"] = {
                    "status": "not_configured",
                    "url": None
                }
        
        return {
            "service": "evo_proxy",
            "status": "operational",
            "models": results,
            "fallback_info": "1B and 7B models will fallback to 40B if unavailable"
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Evo health check failed: {str(e)}") 

@router.post("/score_variant_multi")
async def score_variant_multi(request: Dict[str, Any]):
    try:
        # Delta-only fast path to avoid upstream multi endpoint when configured
        try:
            if get_feature_flags().get("evo_use_delta_only", False):
                chrom = str(request.get("chrom"))
                pos = int(request.get("pos"))
                ref = str(request.get("ref", "")).upper()
                alt = str(request.get("alt", "")).upper()
                model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
                base = get_model_url(model_id)
                res = await _score_delta_with_flanks(base, model_id, request.get("assembly", "GRCh38"), chrom, pos, ref, alt, [4096,8192,12500,16384], debug=False)
                if res.get("ok"):
                    return {"min_delta": float(res.get("delta") or 0.0), "provenance": {"method": "delta_only", "model": model_id, "flank": res.get("flank")}}
        except Exception:
            pass
        model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
        chrom = str(request.get("chrom"))
        pos = int(request.get("pos"))
        ref = str(request.get("ref", "")).upper()
        alt = str(request.get("alt", "")).upper()
        
        # Check cache first
        cache_key = _get_cache_key(chrom, pos, ref, alt, model_id, "score_variant_multi")
        cached = _get_cached_result(cache_key)
        if cached is not None:
            return cached
        
        base = get_model_url(model_id)
        if not base:
            raise HTTPException(status_code=503, detail=f"Evo service URL not configured for {model_id}")
        
        payload = {
            "assembly": request.get("assembly", "GRCh38"),
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "model_id": model_id,
        }
        
        async with httpx.AsyncClient(timeout=60.0, verify=False, follow_redirects=True) as client:
            try:
                r = await client.post(f"{base}/score_variant_multi", json=payload, headers={"Content-Type": "application/json"})
                if r.status_code < 400:
                    js = r.json() or {}
                    md = js.get("min_delta")
                    try:
                        md = float(md) if md is not None else None
                    except Exception:
                        md = None
                    if md is not None:
                        result = {"min_delta": md, "provenance": {"method": "upstream_score_variant_multi", "model": model_id, "window_used": js.get("window_used"), "deltas": js.get("deltas")}}
                        _cache_result(cache_key, result)
                        return result
                    # If shape differs, attempt to map common keys
                    for k in ("delta","delta_score"):
                        if k in js:
                            try:
                                result = {"min_delta": float(js[k]), "provenance": {"method": "upstream_score_variant_multi_alt", "model": model_id}}
                                _cache_result(cache_key, result)
                                return result
                            except Exception:
                                pass
            except Exception:
                pass
        # Fallback to /score_delta mapping with multi-flank attempts
        assembly = payload["assembly"] ; chrom = payload["chrom"] ; pos = payload["pos"] ; ref = payload["ref"] ; alt = payload["alt"]
        try:
            ff = get_feature_flags()
            max_flanks = int(ff.get("evo_max_flanks", 1))
        except Exception:
            max_flanks = 1
        res = await _score_delta_with_flanks(base, model_id, assembly, chrom, pos, ref, alt, [4096,8192,12500,16384][:max_flanks], debug=False)
        if res.get("ok"):
            result = {"min_delta": float(res.get("delta") or 0.0), "provenance": {"method": "mapped_score_delta", "model": model_id, "flank": res.get("flank")}}
            _cache_result(cache_key, result)
            return result
        
        result = {"min_delta": 0.0, "provenance": {"fallback": "no_signal", "model": model_id}}
        _cache_result(cache_key, result)
        return result
    except httpx.HTTPStatusError as e:
        result = {"min_delta": 0.0, "provenance": {"fallback": "http_status_error", "status": getattr(e.response, 'status_code', None)}}
        _cache_result(cache_key, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"score_variant_multi failed: {e}")

@router.post("/score_variant_exon")
async def score_variant_exon(request: Dict[str, Any]):
    try:
        # Delta-only fast path to avoid upstream exon endpoint when configured
        try:
            if get_feature_flags().get("evo_use_delta_only", False):
                model_id = _effective_model_id(request.get("model_id", DEFAULT_EVO_MODEL))
                chrom = str(request.get("chrom"))
                pos = int(request.get("pos"))
                ref = str(request.get("ref", "")).upper()
                alt = str(request.get("alt", "")).upper()
                flank = int(request.get("flank", 4096))
                base = get_model_url(model_id)
                res = await _score_delta_with_flanks(base, model_id, request.get("assembly", "GRCh38"), chrom, pos, ref, alt, [flank,8192,12500,16384], debug=False)
                if res.get("ok"):
                    return {"exon_delta": float(res.get("delta") or 0.0), "provenance": {"method": "delta_only", "model": model_id, "flank": res.get("flank")}}
        except Exception:
            pass
        model_id = request.get("model_id", DEFAULT_EVO_MODEL)
        chrom = str(request.get("chrom"))
        pos = int(request.get("pos"))
        ref = str(request.get("ref", "")).upper()
        alt = str(request.get("alt", "")).upper()
        flank = int(request.get("flank", 4096))
        
        # Check cache first (include flank in cache key)
        cache_key = _get_cache_key(chrom, pos, ref, alt, f"{model_id}_{flank}", "score_variant_exon")
        cached = _get_cached_result(cache_key)
        if cached is not None:
            return cached
        
        base = get_model_url(model_id)
        if not base:
            raise HTTPException(status_code=503, detail=f"Evo service URL not configured for {model_id}")
        
        payload = {
            "assembly": request.get("assembly", "GRCh38"),
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "flank": flank,
            "model_id": model_id,
        }
        async with httpx.AsyncClient(timeout=60.0, verify=False, follow_redirects=True) as client:
            try:
                r = await client.post(f"{base}/score_variant_exon", json=payload, headers={"Content-Type": "application/json"})
                if r.status_code < 400:
                    js = r.json() or {}
                    ed = js.get("exon_delta")
                    try:
                        ed = float(ed) if ed is not None else None
                    except Exception:
                        ed = None
                    if ed is not None:
                        result = {"exon_delta": ed, "provenance": {"method": "upstream_score_variant_exon", "model": model_id}}
                        _cache_result(cache_key, result)
                        return result
                    for k in ("delta","delta_score"):
                        if k in js:
                            try:
                                result = {"exon_delta": float(js[k]), "provenance": {"method": "upstream_score_variant_exon_alt", "model": model_id}}
                                _cache_result(cache_key, result)
                                return result
                            except Exception:
                                pass
            except Exception:
                pass
        # Fallback to mapped /score_delta multi-flank attempts
        try:
            ff = get_feature_flags()
            max_flanks = int(ff.get("evo_max_flanks", 1))
        except Exception:
            max_flanks = 1
        res = await _score_delta_with_flanks(base, model_id, payload["assembly"], payload["chrom"], payload["pos"], payload["ref"], payload["alt"], [payload["flank"],8192,12500,16384][:max_flanks], debug=False)
        if res.get("ok"):
            result = {"exon_delta": float(res.get("delta") or 0.0), "provenance": {"method": "mapped_score_delta", "model": model_id, "flank": res.get("flank")}}
            _cache_result(cache_key, result)
            return result
        
        result = {"exon_delta": 0.0, "provenance": {"fallback": "no_signal", "model": model_id}}
        _cache_result(cache_key, result)
        return result
    except httpx.HTTPStatusError as e:
        result = {"exon_delta": 0.0, "provenance": {"fallback": "http_status_error", "status": getattr(e.response, 'status_code', None)}}
        _cache_result(cache_key, result)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"score_variant_exon failed: {e}")

@router.post("/score_variant_profile")
async def score_variant_profile(request: Dict[str, Any]):
    try:
        # Fast guard: if coords are missing, skip upstream call and return empty profile
        chrom = request.get("chrom")
        pos = request.get("pos")
        ref = request.get("ref")
        alt = request.get("alt")
        if not (chrom and pos and ref and alt):
            return {"profiles": [], "provenance": {"fallback": "missing_coords"}}

        model_id = request.get("model_id", os.getenv("DEFAULT_EVO_MODEL", DEFAULT_EVO_MODEL))
        base = get_model_url(model_id)
        if not base:
            raise HTTPException(status_code=503, detail=f"Evo service URL not configured for {model_id}")
        async with httpx.AsyncClient(timeout=20.0) as client:
            try:
                r = await client.post(f"{base}/score_variant_profile", json=request, headers={"Content-Type": "application/json"})
                if r.status_code < 400:
                    return r.json()
                return {"profiles": [], "provenance": {"fallback": "upstream_error", "status": r.status_code}}
            except Exception as e:
                return {"profiles": [], "provenance": {"fallback": "exception", "error": str(e)}}
    except httpx.HTTPStatusError as e:
        return {"profiles": [], "provenance": {"fallback": "http_status_error", "status": getattr(e.response, 'status_code', None)}}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"score_variant_profile failed: {e}")

@router.post("/score_variant_probe")
async def score_variant_probe(request: Dict[str, Any]):
    try:
        model_id = request.get("model_id", DEFAULT_EVO_MODEL)
        base = get_model_url(model_id)
        if not base:
            raise HTTPException(status_code=503, detail=f"Evo service URL not configured for {model_id}")
        async with httpx.AsyncClient(timeout=120.0) as client:
            r = await client.post(f"{base}/score_variant_probe", json=request, headers={"Content-Type": "application/json"})
            r.raise_for_status()
            return r.json()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=e.response.text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"score_variant_probe failed: {e}")

@router.post("/score_batch")
async def score_batch(request: Dict[str, Any]):
    """Batch delta scoring. Fallback to per-pair if upstream lacks /score_batch."""
    try:
        model_id = request.get("model_id", DEFAULT_EVO_MODEL)
        base = get_model_url(model_id)
        pairs = request.get("pairs") or []
        if not base:
            raise HTTPException(status_code=503, detail=f"Evo service URL not configured for {model_id}")
        async with httpx.AsyncClient(timeout=180.0) as client:
            try:
                r = await client.post(f"{base}/score_batch", json=request, headers={"Content-Type": "application/json"})
                if r.status_code < 400:
                    return r.json()
            except Exception:
                pass
            # Fallback: loop pairs with /score_delta
            results = []
            for p in pairs:
                try:
                    rr = await client.post(f"{base}/score_delta", json=p, headers={"Content-Type": "application/json"})
                    if rr.status_code < 400:
                        results.append(rr.json())
                    else:
                        results.append({"error": rr.text})
                except Exception as ee:
                    results.append({"error": str(ee)})
            return {"results": results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"score_batch failed: {e}") 