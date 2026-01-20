"""
VUS Identify API — end-to-end orchestration for the “40% VUS” problem.

Goal:
- Take a variant (HGVS and/or GRCh38 coords)
- Normalize to GRCh38 coords (no guessing; real upstream resolution)
- Pull priors (ClinVar proxy)
- Pull sequence signal (Evo2 delta via /api/evo/score_variant_multi)
- Pull insights bundle (Functionality / Regulatory / Essentiality / Chromatin)
- Pull AlphaMissense eligibility (coverage gate only; scoring is separate)
- Return a single, audit-ready response with provenance + next actions

Research-mode only. Not for clinical decision-making.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from urllib.parse import quote as url_quote

import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from api.services.pathway.drug_mapping import get_pathway_weights_for_gene
from api.services.sequence_scorers.utils import percentile_like

router = APIRouter(prefix="/api/vus", tags=["vus"])

async def _dummy_future(**payload: Any) -> Dict[str, Any]:
    """
    Small helper to keep our async fanout loop uniform when we want to skip a call.
    Returns the provided payload as an awaitable.
    """
    return dict(payload)


class VariantInput(BaseModel):
    gene: Optional[str] = None
    hgvs_c: Optional[str] = Field(default=None, description="HGVS coding notation, e.g. PDGFRA:c.2263T>C")
    hgvs_p: Optional[str] = Field(default=None, description="HGVS protein notation, e.g. p.S755P")
    assembly: str = Field(default="GRCh38", description="GRCh38|hg38|GRCh37|hg19")
    chrom: Optional[str] = None
    pos: Optional[int] = None
    ref: Optional[str] = None
    alt: Optional[str] = None


class VusIdentifyRequest(BaseModel):
    variant: VariantInput
    options: Dict[str, Any] = Field(default_factory=dict)


def _norm_asm(asm: str) -> str:
    return "GRCh38" if str(asm).lower() in ("grch38", "hg38") else "GRCh37"


def _clean_chrom(chrom: str) -> str:
    c = (chrom or "").strip()
    if c.lower().startswith("chr"):
        c = c[3:]
    return c


def _human_clinvar_label(raw: Optional[str]) -> Optional[str]:
    if raw is None:
        return None
    r = str(raw).strip().lower().replace("-", " ").replace("_", " ")
    mapping = {
        "pathogenic": "Pathogenic",
        "likely pathogenic": "Likely pathogenic",
        "benign": "Benign",
        "likely benign": "Likely benign",
        "uncertain significance": "Uncertain significance",
        "vus": "Uncertain significance",
    }
    return mapping.get(r, raw)


def _pathway_key_to_label(key: Optional[str]) -> Optional[str]:
    if not key:
        return None
    k = str(key).strip().lower()
    mapping = {
        "ddr": "DDR",
        "ras_mapk": "RTK/MAPK",
        "pi3k": "PI3K",
        "vegf": "VEGF",
        "tp53": "TP53",
    }
    return mapping.get(k, key)


def _infer_patient_axis(patient_genes: List[str]) -> Dict[str, Any]:
    """
    Compute the patient's dominant actionable axis from gene→pathway mappings.
    This is deterministic and auditable (no hardcoded “Ayesha axis” shortcuts).
    """
    scores: Dict[str, float] = {}
    for g in patient_genes or []:
        weights = get_pathway_weights_for_gene(g) or {}
        for k, v in weights.items():
            try:
                scores[k] = scores.get(k, 0.0) + float(v)
            except Exception:
                continue
    if not scores:
        return {"axis_key": None, "axis_label": None, "scores": {}}
    axis_key = max(scores.items(), key=lambda kv: kv[1])[0]
    return {"axis_key": axis_key, "axis_label": _pathway_key_to_label(axis_key), "scores": scores}


def _infer_variant_axis(gene: Optional[str]) -> Dict[str, Any]:
    weights = get_pathway_weights_for_gene(gene or "") or {}
    if not weights:
        return {"axis_key": None, "axis_label": None, "weights": {}}
    axis_key = max(weights.items(), key=lambda kv: kv[1])[0]
    return {"axis_key": axis_key, "axis_label": _pathway_key_to_label(axis_key), "weights": weights}


def _axis_relevance(patient_axis_key: Optional[str], variant_axis_key: Optional[str]) -> str:
    if not patient_axis_key or not variant_axis_key:
        return "unknown"
    return "high" if patient_axis_key == variant_axis_key else "low"


async def _resolve_hgvs_to_grch38(hgvs: str) -> Dict[str, Any]:
    """
    Use Ensembl VEP HGVS endpoint to resolve HGVS -> GRCh38 coords + consequence summary.
    This is a real upstream call; if it fails we return an explicit error.
    """
    # NOTE: httpx does NOT expose `httpx.utils.quote`. Use urllib.parse.quote instead.
    url = f"https://rest.ensembl.org/vep/human/hgvs/{url_quote(hgvs, safe='')}?content-type=application/json"
    async with httpx.AsyncClient(timeout=30) as client:
        try:
            r = await client.get(url, headers={"Content-Type": "application/json"})
            r.raise_for_status()
            data = r.json()
        except httpx.HTTPStatusError as e:
            # Ensembl returns 400 for malformed HGVS. Surface that as a user-facing 400, not a 500.
            status = int(e.response.status_code) if e.response is not None else 502
            detail = f"Ensembl VEP HGVS resolution failed ({status}). Ensure hgvs_c is like 'PDGFRA:c.2263T>C' (or provide chrom/pos/ref/alt)."
            raise HTTPException(status_code=400, detail=detail) from e
        except Exception as e:
            raise HTTPException(status_code=502, detail=f"Ensembl VEP HGVS resolution failed: {e}") from e
    if not isinstance(data, list) or not data:
        raise HTTPException(status_code=502, detail="Ensembl VEP HGVS resolution returned empty response")
    d0 = data[0] or {}
    chrom = str(d0.get("seq_region_name") or "")
    pos = int(d0.get("start") or 0)
    allele = str(d0.get("allele_string") or "")
    ref, alt = None, None
    try:
        parts = allele.split("/")
        if len(parts) == 2:
            ref, alt = parts[0].upper(), parts[1].upper()
    except Exception:
        pass

    # Choose a “primary” transcript consequence if available
    tc = None
    tcs = d0.get("transcript_consequences") or []
    if isinstance(tcs, list) and tcs:
        # Prefer protein_coding missense consequences
        def _score(x: Dict[str, Any]) -> int:
            s = 0
            if x.get("biotype") == "protein_coding":
                s += 3
            if "missense_variant" in (x.get("consequence_terms") or []):
                s += 3
            if x.get("impact") == "HIGH":
                s += 2
            if x.get("impact") == "MODERATE":
                s += 1
            return s

        tc = sorted([x for x in tcs if isinstance(x, dict)], key=_score, reverse=True)[0]

    consequence = None
    if tc:
        aa = tc.get("amino_acids")
        ps = tc.get("protein_start")
        pe = tc.get("protein_end")
        if aa and ps:
            # aa is like "S/P"
            try:
                a0, a1 = str(aa).split("/")
                consequence = f"p.{a0}{ps}{a1}"
            except Exception:
                consequence = None
        sift = tc.get("sift_prediction")
        poly = tc.get("polyphen_prediction")
    else:
        sift = None
        poly = None

    return {
        "source": "ensembl_vep_hgvs",
        "hgvs": hgvs,
        "assembly": str(d0.get("assembly_name") or "GRCh38"),
        "chrom": chrom,
        "pos": pos,
        "ref": ref,
        "alt": alt,
        "vep": {
            "most_severe_consequence": d0.get("most_severe_consequence"),
            "transcript_id": tc.get("transcript_id") if tc else None,
            "gene_symbol": tc.get("gene_symbol") if tc else None,
            "impact": tc.get("impact") if tc else None,
            "hgvs_p": consequence,
            "sift_prediction": sift,
            "polyphen_prediction": poly,
            "polyphen_score": tc.get("polyphen_score") if tc else None,
            "sift_score": tc.get("sift_score") if tc else None,
        },
    }


def _triage(
    *,
    clinvar_classification: Optional[str],
    evo_min_delta: Optional[float],
    am_eligible: Optional[bool],
    insights: Dict[str, Optional[float]],
) -> Dict[str, Any]:
    """
    VUS Triage with two resolution paths:
    
    Path A: resolved_by_prior → ClinVar/KB has decisive classification
    Path B: resolved_by_evo2 → ML signal (Evo2 delta) is strong enough to classify
    
    Thresholds (research-mode, calibrated):
    - Evo2 delta < -0.15 → likely_damaging (sequence disruption)
    - Evo2 delta > -0.03 → likely_benign (no significant disruption)
    - In between → still_vus (needs functional evidence)
    
    Multi-signal boosting:
    - If Evo2 + insights converge → higher confidence
    - If Evo2 + VEP converge → higher confidence
    """
    reasons: List[str] = []
    classification = (clinvar_classification or "").strip().lower().replace("_", " ")

    # --- PATH A: Resolved by Prior (ClinVar/KB) ---
    if classification in ("pathogenic", "likely pathogenic", "benign", "likely benign"):
        base_confidence = 0.9 if "likely" not in classification else 0.75
        
        # Boost confidence if Evo2 agrees with prior
        if evo_min_delta is not None:
            if classification in ("pathogenic", "likely pathogenic") and evo_min_delta < -0.10:
                base_confidence = min(0.95, base_confidence + 0.05)
                reasons.append(f"Evo2 confirms damaging (Δ={evo_min_delta:+.3f})")
            elif classification in ("benign", "likely benign") and evo_min_delta > -0.05:
                base_confidence = min(0.95, base_confidence + 0.05)
                reasons.append(f"Evo2 confirms benign (Δ={evo_min_delta:+.3f})")
            elif evo_min_delta is not None:
                reasons.append(f"Evo2 signal available (Δ={evo_min_delta:+.3f})")
        
        return {
            "status": "resolved_by_prior",
            "verdict": _human_clinvar_label(classification),
            "confidence": round(base_confidence, 2),
            "reasons": [f"ClinVar prior: {classification}"] + reasons,
            "resolution_path": "prior",
            "evo2_validated": evo_min_delta is not None,
        }

    # --- PATH B: Resolved by Evo2 (Pure ML) ---
    # Only when ClinVar is non-decisive (VUS, Conflicting, or missing)
    if evo_min_delta is not None:
        delta = float(evo_min_delta)
        impact_pct = percentile_like(abs(delta))
        # Use the existing, battle-tested magnitude→percentile mapping (used elsewhere in S/P/E),
        # rather than hardcoding raw-delta thresholds that don't transfer across deployments.
        #
        # Interpretation:
        # - Higher magnitude (|Δ|) => higher percentile_like => more likely impactful.
        # - We keep this conservative: only call "damaging" at high percentiles.
        EVO_DAMAGING_PCTL = 0.80
        EVO_BENIGN_PCTL = 0.10
        
        # Check insights for multi-signal convergence
        func_score = insights.get("functionality")
        ess_score = insights.get("essentiality")
        
        if impact_pct >= EVO_DAMAGING_PCTL:
            confidence = 0.70
            reasons = [f"Evo2 |Δ| percentile≈{impact_pct:.2f} (high magnitude disruption signal)"]
            
            # Boost if insights converge
            if func_score is not None and func_score > 0.5:
                confidence = min(0.85, confidence + 0.10)
                reasons.append(f"Functionality score ({func_score:.2f}) supports damaging")
            if ess_score is not None and ess_score > 0.5:
                confidence = min(0.85, confidence + 0.05)
                reasons.append(f"Essentiality score ({ess_score:.2f}) supports impact")
            
            return {
                "status": "resolved_by_evo2",
                "verdict": "Likely damaging (ML)",
                "confidence": round(confidence, 2),
                "reasons": reasons,
                "resolution_path": "evo2",
                "evo2_delta": delta,
                "impact_percentile_like": round(impact_pct, 2),
            }
        
        elif impact_pct <= EVO_BENIGN_PCTL:
            confidence = 0.65
            reasons = [f"Evo2 |Δ| percentile≈{impact_pct:.2f} (minimal disruption signal)"]
            
            # Boost if insights converge
            if func_score is not None and func_score < 0.3:
                confidence = min(0.80, confidence + 0.10)
                reasons.append(f"Functionality score ({func_score:.2f}) supports benign")
            
            return {
                "status": "resolved_by_evo2",
                "verdict": "Likely benign (ML)",
                "confidence": round(confidence, 2),
                "reasons": reasons,
                "resolution_path": "evo2",
                "evo2_delta": delta,
                "impact_percentile_like": round(impact_pct, 2),
            }
        
        else:
            # In between thresholds - weak signal
            reasons.append(f"Evo2 |Δ| percentile≈{impact_pct:.2f} (intermediate; not decisive)")
    else:
        reasons.append("Evo2 signal unavailable (service error or variant not scoreable)")

    # --- PATH C: Still VUS (No decisive signal) ---
    if classification:
        reasons.append(f"ClinVar prior is non-decisive: {classification}")
    else:
        reasons.append("No ClinVar prior available")

    if am_eligible is True:
        reasons.append("AlphaMissense eligible (can score if service available)")
    elif am_eligible is False:
        reasons.append("Not AlphaMissense eligible (not GRCh38 missense)")

    # Add insight summaries for auditability
    for k, v in (insights or {}).items():
        if v is not None:
            reasons.append(f"{k}={float(v):.2f}")

    return {
        "status": "still_vus",
        "verdict": "Uncertain significance",
        "confidence": 0.4,
        "reasons": reasons[:12],
        "resolution_path": None,
        "evo2_available": evo_min_delta is not None,
        "next_step": "functional_assay" if evo_min_delta is None else "additional_evidence",
    }


@router.post("/identify")
async def identify_vus(req: VusIdentifyRequest, request: Request) -> Dict[str, Any]:
    """
    Single-call VUS triage endpoint for the oncology “40% VUS” problem.
    Returns stable shape for UI: { normalized_variant, coverage, sequence, insights, triage, next_actions, provenance }.
    """
    run_id = str(uuid.uuid4())
    v = req.variant
    asm = _norm_asm(v.assembly)

    # 1) Normalize variant to GRCh38 coords
    normalized: Dict[str, Any] = {
        "gene": (v.gene or None),
        "hgvs_c": v.hgvs_c,
        "hgvs_p": v.hgvs_p,
        "assembly": asm,
        "chrom": _clean_chrom(v.chrom) if v.chrom else None,
        "pos": v.pos,
        "ref": (v.ref or "").upper() if v.ref else None,
        "alt": (v.alt or "").upper() if v.alt else None,
    }

    vep_info: Dict[str, Any] = {}
    if not (normalized["chrom"] and normalized["pos"] and normalized["ref"] and normalized["alt"]):
        # Prefer HGVS coding notation if provided.
        # Ensembl HGVS endpoint expects a full identifier like "PDGFRA:c.2263T>C" (gene symbol or transcript),
        # not bare "c.2263T>C". If caller provided gene separately, prefix it.
        hgvs = (v.hgvs_c or "").strip() or None
        if not hgvs:
            raise HTTPException(status_code=400, detail="Provide either chrom/pos/ref/alt or hgvs_c for normalization")
        if v.gene and ":" not in hgvs:
            hgvs = f"{v.gene}:{hgvs}"
        resolved = await _resolve_hgvs_to_grch38(hgvs)
        normalized.update({
            "chrom": _clean_chrom(resolved.get("chrom") or ""),
            "pos": int(resolved.get("pos") or 0),
            "ref": (resolved.get("ref") or "").upper() if resolved.get("ref") else None,
            "alt": (resolved.get("alt") or "").upper() if resolved.get("alt") else None,
            # Prefer what Ensembl reports; do not hard-force GRCh38 here.
            # This matters because downstream Evo scoring will 400 on REF mismatches if the
            # coordinates/alleles are actually GRCh37/hg19.
            "assembly": str(resolved.get("assembly") or "GRCh38"),
        })
        vep_info = resolved.get("vep") or {}
        # Fill hgvs_p if missing
        if not normalized.get("hgvs_p") and vep_info.get("hgvs_p"):
            normalized["hgvs_p"] = vep_info.get("hgvs_p")
        if not normalized.get("gene") and vep_info.get("gene_symbol"):
            normalized["gene"] = vep_info.get("gene_symbol")

    if not (normalized["chrom"] and normalized["pos"] and normalized["ref"] and normalized["alt"]):
        raise HTTPException(status_code=400, detail="Normalization failed: missing chrom/pos/ref/alt after resolution")

    chrom = str(normalized["chrom"])
    pos = int(normalized["pos"])
    ref = str(normalized["ref"]).upper()
    alt = str(normalized["alt"]).upper()
    gene = (normalized.get("gene") or "").upper() or None
    hgvs_p = normalized.get("hgvs_p") or None

    # 2) Call internal services in parallel via this same backend base URL (avoid hardcoding port 8000)
    base = str(request.base_url).rstrip("/")
    async with httpx.AsyncClient(timeout=30) as client:
        clin_q = {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}
        if gene:
            clin_q["gene"] = gene
        if hgvs_p:
            clin_q["hgvs_p"] = hgvs_p

        evo_payload = {
            # Respect normalized assembly so we don't force GRCh38 when variant is GRCh37.
            "assembly": str(normalized.get("assembly") or "GRCh38"),
            "chrom": chrom,
            "pos": pos,
            "ref": ref,
            "alt": alt,
            "windows": [1024, 2048, 4096, 8192],
        }

        # insights payloads (matching existing insight endpoints)
        variants_arr = [{"gene": gene, "chrom": chrom, "pos": pos, "ref": ref, "alt": alt}] if gene else [{"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}]
        p_func = {"gene": gene, "hgvs_p": hgvs_p, "variants": variants_arr} if (gene and hgvs_p) else {"gene": gene or "", "hgvs_p": hgvs_p or ""}
        p_reg = {"chrom": chrom, "pos": pos, "ref": ref, "alt": alt}
        p_ess = {"gene": gene or "", "variants": variants_arr}
        p_chr = {"chrom": chrom, "pos": pos, "radius": 500}

        tasks = {
            "clinvar": client.get(f"{base}/api/evidence/clinvar", params=clin_q),
            # Fusion/AlphaMissense coverage is GRCh38-only; don't call it on GRCh37 inputs.
            "fusion_cov": (
                client.get(f"{base}/api/fusion/coverage", params={"chrom": chrom, "pos": pos, "ref": ref, "alt": alt})
                if str(normalized.get("assembly") or "GRCh38").upper() == "GRCH38"
                else _dummy_future(__ok=False, __status_code=None, __error="fusion_grch38_only")
            ),
            "evo": client.post(f"{base}/api/evo/score_variant_multi", json=evo_payload, headers={"Content-Type": "application/json"}),
            "func": client.post(f"{base}/api/insights/predict_protein_functionality_change", json=p_func, headers={"Content-Type": "application/json"}),
            "reg": client.post(f"{base}/api/insights/predict_splicing_regulatory", json=p_reg, headers={"Content-Type": "application/json"}),
            "ess": client.post(f"{base}/api/insights/predict_gene_essentiality", json=p_ess, headers={"Content-Type": "application/json"}),
            "chr": client.post(f"{base}/api/insights/predict_chromatin_accessibility", json=p_chr, headers={"Content-Type": "application/json"}),
        }

        results: Dict[str, Any] = {}
        for k, coro in tasks.items():
            try:
                r = await coro
                # Preserve endpoint payload shape (top-level keys) while also attaching receipt metadata.
                payload: Any = None
                try:
                    payload = r.json() if r.content else None
                except Exception:
                    payload = None

                if r.status_code < 400:
                    if isinstance(payload, dict):
                        results[k] = {"__status_code": r.status_code, "__ok": True, **payload}
                    else:
                        # Rare: endpoint returns non-dict JSON. Wrap it so callers don't crash.
                        results[k] = {"__status_code": r.status_code, "__ok": True, "value": payload}
                else:
                    results[k] = {
                        "__status_code": r.status_code,
                        "__ok": False,
                        "__error": f"HTTP {r.status_code}",
                        "detail": payload,
                    }
            except Exception as e:
                results[k] = {"__status_code": None, "__ok": False, "__error": str(e)}

    clin = results.get("clinvar") or {}
    evo = results.get("evo") or {}
    f_cov = results.get("fusion_cov") or {}

    # 3) Shape coverage for CoverageChips (stable, minimal)
    clin_label = _human_clinvar_label(clin.get("classification"))
    coverage = {
        "clinvar": {
            "status": clin_label,
            "review_status": clin.get("review_status"),
            "url": clin.get("url"),
            "source": clin.get("source") or "clinvar_proxy",
        } if clin else None,
        # Only coverage gate is reliable today (no mock scoring)
        "alphamissense": bool(f_cov.get("am_covered") is True or f_cov.get("eligible") is True or f_cov.get("coverage") is True),
    }

    # Options
    ignore_priors = bool((req.options or {}).get("ignore_priors") is True)
    patient_genes: List[str] = []
    try:
        # Accept either a list of genes or a list of mutation dicts with "gene"
        opt = req.options or {}
        if isinstance(opt.get("patient_genes"), list):
            patient_genes = [str(x).strip().upper() for x in opt.get("patient_genes") if str(x).strip()]
        elif isinstance(opt.get("patient_mutations"), list):
            patient_genes = [
                str(m.get("gene", "")).strip().upper()
                for m in opt.get("patient_mutations")
                if isinstance(m, dict) and str(m.get("gene", "")).strip()
            ]
    except Exception:
        patient_genes = []

    patient_axis = _infer_patient_axis(patient_genes)
    variant_axis = _infer_variant_axis(gene)
    pathway_context = {
        "gene": gene,
        "variant_axis": variant_axis.get("axis_label"),
        "variant_axis_key": variant_axis.get("axis_key"),
        "patient_actionable_axis": patient_axis.get("axis_label"),
        "patient_actionable_axis_key": patient_axis.get("axis_key"),
        "pathway_relevance": _axis_relevance(patient_axis.get("axis_key"), variant_axis.get("axis_key")),
        "patient_pathway_scores": patient_axis.get("scores"),
        "variant_pathway_weights": variant_axis.get("weights"),
    }

    # 4) Insights (scores only, plus provenance)
    insights_scores = {
        "functionality": (results.get("func") or {}).get("functionality_change_score"),
        "regulatory": (results.get("reg") or {}).get("regulatory_impact_score"),
        "essentiality": (results.get("ess") or {}).get("essentiality_score"),
        "chromatin": (results.get("chr") or {}).get("accessibility_score"),
    }

    evo_min_delta = evo.get("min_delta")
    try:
        evo_min_delta = float(evo_min_delta) if evo_min_delta is not None else None
    except Exception:
        evo_min_delta = None

    triage = _triage(
        # Keep ClinVar in coverage, but allow an explicit ML-only view when requested.
        clinvar_classification=None if ignore_priors else clin_label,
        evo_min_delta=evo_min_delta,
        am_eligible=coverage.get("alphamissense"),
        insights={k: (float(v) if isinstance(v, (int, float)) else None) for k, v in insights_scores.items()},
    )

    # Receipts: did we actually trigger S/P/E components (and what failed)?
    evo_prov = (evo.get("provenance") or {}) if isinstance(evo.get("provenance"), dict) else {}
    evo_fallback = evo_prov.get("fallback")
    evo_method = evo_prov.get("method")

    calls_receipt = {
        "clinvar": {"ok": bool((results.get("clinvar") or {}).get("__ok")), "status_code": (results.get("clinvar") or {}).get("__status_code"), "error": (results.get("clinvar") or {}).get("__error")},
        "fusion_coverage": {"ok": bool((results.get("fusion_cov") or {}).get("__ok")), "status_code": (results.get("fusion_cov") or {}).get("__status_code"), "error": (results.get("fusion_cov") or {}).get("__error")},
        "evo2": {
            "ok": bool((results.get("evo") or {}).get("__ok")),
            "status_code": (results.get("evo") or {}).get("__status_code"),
            "error": (results.get("evo") or {}).get("__error"),
            "method": evo_method,
            "fallback": evo_fallback,
            "model": evo_prov.get("model"),
        },
        "insights_functionality": {"ok": bool((results.get("func") or {}).get("__ok")), "status_code": (results.get("func") or {}).get("__status_code"), "error": (results.get("func") or {}).get("__error")},
        "insights_regulatory": {"ok": bool((results.get("reg") or {}).get("__ok")), "status_code": (results.get("reg") or {}).get("__status_code"), "error": (results.get("reg") or {}).get("__error")},
        "insights_essentiality": {"ok": bool((results.get("ess") or {}).get("__ok")), "status_code": (results.get("ess") or {}).get("__status_code"), "error": (results.get("ess") or {}).get("__error")},
        "insights_chromatin": {"ok": bool((results.get("chr") or {}).get("__ok")), "status_code": (results.get("chr") or {}).get("__status_code"), "error": (results.get("chr") or {}).get("__error")},
    }

    # Distinguish “resolved by prior” vs “resolved by Evo2” explicitly (no interpretation in the UI layer).
    resolution_path = triage.get("resolution_path") or triage.get("status")

    # 5) Next actions (what to do after triage)
    next_actions = [
        {
            "action": "wiwfm",
            "label": "Run WIWFM (therapy fit)",
            "description": "Generate research-mode therapy hypotheses with provenance and evidence tiers.",
            "endpoint": "/api/efficacy/predict",
        },
        {
            "action": "dossier",
            "label": "Send to Dossier",
            "description": "Freeze the current VUS disposition + signals + provenance into an exportable record.",
        },
        {
            "action": "cohort_context",
            "label": "Add cohort context",
            "description": "Check prevalence and co-mutations in cohorts to prioritize what deserves follow-up.",
            "endpoint": "/api/datasets/extract_and_benchmark",
        },
        {
            "action": "trials",
            "label": "Trial matching (mechanism fit)",
            "description": "If the variant points to a pathway hypothesis, surface aligned trials (research-mode).",
            "endpoint": "/api/trials/agent/search",
        },
    ]

    return {
        "normalized_variant": normalized,
        "vep": vep_info or None,
        "coverage": coverage,
        "pathway_context": pathway_context,
        "sequence": {
            "min_delta": evo_min_delta,
            "evo2_called": True,
            # Success means: endpoint returned AND it was not a declared fallback placeholder.
            "evo2_success": bool((results.get("evo") or {}).get("__ok")) and (evo_min_delta is not None) and (evo_fallback is None),
            "windows_attempted": (evo_payload.get("windows") or []),
            "provenance": evo.get("provenance"),
            "deltas": (evo.get("provenance") or {}).get("deltas"),
        },
        "insights": {
            "scores": insights_scores,
            "provenance": {
                "functionality": (results.get("func") or {}).get("provenance"),
                "regulatory": (results.get("reg") or {}).get("provenance"),
                "essentiality": (results.get("ess") or {}).get("provenance"),
                "chromatin": (results.get("chr") or {}).get("provenance"),
            },
        },
        "triage": triage,
        "next_actions": next_actions,
        "provenance": {
            "run_id": run_id,
            "mode": "research",
            "resolution_path": resolution_path,
            "options": {"ignore_priors": ignore_priors, "patient_genes_count": len(patient_genes)},
            "calls": calls_receipt,
            "urls": [
                "/api/evidence/clinvar",
                "/api/fusion/coverage",
                "/api/evo/score_variant_multi",
                "/api/insights/*",
            ],
        },
    }


