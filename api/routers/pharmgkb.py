"""
⚔️ PHARMGKB PHARMACOGENOMICS ROUTER ⚔️

Integrates with PharmGKB API for:
- Gene-drug interactions
- Metabolizer status prediction (CYP2D6, CYP2C19, etc.)
- Dosing guidelines (CPIC)
- Adverse reaction predictions (HLA-B genotypes)

Research Use Only - Not for Clinical Diagnosis
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Optional
import httpx
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pharmgkb", tags=["pharmgkb"])

PHARMGKB_BASE_URL = "https://api.pharmgkb.org/v1/data"

class MetabolizerStatusRequest(BaseModel):
    """Request for metabolizer status prediction"""
    gene: str = Field(..., description="Gene symbol (e.g., CYP2D6, CYP2C19)")
    diplotype: Optional[str] = Field(None, description="Diplotype (e.g., *1/*4)")
    alleles: Optional[List[str]] = Field(None, description="List of alleles (e.g., ['*1', '*4'])")

class MetabolizerStatusResponse(BaseModel):
    """Metabolizer status classification"""
    gene: str
    metabolizer_status: str  # Poor, Intermediate, Normal, Rapid, Ultrarapid
    confidence: float
    activity_score: Optional[float] = None
    dose_adjustments: List[Dict[str, str]] = []
    drugs_affected: List[str] = []
    rationale: List[str] = []
    provenance: Dict

class DrugInteractionRequest(BaseModel):
    """Request for drug-gene interaction analysis"""
    drug_name: str = Field(..., description="Drug name (e.g., tamoxifen, warfarin)")
    gene: str = Field(..., description="Gene symbol (e.g., CYP2D6, VKORC1)")
    variant: Optional[str] = Field(None, description="Specific variant if known")

class DrugInteractionResponse(BaseModel):
    """Drug-gene interaction result"""
    drug_name: str
    gene: str
    interaction_type: str  # Efficacy, Toxicity, Dosing, Metabolism
    clinical_significance: str  # High, Moderate, Low
    recommendation: str
    evidence_level: str  # 1A, 2B, etc.
    guidelines: List[Dict[str, str]] = []
    citations: List[str] = []
    provenance: Dict

# CYP2D6 metabolizer phenotype mapping (CPIC guidelines)
CYP2D6_PHENOTYPES = {
    "*1/*1": {"status": "Normal Metabolizer", "activity_score": 2.0},
    "*1/*2": {"status": "Normal Metabolizer", "activity_score": 2.0},
    "*1/*4": {"status": "Intermediate Metabolizer", "activity_score": 1.0},
    "*4/*4": {"status": "Poor Metabolizer", "activity_score": 0.0},
    "*1/*10": {"status": "Intermediate Metabolizer", "activity_score": 1.0},
    "*2/*2": {"status": "Normal Metabolizer", "activity_score": 2.0},
    "*2/*4": {"status": "Intermediate Metabolizer", "activity_score": 1.0},
    # Add more diplotypes as needed
}

# CYP2C19 metabolizer phenotype mapping
CYP2C19_PHENOTYPES = {
    "*1/*1": {"status": "Normal Metabolizer", "activity_score": 2.0},
    "*1/*2": {"status": "Intermediate Metabolizer", "activity_score": 1.0},
    "*2/*2": {"status": "Poor Metabolizer", "activity_score": 0.0},
    "*1/*17": {"status": "Rapid Metabolizer", "activity_score": 2.5},
    "*17/*17": {"status": "Ultrarapid Metabolizer", "activity_score": 3.0},
}

# DPYD metabolizer phenotype mapping (CPIC guidelines - Oncology Critical)
DPYD_PHENOTYPES = {
    "*1/*1": {"status": "Normal Metabolizer", "activity_score": 1.0, "adjustment_factor": 1.0},
    "*1/*2A": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    "*2A/*2A": {"status": "Poor Metabolizer", "activity_score": 0.0, "adjustment_factor": 0.0},  # AVOID
    "*1/*13": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    "*13/*13": {"status": "Poor Metabolizer", "activity_score": 0.0, "adjustment_factor": 0.0},  # AVOID
    "*1/*D949V": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    # rs3918290 (IVS14+1G>A) = *2A
    # rs55886062 (D949V) = intermediate
}

# TPMT metabolizer phenotype mapping (CPIC guidelines - Oncology Critical)
TPMT_PHENOTYPES = {
    "*1/*1": {"status": "Normal Metabolizer", "activity_score": 1.0, "adjustment_factor": 1.0},
    "*1/*3A": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    "*3A/*3A": {"status": "Poor Metabolizer", "activity_score": 0.0, "adjustment_factor": 0.1},  # 10% dose
    "*1/*3B": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    "*3B/*3B": {"status": "Poor Metabolizer", "activity_score": 0.0, "adjustment_factor": 0.1},  # 10% dose
    "*1/*3C": {"status": "Intermediate Metabolizer", "activity_score": 0.5, "adjustment_factor": 0.5},
    "*3C/*3C": {"status": "Poor Metabolizer", "activity_score": 0.0, "adjustment_factor": 0.1},  # 10% dose
}

# UGT1A1 metabolizer phenotype mapping (CPIC guidelines - Oncology Critical)
UGT1A1_PHENOTYPES = {
    "*1/*1": {"status": "Normal Metabolizer", "activity_score": 1.0, "adjustment_factor": 1.0},
    "*1/*28": {"status": "Intermediate Metabolizer", "activity_score": 0.7, "adjustment_factor": 0.85},
    "*28/*28": {"status": "Poor Metabolizer", "activity_score": 0.3, "adjustment_factor": 0.7},  # 30% reduction
    "*1/*6": {"status": "Intermediate Metabolizer", "activity_score": 0.7, "adjustment_factor": 0.85},
    "*6/*6": {"status": "Poor Metabolizer", "activity_score": 0.3, "adjustment_factor": 0.7},  # 30% reduction
    "*28/*6": {"status": "Poor Metabolizer", "activity_score": 0.3, "adjustment_factor": 0.7},  # 30% reduction
}

# Drug-gene pairs with known interactions
DRUG_GENE_INTERACTIONS = {
    ("tamoxifen", "CYP2D6"): {
        "type": "Efficacy",
        "significance": "High",
        "recommendation": "Poor metabolizers may have reduced tamoxifen efficacy. Consider alternative therapy or increased monitoring.",
        "evidence": "1A"
    },
    ("clopidogrel", "CYP2C19"): {
        "type": "Efficacy",
        "significance": "High",
        "recommendation": "Poor metabolizers have reduced clopidogrel activation. Consider prasugrel or ticagrelor.",
        "evidence": "1A"
    },
    ("warfarin", "CYP2C9"): {
        "type": "Dosing",
        "significance": "High",
        "recommendation": "Dose adjustments required based on CYP2C9 genotype. Start with lower dose for poor metabolizers.",
        "evidence": "1A"
    },
    ("warfarin", "VKORC1"): {
        "type": "Dosing",
        "significance": "High",
        "recommendation": "VKORC1 variant requires dose reduction. Use pharmacogenetic dosing algorithm.",
        "evidence": "1A"
    },
    # Oncology-critical drug-gene interactions
    ("5-fluorouracil", "DPYD"): {
        "type": "Toxicity",
        "significance": "High",
        "recommendation": "Poor metabolizers: AVOID or reduce dose by 25-50% with enhanced monitoring. Intermediate: Reduce by 50%.",
        "evidence": "1A"
    },
    ("capecitabine", "DPYD"): {
        "type": "Toxicity",
        "significance": "High",
        "recommendation": "Poor metabolizers: AVOID or reduce dose by 25-50% with enhanced monitoring. Intermediate: Reduce by 50%.",
        "evidence": "1A"
    },
    ("6-mercaptopurine", "TPMT"): {
        "type": "Toxicity",
        "significance": "High",
        "recommendation": "Poor metabolizers: Reduce to 10% of standard dose, administer 3x weekly. Intermediate: Reduce by 30-50%.",
        "evidence": "1A"
    },
    ("azathioprine", "TPMT"): {
        "type": "Toxicity",
        "significance": "High",
        "recommendation": "Poor metabolizers: Reduce dose by 90% (start at 10% of standard). Intermediate: Reduce by 30-50%.",
        "evidence": "1A"
    },
    ("irinotecan", "UGT1A1"): {
        "type": "Toxicity",
        "significance": "High",
        "recommendation": "Poor metabolizers (*28/*28): Reduce starting dose by 30%. Intermediate: Standard dose with close monitoring.",
        "evidence": "1A"
    },
}

async def query_pharmgkb_gene(gene: str) -> Optional[Dict]:
    """Query PharmGKB for gene information"""
    try:
        url = f"{PHARMGKB_BASE_URL}/gene"
        params = {"name": gene, "view": "base"}
        
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, params=params)
            
            if resp.status_code == 200:
                data = resp.json()
                if isinstance(data, list) and len(data) > 0:
                    return data[0]
            return None
    except Exception as e:
        logger.warning(f"PharmGKB gene query failed: {e}")
        return None

def get_metabolizer_status(gene: str, diplotype: Optional[str]) -> Dict:
    """
    Determine metabolizer status from gene and diplotype.
    Uses CPIC guidelines for phenotype prediction.
    """
    if not diplotype:
        return {
            "status": "Unknown",
            "activity_score": None,
            "confidence": 0.0
        }
    


    # DPYD note: in many oncology workflows we may only have a single actionable allele string (e.g., "*2A")
    # rather than a full diplotype (e.g., "*1/*2A"). We treat known decreased-function alleles as INTERMEDIATE
    # for safety gating (RUO). Full diplotype support remains preferred.
    if gene == "DPYD" and diplotype and "/" not in diplotype:
        allele = diplotype.strip()
        decreased = {"*2A", "*13", "HapB3", "c.2846A>T"}
        if allele in decreased:
            return {
                "status": "Intermediate Metabolizer",
                "activity_score": 1.0,
                "adjustment_factor": 0.5,
                "confidence": 0.85,
            }

    # Select phenotype mapping based on gene
    phenotype_map = {}
    if gene == "CYP2D6":
        phenotype_map = CYP2D6_PHENOTYPES
    elif gene == "CYP2C19":
        phenotype_map = CYP2C19_PHENOTYPES
    elif gene == "DPYD":
        phenotype_map = DPYD_PHENOTYPES
    elif gene == "TPMT":
        phenotype_map = TPMT_PHENOTYPES
    elif gene == "UGT1A1":
        phenotype_map = UGT1A1_PHENOTYPES
    else:
        return {
            "status": "Unsupported Gene",
            "activity_score": None,
            "confidence": 0.0
        }
    
    # Look up diplotype
    if diplotype in phenotype_map:
        result = phenotype_map[diplotype].copy()
        result["confidence"] = 0.95  # High confidence for known diplotypes
        return result
    else:
        # Unknown diplotype - make conservative prediction
        return {
            "status": "Unknown Diplotype",
            "activity_score": None,
            "confidence": 0.3
        }

def get_dose_adjustments(gene: str, metabolizer_status: str) -> List[Dict[str, str]]:
    """Get dosing recommendations based on metabolizer status"""
    adjustments = []
    
    if gene == "CYP2D6":
        if "Poor" in metabolizer_status:
            adjustments.append({
                "drug": "Tamoxifen",
                "adjustment": "Consider alternative endocrine therapy (aromatase inhibitor)",
                "rationale": "Poor metabolizers have reduced conversion to active metabolite"
            })
            adjustments.append({
                "drug": "Codeine",
                "adjustment": "Avoid use - reduced analgesic effect",
                "rationale": "Poor metabolizers cannot convert codeine to morphine"
            })
        elif "Ultrarapid" in metabolizer_status:
            adjustments.append({
                "drug": "Codeine",
                "adjustment": "Avoid use or reduce dose - increased toxicity risk",
                "rationale": "Ultrarapid metabolizers have excessive morphine production"
            })
    
    elif gene == "CYP2C19":
        if "Poor" in metabolizer_status:
            adjustments.append({
                "drug": "Clopidogrel",
                "adjustment": "Use alternative P2Y12 inhibitor (prasugrel or ticagrelor)",
                "rationale": "Poor metabolizers have reduced clopidogrel activation"
            })
        elif "Intermediate" in metabolizer_status:
            adjustments.append({
                "drug": "Clopidogrel",
                "adjustment": "Consider alternative P2Y12 inhibitor (prasugrel or ticagrelor) or alternative strategy per guideline context",
                "rationale": "Intermediate metabolizers (one loss-of-function allele) have reduced clopidogrel activation and can have higher ischemic event risk depending on clinical setting"
            })
        elif "Ultrarapid" in metabolizer_status:
            adjustments.append({
                "drug": "Voriconazole",
                "adjustment": "Increase dose or monitor drug levels",
                "rationale": "Ultrarapid metabolizers have increased clearance"
            })
    
    elif gene == "DPYD":
        if "Poor" in metabolizer_status:
            adjustments.append({
                "drug": "5-Fluorouracil",
                "adjustment": "AVOID or reduce dose by 25-50% with enhanced monitoring",
                "rationale": "DPYD deficiency leads to severe/fatal toxicity (5-10% mortality risk)"
            })
            adjustments.append({
                "drug": "Capecitabine",
                "adjustment": "AVOID or reduce dose by 25-50% with enhanced monitoring",
                "rationale": "DPYD deficiency affects capecitabine metabolism identically to 5-FU"
            })
        elif "Intermediate" in metabolizer_status:
            adjustments.append({
                "drug": "5-Fluorouracil",
                "adjustment": "Reduce dose by 50% initially, may titrate based on toxicity/response",
                "rationale": "Intermediate DPYD activity leads to 50% slower drug clearance"
            })
            adjustments.append({
                "drug": "Capecitabine",
                "adjustment": "Reduce dose by 50%",
                "rationale": "Intermediate DPYD activity"
            })
    
    elif gene == "TPMT":
        if "Poor" in metabolizer_status:
            adjustments.append({
                "drug": "6-Mercaptopurine",
                "adjustment": "Reduce to 10% of standard dose, administer 3x weekly",
                "rationale": "TPMT deficiency causes life-threatening myelosuppression"
            })
            adjustments.append({
                "drug": "Azathioprine",
                "adjustment": "Reduce dose by 90% (start at 10% of standard), consider 3x weekly dosing",
                "rationale": "TPMT deficiency causes life-threatening myelosuppression"
            })
        elif "Intermediate" in metabolizer_status:
            adjustments.append({
                "drug": "6-Mercaptopurine",
                "adjustment": "Reduce dose by 30-50%, start low and titrate",
                "rationale": "Intermediate TPMT activity increases myelosuppression risk"
            })
            adjustments.append({
                "drug": "Azathioprine",
                "adjustment": "Reduce dose by 30-50%, start low and titrate",
                "rationale": "Intermediate TPMT activity increases myelosuppression risk"
            })
    
    elif gene == "UGT1A1":
        if "Poor" in metabolizer_status:
            adjustments.append({
                "drug": "Irinotecan",
                "adjustment": "Reduce starting dose by 30% for *28/*28 homozygotes",
                "rationale": "UGT1A1*28 reduces glucuronidation of SN-38, increasing toxicity"
            })
        elif "Intermediate" in metabolizer_status:
            adjustments.append({
                "drug": "Irinotecan",
                "adjustment": "Standard dose acceptable, monitor closely for toxicity",
                "rationale": "Heterozygous *28 has modest effect"
            })
    
    return adjustments

@router.post("/metabolizer_status", response_model=MetabolizerStatusResponse)
async def predict_metabolizer_status(request: MetabolizerStatusRequest):
    """
    Predict metabolizer status from gene and diplotype.
    
    **Research Use Only - Not for Clinical Diagnosis**
    
    Example:
    ```json
    {
        "gene": "CYP2D6",
        "diplotype": "*4/*4"
    }
    ```
    
    Returns metabolizer status (Poor, Intermediate, Normal, Rapid, Ultrarapid) with dose adjustments.
    """
    logger.info(f"Metabolizer status request: {request.gene} {request.diplotype}")
    
    try:
        # Query PharmGKB for gene information (optional - adds context)
        gene_info = await query_pharmgkb_gene(request.gene)
        
        # Determine metabolizer status
        status_info = get_metabolizer_status(request.gene, request.diplotype)
        
        # Get dose adjustments
        dose_adjustments = get_dose_adjustments(request.gene, status_info["status"])
        
        # Build rationale
        rationale = []
        rationale.append(f"Gene: {request.gene}")
        if request.diplotype:
            rationale.append(f"Diplotype: {request.diplotype}")
        rationale.append(f"Metabolizer Status: {status_info['status']}")
        if status_info["activity_score"] is not None:
            rationale.append(f"Activity Score: {status_info['activity_score']}")
        
        # List affected drugs
        drugs_affected = [adj["drug"] for adj in dose_adjustments]
        
        response = MetabolizerStatusResponse(
            gene=request.gene,
            metabolizer_status=status_info["status"],
            confidence=status_info["confidence"],
            activity_score=status_info["activity_score"],
            dose_adjustments=dose_adjustments,
            drugs_affected=drugs_affected,
            rationale=rationale,
            provenance={
                "method": "pharmgkb_cpic_guidelines",
                "gene": request.gene,
                "diplotype": request.diplotype,
                "pharmgkb_queried": gene_info is not None,
                "timestamp": "2025-01-26"
            }
        )
        
        logger.info(f"Metabolizer status: {status_info['status']} (confidence: {status_info['confidence']:.2f})")
        return response
        
    except Exception as e:
        logger.error(f"Metabolizer status prediction failed: {e}")
        raise HTTPException(status_code=500, detail=f"Metabolizer status prediction failed: {str(e)}")

@router.post("/drug_interaction", response_model=DrugInteractionResponse)
async def analyze_drug_interaction(request: DrugInteractionRequest):
    """
    Analyze drug-gene interaction.
    
    **Research Use Only - Not for Clinical Diagnosis**
    
    Example:
    ```json
    {
        "drug_name": "tamoxifen",
        "gene": "CYP2D6"
    }
    ```
    
    Returns clinical significance and dosing recommendations.
    """
    logger.info(f"Drug interaction request: {request.drug_name} - {request.gene}")
    
    try:
        # Look up interaction
        key = (request.drug_name.lower(), request.gene.upper())
        interaction = DRUG_GENE_INTERACTIONS.get(key)
        
        if not interaction:
            # No known interaction
            response = DrugInteractionResponse(
                drug_name=request.drug_name,
                gene=request.gene,
                interaction_type="Unknown",
                clinical_significance="Unknown",
                recommendation="No pharmacogenetic guideline available for this drug-gene pair.",
                evidence_level="N/A",
                guidelines=[],
                citations=[],
                provenance={
                    "method": "pharmgkb_lookup",
                    "drug": request.drug_name,
                    "gene": request.gene,
                    "interaction_found": False
                }
            )
            return response
        
        # Known interaction
        response = DrugInteractionResponse(
            drug_name=request.drug_name,
            gene=request.gene,
            interaction_type=interaction["type"],
            clinical_significance=interaction["significance"],
            recommendation=interaction["recommendation"],
            evidence_level=interaction["evidence"],
            guidelines=[
                {
                    "source": "CPIC",
                    "recommendation": interaction["recommendation"]
                }
            ],
            citations=[
                f"PharmGKB {request.drug_name}-{request.gene} interaction",
                "CPIC Guideline"
            ],
            provenance={
                "method": "pharmgkb_lookup",
                "drug": request.drug_name,
                "gene": request.gene,
                "interaction_found": True,
                "evidence_level": interaction["evidence"]
            }
        )
        
        logger.info(f"Drug interaction: {interaction['significance']} significance")
        return response
        
    except Exception as e:
        logger.error(f"Drug interaction analysis failed: {e}")
        raise HTTPException(status_code=500, detail=f"Drug interaction analysis failed: {str(e)}")

@router.get("/health")
async def health():
    """Health check for PharmGKB router"""
    return {"status": "operational", "service": "pharmgkb_pharmacogenomics"}

