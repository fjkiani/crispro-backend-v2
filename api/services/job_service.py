"""
Background job management and execution
"""
import asyncio
import json
import os
import time
import uuid
from datetime import datetime
from typing import Dict, Any
import httpx

from ..config import DIFFBOT_TOKEN, SUPABASE_JOB_RESULTS_TABLE, SUPABASE_URL, SUPABASE_KEY
from .supabase_service import _supabase_insert

# Optional: Google GenAI for synthesis
try:
    import google.genai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

# In-memory job store (in production, use Redis or database)
JOBS = {}

class BackgroundJob:
    def __init__(self, job_id: str, job_type: str, payload: Dict[str, Any]):
        self.job_id = job_id
        self.job_type = job_type
        self.payload = payload
        self.status = "pending"
        self.progress = {"total": 0, "done": 0}
        self.result = None
        self.error = None
        self.created_at = datetime.utcnow().isoformat()
        self.updated_at = self.created_at

    def update_progress(self, done: int, total: int = None):
        if total is not None:
            self.progress["total"] = total
        self.progress["done"] = done
        self.updated_at = datetime.utcnow().isoformat()

    def set_running(self):
        self.status = "running"
        self.updated_at = datetime.utcnow().isoformat()

    def set_complete(self, result: Any):
        self.status = "complete"
        self.result = result
        self.updated_at = datetime.utcnow().isoformat()

    def set_error(self, error: str):
        self.status = "error"
        self.error = error
        self.updated_at = datetime.utcnow().isoformat()

    def to_dict(self):
        return {
            "job_id": self.job_id,
            "job_type": self.job_type,
            "status": self.status,
            "progress": self.progress,
            "result": self.result,
            "error": self.error,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

def _variant_call_from_detail(detail: Dict[str, Any]) -> str:
    """Extract a human-readable variant call from detailed analysis"""
    try:
        evo = detail.get("evo2_result") or {}
        interpretation = evo.get("interpretation", "").lower()
        confidence = float(evo.get("confidence_score") or 0.0)
        
        if confidence < 0.4:
            return "Unknown (low sequence evidence)"
        elif interpretation in ("pathogenic", "likely pathogenic", "disruptive"):
            return "Likely Disruptive"
        elif interpretation in ("benign", "likely benign"):
            return "Likely Neutral"
        else:
            return "Unknown"
    except Exception:
        return "Unknown"

async def _run_crawl_job(job_id: str):
    """Execute a crawling job to extract full text from URLs"""
    job = JOBS.get(job_id)
    if not job:
        return
    
    try:
        job.set_running()
        urls = job.payload.get("urls", [])
        job.update_progress(0, len(urls))
        
        extracts = []
        for i, url in enumerate(urls):
            try:
                api_url = "https://api.diffbot.com/v3/article"
                params = {
                    "token": DIFFBOT_TOKEN,
                    "url": url,
                    "fields": "title,author,date,siteName,tags,text",
                }
                with httpx.Client(timeout=30) as client:
                    r = client.get(api_url, params=params)
                    r.raise_for_status()
                    js = r.json()
                obj = (js.get("objects") or [None])[0]
                if obj:
                    extracts.append({
                        "url": url,
                        "title": obj.get("title"),
                        "author": obj.get("author"),
                        "date": obj.get("date"),
                        "site_name": obj.get("siteName"),
                        "text": obj.get("text"),
                        "tags": obj.get("tags"),
                    })
                else:
                    extracts.append({"url": url, "error": "no article found"})
            except Exception as e:
                extracts.append({"url": url, "error": str(e)})
            
            job.update_progress(i + 1)
            await asyncio.sleep(0.1)  # Small delay between requests
        
        job.set_complete({"extracts": extracts})
        
        # Persist to Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            ts = int(time.time())
            job_row = {
                "job_id": job_id,
                "job_type": "crawl",
                "status": "complete",
                "urls_count": len(urls),
                "extracts_count": len([e for e in extracts if "error" not in e]),
                "result_json": json.dumps({"extracts": extracts})[:8000],
                "created_at": ts,
            }
            asyncio.create_task(_supabase_insert(SUPABASE_JOB_RESULTS_TABLE, [job_row]))
    
    except Exception as e:
        job.set_error(str(e))

async def _run_summarize_job(job_id: str):
    """Execute a summarization job to analyze extracted content"""
    job = JOBS.get(job_id)
    if not job:
        return
    
    try:
        job.set_running()
        extracted_texts = job.payload.get("extracted_texts", [])
        gene = job.payload.get("gene", "")
        variant = job.payload.get("variant", "")
        job.update_progress(0, len(extracted_texts))
        
        if not genai or not os.getenv("GEMINI_API_KEY"):
            job.set_error("LLM not configured")
            return
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
        summaries = []
        
        for i, extract in enumerate(extracted_texts):
            try:
                text = extract.get("text", "")
                title = extract.get("title", "")
                url = extract.get("url", "")
                
                if not text:
                    summaries.append({"url": url, "error": "no text to summarize"})
                    continue
                
                prompt = (
                    f"Summarize this article focusing on {gene} {variant} and its clinical relevance. "
                    f"Extract key findings about pathogenicity, mechanism, therapeutic implications, and prognosis.\n\n"
                    f"Title: {title}\n\n"
                    f"Text: {text[:4000]}"  # Limit text length
                )
                
                resp = client.models.generate_content(
                    model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"),
                    contents=prompt
                )
                summary_text = getattr(resp, "text", None) or str(resp)
                
                summaries.append({
                    "url": url,
                    "title": title,
                    "summary": summary_text,
                })
            
            except Exception as e:
                summaries.append({"url": extract.get("url", ""), "error": str(e)})
            
            job.update_progress(i + 1)
            await asyncio.sleep(0.1)
        
        job.set_complete({"summaries": summaries})
        
        # Persist to Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            ts = int(time.time())
            job_row = {
                "job_id": job_id,
                "job_type": "summarize",
                "status": "complete",
                "texts_count": len(extracted_texts),
                "summaries_count": len([s for s in summaries if "error" not in s]),
                "gene": gene,
                "variant": variant,
                "result_json": json.dumps({"summaries": summaries})[:8000],
                "created_at": ts,
            }
            asyncio.create_task(_supabase_insert(SUPABASE_JOB_RESULTS_TABLE, [job_row]))
    
    except Exception as e:
        job.set_error(str(e))

async def _run_align_job(job_id: str):
    """Execute an alignment job to reconcile evidence with variant assessment"""
    job = JOBS.get(job_id)
    if not job:
        return
    
    try:
        job.set_running()
        summaries = job.payload.get("summaries", [])
        evo2_result = job.payload.get("evo2_result", {})
        clinvar = job.payload.get("clinvar", {})
        job.update_progress(0, 1)
        
        if not genai or not os.getenv("GEMINI_API_KEY"):
            job.set_error("LLM not configured")
            return
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
        
        # Compile evidence
        evidence_parts = []
        evidence_parts.append("## Evo2 Sequence Analysis")
        evidence_parts.append(f"- Zeta Score: {evo2_result.get('zeta_score', 'n/a')}")
        evidence_parts.append(f"- Min Delta: {evo2_result.get('min_delta', 'n/a')}")
        evidence_parts.append(f"- Confidence: {evo2_result.get('confidence_score', 'n/a')}")
        evidence_parts.append(f"- Interpretation: {evo2_result.get('interpretation', 'n/a')}")
        
        if clinvar:
            evidence_parts.append("\n## ClinVar Evidence")
            evidence_parts.append(f"- Classification: {clinvar.get('classification', 'n/a')}")
            evidence_parts.append(f"- Review Status: {clinvar.get('review_status', 'n/a')}")
        
        evidence_parts.append("\n## Literature Evidence")
        for i, summary in enumerate(summaries[:5]):  # Limit to top 5
            if "summary" in summary:
                evidence_parts.append(f"- Source {i+1}: {summary.get('title', 'Unknown')}")
                evidence_parts.append(f"  Summary: {summary['summary'][:500]}...")
        
        prompt = (
            "You are an expert oncology variant analyst. Review the following evidence and provide a comprehensive "
            "assessment that reconciles sequence-based predictions with clinical evidence and literature findings. "
            "Address any discrepancies and provide a final recommendation.\n\n" +
            "\n".join(evidence_parts) +
            "\n\nProvide: 1) Evidence synthesis, 2) Discrepancy analysis, 3) Final clinical recommendation, 4) Confidence level"
        )
        
        resp = client.models.generate_content(
            model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"),
            contents=prompt
        )
        alignment_text = getattr(resp, "text", None) or str(resp)
        
        job.update_progress(1)
        job.set_complete({
            "alignment": alignment_text,
            "evidence_count": len(summaries),
            "evo2_included": bool(evo2_result),
            "clinvar_included": bool(clinvar),
        })
        
        # Persist to Supabase
        if SUPABASE_URL and SUPABASE_KEY:
            ts = int(time.time())
            job_row = {
                "job_id": job_id,
                "job_type": "align",
                "status": "complete",
                "evidence_count": len(summaries),
                "alignment": alignment_text[:8000],
                "created_at": ts,
            }
            asyncio.create_task(_supabase_insert(SUPABASE_JOB_RESULTS_TABLE, [job_row]))
    
    except Exception as e:
        job.set_error(str(e)) 
