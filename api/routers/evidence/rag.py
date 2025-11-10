"""
RAG Module - RAG-based conversational query endpoints
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import os
from pathlib import Path
import sys

router = APIRouter()

# Initialize RAG agent (lazy loading)
_rag_agent = None

def get_rag_agent():
    """Get or initialize the RAG agent."""
    global _rag_agent
    if _rag_agent is None:
        # Check if API key is available before trying to initialize
        if not os.getenv("GEMINI_API_KEY"):
            print("Warning: GEMINI_API_KEY not found. RAG agent will not be available.")
            return None

        try:
            agent_dir = Path(__file__).resolve().parent.parent.parent.parent / "Pubmed-LLM-Agent-main"
            sys.path.append(str(agent_dir))
            from rag_agent import RAGAgent  # type: ignore
            _rag_agent = RAGAgent()
            print("✅ RAG Agent initialized successfully")
        except Exception as e:
            print(f"Warning: Could not initialize RAG agent: {e}")
            _rag_agent = None
    return _rag_agent

@router.post("/rag-query")
async def evidence_rag_query(request: Dict[str, Any]):
    """RAG-based conversational query for clinical literature.
    Input: { query: str, gene?: str, hgvs_p?: str, disease?: str, max_context_papers?: int }
    Output: { query, answer, evidence_level, confidence_score, supporting_papers, ... }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        query = (request.get("query") or "").strip()
        if not query:
            raise HTTPException(status_code=400, detail="query required")

        # Extract variant information
        gene = (request.get("gene") or "").strip()
        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        max_context_papers = int(request.get("max_context_papers") or 5)

        variant_info = {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease,
            'variant_info': f"{gene or 'Unknown'} {hgvs_p or 'Unknown'}"
        }

        # Get RAG agent
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        # Process the query
        result = rag_agent.query(
            query=query,
            variant_info=variant_info if gene or hgvs_p else None,
            max_context_papers=max_context_papers
        )

        # Format supporting papers for response
        formatted_papers = []
        for paper in result.get('supporting_papers', []):
            formatted_papers.append({
                'pmid': paper.get('pmid'),
                'title': paper.get('title', '')[:100] + "..." if len(paper.get('title', '')) > 100 else paper.get('title', ''),
                'year': paper.get('year'),
                'journal': paper.get('source'),
                'relevance_score': paper.get('similarity_score', 0),
                'doi': paper.get('doi'),
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pmid')}/" if paper.get('pmid') else None
            })

        return {
            'query': result.get('query'),
            'query_type': result.get('query_type'),
            'answer': result.get('answer'),
            'evidence_level': result.get('evidence_level'),
            'confidence_score': result.get('confidence_score'),
            'supporting_papers': formatted_papers,
            'total_papers_found': result.get('total_papers_found', 0),
            'generated_at': result.get('generated_at'),
            'variant_info': result.get('variant_info')
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query failed: {e}")

@router.post("/rag-add-variant")
async def evidence_rag_add_variant(request: Dict[str, Any]):
    """Add papers about a variant to the RAG knowledge base.
    Input: { gene: str, hgvs_p?: str, disease?: str, max_papers?: int }
    Output: { added, skipped, failed, total_found, new_found }
    """
    try:
        if not isinstance(request, dict):
            raise HTTPException(status_code=400, detail="invalid payload")

        gene = (request.get("gene") or "").strip()
        if not gene:
            raise HTTPException(status_code=400, detail="gene required")

        hgvs_p = (request.get("hgvs_p") or "").strip()
        disease = (request.get("disease") or "").strip()
        max_papers = int(request.get("max_papers") or 50)

        variant_info = {
            'gene': gene,
            'hgvs_p': hgvs_p,
            'disease': disease
        }

        # Get RAG agent
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        # Add variant to knowledge base
        result = rag_agent.add_variant_to_knowledge_base(variant_info, max_papers)

        if 'error' in result:
            raise HTTPException(status_code=500, detail=f"Failed to add variant: {result['error']}")

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Add variant failed: {e}")

@router.get("/rag-stats")
async def evidence_rag_stats():
    """Get RAG knowledge base statistics."""
    try:
        rag_agent = get_rag_agent()
        if not rag_agent:
            raise HTTPException(status_code=501, detail="RAG agent not available")

        stats = rag_agent.get_knowledge_base_stats()
        return stats

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Stats retrieval failed: {e}")



