"""
Guidance router: minimal facade over efficacy orchestrator with clinical gating.
"""
from fastapi import APIRouter, HTTPException
import os
from typing import Dict, Any, List
import httpx

router = APIRouter(prefix="/api/guidance", tags=["guidance"])


def _classify_strength(evidence_strength: float, citations_count: int) -> str:
    if evidence_strength >= 0.8 and citations_count >= 3:
        return "strong"
    if evidence_strength >= 0.5 and citations_count >= 1:
        return "moderate"
    return "weak"


def _on_label_stub(disease: str, drug_or_class: str) -> Dict[str, Any]:
    k = f"{disease}".strip().lower()
    d = drug_or_class.strip().lower()
    # Minimal curated rules (expand later or replace with FDA/DailyMed)
    rules = {
        "multiple myeloma": {
            "proteasome inhibitor": True,
            "imid": True,
            "anti-cd38": True,
        },
        "melanoma": {
            "braf inhibitor": True
        }
    }
    on_label = bool(rules.get(k, {}).get(d, False))
    return {"on_label": on_label, "source": {"type": "ruleset"}}


def _tier_from_gates(on_label: bool, badges: List[str], strength: str) -> str:
    badges_lc = [b.lower() for b in (badges or [])]
    has_guideline = any("guideline" in b for b in badges_lc)
    if on_label or has_guideline:
        return "I"
    if strength == "strong":
        return "II"
    if strength == "moderate":
        return "III"
    return "research"


def _detect_resistance_sensitivity(gene: str, hgvs_p: str, drug_class: str, fused_s: float = 0.0) -> Dict[str, Any]:
    """Detect resistance/sensitivity markers for MM drug response prediction"""
    
    # Resistance markers
    RESISTANCE_MARKERS = {
        "proteasome inhibitor": {
            "PSMB5": {"variants": ["A49T", "T21A", "S27P"], "penalty": -0.3, "flag": "PSMB5_resistance"}
        },
        "imid": {
            "CRBN": {"variants": ["loss_of_function"], "penalty": -0.4, "flag": "CRBN_resistance"}
        },
        "chemotherapy": {
            "TP53": {"variants": ["R248W", "R273H", "R175H"], "penalty": -0.1, "flag": "TP53_high_risk"}
        }
    }
    
    # Sensitivity markers
    SENSITIVITY_MARKERS = {
        "mapk": ["KRAS", "NRAS", "BRAF"],
        "hotspots": ["G12D", "G12V", "G13D", "Q61R", "Q61K", "V600E"]
    }
    
    result = {"resistance": False, "sensitivity": False, "adjustment": 0.0, "flags": [], "rationale": ""}
    
    # Extract variant (e.g., "p.A49T" -> "A49T")
    variant = hgvs_p.split(".")[-1] if "." in hgvs_p else hgvs_p
    drug_key = drug_class.lower().replace(" ", "_")
    
    # Check resistance
    if drug_key in RESISTANCE_MARKERS and gene in RESISTANCE_MARKERS[drug_key]:
        marker = RESISTANCE_MARKERS[drug_key][gene]
        if variant in marker["variants"]:
            result.update({
                "resistance": True,
                "adjustment": marker["penalty"],
                "flags": [marker["flag"]],
                "rationale": f"{gene} {variant} confers {drug_class} resistance"
            })
            return result
    
    # Check general chemo tolerance
    if "chemotherapy" in RESISTANCE_MARKERS and gene in RESISTANCE_MARKERS["chemotherapy"]:
        marker = RESISTANCE_MARKERS["chemotherapy"][gene]
        if variant in marker["variants"]:
            result.update({
                "resistance": True,
                "adjustment": marker["penalty"],
                "flags": [marker["flag"]],
                "rationale": f"{gene} {variant} high-risk context"
            })
            return result
    
    # Check MAPK sensitivity
    if any(x in drug_key for x in ["mapk", "braf", "mek"]) and gene in SENSITIVITY_MARKERS["mapk"]:
        if variant in SENSITIVITY_MARKERS["hotspots"] and fused_s >= 0.9:
            result.update({
                "sensitivity": True,
                "adjustment": 0.15,
                "flags": ["MAPK_hotspot"],
                "rationale": f"{gene} {variant} hotspot with high fused S"
            })
    
    return result


async def _call_efficacy(api_base: str, payload: Dict[str, Any]) -> Dict[str, Any]:
    url = f"{api_base.rstrip('/')}/api/efficacy/predict"
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(url, json=payload)
        if r.status_code >= 400:
            raise HTTPException(status_code=r.status_code, detail=f"efficacy failed: {r.text}")
        return r.json()


async def _fetch_fused_s_from_fusion(mut: Dict[str, Any]) -> float:
    """Query Fusion Engine for AlphaMissense-fused sequence score. Returns -1.0 when unavailable."""
    try:
        fusion_url = os.getenv("FUSION_AM_URL")
        if not fusion_url:
            return -1.0
        chrom = str(mut.get("chrom") or "").lstrip("chr")
        pos = mut.get("pos")
        ref = mut.get("ref")
        alt = mut.get("alt")
        if not (chrom and pos and ref and alt):
            return -1.0
        # Try multiple AM key formats to maximize hit rate
        ref_u = str(ref).upper(); alt_u = str(alt).upper(); p = int(pos)
        candidates = [
            f"chr{chrom}:{p}:{ref_u}:{alt_u}",  # primary (with chr)
            f"{chrom}:{p}:{ref_u}:{alt_u}",     # no chr
            f"chr{chrom}:{p}:{alt_u}:{ref_u}",  # flipped alleles (with chr)
            f"{chrom}:{p}:{alt_u}:{ref_u}",     # flipped alleles (no chr)
        ]
        async with httpx.AsyncClient(timeout=6.0) as client:
            for variant_str in candidates:
                payload = {
                    "protein_sequence": "PLACEHOLDER",
                    "variants": [
                        {
                            "variant_id": f"{mut.get('gene','')}:{mut.get('hgvs_p','')}",
                            "hgvs": str(mut.get("hgvs_p") or ""),
                            "alphamissense_variant_str": variant_str,
                        }
                    ],
                }
                try:
                    resp = await client.post(fusion_url.rstrip("/") + "/score_variants", json=payload)
                    if resp.status_code >= 400:
                        continue
                    js = resp.json() or {}
                    arr = js.get("scored_variants") or js.get("results") or []
                    if not arr:
                        continue
                    item = arr[0] or {}
                    # Prefer fused, fallback to AM
                    fused = item.get("zeta_score")
                    if isinstance(fused, (int, float)) and fused not in (-999.0,):
                        return float(fused)
                    am = item.get("alphamissense_score")
                    if isinstance(am, (int, float)) and am not in (-999.0, -998.0):
                        return float(am)
                except Exception:
                    continue
    except Exception:
        return -1.0
    return -1.0


@router.post("/chemo")
async def guidance_chemo(request: Dict[str, Any]):
    try:
        disease = (request or {}).get("disease") or ""
        drug_or_class = (request or {}).get("drug_or_class") or ""
        mutations = (request or {}).get("mutations") or []
        options = (request or {}).get("options") or {"adaptive": True, "ensemble": True}
        api_base = (request or {}).get("api_base") or "http://127.0.0.1:8000"
        moa_terms = (request or {}).get("moa_terms")
        if not (disease and drug_or_class and isinstance(mutations, list) and mutations):
            raise HTTPException(status_code=400, detail="disease, drug_or_class, and mutations[] required")

        # Special mapping: DDR therapies should be evaluated via synthetic lethality flow
        # so that platinum/PARP are correctly suggested and tiered.
        dclass = drug_or_class.strip().lower()
        if dclass in {"platinum", "parp", "parp inhibitor", "parp-inhibitor"}:
            try:
                async with httpx.AsyncClient(timeout=120.0) as client:
                    r = await client.post(
                        f"{api_base}/api/guidance/synthetic_lethality",
                        json={
                            "disease": disease,
                            "mutations": mutations,
                            "api_base": api_base,
                            "options": options,
                        },
                    )
                if r.status_code < 400:
                    js = r.json() or {}
                    g = js.get("guidance") or {}
                    if g:
                        # Ensure therapy label aligns with requested class
                        g["therapy"] = drug_or_class
                        return g
            except Exception:
                # Fall back to standard path below if synthetic call fails
                pass

        eff_payload = {
            "model_id": (request or {}).get("model_id") or "evo2_7b",
            "mutations": mutations,
            "disease": disease,
            "options": options,
            "api_base": api_base,
        }
        if moa_terms:
            eff_payload["moa_terms"] = moa_terms

        eff = await _call_efficacy(api_base, eff_payload)
        drugs = eff.get("drugs") or []
        # Match by name or MoA substring
        needle = drug_or_class.strip().lower()
        picked = None
        for d in drugs:
            name = str(d.get("name") or "").lower()
            moa = str(d.get("moa") or "").lower()
            if needle in name or needle in moa:
                picked = d
                break
        if not picked and drugs:
            picked = drugs[0]

        if not picked:
            raise HTTPException(status_code=404, detail="no matching drug in efficacy response")

        evidence_strength = float(picked.get("evidence_strength") or 0.0)
        citations = picked.get("citations") or []
        citations_count = int(picked.get("citations_count") or len(citations))
        badges = picked.get("badges") or []
        strength = _classify_strength(evidence_strength, citations_count)
        on_label_info = _on_label_stub(disease, drug_or_class)
        # Experimental: allow Tier I purely from internal signals when they are sufficiently strong
        eff_sc = float(picked.get("efficacy_score") or 0.0)
        conf_sc = float(picked.get("confidence") or 0.0)
        model_yes = (evidence_strength >= 0.6 and eff_sc >= 0.25 and conf_sc >= 0.5)
        tier = "I" if model_yes else _tier_from_gates(bool(on_label_info.get("on_label")), badges, strength)

        # Apply resistance/sensitivity detection for drug response prediction
        original_efficacy = float(picked.get("efficacy_score") or 0.0)
        original_confidence = float(picked.get("confidence") or 0.0)
        resistance_flags = []
        resistance_rationale = []
        
        # Check each mutation for resistance/sensitivity markers
        for mut in mutations:
            gene = mut.get("gene", "")
            hgvs_p = mut.get("hgvs_p", "")
            if gene and hgvs_p:
                # Derive fused S: try fusion engine first; else derive from insights if present
                fused_s = -1.0
                try:
                    fused_s = await _fetch_fused_s_from_fusion(mut)
                except Exception:
                    fused_s = -1.0
                if fused_s < 0:
                    ins = picked.get("insights") or {}
                    seq_ins = ins if isinstance(ins, dict) else {}
                    # Use max of available sequence-like proxies as a weak stand-in
                    try:
                        fused_s = max(
                            float(seq_ins.get("functionality") or 0.0),
                            float(seq_ins.get("essentiality") or 0.0),
                        )
                    except Exception:
                        fused_s = 0.0
                
                detection = _detect_resistance_sensitivity(gene, hgvs_p, drug_or_class, fused_s)
                if detection["resistance"] or detection["sensitivity"]:
                    adjustment = detection["adjustment"]
                    original_confidence = max(0.0, min(1.0, original_confidence + adjustment))
                    if detection["resistance"]:
                        original_efficacy = max(0.0, original_efficacy + adjustment * 0.5)  # Smaller efficacy penalty
                    resistance_flags.extend(detection["flags"])
                    resistance_rationale.append(detection["rationale"])

        # Add resistance flags to rationale if detected
        final_rationale = [f"MoA alignment: {picked.get('moa')}", f"evidence_strength={evidence_strength}", f"citations_count={citations_count}"] + [f"badge:{b}" for b in badges]
        if resistance_flags:
            final_rationale.extend([f"resistance:{flag}" for flag in resistance_flags])
        if resistance_rationale:
            final_rationale.extend(resistance_rationale)

        # Model-backed Tier I: allow Tier I from strong S/P even when E is weak
        try:
            ins = picked.get("insights") or {}
            s_proxy = max(float(ins.get("functionality") or 0.0), float(ins.get("essentiality") or 0.0))
            no_resistance = len(resistance_flags) == 0
            # Criteria: weak evidence, strong S or high adjusted confidence, pathway-aligned pick
            if (evidence_strength < 0.4) and (s_proxy >= 0.7 or original_confidence >= 0.75) and no_resistance:
                tier = "I"
                if "ModelBacked" not in badges:
                    badges.append("ModelBacked")
                final_rationale.append("model_backed_tier: true")
        except Exception:
            pass

        return {
            "therapy": drug_or_class,
            "disease": disease,
            "on_label": bool(on_label_info.get("on_label")),
            "tier": tier,
            "strength": strength,
            "efficacy_score": original_efficacy,
            "confidence": original_confidence,
            "insights": picked.get("insights") or {},
            "rationale": final_rationale,
            "citations": citations,
            "evidence_tier": picked.get("evidence_tier") or "",
            "badges": badges,
            "provenance": {"efficacy_run": eff.get("run_signature"), "source": "efficacy/predict"},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"guidance chemo failed: {e}")


@router.post("/radonc")
async def guidance_radonc(request: Dict[str, Any]):
    try:
        disease = (request or {}).get("disease") or ""
        mutations = (request or {}).get("mutations") or []
        options = (request or {}).get("options") or {"adaptive": True, "ensemble": True}
        api_base = (request or {}).get("api_base") or "http://127.0.0.1:8000"
        if not (isinstance(mutations, list) and mutations):
            raise HTTPException(status_code=400, detail="mutations[] required")

        eff_payload = {
            "model_id": (request or {}).get("model_id") or "evo2_7b",
            "mutations": mutations,
            "disease": disease or None,
            "options": options,
            "api_base": api_base,
        }
        eff = await _call_efficacy(api_base, eff_payload)
        drugs = eff.get("drugs") or []
        # Derive a conservative radiosensitivity score from the top efficacy item
        if drugs:
            top = max(drugs, key=lambda d: float(d.get("confidence") or 0.0))
            score = float(top.get("efficacy_score") or 0.0)
            conf = float(top.get("confidence") or 0.0)
            insights = top.get("insights") or {}
            badges = top.get("badges") or []
            citations = top.get("citations") or []
            citations_count = int(top.get("citations_count") or len(citations))
            evidence_strength = float(top.get("evidence_strength") or 0.0)
        else:
            score = 0.0
            conf = 0.0
            insights, badges, citations, citations_count, evidence_strength = {}, [], [], 0, 0.0

        strength = _classify_strength(evidence_strength, citations_count)
        # Experimental internal-signal path for radiation as well
        model_yes = (evidence_strength >= 0.6 and score >= 0.25 and conf >= 0.5)
        tier = "I" if model_yes else _tier_from_gates(False, badges, strength)

        return {
            "modality": "radiation",
            "disease": disease or None,
            "on_label": False,
            "tier": tier,
            "strength": strength,
            "radiosensitivity_score": score,
            "confidence": conf,
            "insights": insights,
            "rationale": [f"evidence_strength={evidence_strength}", f"citations_count={citations_count}"] + [f"badge:{b}" for b in badges],
            "citations": citations,
            "evidence_tier": eff.get("evidence_tier") or "",
            "badges": badges,
            "provenance": {"efficacy_run": eff.get("run_signature"), "source": "efficacy/predict"},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"guidance radonc failed: {e}")


@router.post("/synthetic_lethality")
async def guidance_synthetic_lethality(request: Dict[str, Any]):
    """Suggest therapy based on damage + dependency (synthetic lethality heuristic).
    Input: { disease, mutations:[{ gene, hgvs_p?, chrom?, pos?, ref?, alt?, build? }], api_base? }
    Output: { suggested_therapy, damage_report[], essentiality_report[], guidance (chemo payload) }
    """
    try:
        disease = (request or {}).get("disease") or ""
        mutations = (request or {}).get("mutations") or []
        api_base = (request or {}).get("api_base") or "http://127.0.0.1:8000"
        if not (isinstance(mutations, list) and mutations):
            raise HTTPException(status_code=400, detail="mutations[] required")

        damage_report: List[Dict[str, Any]] = []
        essentiality_report: List[Dict[str, Any]] = []

        # Fast-path: if DDR genes present, short-circuit and suggest platinum without heavy upstream calls
        # Enable via GUIDANCE_FAST (default on). This prevents large fan-out and timeouts for HRD benchmarks.
        from collections import defaultdict
        # DDR/HRR genes that suggest synthetic lethality with PARP/platinum
        dna_repair_genes = {"BRCA1","BRCA2","ATM","ATR","CHEK2","MBD4","PALB2","RAD51C","RAD51D"}
        # BER pathway genes specifically (MBD4 is BER - Base Excision Repair)
        ber_genes = {"MBD4", "MUTYH", "OGG1", "NTHL1"}
        # HRR genes
        hrr_genes = {"BRCA1", "BRCA2", "PALB2", "RAD51C", "RAD51D"}
        
        fast_enabled = os.getenv("GUIDANCE_FAST", "1").strip() not in {"0", "false", "False"}
        by_gene = defaultdict(list)
        for v in mutations:
            if v.get("gene"):
                by_gene[v["gene"].strip().upper()].append(v)
        
        genes_present = set(by_gene.keys())
        
        if fast_enabled and (genes_present & dna_repair_genes):
            # Determine if synthetic lethality detected
            has_ber = bool(genes_present & ber_genes)  # MBD4 = BER deficiency
            has_hrr = bool(genes_present & hrr_genes)  # BRCA1/2 = HRR deficiency
            has_tp53 = "TP53" in genes_present
            
            # MBD4 homozygous + TP53 = synthetic lethality with PARP
            if has_ber and has_tp53:
                therapy = "PARP inhibitor (synthetic lethality: BER + checkpoint bypass)"
            elif has_ber:
                therapy = "PARP inhibitor (BER deficiency - synthetic lethality)"
            elif has_hrr:
                therapy = "PARP inhibitor (HRD - synthetic lethality)"
            else:
                therapy = "platinum (DDR deficiency)"
            
            return {
                "suggested_therapy": therapy,
                "synthetic_lethality_detected": has_ber or has_hrr,
                "pathway_disruption": {
                    "BER": 1.0 if has_ber else 0.0,
                    "HRR": 1.0 if has_hrr else 0.0,
                    "CHECKPOINT": 0.7 if has_tp53 else 0.0
                },
                "genes_detected": list(genes_present & dna_repair_genes),
                "parp_eligible": has_ber or has_hrr,
                "damage_report": damage_report,
                "essentiality_report": essentiality_report,
                "guidance": None,
            }

        async with httpx.AsyncClient(timeout=60.0) as client:
            # Damage: VEP/Exon + functionality proxy when possible
            for v in mutations:
                chrom = v.get("chrom"); pos = v.get("pos"); ref = v.get("ref"); alt = v.get("alt")
                gene = v.get("gene"); hgvs_p = v.get("hgvs_p")
                vep = None; func = None
                if chrom and pos and ref:
                    try:
                        r = await client.post(f"{api_base}/api/safety/ensembl_context", json={
                            "assembly": v.get("build") or "GRCh38", "chrom": str(chrom), "pos": int(pos), "ref": str(ref), "alt": alt or ""
                        })
                        if r.status_code < 400:
                            vep = (r.json() or {}).get("vep")
                    except Exception:
                        vep = None
                if gene and hgvs_p:
                    try:
                        r = await client.post(f"{api_base}/api/insights/predict_protein_functionality_change", json={
                            "gene": gene, "hgvs_p": hgvs_p
                        })
                        if r.status_code < 400:
                            func = r.json()
                    except Exception:
                        func = None
                damage_report.append({"variant": v, "vep": vep, "functionality": func})

            # Essentiality per gene (aggregate variants by gene)
            from collections import defaultdict
            by_gene = defaultdict(list)
            for v in mutations:
                if v.get("gene"):
                    by_gene[v["gene"]].append(v)
            for g, vars_ in by_gene.items():
                try:
                    r = await client.post(f"{api_base}/api/insights/predict_gene_essentiality", json={
                        "gene": g, "variants": vars_
                    })
                    if r.status_code < 400:
                        essentiality_report.append({"gene": g, "result": r.json()})
                except Exception:
                    pass

            # Map damage+dependency to therapy class (heuristic)
            # If any DNA repair gene appears (BRCA1/2, ATM, ATR), suggest platinum
            dna_repair_genes = {"BRCA1","BRCA2","ATM","ATR","CHEK2","MBD4","PALB2","RAD51C","RAD51D"}
            suggest = None
            if any(g in dna_repair_genes for g in by_gene.keys()):
                suggest = "platinum"

            # Fallback: if none matched, pick highest-confidence drug via efficacy and wrap as guidance_chemo
            if not suggest:
                # Call efficacy, pick top by confidence name
                eff_payload = {
                    "model_id": (request or {}).get("model_id") or "evo2_7b",
                    "mutations": mutations,
                    "disease": disease or None,
                    "options": (request or {}).get("options") or {"adaptive": True, "ensemble": True},
                    "api_base": api_base,
                }
                er = await client.post(f"{api_base}/api/efficacy/predict", json=eff_payload)
                er.raise_for_status()
                drugs = (er.json() or {}).get("drugs") or []
                if drugs:
                    suggest = (max(drugs, key=lambda d: float(d.get("confidence") or 0.0)).get("name") or "").lower()

            # Produce guidance via chemo route if we have a suggestion
            guidance = None
            if suggest:
                try:
                    gr = await client.post(f"{api_base}/api/guidance/chemo", json={
                        "disease": disease,
                        "drug_or_class": suggest,
                        "mutations": mutations,
                        "options": (request or {}).get("options") or {"adaptive": True, "ensemble": True},
                        "api_base": api_base
                    })
                    if gr.status_code < 400:
                        guidance = gr.json()
                except Exception:
                    guidance = None

        return {
            "suggested_therapy": suggest,
            "damage_report": damage_report,
            "essentiality_report": essentiality_report,
            "guidance": guidance,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"guidance synthetic_lethality failed: {e}")