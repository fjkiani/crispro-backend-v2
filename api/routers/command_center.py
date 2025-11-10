"""
Slim orchestrator endpoints that compose evidence and design calls
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import httpx
import asyncio

from ..config import get_feature_flags, EVO_TIMEOUT

router = APIRouter(prefix="/api/command", tags=["command_center"])


def _ensure_enabled():
    flags = get_feature_flags()
    if not flags.get("enable_command_center", False):
        raise HTTPException(status_code=403, detail="Command Center disabled by configuration")


async def _gather_safe(*aws):
    results = await asyncio.gather(*aws, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"error": str(r)})
        else:
            out.append(r)
    return out


@router.post("/run_evidence_bundle")
async def run_evidence_bundle(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        payload = request or {}
        async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
            efficacy_payload = {
                "model_id": payload.get("model_id", "evo2_7b"),
                "mutations": payload.get("mutations") or [],
                "options": payload.get("options") or {"adaptive": True, "ensemble": True},
                "api_base": "http://127.0.0.1:8000",
            }
            insights_payload = {
                "gene": (payload.get("mutations") or [{}])[0].get("gene"),
                "variants": payload.get("mutations") or []
            }
            tasks = [
                client.post("http://127.0.0.1:8000/api/efficacy/predict", json=efficacy_payload),
                client.post("http://127.0.0.1:8000/api/insights/predict_gene_essentiality", json=insights_payload),
            ]
            results = await _gather_safe(*tasks)
            outputs = []
            for r in results:
                # If gather returned an error dict
                if isinstance(r, dict):
                    # Pass through error dicts; wrap non-error dicts
                    outputs.append(r if r.get("error") else {"data": r})
                    continue
                # Otherwise expect an httpx.Response
                try:
                    outputs.append(r.json())
                except Exception as e:
                    try:
                        outputs.append({"status": getattr(r, "status_code", None), "text": getattr(r, "text", None)})
                    except Exception:
                        outputs.append({"error": f"parse_failed: {e}"})
            return {"bundle": outputs, "feature_flags_snapshot": get_feature_flags()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run_evidence_bundle failed: {e}")


@router.post("/run_design_bundle")
async def run_design_bundle(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        payload = request or {}
        async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
            tasks = [
                client.post("http://127.0.0.1:8000/api/design/generate_guide_rna", json=payload),
                client.post("http://127.0.0.1:8000/api/design/generate_repair_template", json=payload),
            ]
            results = await _gather_safe(*tasks)
            outputs = []
            for r in results:
                if isinstance(r, dict):
                    outputs.append(r if r.get("error") else {"data": r})
                    continue
                try:
                    outputs.append(r.json())
                except Exception as e:
                    try:
                        outputs.append({"status": getattr(r, "status_code", None), "text": getattr(r, "text", None)})
                    except Exception:
                        outputs.append({"error": f"parse_failed: {e}"})
            return {"bundle": outputs, "feature_flags_snapshot": get_feature_flags()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run_design_bundle failed: {e}")


@router.post("/run_full_pipeline")
async def run_full_pipeline(request: Dict[str, Any]):
    _ensure_enabled()
    try:
        eb = await run_evidence_bundle(request)
        db = await run_design_bundle(request)
        return {"evidence": eb, "design": db, "feature_flags_snapshot": get_feature_flags()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"run_full_pipeline failed: {e}")




