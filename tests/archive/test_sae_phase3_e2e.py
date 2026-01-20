#!/usr/bin/env python3
"""
E2E Test for SAE Phase 3 Frontend Integration

Tests the complete flow:
1. Backend /api/ayesha/complete_care_v2 endpoint
2. Response structure validation
3. SAE Phase 3 services (next_test_recommender, hint_tiles, mechanism_map)
4. Data format compatibility with frontend components

Usage:
    python test_sae_phase3_e2e.py
"""

import asyncio
import httpx
import json
from pathlib import Path
from typing import Dict, Any

API_ROOT = "http://localhost:8000"

# Ayesha's default profile (pre-NGS)
AYESHA_PROFILE = {
    "ca125_value": 2842.0,
    "stage": "IVB",
    "germline_status": "negative",
    "treatment_line": "first-line",  # String, not int
    "location_state": "NY",  # State code, not city
    "tumor_context": None,  # Pre-NGS
    "include_trials": True,
    "include_soc": True,
    "include_ca125": True,
    "include_wiwfm": True,
    "include_food": False,
    "include_resistance": False,
    "max_trials": 10
}


async def test_complete_care_v2():
    """Test the unified complete_care_v2 endpoint"""
    print("⚔️ E2E TEST: SAE Phase 3 Frontend Integration\n")
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Health check
        print("1. Health Check...")
        try:
            health_response = await client.get(f"{API_ROOT}/api/ayesha/complete_care_v2/health")
            if health_response.status_code == 200:
                print(f"   ✅ Health check passed: {health_response.json()['status']}")
            else:
                print(f"   ⚠️ Health check returned {health_response.status_code}")
        except Exception as e:
            print(f"   ❌ Health check failed: {e}")
            return False
        
        # 2. Call complete_care_v2
        print("\n2. Calling /api/ayesha/complete_care_v2...")
        try:
            response = await client.post(
                f"{API_ROOT}/api/ayesha/complete_care_v2",
                json=AYESHA_PROFILE,
                headers={"Content-Type": "application/json"}
            )
            
            if response.status_code != 200:
                print(f"   ❌ Request failed: {response.status_code}")
                print(f"   Response: {response.text[:500]}")
                return False
            
            data = response.json()
            print(f"   ✅ Response received (status: {response.status_code})")
            
        except Exception as e:
            print(f"   ❌ Request failed: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # 3. Validate response structure
        print("\n3. Validating Response Structure...")
        required_keys = [
            "trials",
            "soc_recommendation",
            "ca125_intelligence",
            "next_test_recommender",
            "hint_tiles",
            "mechanism_map",
            "summary",
            "provenance"
        ]
        
        missing_keys = [key for key in required_keys if key not in data]
        if missing_keys:
            print(f"   ❌ Missing keys: {missing_keys}")
            return False
        else:
            print(f"   ✅ All required keys present")
        
        # 4. Validate SAE Phase 3 Services
        print("\n4. Validating SAE Phase 3 Services...")
        
        # 4a. Next Test Recommender
        next_test = data.get("next_test_recommender")
        if not next_test:
            print("   ❌ next_test_recommender is None")
            return False
        if "recommendations" not in next_test:
            print("   ❌ next_test_recommender missing 'recommendations' key")
            return False
        recommendations = next_test.get("recommendations", [])
        if not isinstance(recommendations, list):
            print("   ❌ recommendations is not a list")
            return False
        print(f"   ✅ Next Test Recommender: {len(recommendations)} recommendations")
        if recommendations:
            rec = recommendations[0]
            required_rec_keys = ["test_name", "priority", "urgency", "rationale"]
            missing_rec_keys = [k for k in required_rec_keys if k not in rec]
            if missing_rec_keys:
                print(f"   ⚠️ Recommendation missing keys: {missing_rec_keys}")
            else:
                print(f"      First: {rec.get('test_name')} (Priority {rec.get('priority')}, {rec.get('urgency')} urgency)")
        
        # 4b. Hint Tiles
        hint_tiles = data.get("hint_tiles")
        if not hint_tiles:
            print("   ❌ hint_tiles is None")
            return False
        if "hint_tiles" not in hint_tiles:
            print("   ❌ hint_tiles missing nested 'hint_tiles' key")
            return False
        tiles_list = hint_tiles.get("hint_tiles", [])
        if not isinstance(tiles_list, list):
            print("   ❌ hint_tiles.hint_tiles is not a list")
            return False
        print(f"   ✅ Hint Tiles: {len(tiles_list)} tiles")
        if tiles_list:
            tile = tiles_list[0]
            required_tile_keys = ["category", "title", "message"]
            missing_tile_keys = [k for k in required_tile_keys if k not in tile]
            if missing_tile_keys:
                print(f"   ⚠️ Tile missing keys: {missing_tile_keys}")
            else:
                print(f"      First: {tile.get('title')} ({tile.get('category')})")
        
        # 4c. Mechanism Map
        mechanism_map = data.get("mechanism_map")
        if not mechanism_map:
            print("   ❌ mechanism_map is None")
            return False
        if "chips" not in mechanism_map:
            print("   ❌ mechanism_map missing 'chips' key")
            return False
        chips = mechanism_map.get("chips", [])
        if not isinstance(chips, list):
            print("   ❌ mechanism_map.chips is not a list")
            return False
        print(f"   ✅ Mechanism Map: {len(chips)} chips (status: {mechanism_map.get('status', 'unknown')})")
        if chips:
            chip = chips[0]
            required_chip_keys = ["pathway", "burden", "color", "label", "status"]
            missing_chip_keys = [k for k in required_chip_keys if k not in chip]
            if missing_chip_keys:
                print(f"   ⚠️ Chip missing keys: {missing_chip_keys}")
            else:
                print(f"      First: {chip.get('pathway')} ({chip.get('label')}, {chip.get('status')})")
        
        # 5. Validate Frontend Compatibility
        print("\n5. Validating Frontend Compatibility...")
        
        # Check trials structure (nested)
        trials_data = data.get("trials")
        if trials_data and isinstance(trials_data, dict):
            trials_list = trials_data.get("trials", [])
            if isinstance(trials_list, list):
                print(f"   ✅ Trials: {len(trials_list)} trials (nested structure)")
            else:
                print("   ⚠️ Trials structure unexpected")
        else:
            print("   ⚠️ Trials data missing or unexpected format")
        
        # 6. Save response for inspection
        output_file = Path(".cursor/ayesha/test_trials/e2e_response_sae_phase3.json")
        output_file.parent.mkdir(parents=True, exist_ok=True)
        with open(output_file, 'w') as f:
            json.dump(data, f, indent=2)
        print(f"\n6. Response saved to: {output_file}")
        
        # 7. Summary
        print("\n✅ E2E TEST COMPLETE!")
        print(f"\nSummary:")
        print(f"   - Next Test Recommender: {len(recommendations)} recommendations")
        print(f"   - Hint Tiles: {len(tiles_list)} tiles")
        print(f"   - Mechanism Map: {len(chips)} chips")
        print(f"   - Trials: {len(trials_list) if trials_data and isinstance(trials_data, dict) else 0} trials")
        print(f"   - SOC Recommendation: {'✅' if data.get('soc_recommendation') else '❌'}")
        print(f"   - CA-125 Intelligence: {'✅' if data.get('ca125_intelligence') else '❌'}")
        print(f"   - Provenance: {'✅' if data.get('provenance') else '❌'}")
        
        return True


async def main():
    """Main test runner"""
    success = await test_complete_care_v2()
    
    if success:
        print("\n🎯 ALL TESTS PASSED - Frontend integration ready!")
        print("\nNext Steps:")
        print("   1. Start frontend: cd oncology-frontend && npm run dev")
        print("   2. Navigate to: http://localhost:5173/ayesha-trials")
        print("   3. Verify all 3 SAE components render correctly")
        print("   4. Check browser console for any errors")
    else:
        print("\n❌ TESTS FAILED - Check backend logs and fix issues")
        return 1
    
    return 0


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    exit(exit_code)

