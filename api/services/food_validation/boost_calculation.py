"""
Boost Calculation Step

Calculates cancer type and biomarker boosts to overall score.
"""

import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


def calculate_boosts(
    compound: str,
    disease: str,
    disease_context: Dict[str, Any],
    treatment_history: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Calculate cancer type and biomarker boosts.
    
    Args:
        compound: Compound name
        disease: Disease ID
        disease_context: Disease context with biomarkers
        treatment_history: Treatment history (optional)
    
    Returns:
        {
            "cancer_type_boost": 0.0-0.15,
            "biomarker_boost": 0.0-0.1,
            "total_boost": 0.0-0.25,
            "reasons": [...]
        }
    """
    from api.services.food_data_loader import load_cancer_type_foods, load_biomarker_foods
    from api.services.food_treatment_line_service import normalize_treatment_line
    
    cancer_type_boost = 0.0
    biomarker_boost = 0.0
    boost_reasons = []
    
    compound_lower = compound.lower()
    
    # === CANCER TYPE FOOD BOOST ===
    cancer_type_foods = load_cancer_type_foods()
    cancer_recs = cancer_type_foods.get("cancer_types", {}).get(disease, {})
    
    if cancer_recs:
        # Check if compound matches any recommended food
        for food_rec in cancer_recs.get("recommended_foods", []):
            food_compound = food_rec.get("compound", "").lower()
            if compound_lower in food_compound or food_compound in compound_lower:
                cancer_type_boost = 0.1
                boost_reasons.append(f"Cancer type match ({disease})")
                
                # Extra boost for treatment line match
                treatment_lines = food_rec.get("treatment_lines", ["L1", "L2", "L3"])
                current_line = treatment_history.get("current_line", "L1") if treatment_history else "L1"
                current_line = normalize_treatment_line(current_line)
                
                if current_line in treatment_lines:
                    cancer_type_boost += 0.05
                    boost_reasons.append(f"Treatment line match ({current_line})")
                break
    
    # === BIOMARKER FOOD BOOST ===
    biomarker_foods = load_biomarker_foods()
    biomarkers = disease_context.get("biomarkers", {})
    
    def check_biomarker_match(biomarker_key: str, compound_list: List[str]) -> bool:
        """Check if compound matches any in biomarker compound list."""
        return any(compound_lower in rec or rec in compound_lower for rec in compound_list)
    
    # Check HRD+
    if biomarkers.get("HRD") == "POSITIVE":
        hrd_recs = biomarker_foods.get("biomarker_mappings", {}).get("HRD_POSITIVE", {})
        hrd_compounds = [f.get("compound", "").lower() for f in hrd_recs.get("recommended_foods", [])]
        if check_biomarker_match("HRD_POSITIVE", hrd_compounds):
            biomarker_boost = max(biomarker_boost, 0.1)
            boost_reasons.append("HRD+ biomarker match")
    
    # Check TMB-H (>=10)
    tmb_value = biomarkers.get("TMB", 0)
    if isinstance(tmb_value, (int, float)) and tmb_value >= 10:
        tmb_recs = biomarker_foods.get("biomarker_mappings", {}).get("TMB_HIGH", {})
        tmb_compounds = [f.get("compound", "").lower() for f in tmb_recs.get("recommended_foods", [])]
        if check_biomarker_match("TMB_HIGH", tmb_compounds):
            biomarker_boost = max(biomarker_boost, 0.1)
            boost_reasons.append("TMB-H biomarker match")
    
    # Check MSI-H
    if biomarkers.get("MSI") == "HIGH":
        msi_recs = biomarker_foods.get("biomarker_mappings", {}).get("MSI_HIGH", {})
        msi_compounds = [f.get("compound", "").lower() for f in msi_recs.get("recommended_foods", [])]
        if check_biomarker_match("MSI_HIGH", msi_compounds):
            biomarker_boost = max(biomarker_boost, 0.1)
            boost_reasons.append("MSI-H biomarker match")
    
    # Check HER2+
    if biomarkers.get("HER2") == "POSITIVE":
        her2_recs = biomarker_foods.get("biomarker_mappings", {}).get("HER2_POSITIVE", {})
        her2_compounds = [f.get("compound", "").lower() for f in her2_recs.get("recommended_foods", [])]
        if check_biomarker_match("HER2_POSITIVE", her2_compounds):
            biomarker_boost = max(biomarker_boost, 0.1)
            boost_reasons.append("HER2+ biomarker match")
    
    # Check BRCA mutant (from mutations or biomarkers)
    if biomarkers.get("BRCA") in ["POSITIVE", "MUTANT"] or any(
        mut.get("gene", "").upper() in ["BRCA1", "BRCA2"] 
        for mut in disease_context.get("mutations", [])
    ):
        brca_recs = biomarker_foods.get("biomarker_mappings", {}).get("BRCA_MUTANT", {})
        brca_compounds = [f.get("compound", "").lower() for f in brca_recs.get("recommended_foods", [])]
        if check_biomarker_match("BRCA_MUTANT", brca_compounds):
            biomarker_boost = max(biomarker_boost, 0.1)
            boost_reasons.append("BRCA mutant biomarker match")
    
    total_boost = cancer_type_boost + biomarker_boost
    
    return {
        "cancer_type_boost": cancer_type_boost,
        "biomarker_boost": biomarker_boost,
        "total_boost": total_boost,
        "reasons": boost_reasons
    }

