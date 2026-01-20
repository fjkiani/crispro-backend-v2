"""
API Client Module

Unified API client for making efficacy predictions with consistent error handling.
"""

import asyncio
from typing import List, Dict, Any, Optional
import httpx


# GRCh37 chromosome lengths (cBioPortal TCGA data uses GRCh37)
CHROM_LENGTHS = {
    "1": 249250621, "2": 243199373, "3": 198022430, "4": 191154276,
    "5": 180915260, "6": 171115067, "7": 159138663, "8": 146364022,
    "9": 141213431, "10": 135534747, "11": 135006516, "12": 133851895,
    "13": 115169878, "14": 107349540, "15": 102531392, "16": 90354753,
    "17": 81195210, "18": 78077248, "19": 59128983, "20": 63025520,
    "21": 48129895, "22": 51304566, "X": 155270560, "Y": 59373566, "MT": 16569
}


def convert_mutation_to_request_format(mutation: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Convert cBioPortal mutation format to our API request format.
    
    Handles:
    - Chromosome normalization (chr17 → 17, 23 → X)
    - Coordinate validation (within chromosome bounds)
    - Field name mapping (chromosome → chrom, position → pos)
    
    Returns:
        Mutation dict in API format, or None if invalid
    """
    # Handle both cBioPortal format (chromosome, position) and standard format (chrom, pos)
    chrom = mutation.get("chrom") or mutation.get("chromosome", "")
    pos = mutation.get("pos") or mutation.get("position", 0)
    hgvs_p = mutation.get("hgvs_p") or mutation.get("protein_change", "")
    
    # Skip if missing critical fields
    if not chrom or not pos or not mutation.get("gene"):
        return None
    
    # Normalize chromosome
    chrom = str(chrom).replace("chr", "").replace("CHR", "").strip()
    
    # Map chromosome 23 → X (cBioPortal uses 23 for X chromosome)
    if chrom == "23":
        chrom = "X"
    
    # Validate chromosome
    valid_chroms = set([str(i) for i in range(1, 23)] + ["X", "Y", "MT", "M"])
    if chrom not in valid_chroms:
        return None  # Skip invalid chromosomes
    
    # Validate coordinates are within chromosome bounds
    if chrom in CHROM_LENGTHS:
        max_pos = CHROM_LENGTHS[chrom]
        try:
            if int(pos) > max_pos:
                return None  # Skip out-of-bounds coordinates
        except (ValueError, TypeError):
            return None
    
    return {
        "gene": mutation.get("gene"),
        "hgvs_p": hgvs_p,
        "chrom": chrom,
        "pos": int(pos),
        "ref": mutation.get("ref", ""),
        "alt": mutation.get("alt", ""),
        "build": "GRCh37"  # TCGA data is on GRCh37
    }


async def predict_patient_efficacy(
    patient: Dict[str, Any],
    client: httpx.AsyncClient,
    api_root: str = "http://127.0.0.1:8000",
    timeout: float = 300.0,
    model_id: str = "evo2_1b",
    disease: str = "ovarian_cancer",
) -> Dict[str, Any]:
    """
    Predict drug efficacy for a single patient.
    
    Args:
        patient: Patient dict with mutations
        client: httpx AsyncClient
        api_root: API base URL
        timeout: Request timeout in seconds
        model_id: Model ID to use
        disease: Disease type
    
    Returns:
        Dict with patient_id, efficacy_score, top_drug, confidence, all_drugs, or error
    """
    try:
        # Convert mutations to API format
        mutations = []
        for mut in patient.get("mutations", []):
            converted = convert_mutation_to_request_format(mut)
            if converted:
                mutations.append(converted)
        
        # Skip if no valid mutations after filtering
        if not mutations:
            return {
                "patient_id": patient.get("patient_id"),
                "error": "No valid mutations after filtering (chromosome/coordinate validation)"
            }
        
        # Build request payload
        payload = {
            "model_id": model_id,
            "mutations": mutations,
            "disease": disease,
            "options": {
                "adaptive": True,
                "ensemble": False,
            },
            "tumor_context": {
                "disease": disease
            }
        }
        
        # Call API
        response = await client.post(
            f"{api_root}/api/efficacy/predict",
            json=payload,
            timeout=timeout,
        )
        
        if response.status_code != 200:
            return {
                "patient_id": patient.get("patient_id"),
                "error": f"API error {response.status_code}: {response.text[:200]}"
            }
        
        data = response.json()
        drugs = data.get("drugs", [])
        top_drug = drugs[0] if drugs else {}
        
        # Extract pathway scores from provenance (if available)
        provenance = data.get("provenance", {})
        pathway_disruption = provenance.get("confidence_breakdown", {}).get("pathway_disruption", {})
        
        return {
            "patient_id": patient.get("patient_id"),
            "efficacy_score": top_drug.get("efficacy_score", 0.0),
            "top_drug": {
                "name": top_drug.get("name", ""),
                "efficacy_score": top_drug.get("efficacy_score", 0.0),
                "confidence": top_drug.get("confidence", 0.0),
                "evidence_tier": top_drug.get("evidence_tier", ""),
            },
            "drug_rankings": [
                {
                    "name": drug.get("name", ""),
                    "efficacy_score": drug.get("efficacy_score", 0.0),
                    "confidence": drug.get("confidence", 0.0),
                }
                for drug in drugs[:10]  # Top 10 drugs
            ],
            "all_drugs": [d.get("name") for d in drugs[:5]],  # For backward compatibility
            "pathway_disruption": pathway_disruption,
            "provenance": {
                "S_contribution": provenance.get("confidence_breakdown", {}).get("S_contribution", 0.0),
                "P_contribution": provenance.get("confidence_breakdown", {}).get("P_contribution", 0.0),
                "E_contribution": provenance.get("confidence_breakdown", {}).get("E_contribution", 0.0),
            }
        }
        
    except Exception as e:
        error_msg = str(e) if str(e) else f"Unknown error: {type(e).__name__}"
        return {
            "patient_id": patient.get("patient_id"),
            "error": error_msg
        }


async def run_benchmark(
    patients: List[Dict[str, Any]],
    api_root: str = "http://127.0.0.1:8000",
    max_concurrent: int = 2,
    timeout: float = 300.0,
    model_id: str = "evo2_1b",
    disease: str = "ovarian_cancer",
) -> List[Dict[str, Any]]:
    """
    Run predictions for all patients with concurrency control.
    
    Args:
        patients: List of patient dicts
        api_root: API base URL
        max_concurrent: Maximum concurrent requests
        timeout: Request timeout per patient
        model_id: Model ID to use
        disease: Disease type
    
    Returns:
        List of prediction results (may include errors)
    """
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def bounded_predict(patient):
        async with semaphore:
            async with httpx.AsyncClient(timeout=timeout) as client:
                return await predict_patient_efficacy(
                    patient, client, api_root, timeout, model_id, disease
                )
    
    tasks = [bounded_predict(p) for p in patients]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Handle exceptions
    valid_results = []
    for i, result in enumerate(results):
        if isinstance(result, Exception):
            valid_results.append({
                "patient_id": patients[i].get("patient_id", "unknown"),
                "error": str(result)
            })
        else:
            valid_results.append(result)
    
    return valid_results

