#!/usr/bin/env python3
"""
End-to-End Test for Personalized Outreach System

Tests the complete workflow:
1. Search trials
2. Extract intelligence
3. Generate email
4. Validate output quality

Usage:
    python test_personalized_outreach_e2e.py
"""

import asyncio
import sys
import os
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(project_root))

import httpx
from typing import Dict, Any

API_ROOT = os.getenv("API_ROOT", "http://localhost:8000")


async def test_search_trials() -> Dict[str, Any]:
    """Test trial search endpoint."""
    print("\n🔍 Step 1: Testing Trial Search...")

    async with httpx.AsyncClit(timeout=30.0) as client:
        response = await client.post(
            f"{API_ROOT}/api/personalized-outreach/search-trials",
            json={
                "conditions": ["ovarian cancer"],
                "interventions": ["platinum-based therapy"],
                "keywords": ["CA-125 monitoring", "resistance"],
                "phases": ["PHASE1", "PHASE2", "PHASE3"],
                "status": ["RECRUITING"],
                "max_results": 5
            }
        )
        response.raise_for_status()
        data = response.json()
        print(f"✅ Search successful. Found {data.get('count', 0)} trials.")
        assert data.get("count", 0) > 0, "Expected to find trials, but found 0."
        return data["trials"][0]  # Return the first trial for further steps


async def test_extract_intelligence(nct_id: str) -> Dict[str, Any]:
    """Test intelligence extraction endpoint."""
    print(f"\n🧠 Step 2: Extracting Intelligence for NCT ID: {nct_id}...")

    async with httpx.AsyncClient(timeo0.0) as client:  # Increased timeout for intelligence extraction
        response = await client.post(
            f"{API_ROOT}/api/personalized-outreach/extract-intelligence",
            json={"nct_id": nct_id}
        )
        response.raise_for_status()
        data = response.json()
        print(f"✅ Intelligence extraction successful for {nct_id}.")
        assert "pi_info" in data, "Expected 'pi_info' in intelligence data."
        assert "research_focus" in data.get("research_intelligence", {}), "Expected 'research_focus' in research intelligence."
        return data


async def test_generate_email(intelligence_profile: Dict[str, Any]) -> Dict[str, Any]:
    """Test email generation endpoint."""
    print("\n✉️ Step 3: Generating Personalized Email...")

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(
            f"{API_ROOT}/api/personalized-outreach/generate-email",
            json={
                "intelligence_profile": intelligence_profi              "outreach_config": {
                    "sender_name": "Fahad Kiani",
                    "sender_title": "CEO, CrisPRO",
                    "company_name": "CrisPRO",
                    "value_proposition_keywords": ["KELIM", "platinum resistance", "biomarker validation"]
                }
            }
        )
        response.raise_for_status()
        data = response.json()
        print("✅ Email generation successful.")
        assert "subject" in data, "Expected 'subject' in email response."
        assert "body" in data, "Expected 'body' in email response."
        print(f"Subject: {data['subject']}")
        print(f"Body: {data['body'][:500]}...")  # Print first 500 chars of body
        return data


async def main():
    print("🚀 Starting End-to-End Personalized Outreach System Test...")
    try:
        # Step 1: Search trials
        first_trial = await test_search_trials()
        nct_id = first_trial["nct_id"]
        pi_name = first_trial.get("pi_info", {}).get("name",A")
        institution = first_trial.get("locations", [{}])[0].get("facility", "N/A")

        # Step 2: Extract intelligence
        intelligence_profile = await test_extract_intelligence(nct_id)

        # Step 3: Generate email
        await test_generate_email(intelligence_profile)

        print("\n🎉 End-to-End Test Completed Successfully!")

    except httpx.HTTPStatusError as e:
        print(f"❌ HTTP Error during test: {e.response.status_code} - {e.response.text}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ An unexpected error occurred: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
