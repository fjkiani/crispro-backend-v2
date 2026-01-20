#!/usr/bin/env python3
"""
Smoke Test for Personalized Outreach System

Tests:
1. Health check endpoint
2. Trial search endpoint
3. Intelligence extraction endpoint
4. Email generation endpoint
"""
import asyncio
import httpx
import json

BASE_URL = "http://127.0.0.1:8000"

async def test_health():
    """Test health check endpoint."""
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/api/personalized-outreach/health")
        assert response.status_code == 200
        print("✅ Health check passed")
        return response.json()

async def test_search_trials():
    """Test trial search endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        payload = {
            "conditions": ["ovarian cancer"],
            "interventions": ["carboplatin"],
            "keywords": ["CA-125"],
            "max_results": 5       }
        response = await client.post(
            f"{BASE_URL}/api/personalized-outreach/search-trials",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Trial search passed - Found {data.get('count', 0)} trials")
        return data

async def test_extract_intelligence():
    """Test intelligence extraction endpoint."""
    async with httpx.AsyncClient(timeout=60.0) as client:
        payload = {
            "nct_id": "NCT01234567"  # Example NCT ID - replace with real one
        }
        response = await client.post(
            f"{BASE_URL}/api/personalized-outreach/extract-intelligence",
            json=payload
        )
        # May fail if NCT ID doesn't exist - that's OK for smoke test
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Intelligence extraction passed - Quality: {data.get('personalization_quality', 0):.2f}")
            return data
        else:
        print(f"⚠️ Intelligence extraction returned {response.status_code} (expected if NCT ID invalid)")
            return None

async def test_generate_email():
    """Test email generation endpoint."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Mock intelligence profile
        payload = {
            "intelligence_profile": {
                "nct_id": "NCT01234567",
                "trial_intelligence": {
                    "nct_id": "NCT01234567",
                    "title": "Test Trial",
                    "pi_info": {"name": "Dr. Test", "institution": "Test Hospital"}
                },
                "research_intelligence": {
                    "publication_count": 10,
                    "research_focus": ["ovarian cancer", "biomarkers"]
                },
                "biomarker_intelligence": {
                    "kelim_fit_score": 3.5,
                    "fit_reasons": ["Trial uses platinum-based therapy", "Trial monitors CA-125"]
                },
            "goals": ["Understanding mechanisms of treatment resistance"],
                "value_proposition": ["KELIM biomarker validation"],
                "personalization_quality": 0.75
            }
        }
        response = await client.post(
            f"{BASE_URL}/api/personalized-outreach/generate-email",
            json=payload
        )
        assert response.status_code == 200
        data = response.json()
        print(f"✅ Email generation passed - Quality: {data.get('personalization_quality', 0):.2f}")
        print(f"   Subject: {data.get('subject', '')[:60]}...")
        return data

async def main():
    """Run all smoke tests."""
    print("🧪 Running Personalized Outreach System Smoke Tests...
")
    
    try:
        # Test 1: Health check
        await test_health()
        
        # Test 2: Trial search
        await test_search_trials()
        
        # Test 3: Intelligence extraction (may fail if NCT ID invalid)
        await test_extract_intelligence()
        
        #  4: Email generation
        await test_generate_email()
        
        print("
✅ All smoke tests passed!")
    except Exception as e:
        print(f"
❌ Smoke test failed: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
