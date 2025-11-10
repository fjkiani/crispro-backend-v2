"""
Jobs Module - Background job orchestration endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import uuid
import asyncio

from ...config import DIFFBOT_TOKEN
from ...services.job_service import JOBS, BackgroundJob, _run_crawl_job, _run_summarize_job, _run_align_job

# Optional: Google GenAI for literature synthesis
try:
    import google.genai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

router = APIRouter()

@router.post("/crawl")
async def evidence_crawl(request: Dict[str, Any]):
    """Submit a background crawling job to extract full text from multiple URLs.
    Input: { urls: [str], job_id?: str }
    Output: { job_id: str, status: "pending" }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        urls = request.get("urls", [])
        if not isinstance(urls, list) or not urls:
            raise HTTPException(status_code=400, detail="urls[] required")
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=501, detail="Diffbot not configured")
        
        job_id = request.get("job_id") or str(uuid.uuid4())
        job = BackgroundJob(job_id, "crawl", {"urls": urls})
        JOBS[job_id] = job
        
        # Start background task
        asyncio.create_task(_run_crawl_job(job_id))
        
        return {"job_id": job_id, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"crawl failed: {e}")

@router.post("/summarize")
async def evidence_summarize(request: Dict[str, Any]):
    """Submit a background summarization job to analyze extracted content.
    Input: { extracted_texts: [{ url, title, text }], gene?: str, variant?: str, job_id?: str }
    Output: { job_id: str, status: "pending" }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        extracted_texts = request.get("extracted_texts", [])
        if not isinstance(extracted_texts, list) or not extracted_texts:
            raise HTTPException(status_code=400, detail="extracted_texts[] required")
        if not genai or not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(status_code=501, detail="LLM not configured")
        
        job_id = request.get("job_id") or str(uuid.uuid4())
        job = BackgroundJob(job_id, "summarize", {
            "extracted_texts": extracted_texts,
            "gene": request.get("gene"),
            "variant": request.get("variant")
        })
        JOBS[job_id] = job
        
        # Start background task
        asyncio.create_task(_run_summarize_job(job_id))
        
        return {"job_id": job_id, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"summarize failed: {e}")

@router.post("/align")
async def evidence_align(request: Dict[str, Any]):
    """Submit a background alignment job to reconcile evidence with variant assessment.
    Input: { summaries: [{ url, summary }], evo2_result: {}, clinvar: {}, job_id?: str }
    Output: { job_id: str, status: "pending" }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        summaries = request.get("summaries", [])
        if not isinstance(summaries, list) or not summaries:
            raise HTTPException(status_code=400, detail="summaries[] required")
        if not genai or not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(status_code=501, detail="LLM not configured")
        
        job_id = request.get("job_id") or str(uuid.uuid4())
        job = BackgroundJob(job_id, "align", {
            "summaries": summaries,
            "evo2_result": request.get("evo2_result", {}),
            "clinvar": request.get("clinvar", {})
        })
        JOBS[job_id] = job
        
        # Start background task
        asyncio.create_task(_run_align_job(job_id))
        
        return {"job_id": job_id, "status": "pending"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"align failed: {e}")

@router.get("/job/{job_id}")
async def evidence_job_status(job_id: str):
    """Get the status of a background job.
    Output: { job_id, job_type, status, progress: {done, total}, result?, error?, created_at, updated_at }
    """
    try:
        job = JOBS.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job not found")
        return job.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"job status failed: {e}")



