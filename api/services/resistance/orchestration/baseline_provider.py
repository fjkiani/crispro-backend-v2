"""
Baseline Provider.

Provides population average baseline SAE features when patient baseline is missing.
"""

from typing import Dict


class BaselineProvider:
    """
    Provide population average baseline SAE features.
    
    Used when patient baseline is missing (Manager Q16).
    """
    
    @staticmethod
    def get_population_baseline() -> Dict:
        """
        Return population average baseline SAE features.
        
        Returns:
            Dict with population average values:
            - dna_repair_capacity: 0.50
            - mechanism_vector: [0.50] * 7
            - pathway_burden_ddr: 0.50
            - essentiality_hrr: 0.50
            - exon_disruption_score: 0.50
        """
        return {
            "dna_repair_capacity": 0.50,
            "mechanism_vector": [0.50] * 7,
            "pathway_burden_ddr": 0.50,
            "essentiality_hrr": 0.50,
            "exon_disruption_score": 0.50,
            "source": "population_average",
            "is_population_average": True
        }
