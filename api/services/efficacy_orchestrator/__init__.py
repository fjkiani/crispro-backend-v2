"""
Efficacy Orchestrator Package: Modular efficacy prediction components.
Lazy exports to avoid heavy import side-effects during test collection.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
	from .models import EfficacyRequest, EfficacyResponse  # pragma: no cover
	from .orchestrator import EfficacyOrchestrator, create_efficacy_orchestrator  # pragma: no cover
	from .drug_scorer import DrugScorer  # pragma: no cover
	from .sequence_processor import SequenceProcessor  # pragma: no cover

__all__ = [
	"EfficacyRequest",
	"EfficacyResponse",
	"EfficacyOrchestrator",
	"create_efficacy_orchestrator",
	"DrugScorer",
	"SequenceProcessor",
]


def __getattr__(name: str):
	if name == "EfficacyRequest" or name == "EfficacyResponse":
		from . import models as _models
		return getattr(_models, name)
	if name in ("EfficacyOrchestrator", "create_efficacy_orchestrator"):
		from . import orchestrator as _orch
		return getattr(_orch, name)
	if name == "DrugScorer":
		from . import drug_scorer as _ds
		return getattr(_ds, name)
	if name == "SequenceProcessor":
		from . import sequence_processor as _sp
		return getattr(_sp, name)
	raise AttributeError(name)
