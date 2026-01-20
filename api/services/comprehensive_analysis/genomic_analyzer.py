"""
Genomic Analyzer - Identifies and explains critical genomic findings.

Extracts critical genomic findings from patient data and explains:
- HOW they work (biological mechanisms)
- WHY they matter (clinical implications)
- Pathway connections
"""

from typing import List, Dict, Any, Optional
import logging

from api.services.toxicity_pathway_mappings import (
    DNA_REPAIR_GENES,
    INFLAMMATION_GENES,
    CARDIOMETABOLIC_GENES,
    PHARMACOGENES,
    is_pharmacogene,
)

logger = logging.getLogger(__name__)


class GenomicAnalyzer:
    """Analyze patient genomics and identify critical findings."""
    
    # Critical genes that warrant detailed explanation
    CRITICAL_GENES = {
        "MBD4": {
            "pathway": "Base Excision Repair (BER)",
            "syndrome": "MBD4-Associated Neoplasia Syndrome (MANS)",
            "implications": ["hypermutator", "ber_deficiency", "synthetic_lethality", "immunotherapy_candidate"]
        },
        "BRCA1": {
            "pathway": "Homologous Recombination (HR)",
            "syndrome": "Hereditary Breast and Ovarian Cancer (HBOC)",
            "implications": ["hrd", "parp_sensitivity", "platinum_sensitivity"]
        },
        "BRCA2": {
            "pathway": "Homologous Recombination (HR)",
            "syndrome": "Hereditary Breast and Ovarian Cancer (HBOC)",
            "implications": ["hrd", "parp_sensitivity", "platinum_sensitivity"]
        },
        "TP53": {
            "pathway": "DNA Damage Response",
            "syndrome": "Li-Fraumeni Syndrome",
            "implications": ["genomic_instability", "treatment_resistance", "poor_prognosis"]
        },
        "ATM": {
            "pathway": "DNA Damage Response",
            "syndrome": "Ataxia-Telangiectasia",
            "implications": ["radiation_sensitivity", "dna_repair_deficiency"]
        },
        "CHEK2": {
            "pathway": "DNA Damage Response",
            "syndrome": "Li-Fraumeni-like Syndrome",
            "implications": ["dna_repair_deficiency", "cancer_predisposition"]
        },
    }
    
    def __init__(self):
        pass
    
    def analyze_critical_findings(
        self,
        germline_variants: List[Dict[str, Any]],
        somatic_variants: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Identify and explain critical genomic findings.
        
        Args:
            germline_variants: List of germline variant dicts with 'gene', 'hgvs_p', etc.
            somatic_variants: Optional list of somatic variant dicts
        
        Returns:
            {
                'critical_findings': List[Dict],  # MBD4, TP53, etc.
                'biological_explanations': Dict[str, str],  # HOW it works
                'clinical_implications': Dict[str, str],  # WHY it matters
                'pathway_connections': Dict[str, List[str]]  # Connected pathways
            }
        """
        critical_findings = []
        biological_explanations = {}
        clinical_implications = {}
        pathway_connections = {}
        
        # Analyze germline variants
        for variant in germline_variants or []:
            gene = variant.get("gene", "").upper()
            if not gene:
                continue
            
            # Check if this is a critical gene
            if gene in self.CRITICAL_GENES:
                gene_info = self.CRITICAL_GENES[gene]
                
                # Determine zygosity
                zygosity = variant.get("zygosity", "unknown")
                if zygosity == "unknown":
                    # Try to infer from variant data
                    if variant.get("allele_frequency", 1.0) > 0.5:
                        zygosity = "homozygous"
                    else:
                        zygosity = "heterozygous"
                
                finding = {
                    "gene": gene,
                    "variant": variant.get("hgvs_p", variant.get("hgvs_c", "")),
                    "zygosity": zygosity,
                    "pathway": gene_info["pathway"],
                    "syndrome": gene_info.get("syndrome", ""),
                    "classification": variant.get("classification", "unknown"),
                    "source": "germline"
                }
                
                critical_findings.append(finding)
                
                # Generate explanations
                biological_explanations[gene] = self._explain_biology(gene, gene_info, zygosity)
                clinical_implications[gene] = self._explain_clinical_impact(gene, gene_info, zygosity)
                pathway_connections[gene] = self._get_pathway_connections(gene, gene_info)
        
        # Analyze somatic variants (TP53 mutant-type, etc.)
        for variant in (somatic_variants or []):
            gene = variant.get("gene", "").upper()
            if gene == "TP53" and variant.get("classification") in ["pathogenic", "likely_pathogenic"]:
                finding = {
                    "gene": gene,
                    "variant": variant.get("hgvs_p", "mutant-type"),
                    "zygosity": "somatic",
                    "pathway": "DNA Damage Response",
                    "classification": variant.get("classification", "pathogenic"),
                    "source": "somatic"
                }
                critical_findings.append(finding)
                
                if gene not in biological_explanations:
                    biological_explanations[gene] = self._explain_biology(gene, self.CRITICAL_GENES.get(gene, {}), "somatic")
                    clinical_implications[gene] = self._explain_clinical_impact(gene, self.CRITICAL_GENES.get(gene, {}), "somatic")
                    pathway_connections[gene] = self._get_pathway_connections(gene, self.CRITICAL_GENES.get(gene, {}))
        
        return {
            "critical_findings": critical_findings,
            "biological_explanations": biological_explanations,
            "clinical_implications": clinical_implications,
            "pathway_connections": pathway_connections
        }
    
    def _explain_biology(self, gene: str, gene_info: Dict[str, Any], zygosity: str) -> str:
        """Generate biological explanation for a gene."""
        
        if gene == "MBD4":
            if zygosity == "homozygous":
                return (
                    "MBD4 (Methyl-CpG Binding Domain 4) is a Base Excision Repair (BER) gene that acts as a "
                    "cellular 'spell-checker' for DNA. It recognizes G:T mismatches (where methylated cytosine "
                    "spontaneously becomes thymine) and removes the incorrect thymine. With HOMOZYGOUS loss "
                    "(both copies non-functional), G:T mismatches accumulate → C>T mutations pile up throughout "
                    "the genome → hypermutator phenotype."
                )
            else:
                return (
                    "MBD4 is a Base Excision Repair gene that fixes G:T mismatches. With heterozygous loss, "
                    "some function remains but mutations accumulate more slowly than homozygous loss."
                )
        
        elif gene == "TP53":
            return (
                "TP53 is the 'guardian of the genome' - it detects DNA damage and either pauses cell division "
                "for repair or triggers cell death if damage is too severe. Mutant TP53 loses this function, "
                "allowing damaged cells to continue dividing → genomic instability → cancer progression."
            )
        
        elif gene in ["BRCA1", "BRCA2"]:
            return (
                f"{gene} is critical for Homologous Recombination (HR) DNA repair. It repairs double-strand "
                "DNA breaks by finding a matching DNA template. Loss of function → cells can't repair "
                "double-strand breaks → genomic instability."
            )
        
        else:
            pathway = gene_info.get("pathway", "DNA repair")
            return (
                f"{gene} is involved in {pathway}. Loss of function affects DNA repair capacity and may "
                "increase cancer risk and affect treatment response."
            )
    
    def _explain_clinical_impact(self, gene: str, gene_info: Dict[str, Any], zygosity: str) -> str:
        """Generate clinical impact explanation."""
        
        implications = gene_info.get("implications", [])
        impact_parts = []
        
        if "hypermutator" in implications:
            impact_parts.append("Likely HIGH tumor mutational burden (TMB) → immunotherapy candidate")
        
        if "ber_deficiency" in implications or "dna_repair_deficiency" in implications:
            impact_parts.append("Enhanced platinum sensitivity (good for current treatment)")
            impact_parts.append("Normal cells also struggle → need nutritional support")
        
        if "synthetic_lethality" in implications or "parp_sensitivity" in implications:
            impact_parts.append("PARP inhibitors may be effective (even if BRCA-negative)")
        
        if "hrd" in implications:
            impact_parts.append("HRD+ phenotype → PARP inhibitor maintenance eligible")
        
        if "immunotherapy_candidate" in implications:
            impact_parts.append("High TMB → pembrolizumab may be effective")
        
        if zygosity == "homozygous":
            impact_parts.insert(0, "HOMOZYGOUS loss = NO functional protein → severe impact")
        
        return " | ".join(impact_parts) if impact_parts else "Requires further analysis"
    
    def _get_pathway_connections(self, gene: str, gene_info: Dict[str, Any]) -> List[str]:
        """Get connected pathways for a gene."""
        connections = []
        
        # Check which pathway sets this gene belongs to
        if gene in DNA_REPAIR_GENES:
            connections.append("DNA Repair")
        if gene in INFLAMMATION_GENES:
            connections.append("Inflammation")
        if gene in CARDIOMETABOLIC_GENES:
            connections.append("Cardiometabolic")
        if is_pharmacogene(gene):
            connections.append("Pharmacogenomics")
        
        # Add pathway from gene_info
        pathway = gene_info.get("pathway", "")
        if pathway and pathway not in connections:
            connections.append(pathway)
        
        return connections













