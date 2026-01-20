#!/usr/bin/env python3
"""
VUS Endpoint Test Script

Tests the /api/vus/identify endpoint with real requests.
Validates VUS identification and resolution functionality.

Deliverable: VUS Endpoint Testing (Item 2)
"""

import pytest
import asyncio
import httpx
import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

API_BASE_URL = "http://127.0.0.1:8000"
TIMEOUT = 60.0


# Test Cases
VUS_TEST_CASES = [
    {
        "name": "PDGFRA c.2263T>C (HGVS coding)",
        "variant": {
            "hgvs_c": "PDGFRA:c.2263T>C",
            "assembly": "GRCh38"
        },
        "expected": {
            "has_resolution": True,
            "has_priors": True,
            "has_sequence_signal": True,
            "has_insights": True
        }
    },
    {
        "name": "BRAF p.V600E (HGVS protein)",
        "variant": {
            "hgvs_p": "p.V600E",
            "gene": "BRAF",
            "assembly": "GRCh38"
        },
        "expected": {
            "has_resolution": True,
            "has_priors": True,
            "has_sequence_signal": True
        }
    },
    {
        "name": "TP53 GRCh38 coordinates",
        "variant": {
            "chrom": "17",
            "pos": 7673802,
            "ref": "G",
            "alt": "A",
            "assembly": "GRCh38"
        },
        "expected": {
            "has_resolution": True,
            "has_priors": True,
            "has_sequence_signal": True
        }
    }
]


async def call_vus_identify(
    client: httpx.AsyncClient,
    variant: Dict[str, Any],
    options: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Call /api/vus/identify endpoint."""
    url = f"{API_BASE_URL}/api/vus/identify"
    
    payload = {
        "variant": variant,
        "options": options or {}
    }
    
    try:
        response = await client.post(url, json=payload, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error: {e.response.status_code} - {e.response.text}")
        return None
    except Exception as e:
        print(f"❌ Error calling API: {e}")
        return None


def validate_vus_response(response: Dict[str, Any], test_case: Dict[str, Any]) -> Dict[str, Any]:
    """Validate VUS response structure."""
    results = {
        "has_resolution": False,
        "has_priors": False,
        "has_sequence_signal": False,
        "has_insights": False,
        "has_next_actions": False,
        "errors": []
    }
    
    expected = test_case["expected"]
    
    # Check resolution
    if "resolution" in response:
        resolution = response["resolution"]
        if "grch38" in resolution and resolution["grch38"].get("chrom"):
            results["has_resolution"] = True
        else:
            results["errors"].append("Resolution missing GRCh38 coordinates")
    else:
        results["errors"].append("Missing 'resolution' field")
    
    # Check priors (ClinVar proxy)
    if "priors" in response:
        priors = response["priors"]
        if isinstance(priors, dict) and len(priors) > 0:
            results["has_priors"] = True
        else:
            results["errors"].append("Priors field exists but is empty")
    else:
        results["errors"].append("Missing 'priors' field")
    
    # Check sequence signal (Evo2 delta)
    if "sequence_signal" in response:
        seq_signal = response["sequence_signal"]
        if isinstance(seq_signal, dict) and "delta" in seq_signal:
            results["has_sequence_signal"] = True
        else:
            results["errors"].append("Sequence signal missing delta score")
    else:
        results["errors"].append("Missing 'sequence_signal' field")
    
    # Check insights bundle
    if "insights" in response:
        insights = response["insights"]
        if isinstance(insights, dict) and len(insights) > 0:
            results["has_insights"] = True
        else:
            results["errors"].append("Insights field exists but is empty")
    else:
        if expected.get("has_insights", False):
            results["errors"].append("Missing 'insights' field (expected)")
    
    # Check next actions
    if "next_actions" in response:
        next_actions = response["next_actions"]
        if isinstance(next_actions, list) and len(next_actions) > 0:
            results["has_next_actions"] = True
        else:
            results["errors"].append("Next actions field exists but is empty")
    else:
        results["errors"].append("Missing 'next_actions' field")
    
    return results


@pytest.mark.asyncio
async def test_vus_endpoint_basic():
    """Test basic VUS endpoint functionality."""
    async with httpx.AsyncClient() as client:
        test_case = VUS_TEST_CASES[0]
        print(f"\nTesting: {test_case['name']}")
        
        response = await call_vus_identify(client, test_case["variant"])
        
        assert response is not None, "API call should succeed"
        
        validation = validate_vus_response(response, test_case)
        
        assert validation["has_resolution"], "Should have resolution"
        assert validation["has_priors"], "Should have priors"
        assert validation["has_sequence_signal"], "Should have sequence signal"
        assert validation["has_next_actions"], "Should have next actions"
        
        print(f"✅ VUS endpoint test passed")
        print(f"   Resolution: {validation['has_resolution']}")
        print(f"   Priors: {validation['has_priors']}")
        print(f"   Sequence Signal: {validation['has_sequence_signal']}")
        print(f"   Next Actions: {validation['has_next_actions']}")


@pytest.mark.asyncio
async def test_vus_endpoint_all_cases():
    """Test all VUS test cases."""
    async with httpx.AsyncClient() as client:
        results = []
        
        for test_case in VUS_TEST_CASES:
            print(f"\n{'='*60}")
            print(f"Testing: {test_case['name']}")
            print(f"{'='*60}")
            
            response = await call_vus_identify(client, test_case["variant"])
            
            if response is None:
                results.append({
                    "test_case": test_case["name"],
                    "status": "FAILED",
                    "error": "API call failed"
                })
                continue
            
            validation = validate_vus_response(response, test_case)
            
            # Check if all expected fields are present
            all_passed = all([
                validation["has_resolution"] == test_case["expected"].get("has_resolution", True),
                validation["has_priors"] == test_case["expected"].get("has_priors", True),
                validation["has_sequence_signal"] == test_case["expected"].get("has_sequence_signal", True)
            ])
            
            status = "PASSED" if all_passed else "FAILED"
            results.append({
                "test_case": test_case["name"],
                "status": status,
                "validation": validation
            })
            
            print(f"Status: {status}")
            if validation["errors"]:
                print("Errors:")
                for error in validation["errors"]:
                    print(f"  - {error}")
        
        # Summary
        passed = sum(1 for r in results if r["status"] == "PASSED")
        failed = sum(1 for r in results if r["status"] == "FAILED")
        
        print(f"\n{'='*60}")
        print(f"VUS Endpoint Test Summary")
        print(f"{'='*60}")
        print(f"Total: {len(results)}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        
        assert failed == 0, f"{failed} test cases failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])













