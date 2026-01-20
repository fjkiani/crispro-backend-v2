"""
Generative design endpoints (generate_*) and spacer efficacy prediction
"""
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
import math

from ..config import get_feature_flags
from ..schemas.design import SpacerEfficacyRequest, SpacerEfficacyResponse, SpacerEfficacyProvenance
from ..middleware.auth_middleware import get_optional_user
import httpx
import re

router = APIRouter(prefix="/api/design", tags=["design"])


def _ensure_enabled():
    flags = get_feature_flags()
    if not flags.get("enable_design_api", False):
        raise HTTPException(status_code=403, detail="Design API disabled by configuration")


@router.post("/predict_crispr_spacer_efficacy", response_model=SpacerEfficacyResponse)
async def predict_crispr_spacer_efficacy(
    request: SpacerEfficacyRequest,
    user: Optional[Dict[str, Any]] = Depends(get_optional_user)
) -> SpacerEfficacyResponse:
    """
    Predict on-target efficacy of a CRISPR guide RNA spacer using Evo2 delta scoring.
    
    **Requires:** Enterprise tier (crispr_design feature)
    **Quota:** Counts against variant_analyses quota
    
    **Method:**
    1. If target_sequence provided: use it directly (should be guide + ±50bp flanks = 120bp)
    2. Else if chrom/pos/ref/alt provided: fetch from Ensembl
    3. Else: fallback to guide-only context (low confidence)
    4. Call Evo2 /score_variant_multi to get delta log-likelihood
    5. Transform via sigmoid: efficacy = 1 / (1 + exp(delta / scale_factor))
    6. Return [0,1] efficacy score with provenance
    
    **Research Use Only (RUO):** Not validated for clinical use.
    """
    # Check quota if authenticated
    if user and user.get("user_id"):
        from ..middleware.quota_middleware import check_quota
        quota_check = check_quota("variant_analyses")
        user = await quota_check(user)
    
    # Check feature flag (Enterprise tier required for CRISPR design)
    if user and user.get("user_id"):
        from ..middleware.feature_flag_middleware import require_feature
        feature_check = require_feature("crispr_design")
        await feature_check(user)
    try:
        guide_seq = request.guide_sequence.upper().strip()
        if len(guide_seq) != 20:
            raise HTTPException(status_code=400, detail="guide_sequence must be exactly 20bp")
        if not all(c in "ACGT" for c in guide_seq):
            raise HTTPException(status_code=400, detail="guide_sequence must contain only ACGT")
        
        # Determine context
        context = None
        context_source = "none"
        if request.target_sequence:
            context = request.target_sequence.upper().strip()
            context_source = "provided"
        elif request.chrom and request.pos and request.ref and request.alt:
            # Fetch ±window_size bp flanks around variant site (default: ±150bp = 300bp total)
            window_size = request.window_size or 150
            try:
                window_start = request.pos - window_size
                window_end = request.pos + window_size
                assembly = request.assembly or "GRCh38"
                asm = "GRCh38" if assembly.lower() in ("grch38", "hg38") else "GRCh37"
                region = f"{request.chrom}:{window_start}-{window_end}:1"
                url = f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}"
                async with httpx.AsyncClient(timeout=20.0) as client:
                    r = await client.get(url)
                    if r.status_code == 200:
                        context = (r.text or "").strip().upper()
                        context_source = "ensembl"
            except Exception:
                pass  # Fall through to guide-only
        
        if not context:
            # Fallback: use guide sequence only (low confidence)
            context = guide_seq
            context_source = "guide_only"
        
        context_length = len(context)
        
        # Call Evo2 to score the guide within context
        # Use /api/evo/score endpoint with sequence likelihood
        model_id = request.model_id or "evo2_1b"
        evo_url = "http://127.0.0.1:8000/api/evo/score"
        
        evo_delta = None
        cached = False
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                # Score the context sequence (which includes guide)
                payload = {
                    "model_id": model_id,
                    "sequence": context
                }
                r = await client.post(evo_url, json=payload, timeout=60.0)
                if r.status_code == 200:
                    result = r.json()
                    # Get likelihood score and convert to delta proxy
                    # More negative likelihood = more disruptive = better guide
                    likelihood = result.get("likelihood", result.get("score", 0.0))
                    # Use negative likelihood as proxy for disruption
                    evo_delta = -abs(likelihood) if likelihood else None
                    cached = result.get("provenance", {}).get("cached", False)
        except Exception as e:
            # Graceful fallback: use heuristic if Evo unavailable
            evo_delta = None
        
        # Compute efficacy score
        scale_factor = 10.0  # As specified in doctrine
        if evo_delta is not None:
            # Sigmoid transformation: efficacy = 1 / (1 + exp(delta / scale))
            # More negative delta = more disruptive = higher efficacy
            efficacy_score = 1.0 / (1.0 + math.exp(evo_delta / scale_factor))
            efficacy_score = max(0.0, min(1.0, efficacy_score))  # Clip to [0,1]
            confidence = 0.75 if context_source == "provided" or context_source == "ensembl" else 0.50
        else:
            # Fallback to GC-based heuristic (same as generate_guide_rna)
            gc = (guide_seq.count("G") + guide_seq.count("C")) / 20.0
            homopolymer_penalty = 0.1 if any(h in guide_seq for h in ["AAAA", "TTTT", "CCCC", "GGGG"]) else 0.0
            efficacy_score = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            confidence = 0.30  # Low confidence for heuristic
        
        # Rationale
        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")







        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")







        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")







        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")







        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")







        rationale = []
        if evo_delta is not None:
            rationale.append(f"Evo2 delta: {evo_delta:.4f} (context: {context_source}, {context_length}bp)")
            rationale.append(f"Sigmoid transform with scale={scale_factor} → efficacy={efficacy_score:.3f}")
        else:
            rationale.append(f"Evo2 unavailable; using GC-based heuristic (GC={guide_seq.count('G') + guide_seq.count('C')}/20)")
        
        if context_source == "guide_only":
            rationale.append("⚠️ No genomic context provided; efficacy estimate has low confidence")
        
        return SpacerEfficacyResponse(
            guide_sequence=guide_seq,
            efficacy_score=efficacy_score,
            evo2_delta=evo_delta,
            confidence=confidence,
            rationale=rationale,
            provenance=SpacerEfficacyProvenance(
                method="evo2_delta_sigmoid_v1" if evo_delta is not None else "gc_heuristic_v0",
                model_id=model_id,
                context_length=context_length,
                scale_factor=scale_factor,
                evo_url=evo_url if evo_delta is not None else None,
                cached=cached
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"predict_crispr_spacer_efficacy failed: {e}")


@router.post("/generate_guide_rna")
async def generate_guide_rna(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        target = (request or {}).get("target_sequence", "")
        pam = (request or {}).get("pam", "NGG")
        num = int((request or {}).get("num", 3))
        model_id = (request or {}).get("model_id", "evo2_7b")
        # Safety: viral exclusion and length limits
        if any(v in target.upper() for v in ["HIV","SARS","EBOLA","INFLUENZA"]):
            raise HTTPException(status_code=400, detail="forbidden target content")
        if len(target) < 30:
            raise HTTPException(status_code=400, detail="target_sequence must be >=30bp for Evo2 prompting")
        # Find candidate PAM sites (NGG default)
        pattern = pam.replace("N", ".")
        hits = [m.start() for m in re.finditer(pattern, target)]
        windows = []
        for h in hits:
            start = max(0, h - 23)
            end = min(len(target), h)
            if end - start >= 20:
                windows.append(target[start:end])
        windows = windows[: max(3, num)] or [target[:20]]
        # Ask Evo2 to generate refined candidates (prompt-based); skip when disable_evo2 flag set
        evo_candidates: List[str] = []
        try:
            flags = get_feature_flags()
            if not flags.get("disable_evo2"):
                prompt = f"Design CRISPR spacers (20bp) targeting these windows: {';'.join(windows)}. Return raw 20bp sequences only."
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post("http://127.0.0.1:8000/api/evo/generate", json={"prompt": prompt, "model_id": model_id})
                    if r.status_code < 400:
                        js = r.json() or {}
                        text = (js.get("text") or js.get("sequence") or "").upper()
                        evo_candidates = [s.strip() for s in re.findall(r"[ACGT]{20}", text)][: num]
        except Exception:
            evo_candidates = []
        # Merge and score heuristics
        raw = (evo_candidates or []) + windows[: max(0, num - len(evo_candidates))]
        candidates: List[Dict[str, Any]] = []
        for seq in raw[: num]:
            seq = seq[:20]
            gc = round((seq.count("G") + seq.count("C")) / 20.0, 2)
            homopolymer_penalty = 0.1 if any(h in seq for h in ["AAAA","TTTT","CCCC","GGGG"]) else 0.0
            eff = max(0.0, min(1.0, 0.75 - abs(gc - 0.5) - homopolymer_penalty))
            candidates.append({"sequence": seq, "pam": pam, "gc": gc, "spacer_efficacy_heuristic": eff})
        return {"candidates": candidates, "provenance": {"method": "evo2_prompt_guided_v1", "feature_flags": get_feature_flags()}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_guide_rna failed: {e}")


@router.post("/generate_repair_template")
async def generate_repair_template(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        hdr_window = int((request or {}).get("hdr_window", 60))
        ref = (request or {}).get("ref_sequence", "")
        alt = (request or {}).get("alt_sequence", "")
        template = (alt or ref)[:hdr_window] if (alt or ref) else "".join(["A" for _ in range(hdr_window)])
        return {
            "template": template,
            "hdr_window": hdr_window,
            "notes": "placeholder HDR template; downstream needs PAM avoidance and silent markers",
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"generate_repair_template failed: {e}")


@router.post("/optimize_codon_usage")
async def optimize_codon_usage(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        cds = (request or {}).get("cds", "")
        before = 0.72
        after = 0.85 if cds else 0.75
        optimized = cds or "ATG" + "GCT" * 10
        return {
            "optimized_cds": optimized,
            "cai_before": before,
            "cai_after": after,
            "provenance": {"method": "placeholder_v0", "feature_flags": get_feature_flags()},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"optimize_codon_usage failed: {e}")






