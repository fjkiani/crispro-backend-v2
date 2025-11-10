"""
Evidence Router Shim - Backward-compatible import for the new evidence package
"""
from .evidence import router

# Re-export the router for backward compatibility
__all__ = ["router"]