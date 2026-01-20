"""
PGx Extraction Service

Extracts pharmacogene variants from patient data (VCF files, patient profiles).

Purpose: Extract germline variants in pharmacogenes (DPYD, TPMT, UGT1A1, CYP2D6, CYP2C19)
for PGx safety screening.

Research Use Only - Not for Clinical Decision Making
"""

import logging
from typing import Dict, List, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

# Pharmacogenes for PGx screening
PHARMACOGENES = {
    "DPYD": {
        "entrez_id": 1806,
        "drugs": ["fluorouracil", "5-FU", "capecitabine", "tegafur"],
        "description": "Dihydropyrimidine dehydrogenase"
    },
    "TPMT": {
        "entrez_id": 7172,
        "drugs": ["mercaptopurine", "6-MP", "azathioprine", "thioguanine"],
        "description": "Thiopurine S-methyltransferase"
    },
    "UGT1A1": {
        "entrez_id": 54658,
        "drugs": ["irinotecan", "camptosar"],
        "description": "UDP glucuronosyltransferase family 1 member A1"
    },
    "CYP2D6": {
        "entrez_id": 1565,
        "drugs": ["tamoxifen", "codeine", "tramadol"],
        "description": "Cytochrome P450 family 2 subfamily D member 6"
    },
    "CYP2C19": {
        "entrez_id": 1557,
        "drugs": ["clopidogrel", "omeprazole", "voriconazole"],
        "description": "Cytochrome P450 family 2 subfamily C member 19"
    }
}


class PGxExtractionService:
    """
    Service for extracting pharmacogene variants from patient data.
    """
    
    def __init__(self):
        self.pharmacogenes = PHARMACOGENES
    
    def extract_from_vcf(
        self,
        vcf_mutations: List[Dict[str, Any]],
        sample_type: str = "germline"
    ) -> List[Dict[str, Any]]:
        """
        Extract pharmacogene variants from VCF mutations.
        
        Args:
            vcf_mutations: List of mutations from VCF parser
            sample_type: "germline" or "somatic" (only germline for PGx)
        
        Returns:
            List of pharmacogene variants
        """
        if sample_type != "germline":
            logger.warning(f"PGx variants should be from germline, got {sample_type}")
        
        pgx_variants = []
        pharmacogene_symbols = set(self.pharmacogenes.keys())
        
        for mutation in vcf_mutations:
            gene = mutation.get("gene", "").upper()
            
            # Check if this is a pharmacogene
            if gene in pharmacogene_symbols:
                variant = {
                    "gene": gene,
                    "variant": mutation.get("variant") or mutation.get("hgvs_c") or mutation.get("hgvs_p") or "",
                    "hgvs_c": mutation.get("hgvs_c", ""),
                    "hgvs_p": mutation.get("hgvs_p", ""),
                    "chrom": mutation.get("chrom"),
                    "pos": mutation.get("pos"),
                    "ref": mutation.get("ref"),
                    "alt": mutation.get("alt"),
                    "zygosity": mutation.get("zygosity", "unknown"),
                    "vaf": mutation.get("vaf"),
                    "source": "vcf",
                    "sample_type": sample_type
                }
                pgx_variants.append(variant)
        
        logger.info(f"Extracted {len(pgx_variants)} PGx variants from {len(vcf_mutations)} mutations")
        return pgx_variants
    
    def extract_from_patient_profile(
        self,
        patient_profile: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Extract pharmacogene variants from patient profile.
        
        Args:
            patient_profile: Patient profile dict (may have germline_panel or germline_variants)
        
        Returns:
            List of pharmacogene variants
        """
        pgx_variants = []
        pharmacogene_symbols = set(self.pharmacogenes.keys())
        
        # Check germline_panel (from extraction models)
        germline_panel = patient_profile.get("germline_panel")
        if germline_panel:
            # Check pathogenic variants
            pathogenic = germline_panel.get("pathogenic", {})
            for gene, variants in pathogenic.items():
                if gene.upper() in pharmacogene_symbols:
                    for variant_data in variants if isinstance(variants, list) else [variants]:
                        variant = {
                            "gene": gene.upper(),
                            "variant": variant_data.get("variant") or variant_data.get("hgvs") or "",
                            "hgvs_c": variant_data.get("hgvs_c", ""),
                            "hgvs_p": variant_data.get("hgvs_p", ""),
                            "classification": "pathogenic",
                            "source": "germline_panel"
                        }
                        pgx_variants.append(variant)
            
            # Check VUS (variants of uncertain significance) - may still be relevant for PGx
            vus = germline_panel.get("vus", {})
            for gene, variants in vus.items():
                if gene.upper() in pharmacogene_symbols:
                    for variant_data in variants if isinstance(variants, list) else [variants]:
                        variant = {
                            "gene": gene.upper(),
                            "variant": variant_data.get("variant") or variant_data.get("hgvs") or "",
                            "hgvs_c": variant_data.get("hgvs_c", ""),
                            "hgvs_p": variant_data.get("hgvs_p", ""),
                            "classification": "vus",
                            "source": "germline_panel"
                        }
                        pgx_variants.append(variant)
        
        # Check germline_variants (direct list format)
        germline_variants = patient_profile.get("germline_variants", [])
        if germline_variants:
            for variant_data in germline_variants:
                gene = variant_data.get("gene", "").upper()
                if gene in pharmacogene_symbols:
                    variant = {
                        "gene": gene,
                        "variant": variant_data.get("variant") or variant_data.get("hgvs") or "",
                        "hgvs_c": variant_data.get("hgvs_c", ""),
                        "hgvs_p": variant_data.get("hgvs_p", ""),
                        "classification": variant_data.get("classification", "unknown"),
                        "source": "germline_variants"
                    }
                    pgx_variants.append(variant)
        
        # Check biomarkers.germline_status (if structured)
        biomarkers = patient_profile.get("biomarkers", {})
        if isinstance(biomarkers, dict):
            germline_status = biomarkers.get("germline_status")
            if germline_status and isinstance(germline_status, dict):
                for gene, variant_info in germline_status.items():
                    if gene.upper() in pharmacogene_symbols:
                        variant = {
                            "gene": gene.upper(),
                            "variant": variant_info.get("variant") or variant_info.get("hgvs") or "",
                            "hgvs_c": variant_info.get("hgvs_c", ""),
                            "hgvs_p": variant_info.get("hgvs_p", ""),
                            "classification": variant_info.get("classification", "unknown"),
                            "source": "biomarkers"
                        }
                        pgx_variants.append(variant)
        
        logger.info(f"Extracted {len(pgx_variants)} PGx variants from patient profile")
        return pgx_variants
    
    def extract_from_mutations_list(
        self,
        mutations: List[Dict[str, Any]],
        sample_type: str = "germline"
    ) -> List[Dict[str, Any]]:
        """
        Extract pharmacogene variants from a list of mutations.
        
        Args:
            mutations: List of mutation dicts (from any source)
            sample_type: "germline" or "somatic"
        
        Returns:
            List of pharmacogene variants
        """
        if sample_type != "germline":
            logger.warning(f"PGx variants should be from germline, got {sample_type}")
        
        pgx_variants = []
        pharmacogene_symbols = set(self.pharmacogenes.keys())
        
        for mutation in mutations:
            gene = mutation.get("gene", "").upper()
            
            if gene in pharmacogene_symbols:
                variant = {
                    "gene": gene,
                    "variant": mutation.get("variant") or mutation.get("hgvs_c") or mutation.get("hgvs_p") or "",
                    "hgvs_c": mutation.get("hgvs_c", ""),
                    "hgvs_p": mutation.get("hgvs_p", ""),
                    "classification": mutation.get("classification", "unknown"),
                    "source": "mutations_list",
                    "sample_type": sample_type
                }
                pgx_variants.append(variant)
        
        return pgx_variants
    
    def get_pharmacogene_info(self, gene: str) -> Optional[Dict[str, Any]]:
        """Get information about a pharmacogene."""
        return self.pharmacogenes.get(gene.upper())
    
    def is_pharmacogene(self, gene: str) -> bool:
        """Check if a gene is a pharmacogene."""
        return gene.upper() in self.pharmacogenes


# Singleton instance
_pgx_extraction_service: Optional[PGxExtractionService] = None


def get_pgx_extraction_service() -> PGxExtractionService:
    """Get singleton PGx extraction service instance."""
    global _pgx_extraction_service
    if _pgx_extraction_service is None:
        _pgx_extraction_service = PGxExtractionService()
    return _pgx_extraction_service


