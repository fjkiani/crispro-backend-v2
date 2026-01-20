"""
Literature Client: Literature search functionality.
"""
import httpx
from typing import Dict, Any, List, Optional

from .models import EvidenceHit


def _safe_lower(x: Any) -> str:
    """Safely convert to lowercase string."""
    try:
        return str(x or "").lower()
    except Exception:
        return ""


def _score_evidence_from_results(top_results: List[Dict[str, Any]]) -> float:
    """
    Score evidence strength from literature results.
    
    Args:
        top_results: List of literature result dictionaries
        
    Returns:
        Evidence strength score [0, 1]
    """
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


async def literature(api_base: str, gene: str, hgvs_p: str, drug_name: str, 
                    drug_moa: str = "", disease: str = "multiple myeloma") -> EvidenceHit:
    """
    Query literature endpoint for gene+variant+drug evidence.
    
    Args:
        api_base: Base API URL
        gene: Gene name
        hgvs_p: HGVS protein notation
        drug_name: Drug name
        drug_moa: Mechanism of action
        disease: Disease context
        
    Returns:
        EvidenceHit with literature results and strength
    """
    result = EvidenceHit(
        top_results=[],
        filtered=[],
        strength=0.0
    )
    
    try:
        # Build MoA terms list with disease-specific enhancements
        moa_terms = [t for t in [drug_name, drug_moa] if t]
        
        # Phase 1.2: Ovarian cancer PARP inhibitor evidence integration
        disease_lower = _safe_lower(disease)
        drug_moa_lower = _safe_lower(drug_moa)
        drug_name_lower = _safe_lower(drug_name)
        
        # Add PARP-specific MoA terms for ovarian cancer
        if "ovarian" in disease_lower or "gynecologic" in disease_lower:
            if "parp" in drug_moa_lower or "parp" in drug_name_lower:
                # Add PARP-specific terms for better evidence retrieval
                parp_terms = [
                    "PARP inhibitor",
                    "synthetic lethality",
                    "HRD",
                    "homologous recombination",
                    "BRCA",
                    "DNA repair deficiency"
                ]
                moa_terms.extend(parp_terms)
                result.provenance["parp_enhanced"] = True
        
        # Add platinum response evidence terms for ovarian cancer
        if "ovarian" in disease_lower:
            if "platinum" in drug_name_lower or "carboplatin" in drug_name_lower or "cisplatin" in drug_name_lower:
                platinum_terms = [
                    "platinum response",
                    "platinum sensitivity",
                    "BRCA",
                    "HRD",
                    "homologous recombination"
                ]
                moa_terms.extend(platinum_terms)
                result.provenance["platinum_enhanced"] = True
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            lr = await client.post(
                f"{api_base}/api/evidence/literature",
                json={
                    "gene": gene,
                    "hgvs_p": hgvs_p,
                    "disease": disease,
                    "time_window": "since 2015",
                    "max_results": 8,
                    "include_abstracts": True,
                    "synthesize": True,
                    "moa_terms": moa_terms,
                },
                headers={"Content-Type": "application/json"}
            )
            
            if lr.status_code < 400:
                res = lr.json() or {}
                tops = res.get("top_results") or []
                
                # Prefer results that reference the drug name or MoA in title/abstract
                dn = _safe_lower(drug_name)
                dm = _safe_lower(drug_moa)
                filtered = []
                
                for t in tops:
                    title_l = _safe_lower(t.get("title"))
                    abstr_l = _safe_lower(t.get("abstract"))
                    if ((dn and (dn in title_l or dn in abstr_l)) or 
                        (dm and (dm in title_l or dm in abstr_l))):
                        filtered.append(t)
                
                if not filtered:
                    # Fallback: prefer gene+disease matches, keep top N
                    filtered = tops[:5]
                
                # Boost if MoA reference appears in title/abstract
                moa_hits = 0
                if dm:
                    for t in tops:
                        if (dm in _safe_lower(t.get("title")) or 
                            dm in _safe_lower(t.get("abstract"))):
                            moa_hits += 1
                
                base_strength = _score_evidence_from_results(filtered or tops)
                # Increase MoA weighting to lift evidence strength
                strength = float(min(1.0, base_strength + 0.10 * moa_hits))
                
                # Phase 1.2: Strength boost for BRCA1/BRCA2 truncating mutations
                # Boost +0.2 for BRCA truncating mutations with PARP inhibitors or platinum
                gene_upper = gene.upper() if gene else ""
                hgvs_p_str = str(hgvs_p or "")
                truncating_boost = 0.0
                
                if gene_upper in {"BRCA1", "BRCA2"}:
                    # Check for truncating mutation (stop codon, frameshift)
                    is_truncating = (
                        "*" in hgvs_p_str or
                        "fs" in hgvs_p_str.lower() or
                        "frameshift" in hgvs_p_str.lower()
                    )
                    
                    if is_truncating:
                        # Boost for PARP inhibitors or platinum in ovarian cancer
                        if ("parp" in drug_moa_lower or "parp" in drug_name_lower or
                            "platinum" in drug_name_lower or "carboplatin" in drug_name_lower or
                            "cisplatin" in drug_name_lower):
                            if "ovarian" in disease_lower:
                                truncating_boost = 0.2
                                result.provenance["brca_truncating_boost"] = truncating_boost
                
                strength = float(min(1.0, strength + truncating_boost))
                
                result.top_results = tops
                result.filtered = filtered
                result.strength = strength
                result.pubmed_query = res.get("pubmed_query")
                result.moa_hits = moa_hits
                result.provenance["literature_method"] = "api/evidence/literature"
                result.provenance["moa_boost"] = moa_hits * 0.10
            else:
                result.provenance["literature_error"] = f"HTTP {lr.status_code}"
                
    except Exception as e:
        result.provenance["literature_error"] = str(e)
    
    return result


