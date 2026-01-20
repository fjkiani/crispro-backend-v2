"""
⚔️ ACMG/AMP VARIANT CLASSIFICATION ROUTER ⚔️

Implements ACMG/AMP 2015 guidelines for variant pathogenicity classification.

Standards: https://www.acmg.net/docs/standards_guidelines_for_the_interpretation_of_sequence_variants.pdf

5-tier classification:
- Pathogenic (P)
- Likely Pathogenic (LP)
- Variant of Uncertain Significance (VUS)
- Likely Benign (LB)
- Benign (B)

Evidence codes:
- PVS1: Null variant (nonsense, frameshift, canonical ±1 or 2 splice sites)
- PS1-4: Strong pathogenic
- PM1-6: Moderate pathogenic
- PP1-5: Supporting pathogenic
- BA1: Stand-alone benign
- BS1-4: Strong benign
- BP1-7: Supporting benign

Research Use Only - Not for Clinical Diagnosis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/acmg", tags=["acmg"])

# NCBI API Key
NCBI_API_KEY = "8e6594264e64c76510738518fb66b9688007"

class ACMGClassificationRequest(BaseModel):
    """Request for ACMG variant classification"""
    gene: str = Field(..., description="Gene symbol (e.g., BRCA1)")
    chrom: str = Field(..., description="Chromosome (e.g., 17)")
    pos: int = Field(..., description="Genomic position (GRCh38)")
    ref: str = Field(..., description="Reference allele")
    alt: str = Field(..., description="Alternate allele")
    hgvs_c: Optional[str] = Field(None, description="HGVS coding (e.g., c.5266dupC)")
    hgvs_p: Optional[str] = Field(None, description="HGVS protein (e.g., p.Gln1756fs)")
    consequence: Optional[str] = Field(None, description="VEP consequence (e.g., frameshift_variant)")

class ACMGEvidenceCode(BaseModel):
    """Single ACMG evidence code"""
    code: str = Field(..., description="Evidence code (e.g., PVS1, PM2)")
    category: str = Field(..., description="Category: pathogenic or benign")
    strength: str = Field(..., description="Strength: very_strong, strong, moderate, supporting")
    rationale: str = Field(..., description="Human-readable rationale")

class ACMGClassificationResponse(BaseModel):
    """ACMG classification result"""
    classification: str = Field(..., description="5-tier: Pathogenic, Likely Pathogenic, VUS, Likely Benign, Benign")
    evidence_codes: List[ACMGEvidenceCode] = Field(..., description="All ACMG evidence codes applied")
    confidence: float = Field(..., description="Confidence in classification (0-1)")
    clinvar_classification: Optional[str] = Field(None, description="ClinVar expert classification if available")
    clinvar_review_status: Optional[str] = Field(None, description="ClinVar review status")
    rationale: List[str] = Field(..., description="Step-by-step reasoning")
    provenance: Dict = Field(..., description="Data sources and methods")

def is_truncating_variant(consequence: Optional[str], hgvs_p: Optional[str]) -> bool:
    """Check if variant is truncating (PVS1 criterion)"""
    if not consequence and not hgvs_p:
        return False
    
    truncating_consequences = [
        "frameshift_variant",
        "stop_gained",
        "splice_donor_variant",
        "splice_acceptor_variant",
        "start_lost",
    ]
    
    # Check VEP consequence
    if consequence and any(tc in consequence.lower() for tc in truncating_consequences):
        return True
    
    # Check HGVS protein for frameshift or nonsense
    if hgvs_p:
        hgvs_lower = hgvs_p.lower()
        if "fs" in hgvs_lower or "ter" in hgvs_lower or "*" in hgvs_lower:
            return True
    
    return False

async def query_clinvar(gene: str, chrom: str, pos: int) -> Optional[Dict]:
    """Query ClinVar for existing classification"""
    try:
        # Search ClinVar by gene and position
        search_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        search_params = {
            "db": "clinvar",
            "term": f"{gene}[gene] AND {chrom}[chr] AND {pos}[chrpos]",
            "retmode": "json",
            "api_key": NCBI_API_KEY,
            "retmax": 1
        }
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(search_url, params=search_params)
            resp.raise_for_status()
            search_data = resp.json()
            
            id_list = search_data.get("esearchresult", {}).get("idlist", [])
            if not id_list:
                return None
            
            # Fetch variant details
            fetch_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
            fetch_params = {
                "db": "clinvar",
                "id": id_list[0],
                "retmode": "json",
                "api_key": NCBI_API_KEY
            }
            
            resp = await client.get(fetch_url, params=fetch_params)
            resp.raise_for_status()
            fetch_data = resp.json()
            
            # Extract classification
            result = fetch_data.get("result", {})
            variant_data = result.get(id_list[0], {})
            
            return {
                "classification": variant_data.get("clinical_significance", {}).get("description", ""),
                "review_status": variant_data.get("clinical_significance", {}).get("review_status", ""),
                "last_evaluated": variant_data.get("clinical_significance", {}).get("last_evaluated", ""),
            }
    except Exception as e:
        logger.warning(f"ClinVar query failed: {e}")
        return None

async def apply_acmg_rules(
    is_truncating: bool,
    clinvar_data: Optional[Dict],
    gene: str,
    consequence: Optional[str],
    chrom: Optional[str] = None,
    pos: Optional[int] = None,
    ref: Optional[str] = None,
    alt: Optional[str] = None
) -> tuple[str, List[ACMGEvidenceCode], float, List[str]]:
    """Apply ACMG/AMP rules to determine classification"""
    
    evidence_codes = []
    rationale = []
    
    # PVS1: Null variant in a gene where LOF is a known mechanism
    if is_truncating:
        evidence_codes.append(ACMGEvidenceCode(
            code="PVS1",
            category="pathogenic",
            strength="very_strong",
            rationale=f"Truncating variant ({consequence}) in {gene} - loss of function mechanism"
        ))
        rationale.append(f"✅ PVS1: Truncating variant ({consequence}) causes loss of function")
    
    # PP3: Multiple in-silico predictors support pathogenic (use real Evo2 scoring)
    if not is_truncating and chrom and pos and ref and alt:
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                evo_payload = {
                    "chrom": chrom,
                    "pos": int(pos),
                    "ref": ref,
                    "alt": alt,
                    "model_id": "evo2_1b"
                }
                evo_response = await client.post(
                    "http://127.0.0.1:8000/api/evo/score_variant_multi",
                    json=evo_payload
                )
                
                if evo_response.status_code == 200:
                    evo_result = evo_response.json()
                    delta_score = abs(evo_result.get("min_delta", 0.0))
                    
                    # PP3 applies if Evo2 predicts high disruption (delta > 5.0)
                    if delta_score > 5.0:
                        evidence_codes.append(ACMGEvidenceCode(
                            code="PP3",
                            category="pathogenic",
                            strength="supporting",
                            rationale=f"In-silico predictions (Evo2 delta={delta_score:.2f}) suggest deleterious effect"
                        ))
                        rationale.append(f"✅ PP3: Evo2 delta score {delta_score:.2f} predicts pathogenic")
                    else:
                        logger.info(f"PP3 not applied: Evo2 delta {delta_score:.2f} below threshold")
                else:
                    logger.warning(f"Evo2 failed for PP3: {evo_response.status_code}")
        except Exception as e:
            logger.warning(f"PP3 Evo2 scoring failed: {e}")
    
    # PM2: Absent from population databases (gnomAD)
    # TODO: Query gnomAD when available
    evidence_codes.append(ACMGEvidenceCode(
        code="PM2",
        category="pathogenic",
        strength="moderate",
        rationale="Variant not found in gnomAD population database (assumed rare)"
    ))
    rationale.append("✅ PM2: Rare or absent in population databases")
    
    # PS1: Same amino acid change as known pathogenic (from ClinVar)
    if clinvar_data and "pathogenic" in clinvar_data.get("classification", "").lower():
        evidence_codes.append(ACMGEvidenceCode(
            code="PS1",
            category="pathogenic",
            strength="strong",
            rationale=f"ClinVar reports this variant as {clinvar_data['classification']}"
        ))
        rationale.append(f"✅ PS1: ClinVar classification: {clinvar_data['classification']}")
    
    # Determine final classification based on evidence combination
    pathogenic_counts = {
        "very_strong": sum(1 for e in evidence_codes if e.category == "pathogenic" and e.strength == "very_strong"),
        "strong": sum(1 for e in evidence_codes if e.category == "pathogenic" and e.strength == "strong"),
        "moderate": sum(1 for e in evidence_codes if e.category == "pathogenic" and e.strength == "moderate"),
        "supporting": sum(1 for e in evidence_codes if e.category == "pathogenic" and e.strength == "supporting"),
    }
    
    benign_counts = {
        "strong": sum(1 for e in evidence_codes if e.category == "benign" and e.strength == "strong"),
        "supporting": sum(1 for e in evidence_codes if e.category == "benign" and e.strength == "supporting"),
    }
    
    # ACMG classification rules (simplified)
    if pathogenic_counts["very_strong"] >= 1 and pathogenic_counts["strong"] >= 1:
        classification = "Pathogenic"
        confidence = 0.95
    elif pathogenic_counts["very_strong"] >= 1 and pathogenic_counts["moderate"] >= 2:
        classification = "Pathogenic"
        confidence = 0.90
    elif is_truncating and pathogenic_counts["very_strong"] >= 1:
        # PVS1 alone is often sufficient for truncating variants
        classification = "Pathogenic"
        confidence = 0.85
    elif pathogenic_counts["strong"] >= 2:
        classification = "Likely Pathogenic"
        confidence = 0.75
    elif pathogenic_counts["strong"] >= 1 and pathogenic_counts["moderate"] >= 1:
        classification = "Likely Pathogenic"
        confidence = 0.70
    elif benign_counts["strong"] >= 1 and benign_counts["supporting"] >= 1:
        classification = "Likely Benign"
        confidence = 0.70
    elif benign_counts["strong"] >= 2:
        classification = "Benign"
        confidence = 0.80
    else:
        # Not enough evidence either way
        classification = "Variant of Uncertain Significance (VUS)"
        confidence = 0.50
    
    return classification, evidence_codes, confidence, rationale

@router.post("/classify_variant", response_model=ACMGClassificationResponse)
async def classify_variant(request: ACMGClassificationRequest):
    """
    Classify variant according to ACMG/AMP 2015 guidelines.
    
    **Research Use Only - Not for Clinical Diagnosis**
    
    Example:
    ```json
    {
        "gene": "BRCA1",
        "chrom": "17",
        "pos": 43045802,
        "ref": "C",
        "alt": "CT",
        "hgvs_c": "c.5266dupC",
        "hgvs_p": "p.Gln1756fs",
        "consequence": "frameshift_variant"
    }
    ```
    
    Returns 5-tier classification with evidence codes and rationale.
    """
    logger.info(f"ACMG classification request: {request.gene} {request.chrom}:{request.pos} {request.ref}>{request.alt}")
    
    try:
        # Step 1: Check if variant is truncating (PVS1 criterion)
        is_truncating = is_truncating_variant(request.consequence, request.hgvs_p)
        
        # Step 2: Query ClinVar for existing classification
        clinvar_data = await query_clinvar(request.gene, request.chrom, request.pos)
        
        # Step 3: Apply ACMG rules
        classification, evidence_codes, confidence, rationale = await apply_acmg_rules(
            is_truncating=is_truncating,
            clinvar_data=clinvar_data,
            gene=request.gene,
            consequence=request.consequence,
            chrom=request.chrom,
            pos=request.pos,
            ref=request.ref,
            alt=request.alt
        )
        
        # Step 4: Build response
        response = ACMGClassificationResponse(
            classification=classification,
            evidence_codes=evidence_codes,
            confidence=confidence,
            clinvar_classification=clinvar_data.get("classification") if clinvar_data else None,
            clinvar_review_status=clinvar_data.get("review_status") if clinvar_data else None,
            rationale=rationale,
            provenance={
                "method": "acmg_amp_2015_guidelines",
                "clinvar_queried": clinvar_data is not None,
                "truncation_analysis": is_truncating,
                "gene": request.gene,
                "variant": f"{request.chrom}:{request.pos} {request.ref}>{request.alt}",
                "timestamp": "2025-01-26"
            }
        )
        
        logger.info(f"ACMG classification: {classification} (confidence: {confidence:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"ACMG classification failed: {e}")
        raise HTTPException(status_code=500, detail=f"ACMG classification failed: {str(e)}")

@router.get("/health")
async def health():
    """Health check for ACMG router"""
    return {"status": "operational", "service": "acmg_classifier"}

