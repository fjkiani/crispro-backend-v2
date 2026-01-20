"""
Drug Recommender - Recommends drugs with E-component augmentation and confidence resolver.
"""
import logging
from typing import List, Dict, Any, Optional, Tuple

from .models import (
    PathwayAnalysis,
    GeneEssentialityScore,
    DrugRecommendation
)
from .constants import DRUG_CATALOG, PATHWAY_DRUG_MAP

logger = logging.getLogger(__name__)

class DrugRecommender:
    """
    Recommend drugs targeting essential backup pathways.
    
    Refinements:
    - E-component augmentation (boost confidence if evidence exists)
    - Confidence resolver (use PMIDs to break ties)
    - Lineage-specific penalties
    """
    
    def recommend(
        self,
        essential_pathways: List[PathwayAnalysis],
        disease: str,
        essentiality_scores: List[GeneEssentialityScore]
    ) -> List[DrugRecommendation]:
        """
        Recommend drugs for synthetic lethality targeting.
        """
        recommendations = []
        
        for pathway in essential_pathways:
            drugs = PATHWAY_DRUG_MAP.get(pathway.pathway_id, [])
            
            for drug_id in drugs:
                drug_info = DRUG_CATALOG.get(drug_id, {})
                if not drug_info:
                    continue
                
                # Step 3: Calculate confidence with DepMap grounding (from pathway disruption score)
                confidence = self._calculate_drug_confidence(
                    drug_info=drug_info,
                    pathway=pathway,
                    essentiality_scores=essentiality_scores,
                    disease=disease
                )
                
                # Step 4: Confidence Resolver (E-component augmentation)
                confidence, evidence_pmids = self._resolve_confidence(drug_info, confidence)
                
                # Generate rationale
                rationale = self._generate_rationale(
                    drug_info=drug_info,
                    pathway=pathway,
                    essentiality_scores=essentiality_scores
                )
                if evidence_pmids:
                    rationale.append(f"Supported by clinical evidence (PMIDs: {', '.join(evidence_pmids)})")

                rec = DrugRecommendation(
                    drug_name=drug_info['name'],
                    drug_class=drug_info['class'],
                    target_pathway=pathway.pathway_id,
                    confidence=round(confidence, 3),
                    mechanism=drug_info.get('mechanism', ''),
                    fda_approved=self._check_fda_approved(drug_info, disease),
                    evidence_tier=self._get_evidence_tier(drug_info, disease, confidence),
                    rationale=rationale
                )
                
                recommendations.append(rec)
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x.confidence, reverse=True)
        
        # Remove duplicates
        seen = set()
        unique = []
        for rec in recommendations:
            if rec.drug_name not in seen:
                seen.add(rec.drug_name)
                unique.append(rec)
        
        return unique[:10]

    def _calculate_drug_confidence(
        self,
        drug_info: dict,
        pathway: PathwayAnalysis,
        essentiality_scores: List[GeneEssentialityScore],
        disease: str
    ) -> float:
        """Calculate confidence including DepMap lineage penalties/boosts."""
        base = 0.4
        
        # Indication boost
        if disease.lower() in [i.lower() for i in drug_info.get('indications', [])]:
            base += 0.2
        
        # Target essentiality boost
        target_genes = drug_info.get('target_genes', [])
        for score in essentiality_scores:
            if score.gene in target_genes and score.essentiality_score >= 0.7:
                base += 0.15
                break
        
        # Pathway alignment
        if pathway.pathway_id in drug_info.get('pathways', []):
            base += 0.1
            
        # Functionalized DepMap Grounding (passed via pathway.disruption_score)
        base += pathway.disruption_score 
        
        return min(max(base, 0.0), 0.95)

    def _resolve_confidence(self, drug_info: dict, confidence: float) -> Tuple[float, List[str]]:
        """
        Confidence Resolver: Use PMIDs to break ties and augment score.
        """
        pmids = drug_info.get('evidence_pmids', [])
        if pmids:
            boost = 0.07 if len(pmids) >= 2 else 0.03
            confidence = min(0.99, confidence + boost)
            return confidence, pmids
        return confidence, []

    def _generate_rationale(
        self,
        drug_info: dict,
        pathway: PathwayAnalysis,
        essentiality_scores: List[GeneEssentialityScore]
    ) -> List[str]:
        rationale = [f"Targets {pathway.pathway_name} pathway"]
        rationale.append(drug_info.get('mechanism', 'Mechanism not specified'))
        
        for score in essentiality_scores:
            if score.essentiality_score >= 0.7:
                rationale.append(f"{score.gene} loss ({score.functional_consequence})")
        
        return rationale[:5]

    def _check_fda_approved(self, drug_info: dict, disease: str) -> bool:
        return any(disease.lower() in i.lower() for i in drug_info.get('indications', []))

    def _get_evidence_tier(self, drug_info: dict, disease: str, confidence: float) -> str:
        if self._check_fda_approved(drug_info, disease):
            return "I"
        elif confidence >= 0.7:
            return "II"
        elif confidence >= 0.5:
            return "III"
        return "Research"
