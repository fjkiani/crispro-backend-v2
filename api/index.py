"""
Minimal FastAPI deployment for oncology-backend-v2
Provides essential API endpoints with mock data for YC demo
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any, List, Optional
import json
import os
import httpx
from httpx import Timeout
from hashlib import sha256
import time
import asyncio
import sys
from pathlib import Path
import uuid
from datetime import datetime

# Optional: Google GenAI for literature synthesis
try:
    import google.genai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

# Optional Supabase logging configuration (set via env to activate)
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_ANON_KEY", "").strip()).strip()
SUPABASE_RUNS_TABLE = os.getenv("SUPABASE_RUNS_TABLE", "mdt_runs").strip()
SUPABASE_RUN_VARIANTS_TABLE = os.getenv("SUPABASE_RUN_VARIANTS_TABLE", "mdt_run_variants").strip()
SUPABASE_EVENTS_TABLE = os.getenv("SUPABASE_EVENTS_TABLE", "mdt_events").strip()
SUPABASE_DEEP_ANALYSIS_TABLE = os.getenv("SUPABASE_DEEP_ANALYSIS_TABLE", "mdt_deep_analysis").strip()
SUPABASE_JOB_RESULTS_TABLE = os.getenv("SUPABASE_JOB_RESULTS_TABLE", "mdt_job_results").strip()

DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN", "").strip()

# Job management for background tasks
import uuid
from datetime import datetime

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

# Use-case configuration (minimal seed; expandable)
USE_CASES = {
    "myeloma": {
        "id": "myeloma",
        "title": "Myeloma Digital Twin",
        "default_windows": [1024, 2048, 4096, 8192],
        "default_exon_flank": 600,
        "decision_policy": {"id": "v1", "ras_threshold": 2.0},
    }
}

async def _supabase_insert(table: str, rows: List[Dict[str, Any]], timeout_s: float = 5.0) -> None:
    if not SUPABASE_URL or not SUPABASE_KEY or not table or not rows:
        return
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    async with httpx.AsyncClient(timeout=Timeout(timeout_s)) as client:
        try:
            await client.post(url, headers=headers, content=json.dumps(rows))
        except Exception:
            # Never fail the request due to analytics
            return

async def _supabase_event(run_signature: str, stage: str, message: str = "") -> None:
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return
        ts = int(time.time())
        await _supabase_insert(SUPABASE_EVENTS_TABLE, [{
            "run_signature": run_signature,
            "stage": stage,
            "message": message[:2000],
            "t": ts,
        }])
    except Exception:
        return

async def _supabase_select(table: str, eq: Dict[str, Any], order: str = "", limit: int = 1000, timeout_s: float = 5.0):
    if not SUPABASE_URL or not SUPABASE_KEY:
        return []
    url = f"{SUPABASE_URL.rstrip('/')}/rest/v1/{table}"
    headers = {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
    }
    params = {"select": "*", "limit": str(limit)}
    # equality filters
    for k, v in (eq or {}).items():
        params[f"{k}"] = f"eq.{v}"
    if order:
        params["order"] = order
    async with httpx.AsyncClient(timeout=Timeout(timeout_s)) as client:
        try:
            r = await client.get(url, headers=headers, params=params)
            r.raise_for_status()
            return r.json()
        except Exception:
            return []

def _variant_call_from_detail(detail: Dict[str, Any]) -> str:
    evo = detail.get("evo2_result") or {}
    conf = evo.get("confidence_score")
    zeta = evo.get("zeta_score")
    impact = detail.get("calculated_impact_level")
    if not isinstance(conf, (int, float)) or conf < 0.4:
        return "Unknown"
    if isinstance(impact, (int, float)) and impact >= 1.0 and isinstance(zeta, (int, float)) and zeta < 0:
        return "Likely Disruptive"
    return "Likely Neutral"

app = FastAPI(
    title="CrisPRO Oncology Backend v2",
    description="AI-Powered R&D De-risking Platform",
    version="2.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Pydantic models
class VariantRequest(BaseModel):
    mutation: str
    gene: Optional[str] = None
    
class TherapeuticRequest(BaseModel):
    target: str
    mutation: str

class DossierRequest(BaseModel):
    target: str
    mutation: str
    analysis_type: str = "comprehensive"

# Mock data for YC demo
MOCK_ORACLE_RESPONSE = {
    "data": {
        "endpoints": [
            {
                "name": "predict_variant_impact",
                "result": {
                    "delta_likelihood_score": -18750.5,
                    "pathogenicity": "pathogenic",
                    "confidence": 0.968
                }
            },
            {
                "name": "predict_gene_essentiality", 
                "result": {
                    "essentiality_score": 0.92,
                    "cancer_dependency": "essential",
                    "tissue_specificity": "breast_cancer"
                }
            },
            {
                "name": "predict_druggability",
                "result": {
                    "druggability_score": 0.88,
                    "binding_sites": 3,
                    "accessibility": "high"
                }
            }
        ]
    }
}

MOCK_FORGE_RESPONSE = {
    "data": {
        "crispr_guides": [
            {
                "sequence": "GCTCGATCGATCGATCGATCG",
                "efficiency": 0.945,
                "specificity": 0.982
            }
        ],
        "small_molecules": [
            {
                "structure": "C1=CC=C(C=C1)C2=CC=CC=C2",
                "binding_affinity": 8.2,
                "selectivity": 0.89
            }
        ]
    }
}

MOCK_GAUNTLET_RESPONSE = {
    "data": {
        "trial_simulation": {
            "objective_response_rate": 0.82,
            "safety_profile": "favorable", 
            "predicted_efficacy": "high"
        },
        "structural_validation": {
            "protein_stability": 0.91,
            "folding_confidence": 0.87
        }
    }
}

MOCK_DOSSIER_RESPONSE = {
    "therapeutic_blueprint": {
        "target": "PIK3CA E542K",
        "cost_avoidance": "$47.2M",
        "development_timeline": "18 months",
        "success_probability": "82%",
        "patent_ready": True,
        "conquest_stages": {
            "VICTORY": {"status": "complete", "value": "IND-Ready Dossier"},
            "FORTIFY": {"status": "ready", "target": "$15K filing cost"},
            "ARM": {"status": "pending", "target": "1,000 NFTs @ $5K each"},
            "FUND": {"status": "pending", "projection": "$5M raised"},
            "CONQUER": {"status": "pending", "projection": "$100M+ licensing"}
        }
    }
}

# API Endpoints
@app.get("/")
async def root():
    return {
        "message": "CrisPRO Oncology Backend v2 - Live!",
        "status": "operational",
        "version": "2.0.0"
    }

@app.get("/health")
async def health_check():
    return {"status": "healthy", "services": "operational"}

@app.post("/api/oracle/assess_variant_threat")
async def assess_variant_threat(request: VariantRequest):
    """Oracle: Assess variant pathogenicity and impact"""
    return MOCK_ORACLE_RESPONSE

@app.post("/api/forge/generate_therapeutics")
async def generate_therapeutics(request: TherapeuticRequest):
    """Forge: Generate CRISPR guides and small molecules"""
    return MOCK_FORGE_RESPONSE

@app.post("/api/gauntlet/run_trials")
async def run_trials(request: Dict[str, Any]):
    """Gauntlet: Run in silico clinical trials"""
    return MOCK_GAUNTLET_RESPONSE

@app.post("/api/dossier/generate")
async def generate_dossier(request: DossierRequest):
    """Generate complete IND-ready dossier"""
    return MOCK_DOSSIER_RESPONSE

# Tool Runner compatibility endpoints
@app.post("/api/predict/myeloma_drug_response")
async def predict_myeloma_response(request: Dict[str, Any]):
    """Myeloma Digital Twin: Predict drug response using Evo2 live scoring only.
    Requires fields: gene, hgvs_p, variant_info, build (or an array in mutations[]). No mock fallbacks.
    """
    # Normalize input to a list of mutations
    mutations = None
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base_url = _choose_base(model_id)
    options = (request or {}).get("options") or {}
    use_priors = bool(options.get("use_priors", False))
    hotspot_relaxation = bool(options.get("hotspot_relaxation", True))
    if isinstance(request, dict):
        if "mutations" in request and isinstance(request["mutations"], list):
            mutations = request["mutations"]
        elif {"gene", "hgvs_p", "variant_info", "build"}.issubset(request.keys()):
            mutations = [
                {
                    "gene": request.get("gene"),
                    "hgvs_p": request.get("hgvs_p"),
                    "variant_info": request.get("variant_info"),
                    "build": request.get("build", "hg38"),
                }
            ]

    if not mutations:
        raise HTTPException(status_code=400, detail="Missing required fields. Provide gene, hgvs_p, variant_info, build or a mutations[] array.")

    detailed = []

    # Preflight: format validation, REF-check, duplicate collapse (policy v1.1 safety)
    import re as _re
    re_vi = _re.compile(r"^chr?([0-9XYM]+):([0-9]+)\s+([ACGT])>([ACGT])$", _re.IGNORECASE)
    seen_keys = set()
    to_score = []
    preflight_issues = {"invalid": 0, "ref_mismatch": 0, "duplicates": 0}

    with httpx.Client(timeout=15) as _client:
        for m in mutations:
            gene = (m.get("gene") or "").upper() or "KRAS"
            hgvs_p = m.get("hgvs_p", "") or "p.Gly12Asp"
            variant_info = (m.get("variant_info", "") or "").strip()
            build = (m.get("build") or "hg38").lower()
            asm = "GRCh38" if build == "hg38" else "GRCh37"
            # Validate format
            if not re_vi.match(variant_info):
                preflight_issues["invalid"] += 1
                detailed.append({
                    "gene": gene,
                    "variant": f"{gene} {hgvs_p}",
                    "calculated_impact_level": "error",
                    "evo2_result": {"error": "Invalid variant format. Use 'chr7:140753336 A>T'"},
                    "selected_model": model_id,
                    "original_variant_data": m,
                })
                continue
            chrom_raw, pos_raw, alleles_raw = variant_info.replace("chr","",1).split(":")[0], variant_info.replace("chr","",1).split(":")[1].split()[0], variant_info.split()[1]
            chrom = chrom_raw
            try:
                pos = int(pos_raw)
            except Exception:
                preflight_issues["invalid"] += 1
                detailed.append({
                    "gene": gene,
                    "variant": f"{gene} {hgvs_p}",
                    "calculated_impact_level": "error",
                    "evo2_result": {"error": "Invalid position"},
                    "selected_model": model_id,
                    "original_variant_data": m,
                })
                continue
            ref = alleles_raw.split(">")[0].upper()
            alt = alleles_raw.split(">")[1].upper()
            # REF-check
            region = f"{chrom}:{pos}-{pos}:1"
            url = f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}"
            try:
                r = _client.get(url)
                r.raise_for_status()
                fetched = r.text.strip().upper()
                if fetched and fetched != "N" and fetched != ref:
                    preflight_issues["ref_mismatch"] += 1
                    detailed.append({
                        "gene": gene,
                        "variant": f"{gene} {hgvs_p}",
                        "chrom": chrom,
                        "pos": pos,
                        "calculated_impact_level": "error",
                        "evo2_result": {"error": f"Reference allele mismatch: fetched='{fetched}' provided='{ref}' at {chrom}:{pos}"},
                        "selected_model": model_id,
                        "original_variant_data": m,
                    })
                    continue
            except Exception as e:
                detailed.append({
                    "gene": gene,
                    "variant": f"{gene} {hgvs_p}",
                    "chrom": chrom,
                    "pos": pos,
                    "calculated_impact_level": "error",
                    "evo2_result": {"error": f"refcheck error: {e}"},
                    "selected_model": model_id,
                    "original_variant_data": m,
                })
                continue
            # Duplicate collapse
            key = (gene, str(chrom), int(pos), f"{ref}>{alt}")
            if key in seen_keys:
                preflight_issues["duplicates"] += 1
                detailed.append({
                    "gene": gene,
                    "variant": f"{gene} {hgvs_p}",
                    "chrom": chrom,
                    "pos": pos,
                    "calculated_impact_level": "error",
                    "evo2_result": {"error": "duplicate input collapsed"},
                    "selected_model": model_id,
                    "original_variant_data": m,
                })
                continue
            seen_keys.add(key)
            to_score.append({"gene": gene, "hgvs_p": hgvs_p, "chrom": chrom, "pos": pos, "ref": ref, "alt": alt, "build": build})

    # Call evo-service for each valid mutation (SNV only)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        for m in to_score:
            gene = m["gene"]
            hgvs_p = m["hgvs_p"]
            chrom_part = m["chrom"]; pos = m["pos"]; ref = m["ref"]; alt = m["alt"]
            payload = {
                "assembly": "GRCh38" if m["build"] == "hg38" else "GRCh37",
                "chrom": chrom_part,
                "pos": pos,
                "ref": str(ref).upper(),
                "alt": str(alt).upper(),
            }
            try:
                r1 = await client.post(f"{base_url}/score_variant", json={**payload, "window": 8192})
                r1.raise_for_status()
                evo = r1.json()
                zeta = float(evo.get("delta_score"))
                # multi-window
                r2 = await client.post(f"{base_url}/score_variant_multi", json={**payload, "windows": [1024, 2048, 4096, 8192]})
                r2.raise_for_status()
                multi = r2.json()
                # exon-tight
                r3 = await client.post(f"{base_url}/score_variant_exon", json={**payload, "flank": 600})
                r3.raise_for_status()
                exon = r3.json()
            except httpx.HTTPError as e:
                body = getattr(getattr(e, 'response', None), 'text', None)
                msg = f"Evo2 scoring failed: {e}"
                if body:
                    msg += f" | body={body[:400]}"
                detailed.append({
                    "gene": gene,
                    "variant": f"{gene} {hgvs_p}",
                    "chrom": chrom_part,
                    "pos": pos,
                    "calculated_impact_level": "error",
                    "evo2_result": {"error": msg},
                    "selected_model": model_id,
                    "original_variant_data": {"gene": gene, "hgvs_p": hgvs_p, "variant_info": f"chr{chrom_part}:{pos} {ref}>{alt}", "build": m["build"]},
                })
                continue

            # Confidence scoring
            import math
            def clamp(x, lo=0.0, hi=1.0):
                return max(lo, min(hi, x))
            # effect size from min_delta
            min_delta = float(multi.get("min_delta")) if multi.get("min_delta") is not None else zeta
            s1 = clamp(abs(min_delta) / 0.5, 0.0, 1.0)
            # exon corroboration
            exon_delta = exon.get("exon_delta")
            if isinstance(exon_delta, (int, float)):
                same_sign = (exon_delta == 0 and min_delta == 0) or (exon_delta * min_delta > 0)
                s2 = 1.0 if same_sign and abs(exon_delta) >= abs(min_delta) else (0.5 if same_sign else 0.0)
            else:
                s2 = 0.3  # partial credit when exon not available
            # window consistency
            deltas = [d.get("delta") for d in (multi.get("deltas") or []) if isinstance(d.get("delta"), (int, float))]
            if len(deltas) >= 2:
                mean = sum(deltas) / len(deltas)
                var = sum((d - mean) ** 2 for d in deltas) / (len(deltas) - 1)
                stdev = math.sqrt(var)
                denom = max(0.05, abs(min_delta))
                s3 = clamp(1.0 - (stdev / denom))
            else:
                s3 = 0.5
            confidence = round(0.5 * s1 + 0.3 * s2 + 0.2 * s3, 2)

            # Policy v1.2: adaptive confidence boost for short-window corroborated signals
            confidence_boost = 0.0
            try:
                w_used = int(multi.get("window_used") or 0)
            except Exception:
                w_used = 0
            if w_used and w_used <= 1024 and isinstance(exon_delta, (int, float)):
                same_dir = (exon_delta == 0 and min_delta == 0) or (exon_delta * min_delta > 0)
                if same_dir and abs(exon_delta) >= 0.8 * abs(min_delta):
                    confidence_boost += 0.10
            if s3 >= 0.7:
                confidence_boost += 0.05
            confidence = round(clamp(confidence + confidence_boost, 0.0, 1.0), 2)

            reason_bits = []
            reason_bits.append(f"effect {abs(min_delta):.3f}")
            reason_bits.append(f"windows {'consistent' if s3>=0.7 else 'variable'}")
            if isinstance(exon_delta, (int, float)):
                reason_bits.append(f"exon {exon_delta:+.3f}")
            confidence_reason = ", ".join(reason_bits)
            confidence_breakdown = {
                "magnitude_s1": round(s1, 3),
                "exon_support_s2": round(s2, 3),
                "window_consistency_s3": round(s3, 3),
                "short_window_boost": 0.10 if (w_used and w_used<=1024 and isinstance(exon_delta,(int,float)) and ((exon_delta==0 and min_delta==0) or (exon_delta*min_delta>0)) and abs(exon_delta)>=0.8*abs(min_delta)) else 0.0,
                "consistency_boost": 0.05 if s3>=0.7 else 0.0,
                "final_confidence": confidence,
            }
            confidence_explanation = (
                f"Confidence combines magnitude (s1={s1:.2f}), exon corroboration (s2={s2:.2f}), window consistency (s3={s3:.2f}), "
                f"plus boosts ({confidence_breakdown['short_window_boost']:+.2f}, {confidence_breakdown['consistency_boost']:+.2f})."
            )

            # Policy v1.1: interpretation gating based on magnitude + confidence
            abs_min = abs(min_delta)
            abs_exon = abs(exon_delta) if isinstance(exon_delta, (int, float)) else 0.0
            magnitude_ok = (abs_min >= 0.02) or (abs_exon >= 0.02)
            neutral_zone = (abs_min < 0.005) and (abs_exon < 0.005)
            interpretation = "unknown"
            if confidence >= 0.6 and magnitude_ok and ((min_delta < 0) or (isinstance(exon_delta, (int,float)) and exon_delta < 0)):
                interpretation = "pathogenic"
            elif confidence >= 0.6 and neutral_zone:
                interpretation = "benign"
            else:
                interpretation = "unknown"

            # ClinVar context (best-effort) for prior
            clinvar_class = None
            clinvar_review = None
            try:
                ctx = await clinvar_context({"url": f"https://www.ncbi.nlm.nih.gov/clinvar/?term={chrom_part}%3A{pos}%20{str(ref).upper()}%3E{str(alt).upper()}"})
                clinvar_class = ctx.get("clinical_significance")
                clinvar_review = ctx.get("review_status")
            except Exception:
                clinvar_class = None

            impact_level = 3.0 if zeta <= -10 else 2.0 if zeta <= -3 else 1.0 if zeta <= -0.5 else 0.5
            # Rationale (initial synthesizer)
            rationale = (
                f"Zeta {zeta:+.3f}; minΔ {min_delta:+.3f} (w={multi.get('window_used')}); "
                f"exonΔ {exon_delta:+.3f} if numeric; windows {'consistent' if s3>=0.7 else 'variable'}; "
                f"confidence {confidence:.2f}"
            )

            detailed.append({
                "gene": gene,
                "variant": f"{gene} {hgvs_p}",
                "chrom": chrom_part,
                "pos": pos,
                "calculated_impact_level": impact_level,
                "evo2_result": {
                    "interpretation": interpretation,
                    "zeta_score": zeta,
                    "min_delta": multi.get("min_delta"),
                    "window_used": multi.get("window_used"),
                    "exon_delta": exon.get("exon_delta"),
                    "confidence_score": confidence,
                    "confidence_reason": confidence_reason,
                    "confidence_explanation": confidence_explanation,
                    "confidence_breakdown": confidence_breakdown,
                    "rationale": rationale,
                    "confidence_boost": round(confidence_boost, 2) if confidence_boost else 0.0,
                    "clinvar_classification": clinvar_class,
                    "clinvar_review_status": clinvar_review,
                    "gating": {
                        "magnitude_ok": magnitude_ok,
                        "neutral_zone": neutral_zone,
                        "confidence_ok": confidence >= 0.6,
                    },
                },
                "selected_model": model_id,
                "original_variant_data": {
                    **m,
                    "variant_info": f"chr{chrom_part}:{pos} {str(ref).upper()}>{str(alt).upper()}"
                },
            })

    # Policy v1.1: deduplicate variants by (gene,chrom,pos,ref,alt)
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for d in detailed:
        vi = (d.get("original_variant_data") or {}).get("variant_info", "")
        key = (str(d.get("gene")).upper(), str(d.get("chrom")), int(d.get("pos") or 0), vi.split(" ")[-1] if " " in vi else vi)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(d)

    # Weighted pathway aggregation
    HOTSPOTS = {
        ("BRAF", "p.Val600Glu"), ("KRAS", "p.Gly12Asp"), ("KRAS", "p.Gly12Val"), ("KRAS", "p.Gly12Cys"),
        ("NRAS", "p.Gln61Lys"), ("NRAS", "p.Gln61Arg"),
    }
    def _is_hotspot(row: Dict[str, Any]) -> bool:
        try:
            gene_u = (row.get("gene") or "").upper()
            hgvs_p = (row.get("variant") or "").split(" ")[1]
            return (gene_u, hgvs_p) in HOTSPOTS
        except Exception:
            return False
    def variant_weight(row: Dict[str, Any]) -> float:
        evo = row.get("evo2_result") or {}
        conf = float(evo.get("confidence_score") or 0.0)
        md = evo.get("min_delta") or 0.0
        exd = evo.get("exon_delta") or 0.0
        eff = max(abs(md if isinstance(md,(int,float)) else 0.0), abs(exd if isinstance(exd,(int,float)) else 0.0))
        eff_scaled = min(eff, 0.05) / 0.05
        # Hotspot relaxation: small confidence boost if exon corroborates
        if hotspot_relaxation and _is_hotspot(row):
            try:
                same_sign = (isinstance(exd,(int,float)) and ((exd*md)>0 or (exd==0 and md==0)))
                if same_sign:
                    conf = min(1.0, conf + 0.10)
            except Exception:
                pass
        base = conf * eff_scaled
        # Optional bounded ClinVar prior
        prior = 0.0
        if use_priors:
            try:
                cls = str((evo.get("clinvar_classification") or "")).lower().replace(" ", "_")
                if cls in ("pathogenic", "likely_pathogenic"):
                    prior = 0.30
            except Exception:
                prior = 0.0
        return base + prior

    summed_ras = 0.0
    summed_tp53 = 0.0
    for d in deduped:
        gene_u = (d.get("gene") or "").upper()
        w = variant_weight(d)
        if gene_u in ("KRAS", "NRAS", "BRAF"):
            summed_ras += 1.3 * w
        else:
            summed_ras += 0.6 * w  # non-RAS contribution (lightly weighted)
        if gene_u == "TP53":
            summed_tp53 += 0.7 * w
        else:
            summed_tp53 += 0.3 * w
    summed_ras = round(summed_ras, 2)
    summed_tp53 = round(summed_tp53, 2)

    prediction_label = "Likely Resistant" if summed_ras >= 2.0 else "Likely Sensitive"

    threshold_config = {
        "ras_threshold": 2.0,
        "weights": {"KRAS": 1.3, "NRAS": 1.3, "BRAF": 1.3, "OTHER": 0.6, "TP53": 0.7},
        "policy": {
            "version": "v1.2",
            "gating": {"conf_min": 0.6, "min_delta_mag": 0.02, "exon_delta_mag": 0.02, "neutral_epsilon": 0.005,
                        "adaptive_boost": {"short_window_corroborated": 0.10, "high_consistency": 0.05}},
            "aggregation": {"eff_cap": 0.05, "score": "confidence*clamp(max(|minΔ|,|exonΔ|),0,0.05)/0.05 + clinvar_prior",
                             "clinvar_prior": 0.30, "prior_condition": "classification in {Pathogenic, Likely pathogenic}"}
        }
    }
    run_signature = sha256(json.dumps({"model_id": model_id, "mutations": mutations}, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    response = {
        "prediction": prediction_label,
        "summed_impact_ras_pathway": summed_ras,
        "summed_impact_tp53": summed_tp53,
        "pathway_scores": {
            "summed_impact_ras_pathway": summed_ras,
            "summed_impact_tp53": summed_tp53
        },
        "detailed_analysis": deduped,
        "mode": "live",
        "upstream_service": base_url,
        "selected_model": model_id,
        "threshold_config": threshold_config,
        "run_signature": run_signature,
        "use_case_id": "myeloma",
        "policy_version": "v1.2",
        "preflight_issues": preflight_issues,
    }

    # Optional dual-model comparison (7B vs 40B)
    dual_compare = bool((request or {}).get("dual_compare", False))
    alt_model = None
    if dual_compare:
        alt_model = "evo2_40b" if model_id.lower() == "evo2_7b" else "evo2_7b"
        alt_base = _choose_base(alt_model)
        compare_rows = []
        agree = 0
        total = 0
        async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
            for d in detailed:
                try:
                    chrom = d.get("chrom"); pos = d.get("pos")
                    vi = (d.get("original_variant_data") or {}).get("variant_info", "")
                    parts = vi.split()
                    if len(parts) < 2:
                        continue
                    ref, alt = parts[1].split(">")
                    payload = {"assembly": "GRCh38", "chrom": str(chrom), "pos": int(pos), "ref": ref, "alt": alt}
                    r_multi = await client.post(f"{alt_base}/score_variant_multi", json={**payload, "windows": [1024,2048,4096,8192]})
                    r_multi.raise_for_status(); multi2 = r_multi.json()
                    r_exon = await client.post(f"{alt_base}/score_variant_exon", json={**payload, "flank": 600})
                    r_exon.raise_for_status(); exon2 = r_exon.json()
                    # minimal confidence calc
                    min_delta2 = float(multi2.get("min_delta"))
                    deltas = [x.get("delta") for x in (multi2.get("deltas") or []) if isinstance(x.get("delta"), (int,float))]
                    if len(deltas) >= 2:
                        mean = sum(deltas)/len(deltas); var = sum((x-mean)**2 for x in deltas)/(len(deltas)-1); import math as _m; sdev = _m.sqrt(var)
                        s3 = max(0.0, min(1.0, 1.0 - (sdev/max(0.05, abs(min_delta2)))))
                    else:
                        s3 = 0.5
                    ex = exon2.get("exon_delta"); same_sign = (isinstance(ex,(int,float)) and ex*min_delta2>0) or (ex==0 and min_delta2==0)
                    s2 = 1.0 if (isinstance(ex,(int,float)) and same_sign and abs(ex)>=abs(min_delta2)) else (0.5 if same_sign else 0.0)
                    s1 = max(0.0, min(1.0, abs(min_delta2)/0.5))
                    conf2 = 0.5*s1 + 0.3*s2 + 0.2*s3
                    # call mapping
                    call1 = _variant_call_from_detail(d)
                    call2 = "Unknown" if conf2 < 0.4 else ("Likely Disruptive" if min_delta2 < -1.0 else "Likely Neutral")
                    compare_rows.append({
                        "gene": d.get("gene"),
                        "chrom": chrom, "pos": pos,
                        "selected_call": call1,
                        "alt_call": call2,
                    })
                    total += 1
                    if call1 == call2:
                        agree += 1
                except Exception:
                    continue
        response["dual_compare"] = {
            "alt_model": alt_model,
            "agree_rate": (agree/total if total else None),
            "comparisons": compare_rows,
        }

    # Fire-and-forget Supabase logging
    try:
        if SUPABASE_URL and SUPABASE_KEY:
            ts = int(time.time())
            run_row = [{
                "run_signature": run_signature,
                "model_id": model_id,
                "prediction": prediction_label,
                "ras_sum": summed_ras,
                "tp53_sum": summed_tp53,
                "num_variants": len(detailed),
                "upstream": base_url,
                "alt_model": alt_model,
                "agree_rate": (response.get("dual_compare") or {}).get("agree_rate"),
                "created_at": ts,
            }]
            variant_rows = []
            for d in detailed:
                evo = d.get("evo2_result") or {}
                # simple discordance flag using evo-provided ClinVar label
                cls = (evo.get("clinvar_classification") or "").lower().replace(" ", "_")
                interp = (evo.get("interpretation") or "").lower()
                confv = float(evo.get("confidence_score") or 0.0)
                our_is_path = (interp in ("pathogenic", "likely pathogenic", "disruptive")) and confv >= 0.6
                clin_is_path = cls in ("pathogenic", "likely_pathogenic")
                discordant = (our_is_path != clin_is_path)
                variant_rows.append({
                    "run_signature": run_signature,
                    "gene": d.get("gene"),
                    "chrom": d.get("chrom"),
                    "pos": d.get("pos"),
                    "zeta": evo.get("zeta_score"),
                    "min_delta": evo.get("min_delta"),
                    "exon_delta": evo.get("exon_delta"),
                    "confidence": evo.get("confidence_score"),
                    "call": _variant_call_from_detail(d),
                    "clinvar_classification": evo.get("clinvar_classification"),
                    "discordant": discordant,
                    "priors_used": use_priors,
                    "raw": json.dumps(d)[:8000],
                    "created_at": ts,
                })
            asyncio.create_task(_supabase_insert(SUPABASE_RUNS_TABLE, run_row))
            if variant_rows:
                asyncio.create_task(_supabase_insert(SUPABASE_RUN_VARIANTS_TABLE, variant_rows))
    except Exception:
        pass

    return response

# Use-case discovery and unified predict endpoints
@app.get("/api/use_cases")
async def list_use_cases():
    return {"use_cases": list(USE_CASES.values())}

@app.get("/api/use_cases/{use_case_id}")
async def get_use_case(use_case_id: str):
    cfg = USE_CASES.get((use_case_id or "").lower())
    if not cfg:
        raise HTTPException(status_code=404, detail="use_case not found")
    return cfg

@app.post("/api/predict")
async def predict_generic(request: Dict[str, Any]):
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    use_case_id = (request.get("use_case_id") or "myeloma").lower()
    if use_case_id != "myeloma":
        raise HTTPException(status_code=400, detail="unsupported use_case_id for now")
    model_id = request.get("model_id", "evo2_7b")
    mutations = request.get("mutations")
    if not isinstance(mutations, list) or not mutations:
        raise HTTPException(status_code=400, detail="mutations[] required")
    # Optional dual compare flag in options
    options = request.get("options") or {}
    req2: Dict[str, Any] = {"model_id": model_id, "mutations": mutations}
    if bool(options.get("dual_compare")):
        req2["dual_compare"] = True
    result = await predict_myeloma_response(req2)  # type: ignore
    if isinstance(result, dict):
        result.setdefault("use_case_id", "myeloma")
        result.setdefault("policy_version", "v1")
    return result

@app.post("/api/workflow/run_seed_soil_analysis")
async def run_seed_soil_analysis(request: Dict[str, Any]):
    """Seed & Soil metastatic analysis"""
    return {
        "metastatic_potential": {
            "score": 0.73,
            "target_organs": ["liver", "lung", "bone"],
            "intervention_targets": ["VEGF", "PDGF"]
        }
    }

EVO_SERVICE_URL = os.getenv("EVO_SERVICE_URL", "https://crispro--evo-service-evoservice-api.modal.run").strip()
EVO_URL_1B = os.getenv("EVO_URL_1B", "").strip()
EVO_URL_7B = os.getenv("EVO_URL_7B", "https://crispro--evo-service-evoservice7b-api-7b.modal.run").strip()
EVO_URL_40B = os.getenv("EVO_URL_40B", EVO_SERVICE_URL).strip()
# Import DEFAULT_EVO_MODEL from centralized config
from api.config import DEFAULT_EVO_MODEL
EVO_TIMEOUT = Timeout(600.0, connect=30.0, read=600.0, write=600.0)

MODEL_TO_BASE = {
    "evo2_1b": lambda: EVO_URL_1B or EVO_URL_7B or EVO_URL_40B,
    "evo2_7b": lambda: EVO_URL_7B or EVO_URL_40B,
    "evo2_40b": lambda: EVO_URL_40B,
}

# Helper to choose base URL
def _choose_base(model_id: str) -> str:
    mid = (model_id or "evo2_7b").lower()
    sel = MODEL_TO_BASE.get(mid, MODEL_TO_BASE["evo2_7b"])()
    if not sel:
        raise HTTPException(status_code=500, detail="No Evo2 base URL configured")
    return sel

@app.post("/api/evo/score_delta")
async def evo_score_delta(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_delta", json=request)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

@app.post("/api/evo/score_batch")
async def evo_score_batch(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_batch", json=request)
            r.raise_for_status()
            return r.json()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

@app.post("/api/evo/score_variant")
async def evo_score_variant(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_variant", json=request)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data.update({"mode": "live", "selected_model": model_id, "upstream_service": base})
            return data
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

@app.post("/api/evo/score_variant_multi")
async def evo_score_variant_multi(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_variant_multi", json=request)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data.update({"mode": "live", "selected_model": model_id, "upstream_service": base})
            return data
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

@app.post("/api/evo/score_variant_exon")
async def evo_score_variant_exon(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_variant_exon", json=request)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data.update({"mode": "live", "selected_model": model_id, "upstream_service": base})
            return data
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

@app.post("/api/evo/warmup")
async def evo_warmup(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    import time
    t0 = time.time()
    payload = {"ref_sequence": "AAAAAA", "alt_sequence": "AAACAA", "model_id": model_id}
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_delta", json=payload)
            r.raise_for_status()
            _ = r.json()
            return {"status": "ready", "selected_model": model_id, "upstream_service": base, "elapsed_sec": round(time.time()-t0, 2)}
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Warmup failed: {e}")

@app.post("/api/evo/score_variant_profile")
async def evo_score_variant_profile(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_variant_profile", json=request)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data.update({"mode": "live", "selected_model": model_id, "upstream_service": base})
            return data
        except Exception as e:
            body = getattr(getattr(e, 'response', None), 'text', None)
            msg = f"Upstream error: {e}"
            if body:
                msg += f" | body={body[:400]}"
            raise HTTPException(status_code=502, detail=msg)

@app.post("/api/evo/score_variant_probe")
async def evo_score_variant_probe(request: Dict[str, Any]):
    model_id = (request or {}).get("model_id", "evo2_7b") if isinstance(request, dict) else "evo2_7b"
    base = _choose_base(model_id)
    async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
        try:
            r = await client.post(f"{base}/score_variant_probe", json=request)
            r.raise_for_status()
            data = r.json()
            if isinstance(data, dict):
                data.update({"mode": "live", "selected_model": model_id, "upstream_service": base})
            return data
        except httpx.HTTPError as e:
            body = getattr(getattr(e, 'response', None), 'text', None)
            msg = f"Upstream error: {e}"
            if body:
                msg += f" | body={body[:400]}"
            raise HTTPException(status_code=502, detail=msg)

@app.post("/api/evo/refcheck")
async def evo_refcheck(request: Dict[str, Any]):
    """Lightweight REF allele validation via Ensembl.
    Input: { assembly:"GRCh38|GRCh37", chrom:"7", pos:140753336, ref:"A" }
    Output: { ok: bool, fetched: str, expected: str, assembly, chrom, pos }
    """
    try:
        asm_in = (request or {}).get("assembly", "GRCh38")
        chrom = str((request or {}).get("chrom"))
        pos = int((request or {}).get("pos"))
        ref = str((request or {}).get("ref", "")).upper()
        asm = "GRCh38" if str(asm_in).lower() in ("grch38","hg38") else "GRCh37"
        region = f"{chrom}:{pos}-{pos}:1"
        url = f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}"
        with httpx.Client(timeout=15) as client:
            r = client.get(url)
            r.raise_for_status()
            base = r.text.strip().upper()
        ok = bool(base) and (base == ref or base == "N")
        return {"ok": ok, "fetched": base, "expected": ref, "assembly": asm, "chrom": chrom, "pos": pos}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"refcheck failed: {e}")

@app.post("/api/evo/refcheck_batch")
async def evo_refcheck_batch(request: Dict[str, Any]):
    """Batch REF allele validation. Input: { items: [{assembly,chrom,pos,ref}, ...] }"""
    try:
        items = (request or {}).get("items") or []
        if not isinstance(items, list) or not items:
            raise HTTPException(status_code=400, detail="items[] required")
        out = []
        with httpx.Client(timeout=15) as client:
            for it in items:
                asm_in = it.get("assembly", "GRCh38")
                chrom = str(it.get("chrom"))
                pos = int(it.get("pos"))
                ref = str(it.get("ref", "")).upper()
                asm = "GRCh38" if str(asm_in).lower() in ("grch38","hg38") else "GRCh37"
                region = f"{chrom}:{pos}-{pos}:1"
                url = f"https://rest.ensembl.org/sequence/region/human/{region}?content-type=text/plain;coord_system_version={asm}"
                try:
                    r = client.get(url)
                    r.raise_for_status()
                    base = r.text.strip().upper()
                    ok = bool(base) and (base == ref or base == "N")
                    out.append({"ok": ok, "fetched": base, "expected": ref, "assembly": asm, "chrom": chrom, "pos": pos})
                except Exception as e:
                    out.append({"ok": False, "error": str(e), "assembly": asm, "chrom": chrom, "pos": pos, "expected": ref})
        return {"results": out}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"refcheck_batch failed: {e}")

@app.post("/api/twin/run")
async def twin_run(request: Dict[str, Any]):
    """Orchestrator: warm model, run scoring (chunked inside predict), emit Supabase events, return full results."""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    model_id = request.get("model_id", "evo2_7b")
    mutations = request.get("mutations")
    if not isinstance(mutations, list) or not mutations:
        raise HTTPException(status_code=400, detail="mutations[] required")
    dual_compare = bool(request.get("dual_compare", False))

    run_signature = sha256(json.dumps({"model_id": model_id, "mutations": mutations, "dual_compare": dual_compare}, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    # Emit start
    asyncio.create_task(_supabase_event(run_signature, "start", f"model={model_id}; n={len(mutations)}; dual={dual_compare}"))

    # Warmup
    try:
        base = _choose_base(model_id)
        async with httpx.AsyncClient(timeout=EVO_TIMEOUT, follow_redirects=True) as client:
            payload = {"ref_sequence": "AAAAAA", "alt_sequence": "AAACAA", "model_id": model_id}
            r = await client.post(f"{base}/score_delta", json=payload)
            r.raise_for_status()
        asyncio.create_task(_supabase_event(run_signature, "warmup_done", base))
    except Exception as e:
        asyncio.create_task(_supabase_event(run_signature, "warmup_error", str(e)))

    # Run scoring by invoking the internal logic
    try:
        # Reuse existing endpoint logic directly
        req2 = {"model_id": model_id, "mutations": mutations}
        if dual_compare:
            req2["dual_compare"] = True
        result = await predict_myeloma_response(req2)  # type: ignore
        # Tag run_signature for provenance
        if isinstance(result, dict):
            result.setdefault("run_signature", run_signature)
        asyncio.create_task(_supabase_event(run_signature, "scoring_done", f"variants={len(result.get('detailed_analysis') or [])}"))
    except Exception as e:
        asyncio.create_task(_supabase_event(run_signature, "scoring_error", str(e)))
        raise

    # Complete
    asyncio.create_task(_supabase_event(run_signature, "complete", "ok"))
    return result

@app.post("/api/twin/submit")
async def twin_submit(request: Dict[str, Any]):
    """Submit a Digital Twin job and return run_signature; processing happens in background."""
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    model_id = request.get("model_id", "evo2_7b")
    mutations = request.get("mutations")
    if not isinstance(mutations, list) or not mutations:
        raise HTTPException(status_code=400, detail="mutations[] required")
    dual_compare = bool(request.get("dual_compare", False))

    run_signature = sha256(json.dumps({"model_id": model_id, "mutations": mutations, "dual_compare": dual_compare}, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    # Queue job
    try:
        asyncio.create_task(_supabase_event(run_signature, "queued", f"model={model_id}; n={len(mutations)}; dual={dual_compare}"))
        # Fire the orchestrator in background
        asyncio.create_task(twin_run({"model_id": model_id, "mutations": mutations, "dual_compare": dual_compare}))
    except Exception:
        pass
    return {"run_signature": run_signature, "status": "queued"}

@app.post("/api/twin/status")
async def twin_status(request: Dict[str, Any]):
    """Fetch job status: events and summary for a given run_signature."""
    if not isinstance(request, dict) or not request.get("run_signature"):
        raise HTTPException(status_code=400, detail="run_signature required")
    rs = request["run_signature"]
    # Fetch events (ascending by t)
    events = await _supabase_select(SUPABASE_EVENTS_TABLE, {"run_signature": rs}, order="t.asc", limit=1000)
    # Fetch run summary if available
    runs = await _supabase_select(SUPABASE_RUNS_TABLE, {"run_signature": rs}, limit=1)
    summary = runs[0] if runs else None
    state = (events[-1]["stage"] if events else "unknown")
    return {"run_signature": rs, "state": state, "events": events, "summary": summary}

@app.get("/api/analytics/dashboard")
async def analytics_dashboard():
    """
    Provide analytics dashboard data from Supabase if configured.
    Returns summary metrics, time series, and recent runs. Gracefully handles missing envs.
    """
    try:
        if not SUPABASE_URL or not SUPABASE_KEY:
            return {
                "summary": {"total_runs": 0, "avg_auroc": None, "avg_agree_rate": None, "avg_latency_ms": None},
                "time_series": [],
                "model_comparison": [],
                "recent_runs": []
            }
        # fetch recent runs
        runs = await _supabase_select(SUPABASE_RUNS_TABLE, eq={}, order="created_at.desc", limit=200)
        total_runs = len(runs)
        # averages
        def _avg(vals):
            vals2 = [v for v in vals if isinstance(v, (int, float))]
            return (sum(vals2) / len(vals2)) if vals2 else None
        avg_auroc = _avg([r.get("auroc") for r in runs])
        avg_agree_rate = _avg([r.get("agree_rate") for r in runs])
        avg_latency_ms = _avg([r.get("latency_ms") for r in runs])
        summary = {
            "total_runs": total_runs,
            "avg_auroc": avg_auroc,
            "avg_agree_rate": avg_agree_rate,
            "avg_latency_ms": avg_latency_ms,
        }
        # time series (by date from epoch or iso)
        from datetime import datetime
        daily = {}
        for r in runs:
            ts = r.get("created_at")
            try:
                if isinstance(ts, (int, float)):
                    d = datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d")
                elif isinstance(ts, str) and len(ts) >= 10:
                    d = ts[:10]
                else:
                    continue
            except Exception:
                continue
            daily.setdefault(d, {"aurocs": [], "agree_rates": []})
            if isinstance(r.get("auroc"), (int, float)):
                daily[d]["aurocs"].append(r["auroc"]) 
            if isinstance(r.get("agree_rate"), (int, float)):
                daily[d]["agree_rates"].append(r["agree_rate"])
        time_series = []
        for d, m in sorted(daily.items()):
            time_series.append({
                "date": d,
                "auroc": _avg(m["aurocs"]),
                "agree_rate": _avg(m["agree_rates"]),
            })
        # model comparison
        model_map: Dict[str, Dict[str, List[float]]] = {}
        for r in runs:
            mid = (r.get("model_id") or "unknown")
            mm = model_map.setdefault(mid, {"aurocs": [], "agree_rates": []})
            if isinstance(r.get("auroc"), (int, float)):
                mm["aurocs"].append(r["auroc"])
            if isinstance(r.get("agree_rate"), (int, float)):
                mm["agree_rates"].append(r["agree_rate"])
        model_comparison = []
        for mid, mm in model_map.items():
            model_comparison.append({
                "model": mid,
                "auroc": _avg(mm["aurocs"]),
                "agree_rate": _avg(mm["agree_rates"]),
            })
        # recent runs
        recent_runs = runs[:10]
        return {
            "summary": summary,
            "time_series": time_series,
            "model_comparison": model_comparison,
            "recent_runs": recent_runs,
        }
    except Exception:
        return {
            "summary": {"total_runs": 0, "avg_auroc": None, "avg_agree_rate": None, "avg_latency_ms": None},
            "time_series": [],
            "model_comparison": [],
            "recent_runs": []
        }

@app.post("/api/evidence/deep_analysis")
async def deep_analysis(request: Dict[str, Any]):
    """Fetch ClinVar context and compare with our call.
    Input: { gene, hgvs_p, assembly, chrom, pos, ref, alt, clinvar_url?, our_interpretation?, our_confidence? }
    Output: { clinvar: { classification, counts:{...}, somatic_tier?, url }, our_call:{...}, discordant: bool, provenance }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        gene = (request.get("gene") or "").upper()
        hgvs_p = request.get("hgvs_p") or ""
        chrom = str(request.get("chrom") or "")
        pos = int(request.get("pos") or 0)
        ref = str(request.get("ref") or "").upper()
        alt = str(request.get("alt") or "").upper()
        asm_in = request.get("assembly") or "GRCh38"
        asm = "GRCh38" if str(asm_in).lower() in ("grch38","hg38") else "GRCh37"
        clinvar_url = request.get("clinvar_url") or f"https://www.ncbi.nlm.nih.gov/clinvar/?term={chrom}%3A{pos}%20{ref}%3E{alt}"

        classification = None
        counts: Dict[str, Any] = {}
        review_status = None
        somatic_tier = None
        resolved_url = clinvar_url
        clinvar_source = "coordinate"

        # 1) Prefer resolving Variation ID via gene+hgvs_p when available
        if gene and hgvs_p:
            try:
                search_url = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={gene}%20{hgvs_p}"
                with httpx.Client(timeout=20, follow_redirects=True) as client:
                    rs = client.get(search_url)
                    if rs.status_code == 200:
                        import re as _re
                        m = _re.search(r"/clinvar/variation/(\d+)/", rs.text)
                        if m:
                            var_id = int(m.group(1))
                            ctx_by_id = await clinvar_context({"variation_id": var_id})
                            if ctx_by_id:
                                classification = ctx_by_id.get("clinical_significance")
                                counts = ctx_by_id.get("counts") or {}
                                review_status = ctx_by_id.get("review_status")
                                somatic_tier = ctx_by_id.get("somatic_tier")
                                resolved_url = ctx_by_id.get("url") or resolved_url
                                clinvar_source = "variation_id"
            except Exception:
                pass

        # 2) Fallback to coordinate URL if still missing
        if not classification:
            try:
                ctx = await clinvar_context({"url": clinvar_url})
                if ctx:
                    classification = ctx.get("clinical_significance") or classification
                    counts = ctx.get("counts") or counts
                    review_status = ctx.get("review_status") or review_status
                    somatic_tier = ctx.get("somatic_tier") or somatic_tier
                    resolved_url = ctx.get("url") or resolved_url
                    if clinvar_source == "coordinate":
                        clinvar_source = "coordinate"
            except Exception:
                pass

        our_call = {
            "interpretation": request.get("our_interpretation"),
            "confidence": request.get("our_confidence"),
        }
        discordant = False
        clin_is_path = None
        our_is_path = None
        if our_call.get("interpretation") and classification:
            our_is_path = str(our_call["interpretation"]).lower() in ("pathogenic","likely pathogenic","disruptive")
            clin_is_path = classification in ("pathogenic","likely_pathogenic")
            discordant = (our_is_path != clin_is_path)

        # Discrepancy analysis
        discrepancy_reason = None
        confidence_gap = None
        try:
            if classification and our_call.get("confidence") is not None:
                c = float(our_call.get("confidence") or 0.0)
                review_level = (review_status or "").lower()
                strong_review = ("expert" in review_level) or ("practice" in review_level)
                moderate_review = ("criteria" in review_level)
                if discordant:
                    if not strong_review and c < 0.6:
                        discrepancy_reason = "low_model_confidence_and_weak_clinvar_review"
                    elif strong_review and c < 0.6:
                        discrepancy_reason = "low_model_confidence_vs_strong_clinvar"
                    elif strong_review and c >= 0.6:
                        discrepancy_reason = "model_disagrees_with_strong_clinvar"
                    elif moderate_review and c >= 0.6:
                        discrepancy_reason = "model_disagrees_with_moderate_clinvar"
                    else:
                        discrepancy_reason = "unknown"
                confidence_gap = round(max(0.0, 0.7 - c), 3)
        except Exception:
            discrepancy_reason = discrepancy_reason or "analysis_error"

        result = {
            "clinvar": {
                "classification": classification,
                "counts": counts,
                "somatic_tier": somatic_tier,
                "url": resolved_url,
                "review_status": review_status,
                "source": clinvar_source,
            },
            "our_call": our_call,
            "discordant": discordant,
            "discrepancy_reason": discrepancy_reason,
            "confidence_gap": confidence_gap,
            "provenance": {"assembly": asm, "chrom": chrom, "pos": pos, "ref": ref, "alt": alt},
            "our_interpretation": our_call.get("interpretation"),
            "our_confidence": our_call.get("confidence"),
        }
        
        # Persist deep analysis result to Supabase
        try:
            if SUPABASE_URL and SUPABASE_KEY:
                ts = int(time.time())
                deep_analysis_row = {
                    "run_signature": f"{gene}_{hgvs_p}_{ts}",
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "assembly": asm,
                    "chrom": chrom,
                    "pos": pos,
                    "ref": ref,
                    "alt": alt,
                    "clinvar_classification": classification,
                    "clinvar_source": clinvar_source,
                    "our_interpretation": our_call.get("interpretation"),
                    "our_confidence": our_call.get("confidence"),
                    "discordant": discordant,
                    "discrepancy_reason": discrepancy_reason,
                    "confidence_gap": confidence_gap,
                    "result_json": json.dumps(result)[:8000],
                    "created_at": ts,
                }
                asyncio.create_task(_supabase_insert(SUPABASE_DEEP_ANALYSIS_TABLE, [deep_analysis_row]))
        except Exception:
            pass
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"deep_analysis failed: {e}")

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
    """Return ClinVar context for a variant via Variation ID or URL fallback.
    Input: { variation_id?: int, url?: str, chrom?, pos?, ref?, alt? }
    """
    try:
        variation_id = request.get("variation_id")
        url = request.get("url")
        chrom = str(request.get("chrom") or "")
        pos = request.get("pos")
        ref = str(request.get("ref") or "").upper()
        alt = str(request.get("alt") or "").upper()
        if not url and variation_id:
            url = f"https://www.ncbi.nlm.nih.gov/clinvar/variation/{variation_id}/"
        if not url and chrom and pos and ref and alt:
            url = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={chrom}%3A{pos}%20{ref}%3E{alt}"
        if not url:
            raise HTTPException(status_code=400, detail="Provide variation_id or url or coordinate+alleles")
        text = ""
        with httpx.Client(timeout=25, follow_redirects=True) as client:
            try:
                r = client.get(url)
                if r.status_code == 200:
                    text = r.text
            except Exception:
                text = ""
        def _count(h, n):
            try: return h.lower().count(n.lower())
            except Exception: return 0
        counts = {
            "pathogenic": _count(text, "Pathogenic"),
            "likely_pathogenic": _count(text, "Likely pathogenic"),
            "vus": _count(text, "Uncertain significance"),
            "benign": _count(text, "Benign"),
            "likely_benign": _count(text, "Likely benign"),
        }
        review_status = None
        if "Reviewed by expert panel" in text:
            review_status = "expert_panel"
        elif "criteria provided" in text:
            review_status = "criteria_provided"
        somatic_tier = "Tier I" if "Tier I" in text else ("Tier II" if "Tier II" in text else None)
        classification = None
        if any(v > 0 for v in counts.values()):
            classification = max(counts.items(), key=lambda kv: kv[1])[0]
        return {
            "variation_id": variation_id,
            "clinical_significance": classification,
            "review_status": review_status,
            "somatic_tier": somatic_tier,
            "counts": counts,
            "url": url,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"clinvar_context failed: {e}")

@app.post("/api/evidence/literature")
async def evidence_literature(request: Dict[str, Any]):
    """Search and rank PubMed evidence via PubMed LLM Agent.
    Input: { gene, hgvs_p, disease, time_window?: str, max_results?: int, include_abstracts?: bool, synthesize?: bool }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        gene = (request.get("gene") or "").strip()
        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        time_window = (request.get("time_window") or "since 2015").strip()
        max_results = int(request.get("max_results") or 10)
        include_abstracts = bool(request.get("include_abstracts", False))
        synthesize = bool(request.get("synthesize", False))
        # Import agent
        agent_dir = Path(__file__).resolve().parent.parent / "Pubmed-LLM-Agent-main"
        sys.path.append(str(agent_dir))
        try:
            from pubmed_llm_agent import run_pubmed_search  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=501, detail=f"literature agent unavailable: {e}")
        query = f"{gene} {hgvs_p} {disease} {time_window}"
        try:
            result = run_pubmed_search(
                query=query,
                max_results=max_results,
                top_k=max_results,
                pmc_only=False,
                llm_rerank=False,
                batch_size=50,
                no_abstracts=not include_abstracts,
                only_trials=False,
                extra_filters=None,
                llm_model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"),
                pubmed_email=os.getenv("NCBI_EMAIL"),
                pubmed_api_key=os.getenv("NCBI_API_KEY"),
                llm_api_key=os.getenv("GEMINI_API_KEY"),
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"literature search failed: {e}")
        # Shape top results, optionally include abstracts
        tops = []
        for r in (result.get("results") or [])[:max_results]:
            tops.append({
                "pmid": r.get("pmid"),
                "pmcid": r.get("pmcid"),
                "title": r.get("title"),
                "year": r.get("year"),
                "journal": r.get("journal"),
                "relevance": r.get("relevance"),
                "relevance_reason": r.get("relevance_reason"),
                "abstract": (r.get("abstract") if include_abstracts else None),
                "license": r.get("license"),
                "publication_types": r.get("publication_types"),
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{r.get('pmid')}/" if r.get("pmid") else None,
            })
        payload: Dict[str, Any] = {
            "query": result.get("natural_query") or query,
            "pubmed_query": result.get("pubmed_query"),
            "total_found": result.get("total_found"),
            "returned_count": len(tops),
            "top_results": tops,
        }
        # Optional LLM synthesis over titles/abstracts
        if synthesize and tops:
            try:
                synthesis = None
                if genai and os.getenv("GEMINI_API_KEY"):
                    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
                    chunks = []
                    for t in tops[:5]:
                        line = f"- {t.get('title') or ''} ({t.get('journal') or 'n/a'}, {t.get('year') or 'n/a'})\n"
                        if include_abstracts and t.get("abstract"):
                            line += f"  Abstract: {str(t.get('abstract'))[:600]}\n"
                        chunks.append(line)
                    prompt = (
                        f"Summarize evidence for {gene} {hgvs_p} in {disease}. "
                        f"Focus on pathogenicity, mechanism, therapeutic relevance, and resistance.\n" + "\n".join(chunks)
                    )
                    resp = client.models.generate_content(model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"), contents=prompt)  # type: ignore
                    synthesis = getattr(resp, "text", None) or getattr(resp, "candidates", None)
                payload["evidence_synthesis"] = synthesis or None
            except Exception:
                payload["evidence_synthesis"] = None
        
        # Persist literature search results to Supabase
        try:
            if SUPABASE_URL and SUPABASE_KEY:
                ts = int(time.time())
                literature_row = {
                    "run_signature": f"{gene}_{hgvs_p}_lit_{ts}",
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "disease": disease,
                    "query": query,
                    "pubmed_query": result.get("pubmed_query"),
                    "total_found": result.get("total_found"),
                    "returned_count": len(tops),
                    "synthesis": payload.get("evidence_synthesis"),
                    "results_json": json.dumps(tops)[:8000],
                    "created_at": ts,
                }
                asyncio.create_task(_supabase_insert("mdt_literature_searches", [literature_row]))
        except Exception:
            pass
        
        return payload
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"literature search failed: {e}")

@app.post("/api/evidence/extract")
async def evidence_extract(request: Dict[str, Any]):
    """Extract article text via Diffbot.
    Input: { url: str }
    Output: { title, author, date, site_name, text, html, tags[] }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        if not DIFFBOT_TOKEN:
            raise HTTPException(status_code=501, detail="Diffbot not configured")
        url_in = (request.get("url") or "").strip()
        if not url_in:
            raise HTTPException(status_code=400, detail="url required")
        api_url = "https://api.diffbot.com/v3/article"
        params = {
            "token": DIFFBOT_TOKEN,
            "url": url_in,
            "fields": "title,author,date,siteName,tags,images,html,text",
        }
        with httpx.Client(timeout=30) as client:
            r = client.get(api_url, params=params)
            r.raise_for_status()
            js = r.json()
        obj = (js.get("objects") or [None])[0]
        if not obj:
            raise HTTPException(status_code=404, detail="no article found")
        return {
            "title": obj.get("title"),
            "author": obj.get("author"),
            "date": obj.get("date"),
            "site_name": obj.get("siteName"),
            "text": obj.get("text"),
            "html": obj.get("html"),
            "tags": obj.get("tags"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"extract failed: {e}")

@app.post("/api/evidence/explain")
async def evidence_explain(request: Dict[str, Any]):
    """LLM-generated explanation combining Evo2 metrics, ClinVar, and literature.
    Input: { gene, hgvs_p, evo2_result, clinvar?, literature? }
    Output: { explanation, used: { gene, hgvs_p, evo2, clinvar, top_results } }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        gene = (request.get("gene") or "").upper()
        hgvs_p = request.get("hgvs_p") or ""
        evo = request.get("evo2_result") or {}
        clin = request.get("clinvar") or {}
        lit = request.get("literature") or {}
        tops = (lit.get("top_results") or [])[:5]
        if not genai or not os.getenv("GEMINI_API_KEY"):
            raise HTTPException(status_code=501, detail="LLM not configured")
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
        def _fmt(x):
            try:
                return f"{float(x):.6f}"
            except Exception:
                return str(x)
        parts: List[str] = []
        parts.append(f"Variant: {gene} {hgvs_p}")
        parts.append(
            f"Zeta Δ={_fmt(evo.get('zeta_score'))}; minΔ={_fmt(evo.get('min_delta'))}; exonΔ={_fmt(evo.get('exon_delta'))}; confidence={_fmt(evo.get('confidence_score'))}"
        )
        if clin:
            parts.append(
                f"ClinVar: classification={clin.get('classification') or 'n/a'}; review={clin.get('review_status') or 'n/a'}"
            )
        if tops:
            parts.append("Top literature:")
            for t in tops:
                parts.append(f"- {t.get('title') or ''} ({t.get('journal') or 'n/a'}, {t.get('year') or 'n/a'}) PMID:{t.get('pmid') or 'n/a'}")
        prompt = (
            "You are an oncology variant analyst. Explain, step by step, what Evo2's sequence metrics imply, "
            "why the deltas may be small even for canonical hotspots, how policy gating (magnitude + confidence) works, "
            "and reconcile with ClinVar and recent literature. Be concise, structured, and explicit about uncertainty.\n\n" +
            "\n".join(parts) +
            "\n\nOutput sections: 1) Summary call (sequence-only), 2) Why small Δ, 3) ClinVar vs our call, 4) Literature highlights, 5) Recommendation (e.g., consider prior)."
        )
        resp = client.models.generate_content(model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"), contents=prompt)  # type: ignore
        text = getattr(resp, "text", None) or str(resp)
        
        result = {
            "explanation": text,
            "used": {
                "gene": gene,
                "hgvs_p": hgvs_p,
                "evo2": evo,
                "clinvar": clin,
                "top_results": tops,
            }
        }
        
        # Persist AI explanation to Supabase
        try:
            if SUPABASE_URL and SUPABASE_KEY:
                ts = int(time.time())
                explanation_row = {
                    "run_signature": f"{gene}_{hgvs_p}_explain_{ts}",
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "explanation": text[:8000],
                    "evo2_data": json.dumps(evo)[:2000],
                    "clinvar_data": json.dumps(clin)[:2000],
                    "literature_count": len(tops),
                    "prompt_hash": sha256(prompt.encode()).hexdigest()[:16],
                    "model_used": os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"),
                    "created_at": ts,
                }
                asyncio.create_task(_supabase_insert("mdt_ai_explanations", [explanation_row]))
        except Exception:
            pass
        
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"explain failed: {e}")

# Background agent endpoints for multi-step evidence orchestration

@app.post("/api/evidence/crawl")
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

@app.post("/api/evidence/summarize")
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

@app.post("/api/evidence/align")
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

@app.get("/api/evidence/job/{job_id}")
async def evidence_job_status(job_id: str):
    """Get the status of a background job.
    Output: { job_id, job_type, status, progress: {done, total}, result?, error?, created_at, updated_at }
    """
    try:
        if job_id not in JOBS:
            raise HTTPException(status_code=404, detail="job not found")
        return JOBS[job_id].to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"job status failed: {e}")

# Background job implementations

async def _run_crawl_job(job_id: str):
    """Background task to crawl URLs and extract full text."""
    try:
        job = JOBS[job_id]
        job.set_running()
        
        urls = job.payload["urls"]
        job.update_progress(0, len(urls))
        
        extracted = []
        for i, url in enumerate(urls):
            try:
                # Call the extract endpoint internally
                result = await evidence_extract({"url": url})
                extracted.append({
                    "url": url,
                    "title": result.get("title"),
                    "text": result.get("text"),
                    "author": result.get("author"),
                    "date": result.get("date"),
                    "site_name": result.get("site_name")
                })
                job.update_progress(i + 1)
            except Exception as e:
                extracted.append({
                    "url": url,
                    "error": str(e)
                })
                job.update_progress(i + 1)
        
        job.set_complete({"extracted_texts": extracted})
        
        # Persist to Supabase if configured
        if SUPABASE_URL:
            asyncio.create_task(_supabase_insert("mdt_job_results", [{
                "job_id": job_id,
                "job_type": "crawl",
                "result": job.result,
                "created_at": job.created_at
            }]))
            
    except Exception as e:
        JOBS[job_id].set_error(str(e))

async def _run_summarize_job(job_id: str):
    """Background task to summarize extracted texts."""
    try:
        job = JOBS[job_id]
        job.set_running()
        
        extracted_texts = job.payload["extracted_texts"]
        gene = job.payload.get("gene", "")
        variant = job.payload.get("variant", "")
        
        job.update_progress(0, len(extracted_texts))
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
        summaries = []
        
        for i, item in enumerate(extracted_texts):
            try:
                if item.get("error"):
                    summaries.append({
                        "url": item["url"],
                        "error": item["error"]
                    })
                else:
                    text = item.get("text", "")[:5000]  # Truncate for LLM
                    prompt = f"""Summarize this article for variant analysis of {gene} {variant}:
                    
Title: {item.get('title', 'N/A')}
Text: {text}

Focus on: 1) Clinical significance, 2) Functional impact, 3) Treatment implications, 4) Population data.
Be concise (max 200 words)."""
                    
                    resp = client.models.generate_content(
                        model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"), 
                        contents=prompt
                    )  # type: ignore
                    summary = getattr(resp, "text", None) or str(resp)
                    
                    summaries.append({
                        "url": item["url"],
                        "title": item.get("title"),
                        "summary": summary
                    })
                
                job.update_progress(i + 1)
            except Exception as e:
                summaries.append({
                    "url": item["url"],
                    "error": str(e)
                })
                job.update_progress(i + 1)
        
        job.set_complete({"summaries": summaries})
        
        # Persist to Supabase if configured
        if SUPABASE_URL:
            asyncio.create_task(_supabase_insert("mdt_job_results", [{
                "job_id": job_id,
                "job_type": "summarize",
                "result": job.result,
                "created_at": job.created_at
            }]))
            
    except Exception as e:
        JOBS[job_id].set_error(str(e))

async def _run_align_job(job_id: str):
    """Background task to align evidence with variant assessment."""
    try:
        job = JOBS[job_id]
        job.set_running()
        
        summaries = job.payload["summaries"]
        evo2_result = job.payload["evo2_result"]
        clinvar = job.payload["clinvar"]
        
        job.update_progress(0, 1)
        
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
        
        # Compile evidence
        evidence_text = "Literature summaries:\n"
        for s in summaries:
            if not s.get("error"):
                evidence_text += f"- {s.get('title', 'N/A')}: {s.get('summary', 'N/A')}\n"
        
        prompt = f"""As an oncology variant analyst, provide a final evidence alignment:

Evo2 Assessment:
- Zeta Score: {evo2_result.get('zeta_score', 'N/A')}
- Confidence: {evo2_result.get('confidence_score', 'N/A')}
- Interpretation: {evo2_result.get('interpretation', 'N/A')}

ClinVar:
- Classification: {clinvar.get('classification', 'N/A')}
- Review Status: {clinvar.get('review_status', 'N/A')}

{evidence_text}

Provide:
1) Evidence alignment score (0-100)
2) Recommendation (agree with model/ClinVar/literature)
3) Confidence gaps and how literature fills them
4) Clinical actionability assessment
"""
        
        resp = client.models.generate_content(
            model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"), 
            contents=prompt
        )  # type: ignore
        alignment = getattr(resp, "text", None) or str(resp)
        
        job.update_progress(1)
        job.set_complete({
            "alignment_analysis": alignment,
            "evidence_count": len([s for s in summaries if not s.get("error")]),
            "evo2_result": evo2_result,
            "clinvar": clinvar
        })
        
        # Persist to Supabase if configured
        if SUPABASE_URL:
            asyncio.create_task(_supabase_insert("mdt_job_results", [{
                "job_id": job_id,
                "job_type": "align",
                "result": job.result,
                "created_at": job.created_at
            }]))
            
    except Exception as e:
        JOBS[job_id].set_error(str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000) 



