"""
Tests for trial refresh filter module.
"""
import pytest
from api.services.trial_refresh.filters import filter_locations_by_state, filter_recruiting_trials


def test_location_filtering_by_state(mock_trial_data):
    """Test extracting locations with contact info and state filtering"""
    filtered = filter_locations_by_state(mock_trial_data, "NY")
    
    assert "NCT12345" in filtered
    assert len(filtered["NCT12345"]["locations"]) == 1
    assert filtered["NCT12345"]["locations"][0]["state"] == "NY"
    assert filtered["NCT12345"]["locations"][0]["facility"] == "Memorial Sloan Kettering"


def test_location_filtering_by_state_no_match(mock_trial_data):
    """Test filtering by state with no matching locations"""
    filtered = filter_locations_by_state(mock_trial_data, "TX")
    
    # Trial should be excluded if no locations match
    assert "NCT12345" not in filtered
    assert len(filtered) == 0


def test_filter_recruiting_trials(mock_trial_data):
    """Test filtering to only recruiting trials"""
    # Add a non-recruiting trial
    mixed_data = {
        **mock_trial_data,
        "NCT99999": {
            "status": "COMPLETED",
            "locations": [],
            "last_updated": "2024-10-20T12:00:00Z"
        }
    }
    
    filtered = filter_recruiting_trials(mixed_data)
    
    assert "NCT12345" in filtered
    assert "NCT99999" not in filtered  # Non-recruiting trial excluded


def test_filter_recruiting_trials_all_included(mock_trial_data):
    """Test filtering when all trials are recruiting"""
    filtered = filter_recruiting_trials(mock_trial_data)
    
    # All should be included
    assert len(filtered) == len(mock_trial_data)
    assert "NCT12345" in filtered

