"""
Evidence Mining Step

Mines evidence from PubMed and other sources.
Handles Research Intelligence paper merging.
"""

import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


async def mine_evidence(
    compound: str,
    disease: str,
    pathways: List[str],
    treatment_line: Optional[str] = None,
    research_intelligence_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Mine evidence for a compound.
    
    Args:
        compound: Compound name
        disease: Disease ID
        pathways: List of pathways
        treatment_line: Treatment line (optional)
        research_intelligence_result: Research Intelligence result (optional, for paper merging)
    
    Returns:
        {
            "papers": [...],
            "evidence_grade": "INSUFFICIENT" | "WEAK" | "MODERATE" | "STRONG",
            "total_papers": 0,
            "rct_count": 0,
            "mechanisms": [...],
            "query_used": "..."
        }
    """
    from api.services.enhanced_evidence_service import get_enhanced_evidence_service
    
    evidence_service = get_enhanced_evidence_service()
    
    evidence_result = await evidence_service.get_complete_evidence(
        compound=compound,
        disease=disease,
        pathways=pathways,
        treatment_line=treatment_line
    )
    
    # Merge Research Intelligence papers if available
    if research_intelligence_result:
        portal_results = research_intelligence_result.get("portal_results", {})
        pubmed_results = portal_results.get("pubmed", {})
        ri_papers = pubmed_results.get("articles", [])
        
        if ri_papers:
            existing_pmids = {p.get("pmid", "") for p in evidence_result.get("papers", [])}
            new_papers = [
                {
                    "title": p.get("title", ""),
                    "abstract": p.get("abstract", ""),
                    "pmid": p.get("pmid", ""),
                    "journal": p.get("journal", ""),
                    "source": "research_intelligence"
                }
                for p in ri_papers[:10]  # Top 10
                if p.get("pmid") and p.get("pmid") not in existing_pmids
            ]
            
            if new_papers:
                evidence_result.setdefault("papers", []).extend(new_papers)
                evidence_result["total_papers"] = evidence_result.get("total_papers", 0) + len(new_papers)
                logger.info(f"   Added {len(new_papers)} papers from research intelligence")
    
    return evidence_result

