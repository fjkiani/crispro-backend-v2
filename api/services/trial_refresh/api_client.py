"""
Trial Refresh Service - API Client Module

Core async functions for fetching live trial status and locations from ClinicalTrials.gov API v2.
"""

import asyncio
import logging
from typing import List, Dict, Any

import httpx

from .config import (
    CLINICAL_TRIALS_API_URL,
    DEFAULT_TIMEOUT,
    MAX_RETRIES,
    RETRY_BACKOFF_BASE,
    REQUESTED_FIELDS
)
from .parser import parse_batch_response

logger = logging.getLogger(__name__)


async def refresh_trial_status(nct_ids: List[str]) -> Dict[str, Dict[str, Any]]:
    """
    Fetch ONLY recruiting status + locations for a list of NCT IDs.
    
    Args:
        nct_ids: List of ClinicalTrials.gov NCT identifiers
        
    Returns:
        Dict mapping NCT ID to {status, locations, last_updated}
        
    Example:
        {
            "NCT12345": {
                "status": "RECRUITING",
                "locations": [
                    {
                        "facility": "Memorial Sloan Kettering",
                        "city": "New York",
                        "state": "NY",
                        "status": "recruiting",
                        "contact_name": "Dr. Smith",
                        "contact_phone": "212-639-XXXX",
                        "contact_email": "smith@mskcc.org"
                    }
                ],
                "last_updated": "2024-10-20T12:00:00Z"
            }
        }
    """
    if not nct_ids:
        return {}
    
    # ⚔️ CRITICAL FIX: Validate and clean NCT IDs before API call
    # Remove None, empty strings, whitespace, and invalid formats
    from .config import MAX_NCT_IDS_PER_REQUEST
    
    clean_nct_ids = []
    for nct_id in nct_ids:
        if not nct_id:
            continue
        nct_id = str(nct_id).strip().upper()
        # Basic validation: NCT ID should start with "NCT" and have at least 8 characters
        if nct_id.startswith("NCT") and len(nct_id) >= 8:
            clean_nct_ids.append(nct_id)
        else:
            logger.warning(f"Invalid NCT ID format: {nct_id} (skipping)")
    
    if not clean_nct_ids:
        logger.warning("No valid NCT IDs after cleaning")
        return {}
    
    # Enforce batch size limit
    if len(clean_nct_ids) > MAX_NCT_IDS_PER_REQUEST:
        logger.warning(
            f"Batch size {len(clean_nct_ids)} exceeds limit {MAX_NCT_IDS_PER_REQUEST}. "
            f"Truncating to first {MAX_NCT_IDS_PER_REQUEST}."
        )
        clean_nct_ids = clean_nct_ids[:MAX_NCT_IDS_PER_REQUEST]
    
    # Build API request parameters
    nct_filter = ",".join(clean_nct_ids)
    
    # ⚔️ FIX: Ensure URL length is reasonable (CT.gov may reject very long URLs)
    # If the filter string is too long, split into smaller batches
    if len(nct_filter) > 5000:  # Conservative limit (most NCT IDs are ~11 chars)
        logger.warning(
            f"Query string too long ({len(nct_filter)} chars). "
            f"Splitting into smaller batches."
        )
        # Split into smaller chunks (avoid recursion by using helper)
        results = {}
        chunk_size = 50  # Smaller chunks for long queries
        for i in range(0, len(clean_nct_ids), chunk_size):
            chunk = clean_nct_ids[i:i+chunk_size]
            # Build params for chunk directly (avoid recursion)
            chunk_filter = ",".join(chunk)
            chunk_params = {
                "query.id": chunk_filter,
                "fields": REQUESTED_FIELDS,
                "format": "json",
                "pageSize": len(chunk)
            }
            try:
                async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
                    chunk_response = await client.get(CLINICAL_TRIALS_API_URL, params=chunk_params)
                    chunk_response.raise_for_status()
                    chunk_data = chunk_response.json()
                    chunk_results = parse_batch_response(chunk_data)
                    results.update(chunk_results)
                    logger.info(f"   Refreshed chunk {i//chunk_size + 1}: {len(chunk_results)}/{len(chunk)} trials")
            except Exception as e:
                logger.error(f"   Chunk {i//chunk_size + 1} failed: {e}")
        return results
    
    params = {
        "query.id": nct_filter,
        "fields": REQUESTED_FIELDS,
        "format": "json",
        "pageSize": min(len(clean_nct_ids), MAX_NCT_IDS_PER_REQUEST)
    }
    
    try:
        async with httpx.AsyncClient(timeout=DEFAULT_TIMEOUT) as client:
            response = await client.get(CLINICAL_TRIALS_API_URL, params=params)
            
            # ⚔️ CRITICAL FIX: Log detailed error for 400 Bad Request
            if response.status_code == 400:
                error_detail = response.text[:500]  # First 500 chars of error
                logger.error(
                    f"CT.gov API 400 Bad Request for {len(clean_nct_ids)} NCT IDs. "
                    f"Error: {error_detail}. "
                    f"Query preview: {nct_filter[:100]}..."
                )
                # Try with single NCT ID to see if it's a format issue
                if len(clean_nct_ids) > 1:
                    logger.info(f"Retrying with first NCT ID only: {clean_nct_ids[0]}")
                    single_result = await refresh_trial_status([clean_nct_ids[0]])
                    if single_result:
                        logger.info(f"Single NCT ID works. Likely batch size or format issue.")
                
                response.raise_for_status()
            
            response.raise_for_status()
            data = response.json()
            
            # Parse response
            results = parse_batch_response(data)
            
            logger.info(f"Refreshed status for {len(results)}/{len(nct_ids)} trials")
            
            return results
            
    except httpx.RequestError as e:
        logger.error(f"API request failed: {e}")
        return {}
    except httpx.HTTPStatusError as e:
        logger.error(f"API returned error status {e.response.status_code}: {e}")
        return {}
    except Exception as e:
        logger.error(f"Unexpected error during refresh: {e}", exc_info=True)
        return {}


async def refresh_trial_status_with_retry(
    nct_ids: List[str], 
    max_retries: int = MAX_RETRIES
) -> Dict[str, Dict[str, Any]]:
    """
    Wrapper with retry logic for transient API failures.
    
    Args:
        nct_ids: List of NCT IDs to refresh
        max_retries: Maximum retry attempts (default from config)
        
    Returns:
        Dict of refreshed trial data (may be empty on total failure)
    """
    for attempt in range(max_retries):
        try:
            result = await refresh_trial_status(nct_ids)
            
            # If we got results (even partial), return them
            if result:
                return result
            
            # If no results and not last attempt, retry
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(
                    f"Retry {attempt + 1}/{max_retries} after {wait_time}s: "
                    f"No results returned for {len(nct_ids)} NCT IDs"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed: No results for {len(nct_ids)} NCT IDs")
                
        except Exception as e:
            if attempt < max_retries - 1:
                wait_time = RETRY_BACKOFF_BASE ** attempt
                logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s: {e}")
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed: {e}")
                return {}
    
    return {}

