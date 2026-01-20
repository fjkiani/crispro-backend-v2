"""
Dependency Identifier - Identifies essential backup pathways with DepMap grounding.

Functionalized: Uses lineage-aware DepMap data as a scoring term/safety net.
"""
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional

from .models import PathwayAnalysis, PathwayStatus
from .constants import SYNTHETIC_LETHALITY_MAP

logger = logging.getLogger(__name__)

class DependencyIdentifier:
    """
    Identify essential backup pathways with DepMap grounding.
    """
    
    def __init__(self):
        self.depmap_data = self._load_depmap_data()
        
    def _load_depmap_data(self) -> Dict[str, Any]:
        """Load lineage-aware DepMap dependency data."""
        # Path relative to the script location
        p = Path(__file__).resolve().parents[5] / "publications" / "synthetic_lethality" / "data" / "depmap_essentiality_by_context.json"
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load DepMap data: {e}")
        return {}

    def identify_dependencies(
        self,
        broken_pathways: List[PathwayAnalysis],
        disease: str
    ) -> List[PathwayAnalysis]:
        """
        Identify essential backup pathways with DepMap grounding.
        """
        essential = []
        
        # Map disease to DepMap lineage (OncotreeLineage)
        lineage = self._map_disease_to_lineage(disease)
        
        for broken in broken_pathways:
            if broken.status not in [PathwayStatus.NON_FUNCTIONAL, PathwayStatus.COMPROMISED]:
                continue
            
            dependencies = SYNTHETIC_LETHALITY_MAP.get(broken.pathway_id, [])
            
            for dep in dependencies:
                # DepMap Grounding: Check if the target drugs' primary targets are essential in this lineage
                # This acts as a "safety net" or "lineage-specific penalty"
                depmap_boost = self._get_depmap_boost(dep['drugs'], lineage)
                
                description = (
                    f"Cancer depends on {dep['name']} due to {broken.pathway_name} loss. "
                    f"Targetable with: {', '.join(dep['drugs'])}. "
                )
                if depmap_boost > 0:
                    description += f"DepMap lineage grounding ({lineage}): +{depmap_boost:.2f} confidence boost."
                elif depmap_boost < 0:
                    description += f"DepMap lineage penalty ({lineage}): {depmap_boost:.2f} penalty (low baseline dependency)."

                essential_pathway = PathwayAnalysis(
                    pathway_name=dep['name'],
                    pathway_id=dep['pathway_id'],
                    status=PathwayStatus.FUNCTIONAL,
                    genes_affected=[],
                    disruption_score=depmap_boost, # Functionalize DepMap data here
                    description=description
                )
                
                if not any(e.pathway_id == essential_pathway.pathway_id for e in essential):
                    essential.append(essential_pathway)
        
        return essential

    def _get_depmap_boost(self, drugs: List[str], lineage: str) -> float:
        """Functional DepMap scoring: calculate boost/penalty based on dependency."""
        if not self.depmap_data:
            return 0.0
            
        # Example: if drug is PARP inhibitor, check PARP1 dependency
        # Simple mapping for demo purposes
        target_genes = []
        for d in drugs:
            d_lower = d.lower()
            if "olaparib" in d_lower or "parp" in d_lower: target_genes.append("PARP1")
            if "ceralasertib" in d_lower or "atr" in d_lower: target_genes.append("ATR")
            if "adavosertib" in d_lower or "wee1" in d_lower: target_genes.append("WEE1")
            
        if not target_genes:
            return 0.0
            
        # Check lineage-specific dependency
        lineage_scores = self.depmap_data.get("by_lineage", {}).get(lineage, {})
        global_scores = self.depmap_data.get("global", {})
        
        max_boost = 0.0
        for gene in target_genes:
            score_data = lineage_scores.get(gene) or global_scores.get(gene)
            if score_data:
                # depmap_mean_effect: lower is more essential (e.g., -1.0 is highly essential)
                effect = score_data.get("depmap_mean_effect", 0.0)
                if effect < -0.5:
                    max_boost = max(max_boost, 0.15)
                elif effect > -0.1:
                    max_boost = min(max_boost, -0.10) # Lineage-specific penalty
                    
        return max_boost

    def _map_disease_to_lineage(self, disease: str) -> str:
        """Map common disease names to OncotreeLineage."""
        mapping = {
            "ovarian": "Ovary/Fallopian Tube",
            "breast": "Breast",
            "lung": "Lung",
            "colorectal": "Bowel",
            "endometrial": "Uterus",
            "pancreatic": "Pancreas",
            "adrenal": "Adrenal Gland"
        }
        return mapping.get(disease.lower(), "Other")
