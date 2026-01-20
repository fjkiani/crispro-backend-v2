"""
Ayesha Care Plan Utilities

Shared utility functions used across care plan services.
"""

import logging
import os
from typing import Dict, List, Any, Optional

import httpx

logger = logging.getLogger(__name__)


async def extract_insights_bundle(
    client: httpx.AsyncClient,
    somatic_mutations: List[Dict[str, Any]],
    api_base: Optional[str] = None
) -> Dict[str, float]:
    """
    Dynamically extract insights bundle from insights endpoints.
    
    Fallback chain:
    1. Try full mutation data → call insights endpoints
    2. If partial data → attempt with available fields, handle errors
    3. If only gene name → use gene-level heuristics
    4. If all fails → use defaults (0.5 for all)
    
    Returns: insights_bundle with functionality, chromatin, essentiality, regulatory
    """
    if api_base is None:
        api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    insights_bundle = {
        "functionality": 0.5,
        "chromatin": 0.5,
        "essentiality": 0.5,
        "regulatory": 0.5
    }
    
    if not somatic_mutations:
        logger.warning("⚠️  No mutations provided for insights extraction - using defaults")
        return insights_bundle
    
    # Get first mutation for insights (can be extended to aggregate multiple)
    primary_mutation = somatic_mutations[0] if somatic_mutations else {}
    primary_gene = primary_mutation.get("gene")
    hgvs_p = primary_mutation.get("hgvs_p")
    chrom = primary_mutation.get("chrom")
    pos = primary_mutation.get("pos")
    ref = primary_mutation.get("ref")
    alt = primary_mutation.get("alt")
    
    # Check data completeness
    has_full_data = bool(chrom and pos and ref and alt)
    has_hgvs_p = bool(hgvs_p)
    has_gene = bool(primary_gene)
    
    logger.info(f"🔍 [INSIGHTS EXTRACTION] Mutation data: gene={primary_gene}, hgvs_p={hgvs_p}, "
               f"has_full_data={has_full_data}, has_hgvs_p={has_hgvs_p}, has_gene={has_gene}")
    
    # Try insights endpoints if we have sufficient data
    if has_full_data or has_hgvs_p:
        logger.info(f"🔍 [INSIGHTS EXTRACTION] Attempting insights extraction: gene={primary_gene}, hgvs_p={hgvs_p}, has_full_data={has_full_data}")
        try:
            # Call functionality endpoint (requires gene + hgvs_p)
            if primary_gene and hgvs_p:
                try:
                    func_response = await client.post(
                        f"{api_base}/api/insights/predict_protein_functionality_change",
                        json={"gene": primary_gene, "hgvs_p": hgvs_p},
                        headers={"Content-Type": "application/json"},
                        timeout=40.0
                    )
                    if func_response.status_code < 400:
                        func_data = func_response.json() or {}
                        func_score = func_data.get("functionality_change_score")
                        if func_score is not None:
                            insights_bundle["functionality"] = float(func_score)
                            logger.info(f"✅ Functionality score: {insights_bundle['functionality']:.3f}")
                        else:
                            logger.warning(f"Functionality endpoint returned no score: {func_data.keys()}")
                    else:
                        logger.warning(f"Functionality endpoint returned {func_response.status_code}: {func_response.text[:200]}")
                except Exception as e:
                    logger.warning(f"Functionality endpoint failed: {e}", exc_info=True)
            
            # Call chromatin accessibility endpoint (requires chrom + pos)
            if chrom and pos:
                try:
                    chrom_response = await client.post(
                        f"{api_base}/api/insights/predict_chromatin_accessibility",
                        json={"chrom": str(chrom), "pos": int(pos), "radius": 500},
                        headers={"Content-Type": "application/json"},
                        timeout=40.0
                    )
                    if chrom_response.status_code < 400:
                        chrom_data = chrom_response.json() or {}
                        chrom_score = chrom_data.get("accessibility_score")
                        if chrom_score is not None:
                            insights_bundle["chromatin"] = float(chrom_score)
                            logger.info(f"✅ Chromatin score: {insights_bundle['chromatin']:.3f}")
                    else:
                        logger.warning(f"Chromatin endpoint returned {chrom_response.status_code}")
                except Exception as e:
                    logger.warning(f"Chromatin endpoint failed: {e}", exc_info=True)
            
            # Call essentiality endpoint (requires gene + variants)
            if primary_gene:
                try:
                    # Build variants list - prefer full data, but can work with just gene
                    variants_payload = []
                    if has_full_data:
                        variants_payload = [{
                            "gene": primary_gene,
                            "chrom": str(chrom),
                            "pos": int(pos),
                            "ref": str(ref),
                            "alt": str(alt),
                            "consequence": primary_mutation.get("consequence", "missense_variant")
                        }]
                    elif hgvs_p:
                        # Can still try with just gene + hgvs_p
                        variants_payload = [{
                            "gene": primary_gene,
                            "consequence": primary_mutation.get("consequence", "missense_variant")
                        }]
                    
                    if variants_payload:
                        ess_response = await client.post(
                            f"{api_base}/api/insights/predict_gene_essentiality",
                            json={
                                "gene": primary_gene,
                                "variants": variants_payload
                            },
                            headers={"Content-Type": "application/json"},
                            timeout=40.0
                        )
                        if ess_response.status_code < 400:
                            ess_data = ess_response.json() or {}
                            ess_score = ess_data.get("essentiality_score")
                            if ess_score is not None:
                                insights_bundle["essentiality"] = float(ess_score)
                                logger.info(f"✅ Essentiality score: {insights_bundle['essentiality']:.3f}")
                            else:
                                logger.warning(f"Essentiality endpoint returned no score: {ess_data.keys()}")
                        else:
                            logger.warning(f"Essentiality endpoint returned {ess_response.status_code}: {ess_response.text[:200]}")
                except Exception as e:
                    logger.warning(f"Essentiality endpoint failed: {e}", exc_info=True)
            
            # Call regulatory endpoint (requires chrom + pos + ref + alt)
            if has_full_data:
                try:
                    reg_response = await client.post(
                        f"{api_base}/api/insights/predict_splicing_regulatory",
                        json={"chrom": str(chrom), "pos": int(pos), "ref": str(ref), "alt": str(alt)},
                        headers={"Content-Type": "application/json"},
                        timeout=40.0
                    )
                    if reg_response.status_code < 400:
                        reg_data = reg_response.json() or {}
                        reg_score = reg_data.get("regulatory_impact_score")
                        if reg_score is not None:
                            insights_bundle["regulatory"] = float(reg_score)
                            logger.info(f"✅ Regulatory score: {insights_bundle['regulatory']:.3f}")
                    else:
                        logger.warning(f"Regulatory endpoint returned {reg_response.status_code}")
                except Exception as e:
                    logger.warning(f"Regulatory endpoint failed: {e}", exc_info=True)
            
            logger.info(f"✅ [INSIGHTS EXTRACTION] Final insights bundle: {insights_bundle}")
            
        except Exception as e:
            logger.error(f"❌ [INSIGHTS EXTRACTION] Insights endpoints failed with exception: {e}", exc_info=True)
    
    # Gene-level heuristics if only gene names available
    elif has_gene:
        # Apply gene-level heuristics (known hotspot genes, etc.)
        known_drivers = ["BRCA1", "BRCA2", "TP53", "KRAS", "BRAF", "PIK3CA", "PTEN"]
        if primary_gene in known_drivers:
            insights_bundle["functionality"] = 0.7  # Known driver genes
            insights_bundle["essentiality"] = 0.7
            logger.info(f"✅ [INSIGHTS EXTRACTION] Applied gene-level heuristics for {primary_gene}")
    else:
        logger.warning(f"⚠️  [INSIGHTS EXTRACTION] No sufficient data for insights extraction - using defaults")
    
    logger.info(f"🔍 [INSIGHTS EXTRACTION] Returning insights_bundle: {insights_bundle}")
    return insights_bundle


def extract_drugs_from_regimen(regimen: str, add_ons: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Extract drug names and classes from SOC regimen string.
    
    Args:
        regimen: Regimen string (e.g., "Carboplatin AUC 5-6 + Paclitaxel 175 mg/m²")
        add_ons: List of add-on drugs (e.g., [{"drug": "Bevacizumab", ...}])
    
    Returns:
        List of drug dicts with name, class, moa
    """
    drugs = []
    
    # Drug name → class mapping
    drug_class_map = {
        "carboplatin": {"class": "platinum", "moa": "DNA crosslinking"},
        "cisplatin": {"class": "platinum", "moa": "DNA crosslinking"},
        "paclitaxel": {"class": "taxane", "moa": "microtubule stabilization"},
        "docetaxel": {"class": "taxane", "moa": "microtubule stabilization"},
        "bevacizumab": {"class": "anti-VEGF", "moa": "angiogenesis inhibition"},
        "olaparib": {"class": "PARP inhibitor", "moa": "PARP inhibition"},
        "niraparib": {"class": "PARP inhibitor", "moa": "PARP inhibition"},
        "rucaparib": {"class": "PARP inhibitor", "moa": "PARP inhibition"},
        "doxorubicin": {"class": "anthracycline", "moa": "topoisomerase inhibition"},
        "epirubicin": {"class": "anthracycline", "moa": "topoisomerase inhibition"}
    }
    
    # Parse regimen string (case-insensitive)
    regimen_lower = regimen.lower()
    for drug_name, drug_info in drug_class_map.items():
        if drug_name in regimen_lower:
            drugs.append({
                "name": drug_name.capitalize(),
                "class": drug_info["class"],
                "moa": drug_info["moa"]
            })
    
    # Add add-ons
    for add_on in add_ons:
        drug_name = add_on.get("drug", "").lower()
        if drug_name in drug_class_map:
            drug_info = drug_class_map[drug_name]
            # Don't duplicate if already in regimen
            if not any(d["name"].lower() == drug_name for d in drugs):
                drugs.append({
                    "name": add_on.get("drug", drug_name.capitalize()),
                    "class": drug_info["class"],
                    "moa": drug_info["moa"]
                })
    
    return drugs
