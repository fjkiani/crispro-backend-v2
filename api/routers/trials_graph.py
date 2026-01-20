"""
Graph-Optimized Trial Search Router - Component 4
Endpoint: /api/trials/search-optimized
"""
from fastapi import APIRouter, HTTPException
from api.services.hybrid_trial_search import HybridTrialSearchService
from api.schemas.trials_graph import OptimizedTrialSearchRequest

router = APIRouter()


@router.post("/api/trials/search-optimized")
async def search_trials_graph_optimized(request: OptimizedTrialSearchRequest):
    """
    Graph-optimized trial search with sporadic cancer filtering:
    - AstraDB: Semantic search (finds 50 candidates)
    - Neo4j: Graph optimization (ranks top 10)
    - Sporadic Filter: Excludes germline-required trials if germline_status="negative"
    - Biomarker Boost: Prioritizes trials matching tumor biomarkers (TMB/MSI/HRD)
    
    **Research Use Only**
    """
    try:
        service = HybridTrialSearchService()
        
        patient_ctx = request.patient_context.dict() if request.patient_context else {}
        
        # Extract sporadic cancer context (new fields)
        germline_status = getattr(request, 'germline_status', None)
        tumor_context_obj = getattr(request, 'tumor_context', None)
        tumor_context = tumor_context_obj.dict() if tumor_context_obj else None
        
        results = await service.search_optimized(
            query=request.query,
            patient_context=patient_ctx,
            germline_status=germline_status,
            tumor_context=tumor_context,
            top_k=request.top_k
        )
        
        # Extract metadata from first result (all have same metadata)
        excluded_count = results[0].get("excluded_count", 0) if results else 0
        sporadic_filtering = results[0].get("sporadic_filtering_applied", False) if results else False
        
        return {
            "success": True,
            "data": {
                "found_trials": results,
                "optimization_method": "hybrid_graph_sporadic",
                "count": len(results),
                "sporadic_filtering_applied": sporadic_filtering,
                "excluded_count": excluded_count
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))






