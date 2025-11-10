"""
Evidence Logger: Specialized logging for evidence items.
"""
from typing import List, Dict, Any
from .models import EvidenceItem
from .supabase_client import LoggingService


class EvidenceLogger:
    """Logger for evidence item data."""
    
    def __init__(self, logging_service: LoggingService):
        self.logging_service = logging_service
    
    async def log_items(self, evidence_items: List[EvidenceItem]) -> bool:
        """
        Log evidence items to Supabase.
        
        Args:
            evidence_items: List of evidence items
            
        Returns:
            True if logged successfully, False otherwise
        """
        if not self.logging_service.is_available() or not evidence_items:
            return False
        
        try:
            # Convert to dictionary format expected by Supabase
            supabase_items = []
            for item in evidence_items:
                supabase_items.append({
                    "run_signature": item.run_signature,
                    "drug_name": item.drug_name,
                    "evidence_type": item.evidence_type,
                    "content": item.content,
                    "strength_score": item.strength_score,
                    "pubmed_id": item.pubmed_id
                })
            
            return await self.logging_service.log_evidence_items(supabase_items)
            
        except Exception:
            # Don't fail the request if logging fails
            return False
    
    def create_evidence_items(self, run_signature: str, drugs_out: List[Dict[str, Any]]) -> List[EvidenceItem]:
        """
        Create evidence items from drug results.
        
        Args:
            run_signature: Run signature
            drugs_out: Drug results
            
        Returns:
            List of EvidenceItem objects
        """
        evidence_items = []
        
        for drug in drugs_out:
            manifest = drug.get("evidence_manifest", {})
            citations = manifest.get("citations", [])
            
            # Log citations
            for citation in citations:
                evidence_items.append(EvidenceItem(
                    run_signature=run_signature,
                    drug_name=drug.get("name"),
                    evidence_type="citation",
                    content=citation,
                    strength_score=citation.get("relevance_score", 0.0),
                    pubmed_id=citation.get("pmid")
                ))
            
            # Log ClinVar info
            clinvar_info = drug.get("clinvar", {})
            if clinvar_info.get("classification"):
                evidence_items.append(EvidenceItem(
                    run_signature=run_signature,
                    drug_name=drug.get("name"),
                    evidence_type="clinvar",
                    content=clinvar_info,
                    strength_score=clinvar_info.get("prior", 0.0)
                ))
        
        return evidence_items



