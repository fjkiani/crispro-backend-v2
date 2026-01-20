"""
Pathway Mapper - Maps mutated genes to biological pathways.

Maps essentiality scores to pathway disruption status.
"""
from typing import List, Dict
import logging

from .models import GeneEssentialityScore, PathwayAnalysis, PathwayStatus
from .constants import PATHWAY_DEFINITIONS, GENE_PATHWAY_MAP

logger = logging.getLogger(__name__)


class PathwayMapper:
    """
    Map mutated genes to biological pathways and determine pathway status.
    
    Pathways tracked:
    - BER (Base Excision Repair): MBD4, MUTYH, OGG1, NTHL1
    - HR (Homologous Recombination): BRCA1, BRCA2, ATM, ATR, PALB2
    - NHEJ (Non-Homologous End Joining): XRCC4, LIG4, PRKDC
    - MMR (Mismatch Repair): MLH1, MSH2, MSH6, PMS2
    - Checkpoint (G1/S, G2/M): TP53, CDKN2A, RB1, CHEK1, CHEK2
    - MAPK: KRAS, BRAF, NRAS, MEK1, ERK
    """
    
    def map_broken_pathways(
        self,
        essentiality_scores: List[GeneEssentialityScore]
    ) -> List[PathwayAnalysis]:
        """
        Map essentiality scores to pathway disruption status.
        
        Args:
            essentiality_scores: Scored genes
        
        Returns:
            List of PathwayAnalysis for each affected pathway
        """
        # Group genes by pathway
        pathway_genes = {}
        for score in essentiality_scores:
            gene = score.gene.upper()
            pathways = self._get_gene_pathways(gene)
            
            for pathway_id in pathways:
                if pathway_id not in pathway_genes:
                    pathway_genes[pathway_id] = []
                pathway_genes[pathway_id].append(score)
        
        # Analyze each pathway
        analyses = []
        for pathway_id, gene_scores in pathway_genes.items():
            analysis = self._analyze_pathway(pathway_id, gene_scores)
            analyses.append(analysis)
        
        # Sort by disruption score (most disrupted first)
        analyses.sort(key=lambda x: x.disruption_score, reverse=True)
        
        return analyses
    
    def _get_gene_pathways(self, gene: str) -> List[str]:
        """Get pathways a gene belongs to."""
        return GENE_PATHWAY_MAP.get(gene, ["UNKNOWN"])
    
    def _analyze_pathway(
        self,
        pathway_id: str,
        gene_scores: List[GeneEssentialityScore]
    ) -> PathwayAnalysis:
        """Analyze a single pathway's status."""
        pathway_def = PATHWAY_DEFINITIONS.get(pathway_id, {
            'name': pathway_id,
            'description': f'{pathway_id} pathway',
            'genes': set()
        })
        
        # Calculate aggregate disruption
        total_disruption = sum(s.essentiality_score for s in gene_scores)
        avg_disruption = total_disruption / len(gene_scores) if gene_scores else 0.0
        
        # Check for high-impact mutations
        has_lof = any(
            s.flags.get('truncation') or s.flags.get('frameshift')
            for s in gene_scores
        )
        has_hotspot = any(s.flags.get('hotspot') for s in gene_scores)
        
        # Determine status
        if has_lof or avg_disruption >= 0.8:
            status = PathwayStatus.NON_FUNCTIONAL
        elif has_hotspot or avg_disruption >= 0.6:
            status = PathwayStatus.COMPROMISED
        elif avg_disruption >= 0.4:
            status = PathwayStatus.COMPROMISED
        else:
            status = PathwayStatus.FUNCTIONAL
        
        # Generate description
        affected_genes = [s.gene for s in gene_scores]
        if status == PathwayStatus.NON_FUNCTIONAL:
            description = f"{pathway_def['name']} is NON-FUNCTIONAL due to {', '.join(affected_genes)} mutations"
        elif status == PathwayStatus.COMPROMISED:
            description = f"{pathway_def['name']} is COMPROMISED by {', '.join(affected_genes)} mutations"
        else:
            description = f"{pathway_def['name']} has minor disruption from {', '.join(affected_genes)}"
        
        return PathwayAnalysis(
            pathway_name=pathway_def['name'],
            pathway_id=pathway_id,
            status=status,
            genes_affected=affected_genes,
            disruption_score=round(avg_disruption, 3),
            description=description
        )


