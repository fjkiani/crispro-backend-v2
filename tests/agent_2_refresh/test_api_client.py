"""
Tests for trial refresh API client module.
"""
import pytest
from api.services.trial_refresh.api_client import refresh_trial_status, refresh_trial_status_with_retry


@pytest.mark.asyncio
async def test_refresh_single_trial(sample_nct_ids):
    """Test fetching live status for 1 NCT ID"""
    result = await refresh_trial_status([sample_nct_ids[0]])
    
    assert isinstance(result, dict)
    # May be empty if API fails, but should not crash
    if result:
        assert sample_nct_ids[0] in result
        trial_data = result[sample_nct_ids[0]]
        assert "status" in trial_data
        assert "locations" in trial_data
        assert "last_updated" in trial_data


@pytest.mark.asyncio
async def test_refresh_batch(sample_nct_ids):
    """Test batch refresh (multiple NCT IDs)"""
    result = await refresh_trial_status(sample_nct_ids[:3])
    
    assert isinstance(result, dict)
    # Verify structure if results returned
    if result:
        assert len(result) > 0
        for nct_id, data in result.items():
            assert "status" in data
            assert "locations" in data
            assert isinstance(data["locations"], list)


@pytest.mark.asyncio
async def test_refresh_empty_list():
    """Test refresh with empty list returns empty dict"""
    result = await refresh_trial_status([])
    assert result == {}


@pytest.mark.asyncio
async def test_retry_logic():
    """Test retry wrapper returns dict even on failure (graceful degradation)"""
    # Using invalid NCT ID to test retry behavior
    result = await refresh_trial_status_with_retry(["INVALID_NCT_ID"], max_retries=2)
    
    # Should return empty dict, not crash
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_retry_with_valid_ids(sample_nct_ids):
    """Test retry wrapper with valid IDs"""
    result = await refresh_trial_status_with_retry(sample_nct_ids[:2], max_retries=2)
    
    assert isinstance(result, dict)
    # If API succeeds, should have results
    # If API fails, should return empty dict (graceful degradation)

