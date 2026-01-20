"""
PGx Health Check Router

Sprint 7: Production Hardening
Purpose: Provide health check endpoint for PGx services

Research Use Only - Not for Clinical Decision Making
"""

from fastapi import APIRouter
from typing import Dict, Any
from datetime import datetime
import logging

from api.services.pgx_production_monitoring import get_pgx_monitor
from api.services.pgx_extraction_service import get_pgx_extraction_service
from api.services.pgx_screening_service import get_pgx_screening_service
from api.services.risk_benefit_composition_service import get_risk_benefit_composition_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/pgx", tags=["pgx"])


@router.get("/health")
async def pgx_health_check() -> Dict[str, Any]:
    """
    Health check for PGx services.
    
    Returns:
        Health status of all PGx services
    """
    try:
        # Check service availability
        extraction_service = get_pgx_extraction_service()
        screening_service = get_pgx_screening_service()
        composition_service = get_risk_benefit_composition_service()
        
        # Get monitoring metrics
        monitor = get_pgx_monitor()
        health_status = monitor.get_health_status()
        
        # Overall health
        all_healthy = all(
            status.get("healthy", False)
            for status in health_status.values()
        )
        
        return {
            "status": "healthy" if all_healthy else "degraded",
            "services": {
                "extraction": "available",
                "screening": "available",
                "composition": "available"
            },
            "metrics": health_status,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }


@router.get("/metrics")
async def pgx_metrics() -> Dict[str, Any]:
    """
    Get PGx service metrics.
    
    Returns:
        Detailed metrics for all PGx services
    """
    try:
        monitor = get_pgx_monitor()
        return {
            "metrics": monitor.get_metrics(),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Metrics retrieval failed: {e}")
        return {
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

