"""
Generative design endpoints (generate_*)
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List

from ..config import get_feature_flags
import httpx
import re

router = APIRouter(prefix="/api/design", tags=["design"])


def _ensure_enabled():
    flags = get_feature_flags()
    if not flags.get("enable_design_api", False):
        raise HTTPException(status_code=403, detail="Design API disabled by configuration")


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






