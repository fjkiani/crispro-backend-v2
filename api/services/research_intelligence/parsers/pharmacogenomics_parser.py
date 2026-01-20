"""
Pharmacogenomics Case Parser

Extracts structured data from pharmacogenomics case reports.
"""

from typing import Dict, List, Any, Optional
import logging
import re

logger = logging.getLogger(__name__)


class PharmacogenomicsParser:
    """
    Parse pharmacogenomics case reports for dosing guidance validation.
    """
    
    def __init__(self):
        pass
    
    def parse_case_report(
        self,
        article: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Parse a pharmacogenomics case report article.
        
        Args:
            article: PubMed article dict with abstract/full-text
        
        Returns:
            Dict with structured pharmacogenomics data
        """
        abstract = article.get("abstract", "")
        title = article.get("title", "")
        
        # Extract key information using simple pattern matching
        # (Would be enhanced with LLM extraction)
        parsed_case = {
            "pmid": article.get("pmid", ""),
            "title": title,
            "gene": self._extract_gene(abstract, title),
            "variant": self._extract_variant(abstract, title),
            "drug": self._extract_drug(abstract, title),
            "phenotype": self._extract_phenotype(abstract),
            "dose_adjustment": self._extract_dose_adjustment(abstract),
            "toxicity_occurred": self._extract_toxicity(abstract),
            "evidence_tier": "CASE_REPORT"
        }
        
        return parsed_case
    
    def _extract_gene(self, abstract: str, title: str) -> Optional[str]:
        """Extract pharmacogene name from text."""
        pharmacogenes = ["DPYD", "UGT1A1", "TPMT", "CYP2D6", "CYP2C19"]
        text = (abstract + " " + title).upper()
        for gene in pharmacogenes:
            if gene in text:
                return gene
        return None
    
    def _extract_variant(self, abstract: str, title: str) -> Optional[str]:
        """Extract variant notation from text."""
        # Simple pattern matching (would be enhanced with LLM)
        patterns = [
            r'c\.\d+[+-]\d+[AGCT]>[AGCT]',  # c.1905+1G>A
            r'\*\d+[A-Z]?',  # *2A, *28
        ]
        text = abstract + " " + title
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group(0)
        return None
    
    def _extract_drug(self, abstract: str, title: str) -> Optional[str]:
        """Extract drug name from text."""
        drugs = ["5-fluorouracil", "5-FU", "irinotecan", "6-mercaptopurine", "tamoxifen"]
        text = abstract.lower() + " " + title.lower()
        for drug in drugs:
            if drug.lower() in text:
                return drug
        return None
    
    def _extract_phenotype(self, abstract: str) -> Optional[str]:
        """Extract metabolizer phenotype from text."""
        phenotypes = ["Poor Metabolizer", "Intermediate Metabolizer", "Normal Metabolizer"]
        abstract_upper = abstract.upper()
        for phenotype in phenotypes:
            if phenotype.upper() in abstract_upper:
                return phenotype
        return None
    
    def _extract_dose_adjustment(self, abstract: str) -> Optional[Dict[str, Any]]:
        """Extract dose adjustment information from text."""
        # Simple pattern matching (would be enhanced with LLM)
        patterns = [
            r'(\d+)%\s*(?:reduction|dose)',
            r'(\d+)\s*mg/m²',
        ]
        for pattern in patterns:
            match = re.search(pattern, abstract, re.IGNORECASE)
            if match:
                return {"adjustment": match.group(0), "type": "REDUCE"}
        return None
    
    def _extract_toxicity(self, abstract: str) -> bool:
        """Extract whether toxicity occurred."""
        toxicity_keywords = ["toxicity", "adverse", "neutropenia", "mucositis", "diarrhea", "severe"]
        abstract_lower = abstract.lower()
        return any(keyword in abstract_lower for keyword in toxicity_keywords)






















