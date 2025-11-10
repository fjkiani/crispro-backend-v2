"""
Main Knowledge Base Router
Combines all KB endpoint modules into a single router
"""
from fastapi import APIRouter

from .endpoints.items import router as items_router
from .endpoints.search import router as search_router
from .endpoints.admin import router as admin_router
from .endpoints.validation import router as validation_router
from .endpoints.client import router as client_router

# Create main KB router
router = APIRouter(prefix="/api/kb", tags=["knowledge-base"])

# Include all endpoint routers
router.include_router(items_router)
router.include_router(search_router)
router.include_router(admin_router)
router.include_router(validation_router)
router.include_router(client_router)

