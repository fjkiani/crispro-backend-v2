#!/usr/bin/env python3
"""Expanded benchmark runner for 100-case dataset using cache."""
import json
from pathlib import Path

def load_cache(cache_file=Path("cache/mock_responses.json")):
    if cache_file.exists():
        with open(cache_file, 'r') as f:
            return json.load(f)
    return {}

def evaluate_prediction(case, prediction):
    gt = case.get("ground_truth", {})
    drugs = prediction.get("drugs", [])
    if drugs:
        top_drug = max(drugs, key=lambda d: float(d.get("confidence", 0)))
        top_drug_name = top_drug.get("name", "").lower()
    else:
        top_drug_name = ""
    effective_drugs_gt = [d.lower() for d in gt.get("effective_drugs", [])]
    correct = top_drug_name in effective_drugs_gt if effective_drugs_gt else False
    return {"case_id": case.get("case_id"), "correct": correct, "top_drug": top_drug_name}

def run_expanded_benchmark(test_file="test_cases_100.json", use_cache=True):
    print("=" * 60)
    print("Expanded Benchmark Runner (100 Cases)")
    print("=" * 60)
    with open(test_file, 'r') as f:
        test_cases = json.load(f)
    print(f"Loaded {len(test_cases)} test cases")
    cache = load_cache() if use_cache else {}
    print(f"Cache loaded: {len(cache)} responses available")
    results = []
    correct_count = 0
    for case in test_cases:
        case_id = case.get("case_id")
        prediction = cache.get(case_id, {"drugs": [], "confidence": 0.0, "source": "placeholder"})
        eval_result = evaluate_prediction(case, prediction)
        results.append({"case": case, "prediction": prediction, "evaluation": eval_result})
        if eval_result["correct"]:
            correct_count += 1
    accuracy = correct_count / len(test_cases) if test_cases else 0.0
    summary = {"total_cases": len(test_cases), "correct": correct_count, "accuracy": accuracy, "cache_used": use_cache}
    print(f"\n📊 Results: Total: {len(test_cases)}, Correct: {correct_count}, Accuracy: {accuracy:.1%}")
    output = {"summary": summary, "predictions": [{"case_id": r["evaluation"]["case_id"], "correct": r["evaluation"]["correct"]} for r in results]}
    output_file = Path("results/benchmark_100_cached.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"✅ Results saved to {output_file}")
    return output

if __name__ == "__main__":
    import sys
    test_file = sys.argv[1] if len(sys.argv) > 1 else "test_cases_100.json"
    run_expanded_benchmark(test_file, use_cache=True)
