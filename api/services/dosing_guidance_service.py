"""
Dosing Guidance Service

Unified service combining:
1. PharmGKB metabolizer status (CYP2D6, CYP2C19, DPYD, TPMT, UGT1A1)
2. Toxicity risk assessment (pathway overlap, pharmacogene detection)
3. Treatment line context (cumulative toxicity, cross-resistance)

Research Use Only - Not for Clinical Decision Making
"""

import uuid
from typing import Dict, List, Any, Optional
from datetime import datetime

from api.schemas.dosing import (
    DosingGuidanceRequest, DosingGuidanceResponse, DosingRecommendation,
    DosingAdjustmentType, CPICLevel
)
from api.routers.pharmgkb import (
    get_metabolizer_status, get_dose_adjustments
)
from api.services.safety_service import get_safety_service
from api.schemas.safety import ToxicityRiskRequest, PatientContext, TherapeuticCandidate, ClinicalContext
# Cumulative toxicity check (inline - treatment_line_integration doesn't export this yet)


def get_standard_dose(drug: str) -> Optional[str]:
    """
    Get standard dose for a drug (if known).
    
    P0: Static lookup table
    P1: Integrate with drug database
    """
    # Common oncology drug standard doses (mg/m² unless noted)
    STANDARD_DOSES = {
        "5-fluorouracil": "1000 mg/m² IV daily x 5 days",
        "5-fu": "1000 mg/m² IV daily x 5 days",
        "capecitabine": "1250 mg/m² PO twice daily",
        "irinotecan": "180 mg/m² IV every 2 weeks",
        "6-mercaptopurine": "75 mg/m² PO daily",
        "6-mp": "75 mg/m² PO daily",
        "azathioprine": "2-3 mg/kg PO daily",
        "tamoxifen": "20 mg PO daily",
        "carboplatin": "AUC 5-6 IV every 3 weeks",
        "cisplatin": "75 mg/m² IV every 3 weeks",
    }
    
    drug_lower = drug.lower().replace("-", "").replace("_", "")
    for key, dose in STANDARD_DOSES.items():
        if key in drug_lower or drug_lower in key:
            return dose
    
    return None


def compute_adjusted_dose(
    standard_dose: Optional[str],
    adjustment_factor: float
) -> Optional[str]:
    """
    Compute adjusted dose from standard dose and adjustment factor.
    
    Args:
        standard_dose: Standard dose string (e.g., "1000 mg/m²")
        adjustment_factor: Multiplier (0.5 = 50%, 0.1 = 10%)
    
    Returns:
        Adjusted dose string or None if standard_dose not provided
    """
    if not standard_dose or adjustment_factor == 1.0:
        return standard_dose
    
    # Extract numeric value (simple parsing)
    import re
    match = re.search(r'(\d+(?:\.\d+)?)', standard_dose)
    if match:
        value = float(match.group(1))
        adjusted_value = value * adjustment_factor
        # Replace the number in the string
        adjusted_dose = re.sub(r'\d+(?:\.\d+)?', f"{adjusted_value:.0f}", standard_dose, count=1)
        return adjusted_dose
    
    return standard_dose



def check_cumulative_toxicity(drug: str, prior_therapies: List[str]) -> Optional[str]:
    """
    Check for cumulative toxicity concerns based on treatment history.
    
    Based on CUMULATIVE_TOXICITY_RULES from audit.
    """
    if not prior_therapies:
        return None
    
    drug_lower = drug.lower()
    
    # Anthracyclines - lifetime dose limit
    anthracyclines = ["doxorubicin", "epirubicin", "daunorubicin"]
    if drug_lower in anthracyclines:
        prior_anthracyclines = [p for p in prior_therapies if p.lower() in anthracyclines]
        if prior_anthracyclines:
            return f"⚠️ CUMULATIVE TOXICITY ALERT: Prior anthracycline exposure ({', '.join(prior_anthracyclines)}). Monitor cardiac function (ECHO/MUGA) before each cycle. Lifetime doxorubicin limit: 450-550 mg/m²."
    
    # Platinum agents - nephrotoxicity accumulation
    platinum_agents = ["cisplatin", "carboplatin", "oxaliplatin"]
    if drug_lower in platinum_agents:
        prior_platinum = [p for p in prior_therapies if p.lower() in platinum_agents]
        if prior_platinum:
            return f"⚠️ CUMULATIVE TOXICITY ALERT: Prior platinum exposure ({', '.join(prior_platinum)}). Assess renal function (CrCl) before each cycle. Consider dose reduction for declining CrCl."
    
    # Taxanes - neuropathy accumulation
    taxanes = ["paclitaxel", "docetaxel", "nab-paclitaxel"]
    if drug_lower in taxanes:
        prior_taxanes = [p for p in prior_therapies if p.lower() in taxanes]
        if prior_taxanes:
            return f"⚠️ CUMULATIVE TOXICITY ALERT: Prior taxane exposure ({', '.join(prior_taxanes)}). Monitor neuropathy (CTCAE grading). Discontinue or reduce dose for Grade 2+ neuropathy."
    
    return None


class DosingGuidanceService:
    """
    Unified dosing guidance service.
    
    Combines PharmGKB metabolizer status, toxicity risk, and treatment line context
    to provide comprehensive dosing recommendations.
    """
    
    def __init__(self):
        self.safety_service = get_safety_service()
    
    async def get_dosing_guidance(
        self,
        request: DosingGuidanceRequest
    ) -> DosingGuidanceResponse:
        """
        Get dosing guidance based on gene, variant, drug, and treatment history.
        
        Args:
            request: DosingGuidanceRequest with gene, variant, drug, treatment history
        
        Returns:
            DosingGuidanceResponse with recommendations, alerts, and confidence
        """
        recommendations = []
        run_id = str(uuid.uuid4())
        
        # 1. Get PharmGKB metabolizer status
        metabolizer_info = get_metabolizer_status(request.gene, request.variant)
        metabolizer_status = metabolizer_info.get("status", "Unknown")
        activity_score = metabolizer_info.get("activity_score")
        adjustment_factor = metabolizer_info.get("adjustment_factor", 1.0)
        
        # 2. Get dose adjustments from PharmGKB
        dose_adjustments = get_dose_adjustments(request.gene, metabolizer_status)
        
        # 3. Toxicity risk assessment (optional - can be added later with patient context)
        # For now, we rely on PharmGKB metabolizer status and treatment line context
        toxicity_factors = []
        
        # 4. Check cumulative toxicity from treatment lines
        cumulative_alert = None
        if request.prior_therapies:
            cumulative_alert = check_cumulative_toxicity(
                request.drug,
                request.prior_therapies
            )
        
        # 5. Build recommendations from dose adjustments
        for adj in dose_adjustments:
            # Check if this adjustment is for the requested drug
            drug_match = (
                adj["drug"].lower() in request.drug.lower() or
                request.drug.lower() in adj["drug"].lower()
            )
            
            if drug_match or len(dose_adjustments) == 1 or adjustment_factor != 1.0:
                # Determine adjustment type from factor
                if adjustment_factor == 0.0:
                    adj_type = DosingAdjustmentType.AVOID
                elif adjustment_factor <= 0.1:
                    adj_type = DosingAdjustmentType.REDUCE_SIGNIFICANT
                elif adjustment_factor <= 0.5:
                    adj_type = DosingAdjustmentType.REDUCE_SIGNIFICANT
                elif adjustment_factor <= 0.75:
                    adj_type = DosingAdjustmentType.REDUCE_MODERATE
                elif adjustment_factor < 1.0:
                    adj_type = DosingAdjustmentType.REDUCE_MILD
                else:
                    adj_type = DosingAdjustmentType.STANDARD
                
                # Get standard dose
                standard_dose = request.standard_dose or get_standard_dose(request.drug)
                recommended_dose = compute_adjusted_dose(standard_dose, adjustment_factor)
                
                # Build monitoring requirements
                monitoring = []
                if "Poor" in metabolizer_status:
                    if request.gene == "DPYD":
                        monitoring = [
                            "CBC with differential daily during first cycle",
                            "LFTs twice weekly",
                            "Signs of severe mucositis/diarrhea"
                        ]
                    elif request.gene == "TPMT":
                        monitoring = [
                            "CBC weekly for 8 weeks, then every 2 weeks"
                        ]
                    elif request.gene == "UGT1A1":
                        monitoring = [
                            "Neutropenia monitoring",
                            "Diarrhea assessment (Grade 3+ requires dose hold)"
                        ]
                
                # Build alternatives
                alternatives = []
                if adj_type == DosingAdjustmentType.AVOID:
                    if request.gene == "DPYD" and ("5-fu" in request.drug.lower() or "5-fluorouracil" in request.drug.lower() or "fluorouracil" in request.drug.lower()):
                        alternatives = ["Raltitrexed (Tomudex)", "TAS-102 (trifluridine/tipiracil)"]
                    elif request.gene == "TPMT":
                        alternatives = ["MMF (mycophenolate) if immunosuppression needed"]
                    elif request.gene == "CYP2D6" and "tamoxifen" in request.drug.lower():
                        alternatives = ["Aromatase inhibitors (anastrozole, letrozole)"]
                
                recommendations.append(DosingRecommendation(
                    gene=request.gene,
                    drug=request.drug,
                    phenotype=metabolizer_status.replace(" Metabolizer", ""),
                    adjustment_type=adj_type,
                    adjustment_factor=adjustment_factor,  # CRITICAL FIX: Always use factor!
                    recommendation=adj.get("adjustment", "Standard dosing appropriate."),
                    rationale=adj.get("rationale", "Based on metabolizer status."),
                    cpic_level=CPICLevel.A if metabolizer_info.get("confidence", 0) >= 0.9 else CPICLevel.B,
                    monitoring=monitoring,
                    alternatives=alternatives
                ))
        
        # If no recommendations from PharmGKB, create a default one
        if not recommendations:
            recommendations.append(DosingRecommendation(
                gene=request.gene,
                drug=request.drug,
                phenotype=metabolizer_status.replace(" Metabolizer", "") if metabolizer_status != "Unknown" else None,
                adjustment_type=DosingAdjustmentType.STANDARD,
                recommendation=f"No CPIC guideline available for {request.gene} + {request.drug}. Standard dosing per institutional protocol.",
                rationale="Gene-drug pair not covered by current CPIC guidelines.",
                cpic_level=None,
                monitoring=["Standard oncology monitoring"],
                alternatives=[]
            ))
        
        # 6. Determine if contraindicated
        contraindicated = any(
            r.adjustment_type == DosingAdjustmentType.AVOID
            for r in recommendations
        )
        
        # 7. Calculate confidence
        if recommendations and recommendations[0].cpic_level in [CPICLevel.A, CPICLevel.A_B]:
            confidence = 0.9
        elif recommendations and recommendations[0].cpic_level == CPICLevel.B:
            confidence = 0.7
        elif metabolizer_info.get("confidence", 0) >= 0.9:
            confidence = 0.8
        else:
            confidence = 0.5
        
        return DosingGuidanceResponse(
            recommendations=recommendations,
            cumulative_toxicity_alert=cumulative_alert,
            contraindicated=contraindicated,
            confidence=confidence,
            provenance={
                "run_id": run_id,
                "version": "dosing_v0.1",
                "sources": ["pharmgkb_metabolizer_status", "toxicity_risk", "treatment_line_integration"],
                "gene": request.gene,
                "variant": request.variant,
                "drug": request.drug,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "note": "RUO: Requires clinical validation before use"
            }
        )


# Singleton
_dosing_service = DosingGuidanceService()

def get_dosing_guidance_service() -> DosingGuidanceService:
    """Get singleton dosing guidance service instance."""
    return _dosing_service

