"""
LLM Literature Service - Enhances Food Validator with PubMed literature mining

Uses existing Pubmed-LLM-Agent infrastructure to:
- Search PubMed for compound + disease evidence
- Extract clinical insights from papers
- Compute confidence based on paper quality/quantity
- Cache results in KnowledgeBase for future use
"""

import sys
from pathlib import Path
from typing import Dict, List, Any, Optional
import asyncio

# Add Pubmed-LLM-Agent to path
pubmed_agent_path = Path(__file__).parent.parent.parent / "Pubmed-LLM-Agent-main"
if str(pubmed_agent_path) not in sys.path:
    sys.path.insert(0, str(pubmed_agent_path))

try:
    from core.knowledge_base import KnowledgeBase
    from core.pubmed_client_enhanced import PubMedClientEnhanced
    LLM_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ Pubmed-LLM-Agent not available: {e}")
    LLM_AVAILABLE = False


class LLMLiteratureService:
    """
    Service to search and extract evidence from PubMed for food/supplement compounds.
    
    Integrates with existing Pubmed-LLM-Agent infrastructure for intelligent
    literature mining and evidence synthesis.
    """
    
    def __init__(self, storage_path: str = "knowledge_base/ayesha_foods"):
        if not LLM_AVAILABLE:
            self.available = False
            return
        
        try:
            self.kb = KnowledgeBase(storage_path=str(pubmed_agent_path / storage_path))
            self.pubmed = PubMedClientEnhanced()
            self.available = True
        except Exception as e:
            print(f"⚠️ Failed to initialize LLM services: {e}")
            self.available = False
    
    async def search_compound_evidence(
        self, 
        compound: str, 
        disease: str = "ovarian cancer",
        max_results: int = 20
    ) -> Dict[str, Any]:
        """
        Search PubMed for evidence linking compound to disease.
        
        Args:
            compound: Food/supplement name (e.g., "Vitamin D", "Curcumin")
            disease: Disease context (e.g., "ovarian cancer")
            max_results: Maximum papers to fetch
            
        Returns:
            {
                "papers": List[paper_dict],
                "evidence_summary": str,
                "confidence": float,
                "paper_count": int
            }
        """
        if not self.available:
            return {
                "papers": [],
                "evidence_summary": "LLM literature service unavailable",
                "confidence": 0.0,
                "paper_count": 0,
                "error": "LLM service not initialized"
            }
        
        try:
            # Build search query
            query = f"{compound} AND {disease} AND (treatment OR therapy OR supplement OR intervention)"
            
            # Search PubMed (async)
            loop = asyncio.get_event_loop()
            papers = await loop.run_in_executor(
                None,
                lambda: self.pubmed.search_papers(query, max_results=max_results)
            )
            
            if not papers or len(papers) == 0:
                return {
                    "papers": [],
                    "evidence_summary": f"No literature found for {compound} + {disease}",
                    "confidence": 0.0,
                    "paper_count": 0
                }
            
            # Add top papers to KB for future use (async)
            await loop.run_in_executor(
                None,
                lambda: self.kb.add_papers_batch(papers[:5], batch_size=3)
            )
            
            # Search KB for similar papers (vector search)
            kb_results = self.kb.search_papers(query, top_k=5, threshold=0.3)
            
            # Combine PubMed + KB results (dedup by PMID)
            all_papers = {}
            for p in papers:
                pmid = p.get('pmid', '')
                if pmid and pmid not in all_papers:
                    all_papers[pmid] = p
            
            for p in kb_results:
                pmid = p.get('pmid', '')
                if pmid and pmid not in all_papers:
                    all_papers[pmid] = p
            
            unique_papers = list(all_papers.values())[:10]  # Top 10 unique
            
            # Generate evidence summary
            evidence_summary = self._summarize_evidence(unique_papers)
            
            # Compute confidence
            confidence = self._compute_confidence(unique_papers)
            
            return {
                "papers": unique_papers,
                "evidence_summary": evidence_summary,
                "confidence": round(confidence, 3),
                "paper_count": len(unique_papers),
                "query": query
            }
            
        except Exception as e:
            print(f"❌ Error searching compound evidence: {e}")
            return {
                "papers": [],
                "evidence_summary": f"Error: {str(e)}",
                "confidence": 0.0,
                "paper_count": 0,
                "error": str(e)
            }
    
    def _summarize_evidence(self, papers: List[Dict[str, Any]]) -> str:
        """Generate evidence summary from papers."""
        if not papers:
            return "No evidence available"
        
        # Extract key findings from top 3 papers
        findings = []
        for i, paper in enumerate(papers[:3], 1):
            title = paper.get('title', 'N/A')
            abstract = paper.get('abstract', '')[:200] if paper.get('abstract') else ''
            pmid = paper.get('pmid', 'N/A')
            year = paper.get('year', 'N/A')
            
            title_truncated = title[:80] + "..." if len(title) > 80 else title
            findings.append(
                f"{i}. {title_truncated} (PMID: {pmid}, {year})"
            )
        
        summary = f"Found {len(papers)} relevant papers. Key findings:\n" + "\n".join(findings)
        return summary
    
    def _compute_confidence(self, papers: List[Dict[str, Any]]) -> float:
        """
        Compute confidence based on paper quality and quantity.
        
        Factors:
        - Paper count (more = better, up to 10)
        - Similarity scores (if available from vector search)
        - Recency (newer papers weighted higher)
        """
        if not papers:
            return 0.0
        
        # Base confidence from paper count (diminishing returns)
        paper_count_score = min(len(papers) / 8.0, 0.5)  # Max 0.5 from count
        
        # Similarity boost (if papers have similarity scores from vector search)
        similarity_scores = [p.get('similarity_score', 0) for p in papers if p.get('similarity_score')]
        similarity_boost = 0.0
        if similarity_scores:
            avg_similarity = sum(similarity_scores) / len(similarity_scores)
            similarity_boost = avg_similarity * 0.3  # Max 0.3 from similarity
        
        # Recency boost (prefer recent papers)
        current_year = 2024
        recent_papers = [p for p in papers if p.get('year') and p.get('year') >= current_year - 3]
        recency_boost = min(len(recent_papers) / 5.0, 0.2)  # Max 0.2 from recency
        
        total_confidence = min(paper_count_score + similarity_boost + recency_boost, 0.9)
        return total_confidence

# Singleton instance
_llm_service = None

def get_llm_service() -> LLMLiteratureService:
    """Get or create singleton LLM service instance."""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMLiteratureService()
    return _llm_service

