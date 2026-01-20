#!/usr/bin/env python3
"""Create mock response cache from existing benchmark results."""
import json
from pathlib import Path

def create_mock_cache():
    """Extract 10 cases from existing results to create cache."""
    results_file = Path("results/benchmark_efficacy_20251203_210907.json")
    
    if not results_file.exists():
        print(f"❌ Results file not found: {results_file}")
        return
    
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    # Extract predictions for each case
    cache = {}
    for result in data.get("results", []):
        case_id = result.get("case_id")
        full_prediction = result.get("full_prediction", {})
        
        if case_id and full_prediction:
            cache[case_id] = full_prediction
    
    # Save cache
    cache_dir = Path("cache")
    cache_dir.mkdir(exist_ok=True)
    
    cache_file = cache_dir / "mock_responses.json"
    with open(cache_file, 'w') as f:
        json.dump(cache, f, indent=2)
    
    print(f"✅ Created mock cache with {len(cache)} responses")
    print(f"   - Saved to {cache_file}")
    print(f"   - Cases: {', '.join(sorted(cache.keys()))}")

if __name__ == "__main__":
    create_mock_cache()
