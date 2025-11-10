"""
Logging Package: Modular logging components for efficacy runs and evidence items.
"""
from .models import EfficacyRunData, EvidenceItem
from .supabase_client import LoggingService
from .efficacy_logger import EfficacyLogger
from .evidence_logger import EvidenceLogger
from .signature_generator import SignatureGenerator

# Global instances
logging_service = LoggingService()
efficacy_logger = EfficacyLogger(logging_service)
evidence_logger = EvidenceLogger(logging_service)
signature_generator = SignatureGenerator()

# Convenience functions
async def log_efficacy_run_async(run_data: EfficacyRunData) -> bool:
    """Async wrapper for logging efficacy run."""
    return await efficacy_logger.log_run(run_data)

async def log_evidence_items_async(evidence_items: list[EvidenceItem]) -> bool:
    """Async wrapper for logging evidence items."""
    return await evidence_logger.log_items(evidence_items)

def create_run_signature(request: dict) -> str:
    """Create run signature from request."""
    return signature_generator.create_signature(request)

def is_logging_available() -> bool:
    """Check if logging service is available."""
    return logging_service.is_available()

__all__ = [
    "EfficacyRunData",
    "EvidenceItem", 
    "LoggingService",
    "EfficacyLogger",
    "EvidenceLogger",
    "SignatureGenerator",
    "logging_service",
    "efficacy_logger",
    "evidence_logger", 
    "signature_generator",
    "log_efficacy_run_async",
    "log_evidence_items_async",
    "create_run_signature",
    "is_logging_available"
]



