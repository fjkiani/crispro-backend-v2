"""
Evidence analysis and literature search endpoints
"""
import sys
print("DEBUG: evidence.py module loaded", file=sys.stderr, flush=True)
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import json
import httpx
import os
import time
import asyncio
import uuid
from hashlib import sha256
from pathlib import Path
import sys
import threading

from ..config import (
    DIFFBOT_TOKEN, SUPABASE_URL, SUPABASE_KEY, 
    SUPABASE_DEEP_ANALYSIS_TABLE, SUPABASE_JOB_RESULTS_TABLE
)
from ..services.supabase_service import _supabase_insert
from ..services.job_service import JOBS, BackgroundJob, _run_crawl_job, _run_summarize_job, _run_align_job

# Optional: Google GenAI for literature synthesis
try:
    import google.genai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

router = APIRouter(prefix="/api/evidence", tags=["evidence"])

# Initialize RAG agent (lazy loading)
_rag_agent = None

def get_rag_agent():
    """Get or initialize the RAG agent."""
    global _rag_agent
    if _rag_agent is None:
        # Check if API key is available before trying to initialize
        if not os.getenv("GEMINI_API_KEY"):
            print("Warning: GEMINI_API_KEY not found. RAG agent will not be available.")
            return None

        try:
            agent_dir = Path(__file__).resolve().parent.parent.parent / "Pubmed-LLM-Agent-main"
            sys.path.append(str(agent_dir))
            from rag_agent import RAGAgent  # type: ignore
            _rag_agent = RAGAgent()
            print("✅ RAG Agent initialized successfully")
        except Exception as e:
            print(f"Warning: Could not initialize RAG agent: {e}")
            _rag_agent = None
    return _rag_agent

# Simple in-memory cache for literature results (24h TTL)
_LIT_CACHE: Dict[str, Dict[str, Any]] = {}
_LIT_CACHE_TTL_S: int = 24 * 60 * 60
_LIT_CACHE_LOCK = threading.Lock()

def _lit_cache_key(payload: Dict[str, Any]) -> str:
    # Cache key based on query params that materially affect results
    parts = [
        str(payload.get("gene") or ""),
        str(payload.get("hgvs_p") or ""),
        str(payload.get("disease") or ""),
        str(payload.get("time_window") or ""),
        str(payload.get("max_results") or 10),
        str(bool(payload.get("include_abstracts", False))),
    ]
    return sha256("|".join(parts).encode()).hexdigest()[:24]

def _lit_cache_get(key: str) -> Any:
    now = int(time.time())
    with _LIT_CACHE_LOCK:
        entry = _LIT_CACHE.get(key)
        if entry and now - int(entry.get("ts", 0)) < _LIT_CACHE_TTL_S:
            return entry.get("data")
        if entry:
            _LIT_CACHE.pop(key, None)
    return None

def _lit_cache_set(key: str, data: Any) -> None:
    with _LIT_CACHE_LOCK:
        _LIT_CACHE[key] = {"ts": int(time.time()), "data": data}

def _extract_year(year_field: Any) -> int:
    try:
        s = str(year_field or "")
        return int(s[:4]) if len(s) >= 4 and s[:4].isdigit() else 0
    except Exception:
        return 0

def _now_year() -> int:
    try:
        return int(time.strftime("%Y"))
    except Exception:
        return 2025

def _normalize(s: Any) -> str:
    try:
        return str(s or "").lower()
    except Exception:
        return ""

def _variant_synonyms(hgvs_p: str) -> List[str]:
    syns: List[str] = []
    up = (hgvs_p or "").upper()
    if not up:
        return syns
    syns.append(up)
    # p.Val600Glu → V600E, Val600Glu, p.V600E
    try:
        if "600" in up:
            if "VAL" in up and "GLU" in up:
                syns.append("V600E")
                syns.append("Val600Glu")
                syns.append("p.V600E")
            if "V600E" in up:
                syns.append("Val600Glu")
                syns.append("p.V600E")
    except Exception:
        pass
    # Compact variant (e.g., BRAFV600E)
    return list({s for s in syns if s})

def _score_and_rank_papers(papers: List[Dict[str, Any]], gene: str, hgvs_p: str, disease: str, moa_terms: List[str]) -> List[Dict[str, Any]]:
    gene_n = _normalize(gene)
    disease_n = _normalize(disease)
    syns = [s.lower() for s in _variant_synonyms(hgvs_p)]
    moa_n = [m.lower() for m in (moa_terms or []) if isinstance(m, str)]
    current_year = _now_year()

    ranked: List[Dict[str, Any]] = []
    for p in papers:
        title_n = _normalize(p.get("title"))
        journal_n = _normalize(p.get("journal"))
        pubtypes = p.get("publication_types") or []
        year = _extract_year(p.get("year"))
        age = max(0, current_year - year) if year else 99
        score = 0.0
        reasons: List[str] = []

        # Matches
        if gene_n and gene_n in title_n:
            score += 2.0
            reasons.append("gene")
        matched_var = False
        for s in syns:
            if s and s in title_n:
                score += 3.0
                matched_var = True
                reasons.append("variant")
                break
        if not matched_var and syns and any(s in journal_n for s in syns):
            score += 1.0
            reasons.append("variant_journal")
        if disease_n:
            if disease_n in title_n:
                score += 2.0
                reasons.append("disease")
            elif "myeloma" in title_n:
                score += 1.0
                reasons.append("myeloma")
        # MoA terms
        for m in moa_n:
            if m and m in title_n:
                score += 1.5
                reasons.append(f"moa:{m}")

        # Publication type weighting
        types_n = [t.lower() for t in pubtypes if isinstance(t, str)]
        if any("clinical" in t and "trial" in t for t in types_n):
            score += 2.0
            reasons.append("clinical_trial")
        if any("guideline" in t for t in types_n):
            score += 3.0
            reasons.append("guideline")
        if any("review" in t for t in types_n):
            score += 1.5
            reasons.append("review")

        # Recency (<=6 years gets boost)
        if age <= 6:
            score += (6 - age) * 0.5
            reasons.append("recent")

        q = dict(p)
        q["relevance"] = round(score, 3)
        q["relevance_reason"] = ",".join(reasons)
        ranked.append(q)

    ranked.sort(key=lambda x: x.get("relevance") or 0.0, reverse=True)
    return ranked

async def clinvar_context(request: Dict[str, Any]) -> Dict[str, Any]:
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

@router.get("/clinvar")
async def clinvar_min(
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    gene: str | None = None,
    hgvs_p: str | None = None,
):
    """Lightweight ClinVar proxy for UI coverage chips.
    Returns minimal, stable shape: { classification, review_status, url, source }.
    """
    try:
        payload = {
            "gene": (gene or "").upper(),
            "hgvs_p": hgvs_p or "",
            "assembly": "GRCh38",
            "chrom": str(chrom),
            "pos": int(pos),
            "ref": str(ref).upper(),
            "alt": str(alt).upper(),
        }
        da = await deep_analysis(payload)
        clin = (da.get("clinvar") or {})
        return {
            "classification": clin.get("classification"),
            "review_status": clin.get("review_status"),
            "url": clin.get("url"),
            "source": clin.get("source"),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"clinvar proxy failed: {e}")

@router.post("/deep_analysis")
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

@router.post("/literature")
async def evidence_literature(request: Dict[str, Any]):
    """Search and rank PubMed evidence via PubMed LLM Agent.
    Input: { gene, hgvs_p, disease, time_window?: str, max_results?: int, include_abstracts?: bool, synthesize?: bool }
    """
    import sys
    try:
        from ..config import get_feature_flags
        if get_feature_flags().get("disable_literature"):
            return {"results": [], "disabled": True}
    except Exception:
        pass
    print(f"DEBUG: evidence_literature called with request: {request}", file=sys.stderr, flush=True)
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        gene = (request.get("gene") or "").strip()
        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        moa_terms = request.get("moa_terms") or []
        time_window = (request.get("time_window") or "since 2015").strip()
        max_results = int(request.get("max_results") or 10)
        include_abstracts = bool(request.get("include_abstracts", False))
        synthesize = bool(request.get("synthesize", False))
        cache_key = _lit_cache_key({
            "gene": gene, "hgvs_p": hgvs_p, "disease": disease,
            "time_window": time_window, "max_results": max_results,
            "include_abstracts": include_abstracts,
        })
        cached = _lit_cache_get(cache_key)
        if cached:
            print(f"DEBUG: Using cached result for key: {cache_key}")
            return cached
        print(f"DEBUG: No cache found, running fresh search")
        # Import enhanced agent
        agent_dir = Path(__file__).resolve().parent.parent.parent / "Pubmed-LLM-Agent-main"
        sys.path.append(str(agent_dir))
        try:
            from pubmed_llm_agent_enhanced import run_enhanced_pubmed_search  # type: ignore
        except Exception as e:
            raise HTTPException(status_code=501, detail=f"enhanced literature agent unavailable: {e}")

        # Build variant info for enhanced agent
        variant_info = {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease,
            'variant_info': f"{gene} {hgvs_p}"
        }

        # Run enhanced search in a worker thread to avoid nested event loop conflicts
        loop = asyncio.get_running_loop()
        result = await loop.run_in_executor(
            None,
            lambda: run_enhanced_pubmed_search(
                variant_info=variant_info,
                max_results=max_results,
                time_window=time_window,
                disease_context=disease,
                include_abstracts=include_abstracts,
                llm_model=os.getenv("LIT_LLM_MODEL", "gemini-2.5-pro"),
                pubmed_email=os.getenv("NCBI_EMAIL"),
                pubmed_api_key=os.getenv("NCBI_API_KEY"),
                llm_api_key=os.getenv("GEMINI_API_KEY"),
            )
        )

        # Debug: Log the result structure and environment
        print(f"DEBUG: Environment NCBI_EMAIL: {os.getenv('NCBI_EMAIL')}", file=sys.stderr, flush=True)
        print(f"DEBUG: Enhanced agent result type: {type(result)}", file=sys.stderr, flush=True)
        print(f"DEBUG: Enhanced agent result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}", file=sys.stderr, flush=True)
        print(f"DEBUG: Results count: {len(result.get('results', [])) if isinstance(result, dict) else 'N/A'}", file=sys.stderr, flush=True)
        print(f"DEBUG: Result sample: {result}", file=sys.stderr, flush=True)

        # Shape top results, optionally include abstracts (robust to agent schema)
        raw_list = (
            result.get("results")
            or result.get("processed_papers")
            or result.get("papers")
            or []
        )
        tops = []
        for r in raw_list[:max_results]:
            pmid = r.get("pmid") or r.get("id")
            title = r.get("title")
            year = r.get("year")
            journal = r.get("journal") or r.get("source")
            pub_types = r.get("publication_types") or r.get("types") or []
            tops.append({
                "pmid": pmid,
                "pmcid": r.get("pmcid"),
                "title": title,
                "year": year,
                "journal": journal,
                "relevance": r.get("relevance") or r.get("similarity_score"),
                "relevance_reason": r.get("relevance_reason"),
                "abstract": (r.get("abstract") if include_abstracts else None),
                "license": r.get("license"),
                "publication_types": pub_types,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None,
            })
        query_str = (
            result.get("natural_query")
            or (result.get("search_metadata") or {}).get("natural_query")
            or f"{gene} {hgvs_p} {disease}"
        )
        payload: Dict[str, Any] = {
            "query": query_str,
            "pubmed_query": result.get("pubmed_query") or (result.get("search_metadata") or {}).get("pubmed_query"),
            "total_found": result.get("total_found") or (result.get("search_metadata") or {}).get("count"),
            "returned_count": len(tops),
            "top_results": tops,
        }

        # Minimal basic fallback via E-utilities if enhanced agent returns empty
        if not tops:
            try:
                # Build a more permissive E-utilities query with synonyms
                gene_q = f'("{gene}"[tiab] OR "{gene} mutation"[tiab])' if gene else ''
                # Map common protein HGVS synonyms (e.g., V600E)
                syn = None
                if hgvs_p:
                    up = hgvs_p.upper()
                    if "V600E" in up or "VAL600GLU" in up:
                        syn = "V600E"
                    else:
                        syn = up.replace("P.", "").replace("VAL","V").replace("GLU","E")
                var_q = f'("{hgvs_p}"[tiab] OR "{syn}"[tiab] OR mutation[tiab])' if (hgvs_p or syn) else 'mutation[tiab]'
                dis_q = '("multiple myeloma"[mh] OR "multiple myeloma"[tiab] OR myeloma[tiab])' if disease else ''
                lang_q = 'english[lang]'
                clauses = [q for q in [gene_q, var_q, dis_q, lang_q] if q]
                term = " AND ".join(clauses) or (f'"{gene}"[tiab]' if gene else 'multiple myeloma[mh]')
                esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                params = {
                    "db": "pubmed",
                    "retmode": "json",
                    "retmax": str(max(25, max_results)),
                    "term": term,
                    "api_key": os.getenv("NCBI_API_KEY", ""),
                    "email": os.getenv("NCBI_EMAIL", ""),
                    "tool": "crispro",
                }
                with httpx.Client(timeout=20) as client:
                    rs = client.get(esearch_url, params=params)
                    js = rs.json() if rs.status_code == 200 else {}
                    idlist = ((js.get("esearchresult") or {}).get("idlist") or [])[:max_results]
                    if idlist:
                        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                        ps = {"db": "pubmed", "retmode": "json", "id": ",".join(idlist), "api_key": os.getenv("NCBI_API_KEY", ""), "email": os.getenv("NCBI_EMAIL", ""), "tool": "crispro"}
                        rr = client.get(esummary_url, params=ps)
                        sj = rr.json() if rr.status_code == 200 else {}
                        recs = (sj.get("result") or {})
                        uids = [u for u in recs.get("uids", [])]
                        simple_tops = []
                        for uid in uids:
                            rec = recs.get(uid) or {}
                            simple_tops.append({
                                "pmid": uid,
                                "title": rec.get("title"),
                                "year": rec.get("pubdate", "")[:4],
                                "journal": rec.get("fulljournalname") or rec.get("source"),
                                "publication_types": rec.get("pubtype") if isinstance(rec.get("pubtype"), list) else [],
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                            })
                        if simple_tops:
                            ranked = _score_and_rank_papers(simple_tops, gene, hgvs_p, disease, moa_terms)
                            payload["top_results"] = ranked[:max_results]
                            payload["returned_count"] = len(payload["top_results"]) 
                            payload["pubmed_query"] = term
            except Exception:
                pass

        # Fallback #2: gene + disease only (no mutation filter)
        if not tops:
            try:
                if gene and disease:
                    term2 = f'("{gene}"[tiab] OR "{gene} mutation"[tiab]) AND ("multiple myeloma"[mh] OR myeloma[tiab] OR "plasma cell myeloma"[tiab]) AND english[lang]'
                elif gene:
                    term2 = f'("{gene}"[tiab] OR "{gene} mutation"[tiab]) AND english[lang]'
                else:
                    term2 = 'multiple myeloma[mh] AND english[lang]'
                esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                params2 = {
                    "db": "pubmed",
                    "retmode": "json",
                    "retmax": "25",
                    "term": term2,
                    "api_key": os.getenv("NCBI_API_KEY", ""),
                    "email": os.getenv("NCBI_EMAIL", ""),
                    "tool": "crispro",
                }
                with httpx.Client(timeout=20) as client:
                    rs2 = client.get(esearch_url, params=params2)
                    js2 = rs2.json() if rs2.status_code == 200 else {}
                    idlist2 = ((js2.get("esearchresult") or {}).get("idlist") or [])[:max(10, max_results)]
                    if idlist2:
                        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                        ps2 = {"db": "pubmed", "retmode": "json", "id": ",".join(idlist2), "api_key": os.getenv("NCBI_API_KEY", ""), "email": os.getenv("NCBI_EMAIL", ""), "tool": "crispro"}
                        rr2 = client.get(esummary_url, params=ps2)
                        sj2 = rr2.json() if rr2.status_code == 200 else {}
                        recs2 = (sj2.get("result") or {})
                        uids2 = [u for u in recs2.get("uids", [])]
                        simple_tops2 = []
                        for uid in uids2:
                            rec = recs2.get(uid) or {}
                            simple_tops2.append({
                                "pmid": uid,
                                "title": rec.get("title"),
                                "year": rec.get("pubdate", "")[:4],
                                "journal": rec.get("fulljournalname") or rec.get("source"),
                                "publication_types": rec.get("pubtype") if isinstance(rec.get("pubtype"), list) else [],
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                            })
                        if simple_tops2:
                            ranked2 = _score_and_rank_papers(simple_tops2, gene, hgvs_p, disease, moa_terms)
                            payload["top_results"] = ranked2[:max_results]
                            payload["returned_count"] = len(payload["top_results"]) 
                            payload["pubmed_query"] = term2
            except Exception:
                pass

        # Fallback #3: ultra-loose search (no field tags) gene + disease, then gene-only
        if not payload.get("top_results"):
            try:
                queries: List[str] = []
                if gene and disease:
                    queries.append(f"{gene} AND {disease}")
                if gene:
                    queries.append(gene)
                for term3 in queries:
                    esearch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
                    params3 = {
                        "db": "pubmed",
                        "retmode": "json",
                        "retmax": str(max(25, max_results)),
                        "term": term3,
                        "api_key": os.getenv("NCBI_API_KEY", ""),
                        "email": os.getenv("NCBI_EMAIL", ""),
                        "tool": "crispro",
                    }
                    with httpx.Client(timeout=20) as client:
                        rs3 = client.get(esearch_url, params=params3)
                        js3 = rs3.json() if rs3.status_code == 200 else {}
                        idlist3 = ((js3.get("esearchresult") or {}).get("idlist") or [])[:max(10, max_results)]
                        if not idlist3:
                            continue
                        esummary_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
                        ps3 = {"db": "pubmed", "retmode": "json", "id": ",".join(idlist3), "api_key": os.getenv("NCBI_API_KEY", ""), "email": os.getenv("NCBI_EMAIL", ""), "tool": "crispro"}
                        rr3 = client.get(esummary_url, params=ps3)
                        sj3 = rr3.json() if rr3.status_code == 200 else {}
                        recs3 = (sj3.get("result") or {})
                        uids3 = [u for u in recs3.get("uids", [])]
                        simple_tops3 = []
                        for uid in uids3:
                            rec = recs3.get(uid) or {}
                            simple_tops3.append({
                                "pmid": uid,
                                "title": rec.get("title"),
                                "year": rec.get("pubdate", "")[:4],
                                "journal": rec.get("fulljournalname") or rec.get("source"),
                                "publication_types": rec.get("pubtype") if isinstance(rec.get("pubtype"), list) else [],
                                "url": f"https://pubmed.ncbi.nlm.nih.gov/{uid}/",
                            })
                        if simple_tops3:
                            ranked3 = _score_and_rank_papers(simple_tops3, gene, hgvs_p, disease, moa_terms)
                            payload["top_results"] = ranked3[:max_results]
                            payload["returned_count"] = len(payload["top_results"]) 
                            payload["pubmed_query"] = term3
                            break
            except Exception:
                pass
        # Optional LLM synthesis over titles/abstracts (use fallback results if present)
        tops_for_synthesis = payload.get("top_results") or tops
        if synthesize and tops_for_synthesis:
            try:
                synthesis = None
                # Attempt to enrich missing abstracts via Diffbot for PubMed URLs
                if include_abstracts and DIFFBOT_TOKEN:
                    try:
                        with httpx.Client(timeout=20) as _c:
                            for t in tops_for_synthesis[:5]:
                                if not t.get("abstract") and t.get("url") and "pubmed.ncbi.nlm.nih.gov" in t.get("url"):
                                    er = _c.post(
                                        f"{str(router.prefix).replace('/api/evidence','')}/api/evidence/extract",
                                        json={"url": t.get("url")},
                                        headers={"Content-Type": "application/json"}
                                    )
                                    if er.status_code < 400:
                                        ej = er.json() or {}
                                        if ej.get("text"):
                                            t["abstract"] = (ej.get("text") or "")[:1200]
                    except Exception:
                        pass
                if genai and os.getenv("GEMINI_API_KEY"):
                    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))  # type: ignore
                    chunks = []
                    for t in tops_for_synthesis[:5]:
                        line = f"- {t.get('title') or ''} ({t.get('journal') or 'n/a'}, {t.get('year') or 'n/a'})\n"
                        if include_abstracts and t.get("abstract"):
                            line += f"  Abstract: {str(t.get('abstract'))[:800]}\n"
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
        # Cache successful payloads
        try:
            _lit_cache_set(cache_key, payload)
        except Exception:
            pass
        
        # Persist literature search results to Supabase
        try:
            if SUPABASE_URL and SUPABASE_KEY:
                ts = int(time.time())
                literature_row = {
                    "run_signature": f"{gene}_{hgvs_p}_lit_{ts}",
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "disease": disease,
                    "query": query_str,
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

@router.post("/test")
async def test_endpoint(request: Dict[str, Any]):
    """Simple test endpoint to verify routing works."""
    import sys
    import os
    print(f"DEBUG: test_endpoint called with request: {request}", file=sys.stderr, flush=True)
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and len(gemini_key) > 10)
    return {
        "message": "Test endpoint works",
        "request": request,
        "gemini_api_available": has_gemini,
        "gemini_key_length": len(gemini_key) if gemini_key else 0
    }

@router.post("/rag-query")
async def evidence_rag_query(request: Dict[str, Any]):
    """RAG-based conversational query for clinical literature.
    Input: { query: str, gene?: str, hgvs_p?: str, disease?: str, max_context_papers?: int }
    Output: { query, answer, evidence_level, confidence_score, supporting_papers, ... }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        query = (request.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query required")

        # Extract variant information
        gene = (request.get("gene") or "").strip()
        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        max_context_papers = int(request.get("max_context_papers") or 5)

        variant_info = {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease,
            'variant_info': f"{gene or 'Unknown'} {hgvs_p or 'Unknown'}"
        }

        # Get RAG agent
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        # Process the query
        result = rag_agent.query(
            query=query,
            variant_info=variant_info if gene or hgvs_p else None,
            max_context_papers=max_context_papers
        )

        # Format supporting papers for response
        formatted_papers = []
        for paper in result.get('supporting_papers', []):
            formatted_papers.append({
                'pmid': paper.get('pmid'),
                'title': paper.get('title', '')[:100] + "..." if len(paper.get('title', '')) > 100 else paper.get('title', ''),
                'year': paper.get('year'),
                'journal': paper.get('source'),
                'relevance_score': paper.get('similarity_score', 0),
                'doi': paper.get('doi'),
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pmid')}/" if paper.get('pmid') else None
            })

        return {
            'query': result.get('query'),
            'query_type': result.get('query_type'),
            'answer': result.get('answer'),
            'evidence_level': result.get('evidence_level'),
            'confidence_score': result.get('confidence_score'),
            'supporting_papers': formatted_papers,
            'total_papers_found': result.get('total_papers_found', 0),
            'generated_at': result.get('generated_at'),
            'variant_info': result.get('variant_info')
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

@router.post("/rag-add-variant")
async def evidence_rag_add_variant(request: Dict[str, Any]):
    """Add papers about a variant to the RAG knowledge base.
    Input: { gene: str, hgvs_p?: str, disease?: str, max_papers?: int }
    Output: { added, skipped, failed, total_found, new_found }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        gene = (request.get("gene") or "").strip()
        if not gene:
            raise HTTPException(status_code=400, detail="gene required")

        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        max_papers = int(request.get("max_papers") or 50)

        variant_info = {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease
        }

        # Get RAG agent
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        # Add variant to knowledge base
        result = rag_agent.add_variant_to_knowledge_base(variant_info, max_papers)

        if 'error' in result:
            raise HTTPException(status_code=500, detail=f"Failed to add variant: {result['error']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Add variant failed: {e}")

@router.get("/rag-stats")
async def evidence_rag_stats():
    """Get RAG knowledge base statistics."""
    try:
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        stats = rag_agent.get_knowledge_base_stats()
        return stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {e}")

@router.post("/extract")
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

@router.post("/explain")
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
        raise HTTPException(status_code=500, detail=f"job status failed: {e}")     """
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
