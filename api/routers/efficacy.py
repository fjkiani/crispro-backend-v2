"""
Efficacy Router - Backward-compatible shim for the new efficacy package.
"""
from .efficacy import router

# Re-export the router for backward compatibility
__all__ = ["router"]
