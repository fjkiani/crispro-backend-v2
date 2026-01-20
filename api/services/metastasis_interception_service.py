"""
Metastasis Interception Service - Target lock → design → safety → score
Orchestrates weapon forging against metastatic cascade steps
"""
import json
import uuid
import httpx
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

# Load ruleset at module level (cached)
RULESET_PATH = Path(__file__).parent.parent / "config" / "metastasis_interception_rules.json"
with open(RULESET_PATH, "r") as f:
    RULESET = json.load(f)


def load_ruleset() -> Dict[str, Any]:
    """Reload ruleset (for testing/hot-reload)"""
    with open(RULESET_PATH, "r") as f:
        return json.load(f)


# === FUNCTION 1: Target Lock ===
async def target_lock(
    mutations: List[Dict[str, Any]],
    mission_step: str,
    api_base: str = "http://127.0.0.1:8000"
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    """
    Identify validated target gene for the mission.
    
    Args:
        mutations: Patient variants
        mission_step: One of 8 cascade steps
        api_base: API root URL
        
    Returns:
        (validated_target, considered_targets) where validated_target includes:
        { gene, rank_score, rationale, provenance }
    """
    ruleset = load_ruleset()
    gene_set_keys = ruleset["mission_to_gene_sets"].get(mission_step, [])
    
    # Flatten gene sets
    candidate_genes = set()
    for key in gene_set_keys:
        candidate_genes.update(ruleset["gene_sets"].get(key, []))
    
    if not candidate_genes:
        raise ValueError(f"No gene sets mapped to mission_step: {mission_step}")
    
    # Fetch insights for each candidate gene
    gene_scores = {}
    async with httpx.AsyncClient(timeout=60.0) as client:
        for gene in candidate_genes:
            signals = {"functionality": 0.0, "essentiality": 0.0, "regulatory": 0.0, "chromatin": 0.0}
            chromatin_meta = {"is_stub": None, "provenance": None}
            
            # Find mutations for this gene
            gene_muts = [m for m in mutations if m.get("gene", "").upper() == gene.upper()]
            
            # Functionality
            if gene_muts:
                try:
                    resp = await client.post(
                        f"{api_base}/api/insights/predict_protein_functionality_change",
                        json={"gene": gene, "hgvs_p": gene_muts[0].get("hgvs_p"), "model_id": "evo2_1b"},
                        timeout=60.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        signals["functionality"] = data.get("functionality_score", 0.0)
                except Exception:
                    pass
            
            # Essentiality
            try:
                resp = await client.post(
                    f"{api_base}/api/insights/predict_gene_essentiality",
                    json={"gene": gene, "variants": gene_muts or [], "model_id": "evo2_1b"},
                    timeout=60.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    signals["essentiality"] = data.get("essentiality_score", 0.0)
            except Exception:
                pass
            
            # Regulatory (if coords available)
            if gene_muts and all(gene_muts[0].get(k) for k in ["chrom", "pos", "ref", "alt"]):
                try:
                    mut = gene_muts[0]
                    resp = await client.post(
                        f"{api_base}/api/insights/predict_splicing_regulatory",
                        json={"chrom": mut["chrom"], "pos": mut["pos"], "ref": mut["ref"], "alt": mut["alt"], "model_id": "evo2_1b"},
                        timeout=60.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        signals["regulatory"] = data.get("regulatory_impact_score", 0.0)
                except Exception:
                    pass
            
            # Chromatin (if coords available)
            if gene_muts and gene_muts[0].get("chrom") and gene_muts[0].get("pos"):
                try:
                    mut = gene_muts[0]
                    resp = await client.post(
                        f"{api_base}/api/insights/predict_chromatin_accessibility",
                        json={"chrom": mut["chrom"], "pos": mut["pos"], "radius": 500},
                        timeout=60.0
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        signals["chromatin"] = data.get("accessibility_score", 0.0)
                        chromatin_meta["provenance"] = data.get("provenance")
                        method = (data.get("provenance") or {}).get("method")
                        chromatin_meta["is_stub"] = (method == "deterministic_fallback")
                except Exception:
                    pass
            
            # Apply thresholds and weights
            thresholds = ruleset["thresholds"]
            weights_raw = ruleset["weights"]["target_lock"]
            # If chromatin is a deterministic stub, drop chromatin weight and renormalize.
            weights = dict(weights_raw)
            if chromatin_meta.get("is_stub") is True and "chromatin" in weights:
                weights["chromatin"] = 0.0
                total = sum(weights.values())
                if total > 0:
                    weights = {k: v / total for k, v in weights.items()}
            
            thresholds_passed = [
                k
                for k, v in signals.items()
                if (v >= thresholds.get(k, 0.6)) and not (k == "chromatin" and chromatin_meta.get("is_stub") is True)
            ]
            
            # Compute weighted score
            raw_score = sum(weights.get(k, 0.0) * signals.get(k, 0.0) for k in weights.keys())
            
            gene_scores[gene] = {
                "gene": gene,
                "rank_score": min(1.0, max(0.0, raw_score)),
                "signals": signals,
                "thresholds_passed": thresholds_passed,
                "in_mutations": any(m.get("gene", "").upper() == gene.upper() for m in mutations)
            }
    
    # Rank: prefer genes in mutations, then by rank_score, then alphabetical
    ranked = sorted(
        gene_scores.values(),
        key=lambda x: (-int(x["in_mutations"]), -x["rank_score"], x["gene"])
    )
    
    if not ranked:
        raise ValueError("No candidate genes scored")
    
    top = ranked[0]
    validated_target = {
        "gene": top["gene"],
        "rank_score": top["rank_score"],
        "rationale": [
            f"{k.capitalize()} signal: {v:.2f}" for k, v in top["signals"].items() if v > 0
        ] + [f"Thresholds passed: {', '.join(top['thresholds_passed']) or 'none'}"],
        "provenance": {
            "signals": top["signals"],
            "weights": ruleset["weights"]["target_lock"],
            "raw_score": top["rank_score"],
            "thresholds_passed": top["thresholds_passed"]
        }
    }
    
    considered_targets = [
        {
            "gene": r["gene"],
            "rank_score": r["rank_score"],
            "brief_rationale": f"Score: {r['rank_score']:.2f}; passed {len(r['thresholds_passed'])}/4 thresholds"
        }
        for r in ranked[1:4]
    ]
    
    return validated_target, considered_targets


# === FUNCTION 2: Design Candidates ===
async def design_candidates(
    target_gene: str,
    mutations: List[Dict[str, Any]],
    num_candidates: int,
    api_base: str = "http://127.0.0.1:8000"
) -> List[Dict[str, Any]]:
    """
    Generate guide RNA candidates for target gene.
    
    Args:
        target_gene: Gene symbol
        mutations: Variant list (to extract coords if available)
        num_candidates: Number of guides to request
        api_base: API root URL
        
    Returns:
        List of design endpoint responses: [{ sequence, pam, gc, spacer_efficacy_heuristic }, ...]
    """
    # Try to extract coords from mutations for target_gene
    target_muts = [m for m in mutations if m.get("gene", "").upper() == target_gene.upper()]
    
    # Check if we have coords to construct a target_sequence
    if not target_muts or not all(target_muts[0].get(k) for k in ["chrom", "pos", "ref", "alt"]):
        raise ValueError(
            f"Target gene {target_gene} lacks genomic coordinates in mutations. "
            "v1 requires chrom/pos/ref/alt for design. Provide a variant with full coords."
        )
    
    # For v1: construct a simple 50bp window around variant position
    # In v2: fetch full transcript sequence
    mut = target_muts[0]
    # v1+: Fetch ±60bp window around variant position from Ensembl REST API
    chrom = str(mut.get("chrom"))
    pos = int(mut.get("pos"))
    start = max(1, pos - 60)
    end = pos + 60
    ensembl_url = (
        f"https://rest.ensembl.org/sequence/region/human/{chrom}:{start}-{end}?"
        "content-type=text/plain;coord_system_version=GRCh38"
    )

    target_sequence = None
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            r = await client.get(ensembl_url)
            if r.status_code == 200:
                target_sequence = (r.text or "").strip().upper()
        except Exception:
            target_sequence = None

    if not target_sequence or len(target_sequence) < 30:
        raise ValueError(
            f"Failed to fetch target_sequence for {target_gene} at {chrom}:{pos}. "
            f"Provide explicit target_sequence or try again later."
        )

    # Call design endpoint
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            resp = await client.post(
                f"{api_base}/api/design/generate_guide_rna",
                json={
                    "target_sequence": target_sequence,
                    "pam": "NGG",
                    "num": num_candidates,
                    "model_id": "evo2_1b",
                },
            )
            if resp.status_code == 200:
                data = resp.json() or {}
                return data.get("candidates", [])
        except Exception:
            pass

    return []


# === FUNCTION 3: Safety Preview ===
async def safety_preview(
    candidates: List[Dict[str, Any]],
    api_base: str = "http://127.0.0.1:8000"
) -> List[Dict[str, Any]]:
    """
    Assess safety for each candidate using heuristic scoring.
    
    Args:
        candidates: List of guides from design endpoint
        api_base: API root URL
        
    Returns:
        List of candidates with added safety_score
    """
    from api.services.safety_service import preview_off_targets
    from api.schemas.safety import OffTargetRequest, GuideSequence
    
    guides = [GuideSequence(seq=c["sequence"]) for c in candidates]
    request = OffTargetRequest(guides=guides)
    
    try:
        response = preview_off_targets(request)
        
        # Map heuristic_score to safety_score (higher = safer)
        for i, cand in enumerate(candidates):
            if i < len(response.guides):
                heuristic = response.guides[i].heuristic_score
                cand["safety_score"] = heuristic
                cand["safety_method"] = "heuristic_v1"
                cand["safety_status"] = "ok"
            else:
                cand["safety_score"] = 0.5
                cand["safety_method"] = "placeholder"
                cand["safety_status"] = "unavailable"
    except Exception:
        # Graceful fallback
        for cand in candidates:
            cand["safety_score"] = 0.5
            cand["safety_method"] = "placeholder"
            cand["safety_status"] = "error"
    
    return candidates


# === FUNCTION 4: Assassin Scoring ===
async def assassin_score(
    candidates: List[Dict[str, Any]],
    target_lock_score: float,
    target_sequence: str = None,
    api_base: str = "http://127.0.0.1:8000"
) -> List[Dict[str, Any]]:
    """
    Compute final assassin_score for each candidate using Evo2-based efficacy.
    
    Args:
        candidates: Guides with efficacy_proxy and safety_score
        target_lock_score: Validated target's rank_score (used as mission_fit)
        target_sequence: Optional genomic context (120bp: guide + ±50bp flanks)
        api_base: API root URL
        
    Returns:
        Candidates with added assassin_score, sorted by score descending
    """
    ruleset = load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    for cand in candidates:
        guide_seq = cand.get("sequence", "")
        
        # Try to get Evo2-based efficacy via new endpoint
        efficacy = cand.get("spacer_efficacy_heuristic", 0.5)
        try:
            if guide_seq and len(guide_seq) == 20:
                # Get window_size from ruleset (default: 150bp = 300bp total context)
                window_size = ruleset.get("design", {}).get("window_size", 150)
                
                payload = {
                    "guide_sequence": guide_seq,
                    "model_id": "evo2_1b",
                    "window_size": window_size
                }
                if target_sequence:
                    payload["target_sequence"] = target_sequence
                
                async with httpx.AsyncClient(timeout=30.0) as client:
                    r = await client.post(
                        f"{api_base}/api/design/predict_crispr_spacer_efficacy",
                        json=payload,
                        timeout=30.0
                    )
                    if r.status_code == 200:
                        result = r.json()
                        efficacy = result.get("efficacy_score", efficacy)
                        cand["evo2_efficacy"] = efficacy
                        cand["evo2_delta"] = result.get("evo2_delta")
                        cand["efficacy_confidence"] = result.get("confidence", 0.5)
        except Exception:
            # Fallback to heuristic if endpoint unavailable
            pass
        
        safety = cand.get("safety_score", 0.5)
        mission_fit = target_lock_score
        
        score = (
            weights["efficacy"] * efficacy +
            weights["safety"] * safety +
            weights["mission_fit"] * mission_fit
        )
        
        cand["efficacy_proxy"] = efficacy
        cand["assassin_score"] = min(1.0, max(0.0, score))
    
    # Sort by assassin_score descending
    candidates.sort(key=lambda x: -x["assassin_score"])
    
    return candidates


# === FUNCTION 5: Main Orchestrator ===
async def intercept_metastatic_step(
    request: Dict[str, Any],
    api_base: str = "http://127.0.0.1:8000"
) -> Dict[str, Any]:
    """
    Main orchestration: target lock → design → safety → score → response.
    
    Args:
        request: InterceptRequest dict
        api_base: API root URL
        
    Returns:
        InterceptResponse dict
    """
    run_id = str(uuid.uuid4())
    ruleset = load_ruleset()
    
    mission_step = request.get("mission_step")
    mutations = request.get("mutations", [])
    patient_id = request.get("patient_id")
    disease = request.get("disease")
    options = request.get("options", {})
    profile = options.get("profile", "baseline")
    
    # Format mission objective
    mission_objective = f"Disrupt {mission_step.replace('_', ' ').title()}"
    if patient_id:
        mission_objective += f" for Patient {patient_id}"
    
    status_warnings = []
    
    # Step 1: Target Lock
    validated_target, considered_targets = await target_lock(mutations, mission_step, api_base)
    
    # Step 2: Design Candidates
    num_candidates = ruleset.get("num_candidates_per_target", 3)
    try:
        candidates = await design_candidates(
            validated_target["gene"],
            mutations,
            num_candidates,
            api_base
        )
    except NotImplementedError as e:
        # v1 limitation: return empty candidates with warning
        status_warnings.append(str(e))
        candidates = []
    except ValueError as e:
        status_warnings.append(str(e))
        candidates = []
    
    # If we have candidates, proceed with safety and scoring
    if candidates:
        # Step 3: Safety Preview
        candidates = await safety_preview(candidates, api_base)
        
        # Step 4: Assassin Scoring (now with Evo2 efficacy)
        # Extract target_sequence from mutations if available for better efficacy scoring
        target_sequence = None
        if mutations and mutations[0].get("chrom") and mutations[0].get("pos"):
            # TODO: v2 - fetch ±50bp context from Ensembl for better efficacy scoring
            pass
        
        candidates = await assassin_score(
            candidates,
            validated_target["rank_score"],
            target_sequence=target_sequence,
            api_base=api_base
        )
    
    # Add warning if <2 candidates
    if len(candidates) < 2:
        status_warnings.append(f"Only {len(candidates)} candidate(s) generated (target: ≥2)")
    
    # Build rationale
    rationale = [
        f"Mission→Gene Set: {mission_step} → {', '.join(ruleset['mission_to_gene_sets'].get(mission_step, []))}",
        f"Validated Target: {validated_target['gene']} (score: {validated_target['rank_score']:.2f})",
        f"Candidates generated: {len(candidates)}"
    ]
    
    # Format candidates for response
    formatted_candidates = [
        {
            "sequence": c["sequence"],
            "pam": c.get("pam", "NGG"),
            "gc": c.get("gc", 0.0),
            "efficacy_proxy": c.get("efficacy_proxy", 0.0),
            "safety_score": c.get("safety_score", 0.0),
            "assassin_score": c.get("assassin_score", 0.0),
            "provenance": {
                "design_method": "evo2_prompt_guided_v1",
                "safety_method": c.get("safety_method", "heuristic_v1"),
                "safety_status": c.get("safety_status", "ok")
            }
        }
        for c in candidates
    ]
    
    return {
        "mission_step": mission_step,
        "mission_objective": mission_objective,
        "validated_target": validated_target,
        "considered_targets": considered_targets,
        "candidates": formatted_candidates,
        "rationale": rationale,
        "provenance": {
            "run_id": run_id,
            "ruleset_version": ruleset["version"],
            "methods": ["target_lock_v1", "design_v1", "safety_preview_v1"],
            "profile": profile,
            "feature_flags": options.get("feature_flags"),
            "status_warnings": status_warnings
        }
    }
