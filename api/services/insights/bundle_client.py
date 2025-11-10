"""
Insights Bundle Client: Calls predict_* insights endpoints and bundles results.
"""
import httpx
from typing import Dict, Any

from .models import InsightsBundle


async def bundle(api_base: str, gene: str, variant: Dict[str, Any], 
                hgvs_p: str) -> InsightsBundle:
    """
    Call insights endpoints and return bundled results.
    
    Args:
        api_base: Base API URL
        gene: Primary gene name
        variant: Variant dictionary with chrom, pos, ref, alt
        hgvs_p: HGVS protein notation
        
    Returns:
        InsightsBundle with all available insights
    """
    result = InsightsBundle()
    
    try:
        async with httpx.AsyncClient(timeout=40.0) as client:
            # Prepare calls
            func_payload = {"gene": gene, "hgvs_p": hgvs_p} if (gene and hgvs_p) else None
            chrom_payload = {
                "chrom": str(variant.get("chrom")), 
                "pos": int(variant.get("pos") or 0), 
                "radius": 500
            } if variant.get("chrom") and variant.get("pos") else None
            # Infer consequence from protein notation to improve essentiality for truncations
            inferred_consequence = "missense_variant"
            try:
                p = (hgvs_p or "").upper()
                if "*" in p or "FS" in p:
                    inferred_consequence = "stop_gained" if "*" in p else "frameshift_variant"
            except Exception:
                inferred_consequence = "missense_variant"

            ess_payload = {
                "gene": gene, 
                "variants": [
                    {
                        "gene": gene, 
                        "chrom": str(variant.get("chrom")), 
                        "pos": int(variant.get("pos") or 0), 
                        "ref": str(variant.get("ref") or ""), 
                        "alt": str(variant.get("alt") or ""), 
                        "consequence": inferred_consequence
                    }
                ]
            } if gene and variant.get("chrom") and variant.get("pos") else None
            reg_payload = {
                "chrom": str(variant.get("chrom")), 
                "pos": int(variant.get("pos") or 0), 
                "ref": str(variant.get("ref") or ""), 
                "alt": str(variant.get("alt") or "")
            } if variant.get("chrom") and variant.get("pos") and variant.get("ref") and variant.get("alt") else None

            tasks = []
            task_names = []
            
            if func_payload:
                tasks.append(client.post(
                    f"{api_base}/api/insights/predict_protein_functionality_change", 
                    json=func_payload, 
                    headers={"Content-Type": "application/json"}
                ))
                task_names.append("functionality")
            else:
                tasks.append(None)
                task_names.append(None)
                
            if chrom_payload:
                tasks.append(client.post(
                    f"{api_base}/api/insights/predict_chromatin_accessibility", 
                    json=chrom_payload, 
                    headers={"Content-Type": "application/json"}
                ))
                task_names.append("chromatin")
            else:
                tasks.append(None)
                task_names.append(None)
                
            if ess_payload:
                tasks.append(client.post(
                    f"{api_base}/api/insights/predict_gene_essentiality", 
                    json=ess_payload, 
                    headers={"Content-Type": "application/json"}
                ))
                task_names.append("essentiality")
            else:
                tasks.append(None)
                task_names.append(None)
                
            if reg_payload:
                tasks.append(client.post(
                    f"{api_base}/api/insights/predict_splicing_regulatory", 
                    json=reg_payload, 
                    headers={"Content-Type": "application/json"}
                ))
                task_names.append("regulatory")
            else:
                tasks.append(None)
                task_names.append(None)

            # Execute calls sequentially to avoid None tasks errors
            responses = []
            for t in tasks:
                if t is None:
                    responses.append(None)
                else:
                    try:
                        r = await t
                        responses.append(r if r.status_code < 400 else None)
                    except Exception:
                        responses.append(None)

            # Process responses
            for i, (response, name) in enumerate(zip(responses, task_names)):
                if response is None or name is None:
                    continue
                    
                try:
                    js = response.json() or {}
                    if name == "functionality":
                        # API returns functionality_change_score per insights.py; accept either key
                        result.functionality = js.get("functionality_change_score", js.get("functionality_score"))
                        result.provenance["functionality_method"] = js.get("provenance", {}).get("method")
                    elif name == "chromatin":
                        result.chromatin = js.get("accessibility_score")
                        result.provenance["chromatin_method"] = js.get("provenance", {}).get("method")
                    elif name == "essentiality":
                        result.essentiality = js.get("essentiality_score")
                        result.provenance["essentiality_method"] = js.get("provenance", {}).get("method")
                    elif name == "regulatory":
                        result.regulatory = js.get("regulatory_impact_score")
                        result.provenance["regulatory_method"] = js.get("provenance", {}).get("method")
                except Exception:
                    continue
                    
    except Exception as e:
        result.provenance["bundle_error"] = str(e)
    
    return result


