"""
ClinVar Module - ClinVar context and deep analysis endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Optional, Dict, Any
import httpx
import time
import json
import asyncio
import gzip
import csv
from pathlib import Path

from ...config import (
    SUPABASE_URL, SUPABASE_KEY, 
    SUPABASE_DEEP_ANALYSIS_TABLE
)
from ...services.supabase_service import _supabase_insert

router = APIRouter()

_DDR_GENES = {"BRCA1", "BRCA2", "RAD51C", "RAD51D", "PALB2", "ATM", "CHEK2", "MBD4"}
_LOCAL_CLINVAR_CACHE: Optional[Dict[str, Any]] = None


def _local_variant_summary_path() -> Optional[Path]:
    """
    Repo-local ClinVar dump (if present):
      oncology-coPilot/oncology-backend-minimal/variant_summary.txt.gz
    """
    try:
        p = Path(__file__).resolve().parents[3] / "variant_summary.txt.gz"
        return p if p.exists() else None
    except Exception:
        return None


def _normalize_clinsig(s: str) -> str:
    return (s or "").strip().lower()


def _collapse_classification(labels: Dict[str, int]) -> Optional[str]:
    """
    Collapse multiple row-level ClinicalSignificance values into a single UI-friendly label.
    Priority:
      - conflicting if any conflicting present OR mixed decisive labels
      - otherwise choose max-count representative
    """
    if not labels:
        return None
    # direct conflicting label
    if any("conflicting" in k for k in labels.keys()):
        return "Conflicting classifications of pathogenicity"

    has_path = any("pathogenic" in k for k in labels.keys())
    has_benign = any("benign" in k for k in labels.keys())
    if has_path and has_benign:
        return "Conflicting classifications of pathogenicity"

    # prefer uncertain significance if present and no decisive mix
    if any("uncertain significance" in k for k in labels.keys()):
        return "Uncertain significance"

    # otherwise choose most frequent (normalized) and title-case-ish
    best = max(labels.items(), key=lambda kv: kv[1])[0]
    # map common variants
    mapping = {
        "likely pathogenic": "Likely pathogenic",
        "pathogenic": "Pathogenic",
        "likely benign": "Likely benign",
        "benign": "Benign",
        "not provided": "Not provided",
        "-": None,
    }
    return mapping.get(best, best)


def _load_local_clinvar_index() -> Dict[str, Any]:
    """
    Load a small in-memory index from variant_summary.txt.gz for DDR genes only.
    Keyed by: (chrom, pos_vcf, ref_vcf, alt_vcf) in GRCh38.
    Value: aggregated labels + a representative review status.
    """
    path = _local_variant_summary_path()
    if not path:
        return {"enabled": False, "path": None, "by_key": {}}

    by_key: Dict[tuple, Dict[str, Any]] = {}
    with gzip.open(path, "rt", encoding="utf-8", errors="replace") as f:
        r = csv.DictReader(f, delimiter="\t")
        for row in r:
            if (row.get("Assembly") or "") != "GRCh38":
                continue
            gene = (row.get("GeneSymbol") or "").strip().upper()
            if gene not in _DDR_GENES:
                continue

            chrom = str(row.get("Chromosome") or "").strip()
            pos = str(row.get("PositionVCF") or "").strip()
            ref = str(row.get("ReferenceAlleleVCF") or "").strip().upper()
            alt = str(row.get("AlternateAlleleVCF") or "").strip().upper()
            if not chrom or not pos or not ref or not alt:
                continue
            try:
                pos_i = int(pos)
            except Exception:
                continue

            key = (chrom, pos_i, ref, alt)
            cs = _normalize_clinsig(row.get("ClinicalSignificance") or "")
            rs = (row.get("ReviewStatus") or "").strip()

            slot = by_key.get(key)
            if not slot:
                slot = {
                    "genes": {gene},
                    "labels": {},
                    "review_statuses": {},
                }
                by_key[key] = slot
            slot["genes"].add(gene)
            if cs:
                slot["labels"][cs] = int(slot["labels"].get(cs, 0)) + 1
            if rs:
                slot["review_statuses"][rs] = int(slot["review_statuses"].get(rs, 0)) + 1

    return {"enabled": True, "path": str(path), "by_key": by_key}


def _local_lookup_grch38(chrom: str, pos: int, ref: str, alt: str) -> Optional[Dict[str, Any]]:
    global _LOCAL_CLINVAR_CACHE
    if _LOCAL_CLINVAR_CACHE is None:
        _LOCAL_CLINVAR_CACHE = _load_local_clinvar_index()
    if not _LOCAL_CLINVAR_CACHE.get("enabled"):
        return None
    key = (str(chrom).strip(), int(pos), str(ref).upper().strip(), str(alt).upper().strip())
    slot = (_LOCAL_CLINVAR_CACHE.get("by_key") or {}).get(key)
    if not slot:
        return None
    classification = _collapse_classification(slot.get("labels") or {})
    # pick most frequent review status
    rs_map = slot.get("review_statuses") or {}
    review_status = max(rs_map.items(), key=lambda kv: kv[1])[0] if rs_map else None
    return {
        "classification": classification,
        "review_status": review_status,
        "source": "variant_summary_local_ddr",
        "genes": sorted(list(slot.get("genes") or [])),
        "labels": slot.get("labels") or {},
        "variant_summary_path": _LOCAL_CLINVAR_CACHE.get("path"),
    }


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
    gene: Optional[str] = None,
    hgvs_p: Optional[str] = None,
):
    """Lightweight ClinVar proxy for UI coverage chips.
    Returns minimal, stable shape: { classification, review_status, url, source }.
    """
    try:
        # Prefer deterministic local lookup when available (avoids HTML scraping errors).
        chrom_s = str(chrom).strip()
        pos_i = int(pos)
        ref_u = str(ref).upper()
        alt_u = str(alt).upper()
        local = _local_lookup_grch38(chrom_s, pos_i, ref_u, alt_u)
        if local:
            return {
                "classification": local.get("classification"),
                "review_status": local.get("review_status"),
                "url": f"https://www.ncbi.nlm.nih.gov/clinvar/?term={chrom_s}%3A{pos_i}%20{ref_u}%3E{alt_u}",
                "source": local.get("source"),
                "local": {"genes": local.get("genes"), "labels": local.get("labels")},
            }

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

        # 0) Prefer local lookup when possible (deterministic).
        if asm == "GRCh38" and chrom and pos and ref and alt:
            local = _local_lookup_grch38(chrom, pos, ref, alt)
            if local:
                classification = local.get("classification")
                review_status = local.get("review_status")
                counts = local.get("labels") or {}
                clinvar_source = local.get("source") or "variant_summary_local_ddr"
                resolved_url = f"https://www.ncbi.nlm.nih.gov/clinvar/?term={chrom}%3A{pos}%20{ref}%3E{alt}"

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



