"""
Myeloma Digital Twin prediction endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import json
import httpx
from httpx import Timeout
from hashlib import sha256
import time
import asyncio
import math

from ..config import (
    USE_CASES, EVO_TIMEOUT, SUPABASE_URL, SUPABASE_KEY, 
    SUPABASE_RUNS_TABLE, SUPABASE_RUN_VARIANTS_TABLE
)
from ..services.supabase_service import _supabase_insert
from ..services.job_service import _variant_call_from_detail

router = APIRouter(prefix="/api", tags=["myeloma"])

def _choose_base(model_id: str) -> str:
    """Choose the appropriate base URL for the model"""
    from ..config import MODEL_TO_BASE
    return MODEL_TO_BASE.get(model_id.lower(), MODEL_TO_BASE["evo2_7b"])

async def clinvar_context(request: Dict[str, Any]) -> Dict[str, Any]:
    """Get ClinVar context for a variant (placeholder implementation)"""
    # This would normally call the actual clinvar_context function
    # For now, return empty context
    return {}

@router.post("/predict/myeloma_drug_response")
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

@router.get("/use_cases")
async def list_use_cases():
    return {"use_cases": list(USE_CASES.values())}

@router.get("/use_cases/{use_case_id}")
async def get_use_case(use_case_id: str):
    cfg = USE_CASES.get((use_case_id or "").lower())
    if not cfg:
        raise HTTPException(status_code=404, detail="use_case not found")
    return cfg

@router.post("/predict")
async def predict_generic(request: Dict[str, Any]):
    if not isinstance(request, dict):
        raise HTTPException(status_code=400, detail="invalid payload")
    use_case_id = (request.get("use_case_id") or "myeloma").lower()
    if use_case_id != "myeloma":
        raise HTTPException(status_code=501, detail=f"Use case '{use_case_id}' not implemented yet")
    # Route to myeloma-specific handler
    return await predict_myeloma_response(request) 
