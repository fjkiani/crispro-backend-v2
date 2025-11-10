"""
Literature Module - PubMed literature search with E-utilities fallbacks and caching
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import httpx
import time
import json
import asyncio
from pathlib import Path
import sys

from ...config import (
    DIFFBOT_TOKEN, SUPABASE_URL, SUPABASE_KEY
)
from ...services.supabase_service import _supabase_insert
from ...services.cache_service import get_cache, set_cache, with_singleflight, literature_cache_key, LITERATURE_TTL

# Optional: Google GenAI for literature synthesis
try:
    import google.genai as genai  # type: ignore
except Exception:
    genai = None  # type: ignore

router = APIRouter()

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

@router.post("/literature")
async def evidence_literature(request: Dict[str, Any]):
    """Search and rank PubMed evidence via PubMed LLM Agent.
    Input: { gene, hgvs_p, disease, time_window?: str, max_results?: int, include_abstracts?: bool, synthesize?: bool }
    """
    try:
        from ...config import get_feature_flags
        if get_feature_flags().get("disable_literature"):
            return {"results": [], "disabled": True}
    except Exception:
        pass
    
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
        
        # Use cache service for literature searches
        cache_key = literature_cache_key(gene, hgvs_p, disease, max_results)
        
        async def _search_literature():
            # Import enhanced agent
            agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "Pubmed-LLM-Agent-main"
            sys.path.append(str(agent_dir))
            try:
                from pubmed_llm_agent_enhanced import run_enhanced_pubmed_search  # type: ignore
            except Exception as e:
                # Fallback to empty results if enhanced agent unavailable
                return {
                    "top_results": [],
                    "pubmed_query": f"{gene} {hgvs_p} {disease}".strip(),
                    "agent_fallback": True,
                    "agent_error": str(e)[:100]
                }

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
        
        # Use single-flight caching for literature searches
        result = await with_singleflight(cache_key, 30, _search_literature)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"literature search failed: {e}")

@router.post("/test")
async def test_endpoint(request: Dict[str, Any]):
    """Simple test endpoint to verify routing works."""
    gemini_key = os.getenv("GEMINI_API_KEY")
    has_gemini = bool(gemini_key and len(gemini_key) > 10)
    return {
        "message": "Test endpoint works",
        "request": request,
        "gemini_api_available": has_gemini,
        "gemini_key_length": len(gemini_key) if gemini_key else 0
    }

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


