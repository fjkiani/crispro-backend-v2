"""
KB Client Endpoints
Task-oriented endpoints that use the KB client service
"""
from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import JSONResponse
from typing import List, Optional
import uuid
import logging

from ....services.kb_client import get_kb_client
from ..utils.rate_limiter import get_rate_limiter
from ..utils.client_extractor import get_client_ip

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/client", tags=["kb-client"])

@router.get("/gene/{gene}")
async def get_gene_info(
    gene: str,
    client_ip: str = Depends(get_client_ip)
):
    """Get gene entity with name, synonyms, and pathways"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_client = get_kb_client()
        gene_data = kb_client.get_gene(gene)
        
        if not gene_data:
            raise HTTPException(status_code=404, detail=f"Gene not found: {gene}")
        
        response = JSONResponse(
            content=gene_data,
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB get_gene_info: gene={gene}, run_id={run_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB get_gene_info error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/variant")
async def get_variant_info(
    gene: str = Query(..., description="Gene symbol"),
    hgvs_p: Optional[str] = Query(None, description="HGVS protein notation"),
    chrom: Optional[str] = Query(None, description="Chromosome"),
    pos: Optional[int] = Query(None, description="Position"),
    client_ip: str = Depends(get_client_ip)
):
    """Get variant entity if curated"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_client = get_kb_client()
        variant_data = kb_client.get_variant(gene, hgvs_p, chrom, pos)
        
        if not variant_data:
            raise HTTPException(status_code=404, detail=f"Variant not found: {gene} {hgvs_p}")
        
        response = JSONResponse(
            content=variant_data,
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB get_variant_info: gene={gene}, hgvs_p={hgvs_p}, run_id={run_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB get_variant_info error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/pathways")
async def get_pathways_info(
    genes: str = Query(..., description="Comma-separated list of gene symbols"),
    client_ip: str = Depends(get_client_ip)
):
    """Get pathway memberships for genes"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        gene_list = [g.strip() for g in genes.split(",") if g.strip()]
        kb_client = get_kb_client()
        pathways_data = kb_client.get_pathways(gene_list)
        
        response = JSONResponse(
            content={
                "genes": gene_list,
                "pathways": pathways_data,
                "count": len(pathways_data)
            },
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB get_pathways_info: genes={gene_list}, count={len(pathways_data)}, run_id={run_id}")
        return response
        
    except Exception as e:
        logger.error(f"KB get_pathways_info error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@router.get("/cohort-coverage/{gene}")
async def get_cohort_coverage_info(
    gene: str,
    client_ip: str = Depends(get_client_ip)
):
    """Get cohort coverage snapshot for gene"""
    
    # Rate limiting
    rate_limiter = get_rate_limiter()
    if not rate_limiter.check_rate_limit(client_ip):
        raise HTTPException(
            status_code=429, 
            detail="Rate limit exceeded",
            headers={"Retry-After": "60"}
        )
    
    # Generate run ID
    run_id = str(uuid.uuid4())
    
    try:
        kb_client = get_kb_client()
        coverage_data = kb_client.get_cohort_coverage(gene)
        
        if not coverage_data:
            raise HTTPException(status_code=404, detail=f"No cohort coverage found for gene: {gene}")
        
        response = JSONResponse(
            content=coverage_data,
            headers={
                "x-run-id": run_id,
                "cache-control": "public, max-age=300",
                "x-rate-remaining": str(rate_limiter.get_remaining_requests(client_ip))
            }
        )
        
        logger.info(f"KB get_cohort_coverage_info: gene={gene}, run_id={run_id}")
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"KB get_cohort_coverage_info error: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")


