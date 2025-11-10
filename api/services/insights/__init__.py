"""
Insights Package: Calls predict_* insights endpoints and bundles results.
"""
from .models import InsightsBundle
from .bundle_client import bundle

__all__ = [
    "InsightsBundle",
    "bundle"
]


