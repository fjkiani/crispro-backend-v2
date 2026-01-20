"""
Trial Refresh Service - Configuration Constants

Centralized configuration for ClinicalTrials.gov API refresh service.
"""

# ClinicalTrials.gov API v2 endpoint
CLINICAL_TRIALS_API_URL = "https://clinicaltrials.gov/api/v2/studies"

# Request timeout in seconds
DEFAULT_TIMEOUT = 10.0

# Retry configuration
MAX_RETRIES = 2
RETRY_BACKOFF_BASE = 2  # Exponential backoff: 2^attempt seconds

# Batch size limits
MAX_NCT_IDS_PER_REQUEST = 100  # API supports up to 1000, but 100 is safer

# Location status values to include (recruiting locations only)
RECRUITING_STATUSES = ["RECRUITING", "NOT_YET_RECRUITING"]

# Requested API fields (minimal set for status + locations)
REQUESTED_FIELDS = (
    "NCTId,OverallStatus,LocationFacility,LocationCity,LocationState,"
    "LocationStatus,LocationContactName,LocationContactPhone,"
    "LocationZip"
)

