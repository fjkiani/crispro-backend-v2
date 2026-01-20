"""
Trial Search Criteria Mapper

Extract search criteria from patient profile (generic, reusable).

Infrastructure component for patient-specific trial searches.
Works for any patient profile - extracts biomarkers, pathways, interventions.
"""

from typing import Dict, List, Any, Optional, Set
import logging

logger = logging.getLogger(__name__)


class TrialSearchCriteriaMapper:
    """
    Extract search criteria from patient profile (generic, reusable).
    
    Works for any patient profile - extracts:
    - Biomarkers (from germline_variants, tumor_context)
    - Pathways (inferred from biomarkers)
    - Interventions (inferred from pathways/biomarkers)
    - Eligibility filters (stage, status, etc.)
    """
    
    # Biomarker → Pathway mapping (configurable)
    BIOMARKER_TO_PATHWAY = {
        "MBD4": ["BER", "DDR"],
        "BRCA1": ["HRR", "DDR"],
        "BRCA2": ["HRR", "DDR"],
        "TP53": ["checkpoint", "apoptosis"],
        "PD-L1": ["checkpoint", "IO"],
        "PD-1": ["checkpoint", "IO"],
        "MSI-H": ["checkpoint", "IO"],
        "TMB-H": ["checkpoint", "IO"],
    }
    
    # Pathway → Intervention mapping (configurable)
    PATHWAY_TO_INTERVENTION = {
        "BER": ["PARP"],
        "HRR": ["PARP"],
        "DDR": ["PARP", "ATR", "WEE1"],
        "checkpoint": ["PD-1", "PD-L1", "CTLA-4"],
        "IO": ["pembrolizumab", "nivolumab", "atezolizumab"],
        "VEGF": ["bevacizumab", "avastin"],
        "PARP": ["olaparib", "niraparib", "rucaparib"],
        "ATR": ["ceralasertib", "berzosertib"],
        "WEE1": ["adavosertib", "AZD1775"],
    }
    
    def extract_criteria(self, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract search criteria from patient profile (generic).
        
        Args:
            patient_profile: Patient profile dict with:
                - germline_variants: List of germline variants
                - tumor_context: Dict with somatic_mutations, biomarkers
                - disease: Disease type
                - stage: Cancer stage
                - treatment_line: Treatment line
                - location_state: Location state
        
        Returns:
            {
                "biomarkers": List[str],  # ["MBD4", "TP53", "PD-L1"]
                "pathways": List[str],  # ["BER", "DDR", "checkpoint"]
                "interventions": List[str],  # ["PARP", "PD-1", "ATR"]
                "conditions": List[str],  # ["ovarian cancer"]
                "eligibility": {
                    "stage": str,  # "IVB"
                    "status": List[str],  # ["RECRUITING", "ACTIVE_NOT_RECRUITING"]
                    "location": Optional[str]  # "NY"
                }
            }
        """
        criteria = {
            "biomarkers": [],
            "pathways": [],
            "interventions": [],
            "conditions": [],
            "eligibility": {}
        }
        
        # Extract biomarkers from germline variants
        germline_variants = patient_profile.get("germline_variants", [])
        for variant in germline_variants:
            gene = variant.get("gene") or variant.get("Gene")
            if gene:
                criteria["biomarkers"].append(gene.upper())
        
        # Extract biomarkers from tumor context
        tumor_context = patient_profile.get("tumor_context", {})
        if tumor_context:
            # Somatic mutations
            somatic_mutations = tumor_context.get("somatic_mutations", [])
            for mutation in somatic_mutations:
                gene = mutation.get("gene") or mutation.get("Gene")
                if gene:
                    criteria["biomarkers"].append(gene.upper())
            
            # Biomarkers (PD-L1, MSI, TMB)
            biomarkers = tumor_context.get("biomarkers", {})
            for key, value in biomarkers.items():
                if key.upper() in ["PD-L1", "PDL1", "MSI", "TMB"]:
                    if value:  # If positive/present
                        criteria["biomarkers"].append(key.upper())
        
        # Dedupe biomarkers
        criteria["biomarkers"] = list(set(criteria["biomarkers"]))
        
        # Infer pathways from biomarkers
        pathways = set()
        for biomarker in criteria["biomarkers"]:
            if biomarker in self.BIOMARKER_TO_PATHWAY:
                pathways.update(self.BIOMARKER_TO_PATHWAY[biomarker])
        criteria["pathways"] = list(pathways)
        
        # Infer interventions from pathways
        interventions = set()
        for pathway in criteria["pathways"]:
            if pathway in self.PATHWAY_TO_INTERVENTION:
                interventions.update(self.PATHWAY_TO_INTERVENTION[pathway])
        criteria["interventions"] = list(interventions)
        
        # Extract conditions
        disease = patient_profile.get("disease", "")
        if disease:
            # Normalize disease name
            disease_normalized = disease.replace("_", " ").lower()
            criteria["conditions"].append(disease_normalized)
        
        # Extract eligibility filters
        criteria["eligibility"] = {
            "stage": patient_profile.get("stage"),
            "status": ["RECRUITING", "ACTIVE_NOT_RECRUITING", "NOT_YET_RECRUITING"],
            "location": patient_profile.get("location_state")
        }
        
        logger.info(f"✅ Extracted search criteria: {len(criteria['biomarkers'])} biomarkers, "
                   f"{len(criteria['pathways'])} pathways, {len(criteria['interventions'])} interventions")
        
        return criteria
