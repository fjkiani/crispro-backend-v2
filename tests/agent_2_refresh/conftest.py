"""
Pytest fixtures for Agent 2 refresh service tests.
"""
import pytest
from typing import List, Dict, Any


@pytest.fixture
def sample_nct_ids() -> List[str]:
    """Sample NCT IDs for testing (real IDs that exist on ClinicalTrials.gov)"""
    return ["NCT02470585", "NCT02470586", "NCT02470587"]


@pytest.fixture
def mock_trial_data() -> Dict[str, Dict[str, Any]]:
    """Mock trial data for unit tests"""
    return {
        "NCT12345": {
            "status": "RECRUITING",
            "locations": [
                {
                    "facility": "Memorial Sloan Kettering",
                    "city": "New York",
                    "state": "NY",
                    "zip": "10065",
                    "status": "recruiting",
                    "contact_name": "Dr. Smith",
                    "contact_phone": "212-639-XXXX",
                    "contact_email": "smith@mskcc.org"
                },
                {
                    "facility": "UCLA Medical Center",
                    "city": "Los Angeles",
                    "state": "CA",
                    "zip": "90095",
                    "status": "recruiting",
                    "contact_name": "Dr. Jones",
                    "contact_phone": "310-825-XXXX",
                    "contact_email": "jones@ucla.edu"
                }
            ],
            "last_updated": "2024-10-20T12:00:00Z"
        }
    }

