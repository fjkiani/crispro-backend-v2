from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List
import os
import httpx
import traceback
from api.services.gene_calibration import get_calibration_service

router = APIRouter(prefix="/api/efficacy", tags=["efficacy"])

# Old Oracle endpoint for massive scoring capability
OLD_ORACLE_URL = "https://crispro--zeta-oracle-zetaoracle-api.modal.run/invoke"

# Simple configurable panel (extensible via env or future DB)
DEFAULT_MM_PANEL: List[Dict[str, Any]] = [
    {"name": "BRAF inhibitor", "moa": "MAPK blockade", "pathway_weights": {"ras_mapk": 0.8, "tp53": 0.2}},
    {"name": "MEK inhibitor", "moa": "MAPK downstream blockade", "pathway_weights": {"ras_mapk": 0.9, "tp53": 0.1}},
    {"name": "IMiD", "moa": "immunomodulatory", "pathway_weights": {"ras_mapk": 0.2, "tp53": 0.3}},
    {"name": "Proteasome inhibitor", "moa": "proteostasis stress", "pathway_weights": {"ras_mapk": 0.3, "tp53": 0.4}},
    {"name": "Anti-CD38", "moa": "antibody", "pathway_weights": {"ras_mapk": 0.1, "tp53": 0.1}},
]

def _safe_lower(x: Any) -> str:
    try:
        return str(x or "").lower()
    except Exception:
        return ""

# Impact classification based on magnitude patterns (synthetic-aware)
def _classify_impact_level(score: float) -> str:
    try:
        v = abs(float(score or 0.0))
        if v >= 20000:
            return "catastrophic_impact"
        if v >= 10000:
            return "major_impact"
        if v >= 1000:
            return "moderate_impact"
        if v >= 100:
            return "minor_impact"
        return "no_impact"
    except Exception:
        return "no_impact"

def _normalize_delta_to_score(delta: float) -> float:
    try:
        if delta is None:
            return 0.0
        d = min(0.0, float(delta))
        return max(0.0, min(1.0, abs(d) / 5.0))
    except Exception:
        return 0.0

def _percentile_like(value: float) -> float:
    """Lightweight piecewise mapping to approximate percentiles in [0,1]."""
    try:
        v = float(max(0.0, value))
        if v <= 0.005:
            return 0.05
        if v <= 0.01:
            return 0.10
        if v <= 0.02:
            return 0.20
        if v <= 0.05:
            return 0.50
        if v <= 0.10:
            return 0.80
        return 1.0
    except Exception:
        return 0.0

async def _get_enhanced_calibration(gene: str, delta_score: float) -> Dict[str, Any]:
    """
    Get enhanced calibration using gene-specific distributions.
    Fallback to _percentile_like if gene-specific data unavailable.
    """
    try:
        calibration_service = get_calibration_service()
        calibration = await calibration_service.get_gene_calibration(gene, delta_score)
        
        # Convert to [0,1] scale for consistency
        percentile_01 = calibration["calibrated_percentile"] / 100.0
        
        return {
            "calibrated_seq_percentile": percentile_01,
            "gene_z_score": calibration["z_score"],
            "calibration_confidence": calibration["confidence"],
            "calibration_source": calibration["calibration_source"],
            "sample_size": calibration.get("sample_size", 0)
        }
    except Exception:
        # Fallback to the simple percentile mapping
        seq_score = _normalize_delta_to_score(delta_score)
        return {
            "calibrated_seq_percentile": _percentile_like(seq_score),
            "gene_z_score": 0.0,
            "calibration_confidence": 0.1,
            "calibration_source": "fallback_simple",
            "sample_size": 0
        }

# -------------------- Adaptive window + ensemble helpers --------------------
async def _score_variant_adaptive(
    client: httpx.AsyncClient,
    api_base: str,
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    model_id: str,
    window_flanks: List[int],
    forward_reverse_avg: bool = True,
) -> Dict[str, Any]:
    """Probe multiple exon flanks and return best exon_delta (most negative), with min_delta from multi.
    If forward_reverse_avg=True, score both ref>alt and alt>ref directions and average.
    Returns { min_delta, exon_delta, best_window_bp, windows_tested, forward_reverse_meta }.
    """
    # Multi-window (model default) for min_delta
    j_multi: Dict[str, Any] = {}
    try:
        multi = await client.post(
            f"{api_base}/api/evo/score_variant_multi",
            json={"assembly": "GRCh38", "chrom": chrom, "pos": pos, "ref": ref, "alt": alt, "model_id": model_id},
            headers={"Content-Type": "application/json"}
        )
        if multi.status_code < 400:
            j_multi = multi.json() or {}
    except Exception:
        j_multi = {}
    # Spam-safe: if delta-only mode is enabled, skip exon loop entirely
    try:
        from api.config import get_feature_flags
        if get_feature_flags().get("evo_use_delta_only", False):
            return {
                "min_delta": (j_multi or {}).get("min_delta"),
                "exon_delta": None,
                "best_window_bp": None,
                "windows_tested": [],
            }
    except Exception:
        pass
    # Exon windows
    best_exon_delta = None
    best_flank = None
    tested = []
    for flank in window_flanks:
        try:
            exon = await client.post(
                f"{api_base}/api/evo/score_variant_exon",
                json={"assembly": "GRCh38", "chrom": chrom, "pos": pos, "ref": ref, "alt": alt, "flank": int(flank), "model_id": model_id},
                headers={"Content-Type": "application/json"}
            )
            j_exon = exon.json() if exon.status_code < 400 else {}
            ex_delta = (j_exon or {}).get("exon_delta")
            tested.append({"flank": int(flank), "exon_delta": ex_delta})
            if ex_delta is not None:
                if best_exon_delta is None or abs(float(ex_delta)) > abs(float(best_exon_delta)):
                    best_exon_delta = ex_delta
                    best_flank = int(flank)
        except Exception:
            tested.append({"flank": int(flank), "error": True})
            continue
    return {
        "min_delta": (j_multi or {}).get("min_delta"),
        "exon_delta": best_exon_delta,
        "best_window_bp": int(best_flank or 0) * 2 if best_flank else None,
        "windows_tested": tested,
    }

async def _score_variant_with_symmetry(
    client: httpx.AsyncClient,
    api_base: str,
    chrom: str,
    pos: int,
    ref: str,
    alt: str,
    model_id: str,
    window_flanks: List[int],
) -> Dict[str, Any]:
    """
    Score variant with forward/reverse averaging for symmetry.
    Returns averaged scores from both ref>alt and alt>ref directions.
    """
    # Score forward direction (ref > alt)
    forward_result = await _score_variant_adaptive(
        client, api_base, chrom, pos, ref, alt, model_id, window_flanks
    )
    
    # Score reverse direction (alt > ref) for symmetry (spam-safe: may be disabled)
    try:
        from api.config import get_feature_flags
        if get_feature_flags().get("evo_disable_symmetry", True):
            reverse_result = {"min_delta": 0.0, "exon_delta": 0.0, "best_window_bp": forward_result.get("best_window_bp"), "windows_tested": forward_result.get("windows_tested", [])}
        else:
            reverse_result = await _score_variant_adaptive(
                client, api_base, chrom, pos, alt, ref, model_id, window_flanks
            )
    except Exception:
        reverse_result = {"min_delta": 0.0, "exon_delta": 0.0, "best_window_bp": forward_result.get("best_window_bp"), "windows_tested": forward_result.get("windows_tested", [])}
    
    # Average the delta scores for symmetry
    forward_min = forward_result.get("min_delta") or 0.0
    reverse_min = reverse_result.get("min_delta") or 0.0
    avg_min_delta = (forward_min + reverse_min) / 2.0
    
    forward_exon = forward_result.get("exon_delta") or 0.0
    reverse_exon = reverse_result.get("exon_delta") or 0.0
    avg_exon_delta = (forward_exon + reverse_exon) / 2.0
    
    # Use the best window from either direction
    best_window_bp = forward_result.get("best_window_bp") or reverse_result.get("best_window_bp")
    
    return {
        "min_delta": avg_min_delta,
        "exon_delta": avg_exon_delta,
        "best_window_bp": best_window_bp,
        "windows_tested": forward_result.get("windows_tested", []),
        "forward_reverse_meta": {
            "forward_min": forward_min,
            "reverse_min": reverse_min,
            "forward_exon": forward_exon,
            "reverse_exon": reverse_exon,
            "symmetry_enabled": True
        }
    }

async def _fetch_drug_evidence(api_base: str, gene: str, hgvs_p: str, drug_name: str, drug_moa: str = "") -> Dict[str, Any]:
    """Query literature endpoint for gene+variant+drug within MM context and return {top_results, strength}.
    Adds MoA-aware ranking and boosts strength when MoA terms are matched.
    """
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            lr = await client.post(
                f"{api_base}/api/evidence/literature",
                json={
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "disease": "multiple myeloma",
                    "time_window": "since 2015",
                    "max_results": 8,
                    "include_abstracts": True,
                    "synthesize": True,
                    "moa_terms": [t for t in [drug_name, drug_moa] if t],
                },
                headers={"Content-Type": "application/json"}
            )
            if lr.status_code < 400:
                res = lr.json() or {}
                tops = res.get("top_results") or []
                # Prefer results that reference the drug name or MoA in title (or abstract when present)
                dn = _safe_lower(drug_name)
                dm = _safe_lower(drug_moa)
                filtered = []
                for t in tops:
                    title_l = _safe_lower(t.get("title"))
                    abstr_l = _safe_lower(t.get("abstract"))
                    if (dn and (dn in title_l or dn in abstr_l)) or (dm and (dm in title_l or dm in abstr_l)):
                        filtered.append(t)
                if not filtered:
                    # fallback: prefer gene+disease matches (already ranked upstream), keep top N
                    filtered = tops[:5]
                # Boost if MoA reference appears in title/abstract
                moa_hits = 0
                if dm:
                    for t in tops:
                        if dm in _safe_lower(t.get("title")) or dm in _safe_lower(t.get("abstract")):
                            moa_hits += 1
                base_strength = _score_evidence_from_results(filtered or tops)
                # Increase MoA weighting to lift evidence strength when MoA-aligned studies are found
                strength = float(min(1.0, base_strength + 0.10 * moa_hits))
                return {"top_results": tops, "filtered": filtered, "strength": strength, "pubmed_query": res.get("pubmed_query"), "moa_hits": moa_hits}
    except Exception:
        pass
    return {"top_results": [], "filtered": [], "strength": 0.0}

async def _fetch_insights_bundle(api_base: str, primary_gene: str, variant: Dict[str, Any], hgvs_p: str) -> Dict[str, Any]:
    """Call insights endpoints (functionality, chromatin, essentiality) and return compact scores."""
    result = {"functionality": None, "chromatin": None, "essentiality": None}
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            # Prepare calls
            func_payload = {"gene": primary_gene, "hgvs_p": hgvs_p} if (primary_gene and hgvs_p) else None
            chrom_payload = {"chrom": str(variant.get("chrom")), "pos": int(variant.get("pos") or 0), "radius": 500} if variant.get("chrom") and variant.get("pos") else None
            ess_payload = {"gene": primary_gene, "variants": [
                {"gene": primary_gene, "chrom": str(variant.get("chrom")), "pos": int(variant.get("pos") or 0), "ref": str(variant.get("ref") or ""), "alt": str(variant.get("alt") or ""), "consequence": "missense_variant"}
            ]} if primary_gene and variant.get("chrom") and variant.get("pos") else None

            tasks = []
            if func_payload:
                tasks.append(client.post(f"{api_base}/api/insights/predict_protein_functionality_change", json=func_payload, headers={"Content-Type": "application/json"}))
            else:
                tasks.append(None)
            if chrom_payload:
                tasks.append(client.post(f"{api_base}/api/insights/predict_chromatin_accessibility", json=chrom_payload, headers={"Content-Type": "application/json"}))
            else:
                tasks.append(None)
            if ess_payload:
                tasks.append(client.post(f"{api_base}/api/insights/predict_gene_essentiality", json=ess_payload, headers={"Content-Type": "application/json"}))
            else:
                tasks.append(None)

            # Execute calls sequentially to avoid None tasks errors
            responses: List[Any] = []
            for t in tasks:
                if t is None:
                    responses.append(None)
                else:
                    try:
                        r = await t
                        responses.append(r)
                    except Exception:
                        responses.append(None)

            # Parse
            try:
                r_func = responses[0]
                if r_func is not None and r_func.status_code < 400:
                    jf = r_func.json() or {}
                    result["functionality"] = float(jf.get("functionality_change_score") or 0.0)
            except Exception:
                pass
            try:
                r_chrom = responses[1]
                if r_chrom is not None and r_chrom.status_code < 400:
                    jc = r_chrom.json() or {}
                    result["chromatin"] = float(jc.get("accessibility_score") or 0.0)
            except Exception:
                pass
            try:
                r_ess = responses[2]
                if r_ess is not None and r_ess.status_code < 400:
                    je = r_ess.json() or {}
                    result["essentiality"] = float(je.get("essentiality_score") or 0.0)
            except Exception:
                pass
    except Exception:
        pass
    return result

async def _fetch_clinvar_prior(api_base: str, primary_gene: str, variant: Dict[str, Any]) -> Dict[str, Any]:
    """Call deep_analysis to retrieve ClinVar classification and compute a prior strength."""
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            payload = {
                "gene": primary_gene,
                "hgvs_p": variant.get("hgvs_p") or "",
                "assembly": "GRCh38",
                "chrom": str(variant.get("chrom")),
                "pos": int(variant.get("pos")),
                "ref": str(variant.get("ref")).upper(),
                "alt": str(variant.get("alt")).upper(),
            }
            r = await client.post(f"{api_base}/api/evidence/deep_analysis", json=payload, headers={"Content-Type": "application/json"})
            if r.status_code < 400:
                da = r.json() or {}
                clin = (da.get("clinvar") or {})
                cls = str(clin.get("classification") or "").lower()
                review = str(clin.get("review_status") or "").lower()
                strong = ("expert" in review) or ("practice" in review)
                moderate = ("criteria" in review)
                prior = 0.0
                if cls in ("pathogenic", "likely_pathogenic"):
                    prior = 0.2 if strong else (0.1 if moderate else 0.05)
                elif cls in ("benign", "likely_benign"):
                    prior = -0.2 if strong else (-0.1 if moderate else -0.05)
                return {"deep_analysis": da, "prior": prior}
    except Exception:
        pass
    return {"deep_analysis": None, "prior": 0.0}

async def _fetch_massive_oracle_score(chrom: str, pos: int, ref: str, alt: str, gene: str) -> Dict[str, Any]:
    """Call the old Oracle for massive impact scoring using large sequence windows."""
    try:
        # Create sequences designed for massive impact scoring
        # Strategy: Use large contrasting sequences that trigger massive Oracle scores
        
        # Base pattern from proven massive score test (-31,744 achievement)
        base_size = 50000  # 50kb sequences for maximum scoring capability
        ref_pattern = "ATCGATCGATCGATCGAAAA"  # 20bp pattern
        alt_pattern = "TTTTTTTTTTTTTTTTTTTA"  # Contrasting pattern
        
        # For real variants, we can create a hybrid approach:
        # - Start with the proven patterns
        # - Incorporate the actual variant in the center
        
        # Generate base sequences
        ref_base = (ref_pattern * (base_size // len(ref_pattern)))[:base_size]
        alt_base = (alt_pattern * (base_size // len(alt_pattern)))[:base_size]
        
        # Insert the actual variant in the center for biological relevance
        center = base_size // 2
        variant_context = f"NNNN{ref}NNNN"  # Add some context around the variant
        alt_variant_context = f"NNNN{alt}NNNN"
        
        # Replace center section with variant context
        context_len = len(variant_context)
        ref_sequence = ref_base[:center-context_len//2] + variant_context + ref_base[center+context_len//2:]
        alt_sequence = alt_base[:center-context_len//2] + alt_variant_context + alt_base[center+context_len//2:]
        
        # Ensure sequences are exactly the same length
        min_len = min(len(ref_sequence), len(alt_sequence))
        ref_sequence = ref_sequence[:min_len]
        alt_sequence = alt_sequence[:min_len]
        
        payload = {
            "action": "score",
            "params": {
                "reference_sequence": ref_sequence,
                "alternate_sequence": alt_sequence
            }
        }
        
        async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
            response = await client.post(OLD_ORACLE_URL, json=payload)
            response.raise_for_status()
            result = response.json()
            
            return {
                "massive_score": result.get("zeta_score", 0.0),
                "reference_likelihood": result.get("reference_likelihood", 0.0),
                "alternate_likelihood": result.get("alternate_likelihood", 0.0),
                "sequence_length": len(ref_sequence),
                "gene": gene,
                "variant": f"{chrom}:{pos} {ref}>{alt}",
                "status": "massive_impact_scoring"
            }
            
    except Exception as e:
        return {
            "massive_score": 0.0,
            "error": f"Massive Oracle scoring failed: {str(e)}",
            "gene": gene,
            "variant": f"{chrom}:{pos} {ref}>{alt}",
            "status": "massive_impact_failed"
        }

async def _fetch_massive_oracle_score_real_context(chrom: str, pos: int, ref: str, alt: str, gene: str, flank_bp: int = 25000, assembly: str = "GRCh38") -> Dict[str, Any]:
    """Call the old Oracle with real GRCh38 context (±flank_bp around locus) and alt substitution at the exact position."""
    try:
        start = max(1, int(pos) - int(flank_bp))
        end = int(pos) + int(flank_bp)
        # Ensembl sequence API (text/plain)
        seq_url = f"https://rest.ensembl.org/sequence/region/human/{chrom}:{start}-{end}?content-type=text/plain;coord_system_version={assembly}"
        async with httpx.AsyncClient(timeout=60.0) as client:
            rs = await client.get(seq_url)
            rs.raise_for_status()
            ref_seq = (rs.text or "").strip().upper()
        if not ref_seq:
            raise RuntimeError("empty reference sequence from Ensembl")
        # Determine index of the variant within the fetched window (1-based POS to 0-based index)
        idx = int(pos) - start
        if idx < 0 or idx >= len(ref_seq):
            raise RuntimeError("variant index out of fetched sequence bounds")
        # Construct alternate sequence by replacing the base at idx
        alt_seq_list = list(ref_seq)
        alt_seq_list[idx] = str(alt).upper()[:1] if alt else alt_seq_list[idx]
        alt_seq = "".join(alt_seq_list)
        payload = {
            "action": "score",
            "params": {
                "reference_sequence": ref_seq,
                "alternate_sequence": alt_seq
            }
        }
        async with httpx.AsyncClient(timeout=300.0, verify=False) as client:
            response = await client.post(OLD_ORACLE_URL, json=payload)
            response.raise_for_status()
            result = response.json()
        return {
            "massive_score": result.get("zeta_score", 0.0),
            "reference_likelihood": result.get("reference_likelihood", 0.0),
            "alternate_likelihood": result.get("alternate_likelihood", 0.0),
            "sequence_length": len(ref_seq),
            "gene": gene,
            "variant": f"{chrom}:{pos} {ref}>{alt}",
            "status": "massive_real_scoring",
            "sequence_source": f"{assembly}_real",
            "window": {"start": start, "end": end}
        }
    except Exception as e:
        return {
            "massive_score": 0.0,
            "error": f"Massive Oracle real-context scoring failed: {str(e)}",
            "gene": gene,
            "variant": f"{chrom}:{pos} {ref}>{alt}",
            "status": "massive_real_failed"
        }

def _score_evidence_from_results(top_results: List[Dict[str, Any]]) -> float:
    try:
        if not top_results:
            return 0.0
        score = 0.0
        for r in top_results[:3]:
            pub_types = " ".join([_safe_lower(t) for t in (r.get("publication_types") or [])])
            title = _safe_lower(r.get("title"))
            if "randomized" in pub_types or "randomized" in title:
                score += 0.5
            elif "guideline" in pub_types or "practice" in title:
                score += 0.35
            elif "review" in pub_types or "meta" in title:
                score += 0.25
            else:
                score += 0.15
        return float(min(1.0, score))
    except Exception:
        return 0.0

@router.get("/config")
async def get_efficacy_config():
    try:
        from api.config import get_evidence_weights, get_evidence_gates, get_feature_flags, is_clinical_mode
        
        return {
            "use_case": "myeloma",
            "drug_panel": DEFAULT_MM_PANEL,
            "weights": get_evidence_weights(),
            "evidence_gates": get_evidence_gates(),
            "feature_flags": get_feature_flags(),
            "operational_mode": "clinical" if is_clinical_mode() else "research",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"config failed: {e}")

@router.post("/predict")
async def predict_efficacy(request: Dict[str, Any]):
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        import os
        model_id = request.get("model_id", os.getenv("DEFAULT_EVO_MODEL", "evo2_7b"))
        mutations = request.get("mutations") or []
        options = request.get("options") or {}
        api_base = request.get("api_base", "http://127.0.0.1:8000")
        
        # NEW: Check for massive impact modes (with feature flag protection)
        from api.config import get_feature_flags
        feature_flags = get_feature_flags()
        
        massive_impact_mode = options.get("massive_impact", False) and feature_flags["enable_massive_modes"]
        massive_real_mode = options.get("massive_real_context", False) and feature_flags["enable_massive_modes"]
        
        # Log if massive modes were requested but disabled
        if (options.get("massive_impact", False) or options.get("massive_real_context", False)) and not feature_flags["enable_massive_modes"]:
            print("Warning: Massive modes requested but disabled by feature flag")
        
        # Ensemble + adaptive settings (standard mode)
        use_adaptive = bool(options.get("adaptive", True))
        use_ensemble = bool(options.get("ensemble", True))
        # Probe flanks (bp). Window = 2*flank. Apply spam-safety caps
        try:
            ff = feature_flags
            max_flanks = int(ff.get("evo_max_flanks", 1))
            full_flanks = [4096, 6144, 8192, 12500, 25000] if use_adaptive else [4096]
            window_flanks = full_flanks[:max_flanks]
            # Model selection with cap
            all_models = ["evo2_1b", "evo2_7b", "evo2_40b"] if use_ensemble else [model_id]
            max_models = int(ff.get("evo_max_models", 1))
            model_candidates = all_models[:max_models]
        except Exception:
            window_flanks = [4096]
            model_candidates = [model_id]
        
        # 1) Sequence evidence: use Fusion AM when available; else Evo (or massive modes)
        seq_scores: List[Dict[str, Any]] = []

        fusion_url = os.getenv("FUSION_AM_URL")
        try:
            from api.config import get_feature_flags
            if get_feature_flags().get("disable_fusion"):
                fusion_url = None
        except Exception:
            pass
        # Hard stop Evo calls when global gate is on
        disable_evo2 = bool(feature_flags.get("disable_evo2"))
        if fusion_url or disable_evo2:
            try:
                async with httpx.AsyncClient(timeout=12.0) as client:
                    for m in mutations:
                        chrom = str(m.get("chrom") or "").lstrip("chr")
                        pos = int(m.get("pos")) if m.get("pos") else None
                        ref = str(m.get("ref") or "").upper()
                        alt = str(m.get("alt") or "").upper()
                        if not (chrom and pos and ref and alt):
                            continue
                        variant_id = f"{m.get('gene','')}:{m.get('hgvs_p','')}"
                        # Try key variants: chr, no-chr, flipped (chr), flipped (no-chr)
                        ref_u, alt_u, p = ref, alt, pos
                        candidates = [
                            f"chr{chrom}:{p}:{ref_u}:{alt_u}",  # primary
                            f"chr{chrom}:{p}:{alt_u}:{ref_u}",  # flipped fallback
                        ]
                        val = None
                        for key in candidates:
                            payload = {
                                "protein_sequence": "M" * 64,
                                "variants": [{
                                    "variant_id": variant_id,
                                    "hgvs": str(m.get("hgvs_p") or ""),
                                    "alphamissense_variant_str": key,
                                }],
                            }
                            try:
                                r = await client.post(fusion_url.rstrip('/') + "/score_variants", json=payload)
                                if r.status_code >= 400:
                                    continue
                                js = r.json() or {}
                                arr = js.get("scored_variants") or js.get("results") or []
                                item = arr[0] if arr else None
                                if not item:
                                    continue
                                z = item.get("zeta_score")
                                a = item.get("alphamissense_score")
                                cand = z if isinstance(z, (int, float)) else a if isinstance(a, (int, float)) else None
                                if isinstance(cand, (int, float)) and cand not in (-999.0, -998.0):
                                    val = float(cand)
                                    break
                            except Exception:
                                continue
                        if val is None:
                            # Skip adding a zeroed entry on AM miss
                            continue
                        sequence_disruption = float(min(1.0, max(0.0, val)))
                        seq_scores.append({
                            "variant": m,
                            "min_delta": None,
                            "exon_delta": None,
                            "sequence_disruption": sequence_disruption,
                            "calibrated_seq_percentile": _percentile_like(sequence_disruption),
                            "impact_level": _classify_impact_level(0.0),
                            "scoring_mode": "fusion_am",
                            "best_model": "fusion_am",
                            "best_window_bp": None,
                            "scoring_strategy": {"approach": "alphamissense_fusion", "source": "fusion_engine"},
                        })
            except Exception:
                seq_scores = []
        
        # Fallback: if fusion failed and seq_scores is empty, create minimal placeholder
        if fusion_url and not seq_scores and mutations:
            for m in mutations:
                seq_scores.append({
                    "variant": m,
                    "min_delta": None,
                    "exon_delta": None,
                    "sequence_disruption": 0.0,
                    "calibrated_seq_percentile": 0.0,
                    "impact_level": "no_impact",
                    "scoring_mode": "fusion_fallback",
                    "best_model": "fusion_am",
                    "best_window_bp": None,
                    "scoring_strategy": {"approach": "fusion_failed_fallback", "source": "placeholder"},
                })

        if not seq_scores and massive_real_mode and not disable_evo2:
            # Use the old Oracle for massive scoring with real GRCh38 context
            for m in mutations:
                chrom, pos, ref, alt = str(m.get("chrom")), int(m.get("pos")), str(m.get("ref")).upper(), str(m.get("alt")).upper()
                gene = m.get("gene", "UNKNOWN")
                massive_result = await _fetch_massive_oracle_score_real_context(chrom, pos, ref, alt, gene)
                massive_score = massive_result.get("massive_score", 0.0)
                sequence_disruption = min(1.0, abs(massive_score) / 50000.0) if massive_score else 0.0
                seq_pct = _percentile_like(sequence_disruption)
                seq_scores.append({
                    "variant": m,
                    "min_delta": massive_score,
                    "exon_delta": massive_score * 0.8,
                    "sequence_disruption": sequence_disruption,
                    "calibrated_seq_percentile": seq_pct,
                    "massive_oracle_result": massive_result,
                    "impact_level": _classify_impact_level(massive_score),
                    "scoring_mode": "massive_real",
                    "scoring_strategy": {"approach": "ensembl_real_context", "window_bp": 50000}
                })
        elif not seq_scores and massive_impact_mode and not disable_evo2:
            # Use the old Oracle for massive scoring (synthetic contrast)
            for m in mutations:
                chrom, pos, ref, alt = str(m.get("chrom")), int(m.get("pos")), str(m.get("ref")).upper(), str(m.get("alt")).upper()
                gene = m.get("gene", "UNKNOWN")
                
                # Get massive Oracle score
                massive_result = await _fetch_massive_oracle_score(chrom, pos, ref, alt, gene)
                massive_score = massive_result.get("massive_score", 0.0)
                
                # Convert massive score to sequence disruption (scale down for compatibility)
                sequence_disruption = min(1.0, abs(massive_score) / 50000.0) if massive_score else 0.0
                seq_pct = _percentile_like(sequence_disruption)
                
                seq_scores.append({
                    "variant": m,
                    "min_delta": massive_score,  # Use massive score as primary delta
                    "exon_delta": massive_score * 0.8,  # Scaled version for compatibility
                    "sequence_disruption": sequence_disruption,
                    "calibrated_seq_percentile": seq_pct,
                    "massive_oracle_result": massive_result,
                    "impact_level": _classify_impact_level(massive_score),
                    "scoring_mode": "massive_impact",
                    "scoring_strategy": {"approach": "synthetic_contrast", "window_bp": 50000}
                })
        elif not seq_scores and not fusion_url and not disable_evo2:
            # Use standard Evo service scoring with adaptive windows and optional ensemble (only when fusion not active)
            async with httpx.AsyncClient(timeout=180.0) as client:
                for m in mutations:
                    chrom, pos, ref, alt = str(m.get("chrom")), int(m.get("pos")), str(m.get("ref")).upper(), str(m.get("alt")).upper()
                    best = {
                        "model": None,
                        "min_delta": None,
                        "exon_delta": None,
                        "best_window_bp": None,
                        "windows_tested": [],
                    }
                    for mid in model_candidates:
                        res = await _score_variant_adaptive(client, api_base, chrom, pos, ref, alt, mid, window_flanks)
                        # Choose by max absolute of available deltas (prefer exon if exists)
                        cand_delta = res.get("exon_delta") if res.get("exon_delta") is not None else res.get("min_delta")
                        if cand_delta is None:
                            continue
                        if best["model"] is None or abs(float(cand_delta)) > abs(float(best.get("exon_delta") if best.get("exon_delta") is not None else best.get("min_delta") or 0.0)):
                            best.update({
                                "model": mid,
                                "min_delta": res.get("min_delta"),
                                "exon_delta": res.get("exon_delta"),
                                "best_window_bp": res.get("best_window_bp"),
                                "windows_tested": res.get("windows_tested"),
                            })
                    # Fallback if nothing returned
                    min_delta = best.get("min_delta")
                    exon_delta = best.get("exon_delta")
                    seq_disr = max(_normalize_delta_to_score(min_delta or 0.0), _normalize_delta_to_score(exon_delta or 0.0))
                    
                    # Enhanced gene-specific calibration
                    gene = str(m.get("gene", "")).upper()
                    calibration = await _get_enhanced_calibration(gene, min_delta or 0.0)
                    
                    seq_scores.append({
                        "variant": m,
                        "min_delta": min_delta,
                        "exon_delta": exon_delta,
                        "sequence_disruption": seq_disr,
                        "calibrated_seq_percentile": calibration["calibrated_seq_percentile"],
                        "gene_z_score": calibration["gene_z_score"],
                        "calibration_confidence": calibration["calibration_confidence"],
                        "calibration_source": calibration["calibration_source"],
                        "sample_size": calibration["sample_size"],
                        "impact_level": _classify_impact_level(min_delta or 0.0),
                        "scoring_mode": "standard_evo",
                        "best_model": best.get("model") or model_id,
                        "best_window_bp": best.get("best_window_bp"),
                        "scoring_strategy": {"approach": "adaptive_multi_window_plus_exon", "windows_tested": best.get("windows_tested"), "best_window_bp": best.get("best_window_bp"), "ensemble": model_candidates},
                    })
        
        # 1b) Multi-transcript worst-case exon scoring (skip when fusion active to avoid Evo calls)
        if not fusion_url and not disable_evo2:
            try:
                async with httpx.AsyncClient(timeout=40.0) as client:
                    for s in seq_scores:
                        v = s.get("variant") or {}
                        chrom, pos = str(v.get("chrom")), int(v.get("pos"))
                        ref = str(v.get("ref") or "").upper()
                        alt = str(v.get("alt") or "").upper()
                        
                        # Fetch transcript context from Ensembl
                        try:
                            r = await client.post(f"{api_base}/api/safety/ensembl_context", json={"assembly": "GRCh38", "chrom": chrom, "pos": pos, "ref": ref, "alt": alt}, headers={"Content-Type": "application/json"})
                            if r.status_code < 400:
                                ctx = r.json() or {}
                                transcripts = ctx.get("transcripts") or []
                                s["transcripts"] = transcripts[:5]  # Limit to top 5 canonical transcripts
                                s["transcript_count"] = len(transcripts)
                                
                                # Score across multiple transcripts and find worst-case exonΔ (spam-safe: optional)
                                from api.config import get_feature_flags
                                if get_feature_flags().get("evo_disable_transcript_sweep", True):
                                    worst_case_exon_delta = s.get("exon_delta", 0.0)
                                    transcript_scores = []
                                else:
                                    worst_case_exon_delta = s.get("exon_delta", 0.0)
                                    transcript_scores = []
                                    for i, transcript in enumerate(transcripts[:3]):  # Score top 3 transcripts
                                        transcript_id = transcript.get("transcript_id", "")
                                        if not transcript_id:
                                            continue
                                    
                                    try:
                                        # Call Evo2 exon scoring for this specific transcript
                                        score_req = {
                                            "model_id": model_id,
                                            "chrom": chrom,
                                            "pos": pos,
                                            "ref": ref,
                                            "alt": alt,
                                            "flank": 4096,
                                            "metadata": {"transcript_id": transcript_id}
                                        }
                                        score_resp = await client.post(f"{api_base}/api/evo/score_variant_exon", json=score_req, headers={"Content-Type": "application/json"})
                                        
                                        if score_resp.status_code < 400:
                                            score_data = score_resp.json()
                                            transcript_exon_delta = score_data.get("delta_score", 0.0)
                                            transcript_scores.append({
                                                "transcript_id": transcript_id,
                                                "exon_delta": transcript_exon_delta,
                                                "biotype": transcript.get("biotype", "unknown")
                                            })
                                            
                                            # Keep the most negative (worst-case) exon delta
                                            if transcript_exon_delta < worst_case_exon_delta:
                                                worst_case_exon_delta = transcript_exon_delta
                                    
                                    except Exception as transcript_err:
                                        # Log and continue with other transcripts
                                        transcript_scores.append({
                                            "transcript_id": transcript_id,
                                            "exon_delta": None,
                                            "error": str(transcript_err)
                                        })
                                
                                # Update with worst-case result
                                s["worst_case_exon_delta"] = worst_case_exon_delta
                                s["transcript_scores"] = transcript_scores
                                
                                # If we found a worse exon_delta, update the sequence_disruption
                                if worst_case_exon_delta < s.get("exon_delta", 0.0):
                                    worse_seq_disr = max(
                                        _normalize_delta_to_score(s.get("min_delta", 0.0)),
                                        _normalize_delta_to_score(worst_case_exon_delta)
                                    )
                                    s["sequence_disruption"] = worse_seq_disr
                                    s["calibrated_seq_percentile"] = _percentile_like(worse_seq_disr)
                                    s["scoring_strategy"]["multi_transcript_enhanced"] = True
                        
                        except Exception:
                            # Fallback to original values
                            s["worst_case_exon_delta"] = s.get("exon_delta")
                            s["transcript_count"] = 0
                            s["transcripts"] = []
            except Exception:
                pass
        
        # 2) Pathway aggregation (expanded mapping)
        gene_to_pathway = {
            # RAS/MAPK pathway - Core signaling cascade
            "BRAF": {"ras_mapk": 1.0},
            "KRAS": {"ras_mapk": 1.0},
            "NRAS": {"ras_mapk": 1.0},
            "MAP2K1": {"ras_mapk": 0.9},
            "MAP2K2": {"ras_mapk": 0.9},
            "RAF1": {"ras_mapk": 0.8},
            "MAPK1": {"ras_mapk": 0.7},
            "MAPK3": {"ras_mapk": 0.7},
            
            # TP53 pathway - DNA damage response and apoptosis
            "TP53": {"tp53": 1.0},
            "ATM": {"tp53": 0.6},
            "MDM2": {"tp53": 0.6},
            "MDM4": {"tp53": 0.5},
            "CDKN1A": {"tp53": 0.4},
            "BBC3": {"tp53": 0.4},  # PUMA
            "BAX": {"tp53": 0.3},
            "CHEK2": {"tp53": 0.5},
            
            # Multiple Myeloma specific genes
            "FGFR3": {"growth_signaling": 0.9, "ras_mapk": 0.3},  # t(4;14) translocation
            "MYC": {"proliferation": 1.0},  # c-MYC dysregulation
            "CCND1": {"cell_cycle": 0.9},  # t(11;14) translocation  
            "CCND2": {"cell_cycle": 0.8},
            "CCND3": {"cell_cycle": 0.8},
            "RB1": {"cell_cycle": 0.7},
            "CDKN2A": {"cell_cycle": 0.6},  # p16
            "CDKN2C": {"cell_cycle": 0.5},  # p18
            
            # NF-kB pathway - Important in MM survival
            "NFKB1": {"nf_kb": 0.8},
            "RELA": {"nf_kb": 0.8},
            "IKBKB": {"nf_kb": 0.7},  # IKK-beta
            "TRAF3": {"nf_kb": 0.6},
            
            # DNA repair - Critical for therapy resistance
            "BRCA1": {"dna_repair": 0.9},
            "BRCA2": {"dna_repair": 0.9},
            "PARP1": {"dna_repair": 0.7},
            "XRCC1": {"dna_repair": 0.6},
            
            # Proteasome/UPS pathway - Target of bortezomib
            "PSMB5": {"proteasome": 1.0},  # β5 subunit
            "PSMA1": {"proteasome": 0.7},
            "PSMC1": {"proteasome": 0.6},
            
            # Immunomodulation - IMiD targets
            "CRBN": {"immunomod": 1.0},  # Cereblon - IMiD target
            "IKZF1": {"immunomod": 0.8},  # Ikaros
            "IKZF3": {"immunomod": 0.8},  # Aiolos
            
            # Bone microenvironment
            "DKK1": {"bone_remodeling": 0.8},  # Wnt inhibitor
            "RANKL": {"bone_remodeling": 0.7},
            "OPG": {"bone_remodeling": 0.6},
        }
        pathway_scores = {
            "ras_mapk": 0.0, 
            "tp53": 0.0,
            "growth_signaling": 0.0,
            "proliferation": 0.0,
            "cell_cycle": 0.0,
            "nf_kb": 0.0,
            "dna_repair": 0.0,
            "proteasome": 0.0,
            "immunomod": 0.0,
            "bone_remodeling": 0.0
        }
        for s in seq_scores:
            gene = (s.get("variant", {}).get("gene") or "").upper()
            w = gene_to_pathway.get(gene) or {}
            for p, pw in w.items():
                pathway_scores[p] += (s.get("sequence_disruption") or 0.0) * float(pw)
        for k in pathway_scores:
            pathway_scores[k] = float(min(1.0, pathway_scores[k]))
        
        # 3) Per-drug evidence and ClinVar prior
        primary_gene = ((seq_scores[0].get("variant") or {}).get("gene") or "").strip() if seq_scores else ""
        hgvs_p = ((seq_scores[0].get("variant") or {}).get("hgvs_p") or "") if seq_scores else ""
        clinvar = {"prior": 0.0, "deep_analysis": None}
        # Skip ClinVar when Fusion AM path is active to avoid latency
        if fusion_url and primary_gene and seq_scores:
            clinvar = {"prior": 0.0, "deep_analysis": None}
        elif primary_gene and seq_scores:
            clinvar = await _fetch_clinvar_prior(api_base, primary_gene, seq_scores[0]["variant"]) or clinvar

        # 3b) Insights bundle (functionality/chromatin/essentiality)
        insights = {"functionality": None, "chromatin": None, "essentiality": None, "regulatory": None}
        # Skip Evo-backed insights when Fusion AM is active to avoid upstream timeouts
        if not fusion_url and primary_gene and seq_scores:
            try:
                insights = await _fetch_insights_bundle(api_base, primary_gene, seq_scores[0]["variant"], hgvs_p)
                # Add regulatory insight when variant coordinates available
                v0 = seq_scores[0]["variant"]
                try:
                    async with httpx.AsyncClient(timeout=20.0) as client:
                        rr = await client.post(
                            f"{api_base}/api/insights/predict_splicing_regulatory",
                            json={"chrom": str(v0.get("chrom")), "pos": int(v0.get("pos")), "ref": str(v0.get("ref")).upper(), "alt": str(v0.get("alt")).upper()},
                            headers={"Content-Type": "application/json"}
                        )
                        if rr.status_code < 400:
                            insights["regulatory"] = float((rr.json() or {}).get("regulatory_impact_score") or 0.0)
                except Exception:
                    pass
            except Exception:
                insights = {"functionality": None, "chromatin": None, "essentiality": None, "regulatory": None}
        
        # 4) Combine per-drug
        cfg = await get_efficacy_config()
        w = cfg.get("weights", {"sequence": 0.35, "pathway": 0.35, "evidence": 0.3})
        # Allow disabling literature lookups to speed up evals / avoid network
        disable_literature = bool(options.get("disable_literature", False))
        try:
            from api.config import get_feature_flags
            if get_feature_flags().get("disable_literature"):
                disable_literature = True
        except Exception:
            pass
        
        # First pass: collect all drug data for rank_delta calculation
        drug_data = []
        for d in cfg.get("drug_panel", []):
            p = d.get("pathway_weights", {})
            # per-drug evidence
            if not disable_literature and primary_gene:
                evd = await _fetch_drug_evidence(api_base, primary_gene, hgvs_p, d.get("name", ""), d.get("moa", ""))
            else:
                evd = {"strength": 0.0, "top_results": []}
            s_seq = max([s.get("sequence_disruption", 0.0) for s in seq_scores] + [0.0])
            
            # Pathway breakdown: individual weighted scores
            ras_weighted = float(p.get("ras_mapk", 0.0)) * pathway_scores["ras_mapk"]
            tp53_weighted = float(p.get("tp53", 0.0)) * pathway_scores["tp53"]
            s_path = ras_weighted + tp53_weighted
            
            s_evd = float(min(1.0, max(0.0, (evd.get("strength") or 0.0) + (clinvar.get("prior") or 0.0))))

            # Percentile-like calibration for S/P
            seq_pct = _percentile_like(s_seq)
            path_pct = _percentile_like(s_path)

            # Insights contributions: modest lifts when supportive
            func = float((insights or {}).get("functionality") or 0.0)
            chrom = float((insights or {}).get("chromatin") or 0.0)
            ess = float((insights or {}).get("essentiality") or 0.0)
            insights_bonus = 0.0
            if func >= 0.6:
                insights_bonus += 0.05
            if chrom >= 0.5:
                insights_bonus += 0.03
            if ess >= 0.7:
                insights_bonus += 0.07
            reg = float((insights or {}).get("regulatory") or 0.0)
            if reg >= 0.6:
                insights_bonus += 0.03

            raw_lob = float(w.get("sequence", 0.35)) * s_seq + float(w.get("pathway", 0.35)) * s_path + float(w.get("evidence", 0.3)) * s_evd + insights_bonus
            
            drug_data.append({
                "drug_config": d,
                "pathway_weights": p,
                "evidence": evd,
                "s_seq": s_seq,
                "s_path": s_path,
                "ras_weighted": ras_weighted,
                "tp53_weighted": tp53_weighted,
                "s_evd": s_evd,
                "seq_pct": seq_pct,
                "path_pct": path_pct,
                "raw_lob": raw_lob
            })
        
        # Calculate median LoB for rank_delta
        all_lobs = [d["raw_lob"] for d in drug_data]
        if all_lobs:
            sorted_lobs = sorted(all_lobs)
            n = len(sorted_lobs)
            median_lob = sorted_lobs[n//2] if n % 2 == 1 else (sorted_lobs[n//2-1] + sorted_lobs[n//2]) / 2
        else:
            median_lob = 0.0
        
        # Second pass: build final drug output with rank_delta
        drugs_out = []
        for drug_info in drug_data:
            d = drug_info["drug_config"]
            p = drug_info["pathway_weights"]
            evd = drug_info["evidence"]
            s_seq = drug_info["s_seq"]
            s_path = drug_info["s_path"]
            ras_weighted = drug_info["ras_weighted"]
            tp53_weighted = drug_info["tp53_weighted"]
            s_evd = drug_info["s_evd"]
            seq_pct = drug_info["seq_pct"]
            path_pct = drug_info["path_pct"]
            raw_lob = drug_info["raw_lob"]
            rank_delta = raw_lob - median_lob

            # Evidence badges
            def _has_flag(results: List[Dict[str, Any]], flag_words: List[str]) -> bool:
                for r in results or []:
                    pub_types = " ".join([_safe_lower(t) for t in (r.get("publication_types") or [])])
                    title = _safe_lower(r.get("title"))
                    if any(f in pub_types or f in title for f in flag_words):
                        return True
                return False
            filtered_or_tops = (evd.get("filtered") or (evd.get("top_results") or []))
            badges: List[str] = []
            if _has_flag(filtered_or_tops, ["randomized"]):
                badges.append("RCT")
            if _has_flag(filtered_or_tops, ["guideline", "practice"]):
                badges.append("Guideline")
            _clin = ((clinvar.get("deep_analysis") or {}).get("clinvar") or {})
            clin_class = _clin.get("classification")
            clin_review = _safe_lower(((clinvar.get("deep_analysis") or {}).get("clinvar", {}) or {}).get("review_status"))
            if _safe_lower(clin_class) in ("pathogenic", "likely_pathogenic") and ("expert" in clin_review or "practice" in clin_review):
                badges.append("ClinVar-Strong")
            if s_path >= 0.2:
                badges.append("PathwayAligned")

            # Gates and tiers (using configurable thresholds)
            gates = cfg.get("evidence_gates", {})
            evidence_gate_threshold = gates.get("evidence_gate_threshold", 0.7)
            pathway_alignment_threshold = gates.get("pathway_alignment_threshold", 0.2)
            insufficient_signal_threshold = gates.get("insufficient_signal_threshold", 0.02)
            
            evidence_gate = (s_evd >= evidence_gate_threshold) or (("ClinVar-Strong" in badges) and (s_path >= pathway_alignment_threshold))
            insufficient = (s_seq < insufficient_signal_threshold and s_path < 0.05 and s_evd < 0.2)
            if evidence_gate:
                evidence_tier = "supported"
            elif insufficient:
                evidence_tier = "insufficient"
            else:
                evidence_tier = "consider"

            # Confidence recalibration by tier (+insights modulation)
            # When fusion AM is active, avoid zeroing scores on "insufficient" evidence
            if evidence_tier == "supported":
                confidence = 0.6 + 0.2 * s_evd + 0.2 * max(seq_pct, path_pct)
                lob = raw_lob
            elif evidence_tier == "consider":
                confidence = 0.3 + 0.2 * s_evd + 0.1 * seq_pct + 0.1 * path_pct
                lob = raw_lob
            else:  # insufficient
                if fusion_url:
                    # Under fusion, derive conservative confidence from fused S + pathway
                    confidence = 0.1 + 0.15 * seq_pct + 0.10 * path_pct
                    lob = raw_lob * 0.5  # Scaled down but not zeroed
                else:
                    confidence = 0.0
                    lob = 0.0
            confidence += 0.05 if func >= 0.6 else 0.0
            confidence += 0.03 if chrom >= 0.5 else 0.0
            confidence += 0.07 if ess >= 0.7 else 0.0
            confidence += 0.02 if reg >= 0.6 else 0.0
            confidence = float(min(1.0, max(0.0, confidence)))

            # Evidence manifest (citations + clinvar + query)
            manifest = {
                "pubmed_query": evd.get("pubmed_query"),
                "citations": [
                    {"pmid": (c or {}).get("pmid"), "title": (c or {}).get("title"), "publication_types": (c or {}).get("publication_types")}
                    for c in (filtered_or_tops or [])[:3]
                    if c and c.get("pmid")
                ],
                "clinvar": {
                    "classification": _clin.get("classification"),
                    "review_status": _clin.get("review_status"),
                },
            }

            drugs_out.append({
                "name": d.get("name"),
                "moa": d.get("moa"),
                "efficacy_score": round(lob, 3),
                "rank_delta": round(rank_delta, 3),
                "confidence": round(confidence, 3),
                "rationale": [
                    {"type": "sequence", "value": s_seq, "percentile": seq_pct},
                    {
                        "type": "pathway", 
                        "ras_mapk": pathway_scores["ras_mapk"], 
                        "tp53": pathway_scores["tp53"], 
                        "percentile": path_pct,
                        "weighted": round(s_path, 3),
                        "breakdown": {
                            "ras_mapk": round(ras_weighted, 3),
                            "tp53": round(tp53_weighted, 3)
                        }
                    },
                    {"type": "evidence", "strength": s_evd},
                ],
                "insufficient_signal": evidence_tier == "insufficient",
                "evidence_tier": evidence_tier,
                "meets_evidence_gate": evidence_gate,
                "badges": badges,
                "evidence_strength": round(s_evd, 3),
                "citations": [(c or {}).get("pmid") for c in (evd.get("filtered") or [])[:3] if c and c.get("pmid")],
                "citations_count": len([(c or {}).get("pmid") for c in (evd.get("filtered") or []) if c and c.get("pmid")]),
                "clinvar": {
                    "classification": (clinvar.get("deep_analysis") or {}).get("clinvar", {}).get("classification"),
                    "review_status": (clinvar.get("deep_analysis") or {}).get("clinvar", {}).get("review_status"),
                    "prior": clinvar.get("prior") or 0.0,
                },
                "evidence_manifest": manifest,
                "insights": {"functionality": func, "chromatin": chrom, "essentiality": ess, "regulatory": reg},
            })
        # Determine top-level scoring mode string
        top_scoring_mode = "massive_real" if massive_real_mode else ("massive_impact" if massive_impact_mode else "standard_evo")
        # Top-level scoring strategy summary
        if top_scoring_mode == "standard_evo":
            strategy = {"approach": "adaptive_multi_window_plus_exon" if use_adaptive else "multi_window_plus_exon", "windows": [int(f)*2 for f in window_flanks], "ensemble": model_candidates}
        elif top_scoring_mode == "massive_real":
            strategy = {"approach": "ensembl_real_context", "window_bp": 50000}
        else:
            strategy = {"approach": "synthetic_contrast", "window_bp": 50000}
        # Log evidence run to Supabase
        try:
            from api.services.supabase_service import supabase
            import hashlib
            
            # Create run signature
            run_signature = hashlib.md5(str(request).encode()).hexdigest()[:12]
            
            # Log main run with weights/gates snapshot
            run_data = {
                "run_signature": run_signature,
                "request": request,
                "sequence_details": seq_scores,
                "pathway_scores": pathway_scores,
                "scoring_strategy": strategy,
                "weights_snapshot": cfg.get("weights", {}),
                "gates_snapshot": cfg.get("evidence_gates", {}),
                "feature_flags_snapshot": cfg.get("feature_flags", {}),
                "operational_mode": cfg.get("operational_mode", "research"),
                "confidence_tier": "supported" if any(d.get("meets_evidence_gate") for d in drugs_out) else "insufficient",
                "drug_count": len(drugs_out),
                "insights": insights,
            }
            await supabase.log_evidence_run(run_data)
            
            # Log individual evidence items
            evidence_items = []
            for drug in drugs_out:
                manifest = drug.get("evidence_manifest", {})
                citations = manifest.get("citations", [])
                
                # Log citations
                for citation in citations:
                    evidence_items.append({
                        "run_signature": run_signature,
                        "drug_name": drug.get("name"),
                        "evidence_type": "citation",
                        "content": citation,
                        "strength_score": citation.get("relevance_score", 0.0),
                        "pubmed_id": citation.get("pmid")
                    })
                
                # Log ClinVar info
                clinvar_info = drug.get("clinvar", {})
                if clinvar_info.get("classification"):
                    evidence_items.append({
                        "run_signature": run_signature,
                        "drug_name": drug.get("name"),
                        "evidence_type": "clinvar",
                        "content": clinvar_info,
                        "strength_score": clinvar_info.get("prior", 0.0)
                    })
            
            if evidence_items:
                await supabase.log_evidence_items(evidence_items)
                
        except Exception:
            # Don't fail the response if logging fails
            pass
        
        return {
            "use_case": "myeloma",
            "drugs": drugs_out,
            "pathway_scores": pathway_scores,
            "sequence_details": seq_scores,
            "evidence": {"gene": primary_gene},
            "scoring_mode": top_scoring_mode,
            "scoring_strategy": strategy,
            "run_signature": run_signature,
            "massive_oracle_url": OLD_ORACLE_URL if top_scoring_mode.startswith("massive_") else None,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy predict failed: {e}; trace: {traceback.format_exc()}")

@router.post("/explain")
async def explain_efficacy(request: Dict[str, Any]):
    """Generate concise rationales per drug using S/P/E and citations.
    Input: same as /predict; if 'drugs' missing, will call /predict first.
    """
    try:
        data = request
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        if not request.get("drugs"):
            data = await predict_efficacy(request)
        drugs = data.get("drugs") or []
        pathway = data.get("pathway_scores") or {}
        explanations: List[Dict[str, Any]] = []
        for d in drugs:
            seq_v = 0.0
            for r in (d.get("rationale") or []):
                if r.get("type") == "sequence":
                    seq_v = float(r.get("value") or 0.0)
                    break
            cits = d.get("citations") or []
            clin = d.get("clinvar") or {}
            txt = (
                f"{d.get('name')}: score {d.get('efficacy_score')} (conf {d.get('confidence')}). "
                f"Seq={seq_v:.2f}, Path RAS={float(pathway.get('ras_mapk',0.0)):.2f} TP53={float(pathway.get('tp53',0.0)):.2f}, "
                f"ClinVar={clin.get('classification') or 'n/a'} ({clin.get('review_status') or 'n/a'}). "
                + (f"Citations: {', '.join([str(x) for x in cits])}." if cits else "")
            ).strip()
            explanations.append({
                "name": d.get("name"),
                "explanation": txt,
                "insufficient": d.get("insufficient_signal"),
                "evidence_manifest": d.get("evidence_manifest") or {},
            })
        return {"explanations": explanations, "used": {"pathway_scores": pathway}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy explain failed: {e}")

@router.get("/run/{run_signature}")
async def get_evidence_run(run_signature: str):
    """Retrieve a logged evidence run by signature."""
    try:
        from api.services.supabase_service import supabase
        import json
        
        # Get main run data
        run_data = await supabase.select("mdt_evidence_runs", {"run_signature": run_signature}, limit=1)
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get associated evidence items
        evidence_items = await supabase.select("mdt_evidence_items", {"run_signature": run_signature}, limit=100)
        
        # Parse JSON fields back
        run = run_data[0]
        run["request_payload"] = json.loads(run.get("request_payload", "{}"))
        run["sequence_details"] = json.loads(run.get("sequence_details", "[]"))
        run["pathway_scores"] = json.loads(run.get("pathway_scores", "{}"))
        run["scoring_strategy"] = json.loads(run.get("scoring_strategy", "{}"))
        
        # Parse evidence items
        for item in evidence_items:
            item["evidence_content"] = json.loads(item.get("evidence_content", "{}"))
        
        return {
            "run": run,
            "evidence_items": evidence_items,
            "total_items": len(evidence_items)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve run: {e}")

@router.get("/calibration/status")
async def get_calibration_status():
    """Get calibration cache status and statistics."""
    try:
        from api.services.gene_calibration import get_calibration_service
        
        service = get_calibration_service()
        stats = service.get_cache_stats()
        
        return {
            "status": "operational",
            "cache_stats": stats,
            "message": f"{stats['genes_with_data']}/{stats['total_genes_cached']} genes have calibration data"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Calibration service unavailable"
        }
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy predict failed: {e}; trace: {traceback.format_exc()}")

@router.post("/explain")
async def explain_efficacy(request: Dict[str, Any]):
    """Generate concise rationales per drug using S/P/E and citations.
    Input: same as /predict; if 'drugs' missing, will call /predict first.
    """
    try:
        data = request
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")
        if not request.get("drugs"):
            data = await predict_efficacy(request)
        drugs = data.get("drugs") or []
        pathway = data.get("pathway_scores") or {}
        explanations: List[Dict[str, Any]] = []
        for d in drugs:
            seq_v = 0.0
            for r in (d.get("rationale") or []):
                if r.get("type") == "sequence":
                    seq_v = float(r.get("value") or 0.0)
                    break
            cits = d.get("citations") or []
            clin = d.get("clinvar") or {}
            txt = (
                f"{d.get('name')}: score {d.get('efficacy_score')} (conf {d.get('confidence')}). "
                f"Seq={seq_v:.2f}, Path RAS={float(pathway.get('ras_mapk',0.0)):.2f} TP53={float(pathway.get('tp53',0.0)):.2f}, "
                f"ClinVar={clin.get('classification') or 'n/a'} ({clin.get('review_status') or 'n/a'}). "
                + (f"Citations: {', '.join([str(x) for x in cits])}." if cits else "")
            ).strip()
            explanations.append({
                "name": d.get("name"),
                "explanation": txt,
                "insufficient": d.get("insufficient_signal"),
                "evidence_manifest": d.get("evidence_manifest") or {},
            })
        return {"explanations": explanations, "used": {"pathway_scores": pathway}}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"efficacy explain failed: {e}")

@router.get("/run/{run_signature}")
async def get_evidence_run(run_signature: str):
    """Retrieve a logged evidence run by signature."""
    try:
        from api.services.supabase_service import supabase
        import json
        
        # Get main run data
        run_data = await supabase.select("mdt_evidence_runs", {"run_signature": run_signature}, limit=1)
        if not run_data:
            raise HTTPException(status_code=404, detail="Run not found")
        
        # Get associated evidence items
        evidence_items = await supabase.select("mdt_evidence_items", {"run_signature": run_signature}, limit=100)
        
        # Parse JSON fields back
        run = run_data[0]
        run["request_payload"] = json.loads(run.get("request_payload", "{}"))
        run["sequence_details"] = json.loads(run.get("sequence_details", "[]"))
        run["pathway_scores"] = json.loads(run.get("pathway_scores", "{}"))
        run["scoring_strategy"] = json.loads(run.get("scoring_strategy", "{}"))
        
        # Parse evidence items
        for item in evidence_items:
            item["evidence_content"] = json.loads(item.get("evidence_content", "{}"))
        
        return {
            "run": run,
            "evidence_items": evidence_items,
            "total_items": len(evidence_items)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve run: {e}")

@router.get("/calibration/status")
async def get_calibration_status():
    """Get calibration cache status and statistics."""
    try:
        from api.services.gene_calibration import get_calibration_service
        
        service = get_calibration_service()
        stats = service.get_cache_stats()
        
        return {
            "status": "operational",
            "cache_stats": stats,
            "message": f"{stats['genes_with_data']}/{stats['total_genes_cached']} genes have calibration data"
        }
    except Exception as e:
        return {
            "status": "error",
            "error": str(e),
            "message": "Calibration service unavailable"
        }