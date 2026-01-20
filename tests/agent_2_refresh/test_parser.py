"""
Tests for trial refresh parser module.
"""
import pytest
from api.services.trial_refresh.parser import parse_trial_locations_and_status, parse_batch_response


def test_parse_trial_locations_and_status_valid():
    """Test parsing valid study object"""
    study = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345"
            },
            "statusModule": {
                "overallStatus": "RECRUITING"
            },
            "contactsLocationsModule": {
                "locations": [
                    {
                        "facility": "Test Facility",
                        "city": "New York",
                        "state": "NY",
                        "zip": "10001",
                        "status": "RECRUITING",
                        "contacts": [
                            {
                                "name": "Dr. Test",
                                "phone": "212-555-1234",
                                "email": "test@example.com"
                            }
                        ]
                    }
                ]
            }
        }
    }
    
    result = parse_trial_locations_and_status(study)
    
    assert result is not None
    assert result["status"] == "RECRUITING"
    assert len(result["locations"]) == 1
    assert result["locations"][0]["facility"] == "Test Facility"
    assert result["locations"][0]["contact_name"] == "Dr. Test"
    assert "last_updated" in result


def test_parse_trial_locations_and_status_no_nct_id():
    """Test parsing study with missing NCT ID returns None"""
    study = {
        "protocolSection": {
            "identificationModule": {}
        }
    }
    
    result = parse_trial_locations_and_status(study)
    assert result is None


def test_parse_trial_locations_and_status_filters_non_recruiting():
    """Test that non-recruiting locations are filtered out"""
    study = {
        "protocolSection": {
            "identificationModule": {
                "nctId": "NCT12345"
            },
            "statusModule": {
                "overallStatus": "RECRUITING"
            },
            "contactsLocationsModule": {
                "locations": [
                    {
                        "facility": "Recruiting Site",
                        "status": "RECRUITING",
                        "city": "NYC",
                        "state": "NY",
                        "contacts": []
                    },
                    {
                        "facility": "Completed Site",
                        "status": "COMPLETED",
                        "city": "Boston",
                        "state": "MA",
                        "contacts": []
                    }
                ]
            }
        }
    }
    
    result = parse_trial_locations_and_status(study)
    
    assert result is not None
    assert len(result["locations"]) == 1  # Only recruiting location included
    assert result["locations"][0]["facility"] == "Recruiting Site"


def test_parse_batch_response():
    """Test parsing batch API response"""
    data = {
        "studies": [
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT12345"},
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "contactsLocationsModule": {"locations": []}
                }
            },
            {
                "protocolSection": {
                    "identificationModule": {"nctId": "NCT67890"},
                    "statusModule": {"overallStatus": "RECRUITING"},
                    "contactsLocationsModule": {"locations": []}
                }
            }
        ]
    }
    
    result = parse_batch_response(data)
    
    assert len(result) == 2
    assert "NCT12345" in result
    assert "NCT67890" in result

