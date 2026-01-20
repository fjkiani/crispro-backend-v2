"""
STAGE 3: Location Validation

Validate trials have NYC metro locations (within 50 miles of 10029).

This stage REJECTS:
- International trials (Italy, Europe, Asia)
- West coast trials (California, Oregon, Washington)
- Trials with no location data
"""

from . import nyc_metro_detector

__all__ = ['nyc_metro_detector']


