"""
Holistic Score Package: Modular holistic score computation components.

Lazy exports to avoid heavy import side-effects during test collection.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .models import HolisticScoreResult, MECHANISM_FIT_WEIGHT, ELIGIBILITY_WEIGHT, PGX_SAFETY_WEIGHT  # pragma: no cover
    from .service import HolisticScoreService  # pragma: no cover
    from .mechanism_fit import compute_mechanism_fit  # pragma: no cover
    from .eligibility_scorer import compute_eligibility  # pragma: no cover
    from .pgx_safety import compute_pgx_safety  # pragma: no cover
    from .interpreter import interpret_score  # pragma: no cover

__all__ = [
    "HolisticScoreResult",
    "HolisticScoreService",
    "get_holistic_score_service",
    "MECHANISM_FIT_WEIGHT",
    "ELIGIBILITY_WEIGHT",
    "PGX_SAFETY_WEIGHT",
    "compute_mechanism_fit",
    "compute_eligibility",
    "compute_pgx_safety",
    "interpret_score",
]


# Singleton instance
_holistic_service_instance = None


def get_holistic_score_service():
    """Get singleton instance of HolisticScoreService."""
    global _holistic_service_instance
    if _holistic_service_instance is None:
        from .service import HolisticScoreService
        _holistic_service_instance = HolisticScoreService()
    return _holistic_service_instance


def __getattr__(name: str):
    """Lazy imports for better startup performance."""
    if name == "HolisticScoreResult":
        from . import models as _models
        return getattr(_models, name)
    if name == "HolisticScoreService":
        from . import service as _service
        return getattr(_service, name)
    if name in ("MECHANISM_FIT_WEIGHT", "ELIGIBILITY_WEIGHT", "PGX_SAFETY_WEIGHT"):
        from . import models as _models
        return getattr(_models, name)
    if name == "compute_mechanism_fit":
        from . import mechanism_fit as _mf
        return getattr(_mf, name)
    if name == "compute_eligibility":
        from . import eligibility_scorer as _es
        return getattr(_es, name)
    if name == "compute_pgx_safety":
        from . import pgx_safety as _pgx
        return getattr(_pgx, name)
    if name == "interpret_score":
        from . import interpreter as _interp
        return getattr(_interp, name)
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")
