"""
Manifest Computation: Evidence manifest generation.
"""
from typing import Dict, Any, List, Optional


def compute_evidence_manifest(citations: List[Dict[str, Any]], 
                             clinvar_data: Dict[str, Any], 
                             pubmed_query: Optional[str] = None) -> Dict[str, Any]:
    """
    Compute evidence manifest for provenance tracking.
    
    Args:
        citations: List of citation dictionaries
        clinvar_data: ClinVar classification data
        pubmed_query: PubMed query string
        
    Returns:
        Evidence manifest dictionary
    """
    return {
        "pubmed_query": pubmed_query,
        "citations": [
            {
                "pmid": citation.get("pmid"),
                "title": citation.get("title"),
                "publication_types": citation.get("publication_types")
            }
            for citation in citations[:3]
            if citation and citation.get("pmid")
        ],
        "clinvar": {
            "classification": clinvar_data.get("classification"),
            "review_status": clinvar_data.get("review_status"),
        },
    }


