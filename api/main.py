"""
Modular FastAPI application for oncology-backend-v2
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from typing import Dict, Any
import httpx
import time
import asyncio

from .config import EVO_TIMEOUT, MODEL_TO_BASE, USE_CASES, SUPABASE_URL, SUPABASE_KEY, get_api_flags
from .services.supabase_service import _supabase_select, _supabase_event
from .routers import health, myeloma, evo, evidence, efficacy
from .routers import fusion as fusion_router
from .routers import guidance as guidance_router
from .routers import datasets as datasets_router
from .routers import insights as insights_router
from .routers import design as design_router
from .routers import command_center as command_router
from .routers import sessions as sessions_router
from .routers import auth as auth_router
from .routers import admin as admin_router
from .routers import toxicity as toxicity_router
from .routers import safety as safety_router
from .routers import metastasis as metastasis_router
# TEMPORARILY DISABLED - IndentationError in metastasis_interception.py line 75
# from .routers import metastasis_interception as metastasis_interception_router
from .routers.kb import router as kb_router
from .routers import acmg as acmg_router
from .routers import pharmgkb as pharmgkb_router
from .routers import clinical_trials as clinical_trials_router
from .routers import trials as trials_router  # NEW: Search and refresh endpoints
from .routers import trials_graph as trials_graph_router  # NEW: Graph-optimized search
from .routers import trials_agent as trials_agent_router  # NEW: Autonomous trial agent
from .routers import resistance as resistance_router
from .routers import nccn as nccn_router
from .routers import clinical_genomics as clinical_genomics_router
# from .routers import offtarget as offtarget_router  # TODO: Not created yet
from .routers import kg as kg_router
from .routers import hypothesis_validator as hypothesis_validator_router
from .routers import ayesha_twin_demo as ayesha_twin_demo_router
from .routers import ayesha as ayesha_router
from .routers import tumor as tumor_router  # NEW: Sporadic Cancer Strategy (Day 1)
# Copilot orchestrator removed - RAG integration is via evidence.router (evidence/rag.py)

# Mock responses for basic endpoints
MOCK_ORACLE_RESPONSE = {"assessment": "HIGH_THREAT", "confidence": 0.95, "reasoning": "Critical pathway disruption predicted"}
MOCK_FORGE_RESPONSE = {"therapeutics": [{"name": "CRISPR-Cas9 Guide RNA", "target": "BRAF V600E", "efficacy": 0.92}]}
MOCK_GAUNTLET_RESPONSE = {"trial_results": {"success_rate": 0.87, "safety_profile": "ACCEPTABLE"}}
MOCK_DOSSIER_RESPONSE = {"dossier_id": "IND-2024-001", "status": "GENERATED", "pages": 847}

app = FastAPI(
    title="Oncology Backend API",
    description="Modular FastAPI backend for CRISPR-based precision oncology",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router)
app.include_router(myeloma.router)
app.include_router(evo.router)
app.include_router(evidence.router)
app.include_router(efficacy.router)
app.include_router(guidance_router.router)
app.include_router(fusion_router.router)
app.include_router(sessions_router.router)
app.include_router(auth_router.router)  # NEW: Authentication endpoints
app.include_router(admin_router.router)  # NEW: Admin dashboard endpoints
# Toxicity hint (germline-aware caution)
# app.include_router(toxicity_router.router)  # Temporarily disabled - pre-existing issue
# Safety endpoints (toxicity risk + off-target preview) - P1 LIVE
app.include_router(safety_router.router)
# Metastasis cascade risk assessment
# TEMPORARILY DISABLED - AttributeError: no attribute 'router'
# app.include_router(metastasis_router.router)
# Metastasis interception (weapon design)
# TEMPORARILY DISABLED - IndentationError
# app.include_router(metastasis_interception_router.router)
# app.include_router(kb_router.router)  # Temporarily disabled

# Conditionally include new routers based on API flags
_api_flags = get_api_flags()
if _api_flags.get("insights"):
    app.include_router(insights_router.router)
if _api_flags.get("design"):
    app.include_router(design_router.router)
if _api_flags.get("command_center"):
    app.include_router(command_router.router)
app.include_router(datasets_router.router)
app.include_router(acmg_router.router)
app.include_router(pharmgkb_router.router)
app.include_router(clinical_trials_router.router)
app.include_router(trials_router.router)  # NEW: /api/search-trials and /api/trials/refresh_status
app.include_router(trials_graph_router.router)  # NEW: /api/trials/search-optimized (hybrid graph search)
app.include_router(trials_agent_router.router)  # NEW: /api/trials/agent/search (autonomous agent)
app.include_router(resistance_router.router)
app.include_router(nccn_router.router)
app.include_router(clinical_genomics_router.router)
# app.include_router(offtarget_router.router)  # TODO: Not created yet
app.include_router(kg_router.router)
app.include_router(hypothesis_validator_router.router)
app.include_router(ayesha_twin_demo_router.router)
app.include_router(ayesha_router.router)
app.include_router(tumor_router.router)  # NEW: Sporadic Cancer Strategy (Day 1-7)
# Co-Pilot conversational endpoint is via evidence.router → evidence/rag.py → /api/evidence/rag-query

@app.on_event("startup")
async def _on_startup():
    """Initialize background services (calibration preload, refresh)."""
    try:
        from .startup import startup_tasks
        await startup_tasks()
    except Exception:
        # Do not block app startup on background init failures
        pass

@app.on_event("shutdown")
async def _on_shutdown():
    """Gracefully stop background services."""
    try:
        from .startup import shutdown_tasks
        await shutdown_tasks()
    except Exception:
        pass

def _choose_base(model_id: str) -> str:
    """Choose the appropriate base URL for the model"""
    model_key = model_id.lower()
    url_func = MODEL_TO_BASE.get(model_key, MODEL_TO_BASE["evo2_7b"])
    if callable(url_func):
        return url_func()
    return url_func

# Additional endpoints that don't fit in specific routers yet

@app.post("/api/workflow/run_seed_soil_analysis")
async def run_seed_soil_analysis(request: Dict[str, Any]):
    """Seed & Soil: Orchestrate metastasis pathway analysis"""
    # This would call multiple services to analyze metastatic potential
    return {"analysis": "SEED_SOIL_COMPATIBLE", "metastatic_risk": 0.78, "recommendations": ["Target EMT pathway", "Monitor circulating tumor cells"]}

@app.post("/api/twin/run")
async def twin_run(request: Dict[str, Any]):
    """Orchestrator: warm model, run scoring (chunked inside predict), emit Supabase events, return full results."""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    model_id = request.get("model_id", "evo2_7b")
    base_url = _choose_base(model_id)
    
    # Warm up the model first
    try:
        async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
            warmup_payload = {"ref_sequence": "AAAAAA", "alt_sequence": "AAACAA", "model_id": model_id}
            r = await client.post(f"{base_url}/score_delta", json=warmup_payload)
            r.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Model warmup failed: {e}")
    
    # Route to myeloma prediction
    from .routers.myeloma import predict_myeloma_response
    result = await predict_myeloma_response(request)
    
    # Emit completion event
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            await _supabase_event("twin_run_complete", {
                "model_id": model_id,
                "num_variants": len(result.get("detailed_analysis", [])),
                "prediction": result.get("prediction")
            })
    except Exception:
        pass
    
    return result

@app.post("/api/twin/submit")
async def twin_submit(request: Dict[str, Any]):
    """Submit a Digital Twin analysis job (async processing)"""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    
    # Generate job ID and return immediately
    import uuid
    job_id = str(uuid.uuid4())
    
    # In production, this would queue the job for background processing
    return {
        "job_id": job_id,
        "status": "submitted",
        "estimated_completion": "2-5 minutes"
    }

@app.post("/api/twin/status")
async def twin_status(request: Dict[str, Any]):
    """Check status of a Digital Twin analysis job"""
    job_id = request.get("job_id")
    if not job_id:
        raise HTTPException(status_code=400, detail="job_id required")
    
    # Mock status response
    return {
        "job_id": job_id,
        "status": "completed",
        "progress": 100,
        "result_available": True
    }

@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    """Analytics dashboard data aggregation"""
    try:
        data = {"summary": {"total_runs": 0, "total_variants": 0, "avg_confidence": 0.0}}
        
        if SUPABASE_URL and SUPABASE_KEY:
            try:
                # Get basic run statistics
                runs_data = await _supabase_select("mdt_runs", ["count(*) as total"])
                if runs_data and len(runs_data) > 0:
                    data["summary"]["total_runs"] = runs_data[0].get("total", 0)
                
                # Get variant statistics  
                variants_data = await _supabase_select("mdt_run_variants", ["count(*) as total", "avg(confidence) as avg_conf"])
                if variants_data and len(variants_data) > 0:
                    data["summary"]["total_variants"] = variants_data[0].get("total", 0)
                    data["summary"]["avg_confidence"] = round(float(variants_data[0].get("avg_conf", 0.0)), 3)
            except Exception:
                pass
        
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"analytics failed: {e}")

@app.post("/api/safety/ensembl_context")
async def ensembl_context(request: Dict[str, Any]):
    """Return Ensembl context for a locus: refcheck, exon overlap, VEP consequence, transcript hints.
    Input: { assembly:"GRCh38|GRCh37", chrom:"7", pos:140753336, ref:"A", alt?:"T" }
    """
    try:
        asm_in = (request or {}).get("assembly", "GRCh38")
        chrom = str((request or {}).get("chrom"))
        pos = int((request or {}).get("pos"))
        ref = str((request or {}).get("ref", "")).upper()
        alt = str((request or {}).get("alt", "")).upper()
        asm = "GRCh38" if str(asm_in).lower() in ("grch38","hg38") else "GRCh37"
        region = f"{chrom}:{pos}-{pos}:1"
        urls = {
            "sequence": f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}",
            "overlap": f"https://rest.ensembl.org/overlap/region/human/{chrom}:{pos}-{pos}?content-type=application/json;feature=exon",
        }
        fetched_base = None
        exon_overlap = False
        transcripts = []
        with httpx.Client(timeout=20) as client:
            # sequence
            try:
                r = client.get(urls["sequence"]) ; r.raise_for_status(); fetched_base = r.text.strip().upper()
            except Exception:
                fetched_base = None
            # overlap
            try:
                ro = client.get(urls["overlap"]) ; ro.raise_for_status(); data = ro.json()
                exon_overlap = bool(isinstance(data, list) and len(data) > 0)
                # pull transcript ids if available
                for it in (data or [])[:10]:
                    tid = it.get("Parent") or it.get("transcript_id") or it.get("id")
                    if tid: transcripts.append(tid)
            except Exception:
                exon_overlap = False
        # VEP consequence (best-effort)
        vep_url = None
        vep = None
        if ref and alt:
            vep_url = f"https://rest.ensembl.org/vep/human/region/{chrom}:{pos}{ref}/{alt}?content-type=application/json"
            try:
                with httpx.Client(timeout=20) as client:
                    rv = client.get(vep_url)
                    if rv.status_code == 200:
                        v = rv.json()
                        if isinstance(v, list) and v:
                            vep = v[0]
            except Exception:
                vep = None
        ok = bool(fetched_base) and (fetched_base == ref or fetched_base == "N" or not ref)
        return {
            "refcheck": {"ok": ok, "fetched": fetched_base, "expected": ref, "assembly": asm, "chrom": chrom, "pos": pos},
            "exon_overlap": exon_overlap,
            "transcripts": transcripts,
            "vep": vep,
            "urls": {k: v for k, v in urls.items() if v} | ({"vep": vep_url} if vep_url else {}),
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"ensembl_context failed: {e}")

@app.post("/api/safety/clinvar_context")
async def clinvar_context(request: Dict[str, Any]):
    """Return ClinVar context for a variant via Variation ID or URL fallback."""
    try:
        # Import from evidence router
        from .routers.evidence import clinvar_context as _clinvar_context
        return await _clinvar_context(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"clinvar_context failed: {e}") 

        # Import from evidence router
        from .routers.evidence import clinvar_context as _clinvar_context
        return await _clinvar_context(request)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"clinvar_context failed: {e}") 
