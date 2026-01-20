#!/usr/bin/env python3
"""
CORRECT Synthetic Lethality Benchmark
Uses /api/efficacy/predict which ACTUALLY calls Evo2

This benchmark properly tests:
- Evo2 sequence disruption scoring
- Pathway aggregation
- Evidence integration
- Drug ranking algorithms
"""
import asyncio
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx
import numpy as np

API_ROOT = "http://127.0.0.1:8000"

# Known effective drug classes for synthetic lethality
SL_DRUG_CLASSES = {
    "BRCA1": ["parp", "platinum"],
    "BRCA2": ["parp", "platinum"],
    "ATM": ["parp", "atr"],
    "ATR": ["wee1", "parp"],
    "MBD4": ["parp", "platinum"],
    "TP53": ["atr", "wee1", "cdk"],
}

async def predict_efficacy(client: httpx.AsyncClient, case: Dict[str, Any]) -> Dict[str, Any]:
    """Call efficacy API - this ACTUALLY uses Evo2."""
    try:
        payload = {
            "model_id": "evo2_7b",  # Explicitly request Evo2
            "mutations": case["mutations"],
            "disease": case.get("disease", "ovarian_cancer"),
            "options": {
                "adaptive": True,
                "ensemble": False,
                "ablation_mode": "SPE",  # Full S/P/E pipeline
            },
            "api_base": API_ROOT,
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/efficacy/predict",
            json=payload,
            timeout=180.0  # Longer timeout for Evo2
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Error for case {case.get('case_id')}: {e}")
        return None

def evaluate_prediction(case: Dict, prediction: Dict) -> Dict:
    """Evaluate efficacy prediction against ground truth."""
    gt = case.get("ground_truth", {})
    metrics = {}
    
    # Get predicted drugs
    drugs = prediction.get("drugs", [])
    
    if not drugs:
        return {
            "drug_match": False,
            "top_drug": None,
            "confidence": 0.0,
            "evo2_used": False,
            "sequence_score": None,
            "pathway_score": None,
        }
    
    # Get top drug
    top_drug = max(drugs, key=lambda d: float(d.get("confidence", 0)))
    top_name = (top_drug.get("name") or "").lower()
    top_moa = (top_drug.get("moa") or "").lower()
    
    # Check if Evo2 was actually used
    insights = top_drug.get("insights", {})
    provenance = prediction.get("provenance", {})
    evo2_used = (
        "evo2" in str(provenance).lower() or
        "evo" in str(insights.get("model_id", "")).lower() or
        insights.get("sequence_score") is not None
    )
    
    # Extract scores
    sequence_score = insights.get("sequence_score") or insights.get("functionality")
    pathway_score = insights.get("pathway_score") or insights.get("pathway_disruption")
    
    # Check drug match against ground truth
    effective_drugs = [d.lower() for d in gt.get("effective_drugs", [])]
    sl_pairs = gt.get("known_sl_pairs", [])
    
    drug_match = False
    
    # Check direct drug name match
    for eff_drug in effective_drugs:
        if eff_drug in top_name or top_name in eff_drug:
            drug_match = True
            break
    
    # Check MoA match (e.g., "parp inhibitor" matches "parp")
    for eff_drug in effective_drugs:
        drug_lower = eff_drug.lower()
        if "parp" in drug_lower and "parp" in top_moa:
            drug_match = True
        if "platinum" in drug_lower and "platinum" in top_name:
            drug_match = True
        if "atr" in drug_lower and "atr" in top_moa:
            drug_match = True
    
    # For DDR genes, both platinum and PARP are valid
    genes = [m.get("gene", "").upper() for m in case.get("mutations", [])]
    ddr_genes = {"BRCA1", "BRCA2", "ATM", "ATR", "CHEK2", "MBD4"}
    if any(g in ddr_genes for g in genes):
        if "parp" in top_moa or "platinum" in top_name:
            drug_match = True
    
    metrics = {
        "drug_match": drug_match,
        "top_drug": top_drug.get("name"),
        "top_drug_moa": top_drug.get("moa"),
        "confidence": float(top_drug.get("confidence", 0)),
        "efficacy_score": float(top_drug.get("efficacy_score", 0)),
        "evo2_used": evo2_used,
        "sequence_score": float(sequence_score) if sequence_score else None,
        "pathway_score": float(pathway_score) if pathway_score else None,
        "num_drugs_returned": len(drugs),
    }
    
    return metrics

async def run_benchmark(test_file: str, max_concurrent: int = 3):
    """Run benchmark using efficacy endpoint."""
    print("=" * 70)
    print("🧬 SYNTHETIC LETHALITY BENCHMARK (via /api/efficacy/predict)")
    print("   This benchmark ACTUALLY uses Evo2 for predictions")
    print("=" * 70)
    
    test_path = Path(test_file)
    if not test_path.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    with open(test_path, 'r') as f:
        test_cases = json.load(f)
    
    print(f"✅ Loaded {len(test_cases)} test cases")
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_case(case: Dict) -> Dict:
        async with semaphore:
            case_id = case['case_id']
            print(f"🔄 Processing {case_id}...")
            
            async with httpx.AsyncClient() as client:
                prediction = await predict_efficacy(client, case)
            
            if prediction is None:
                print(f"   ❌ Failed")
                return None
            
            metrics = evaluate_prediction(case, prediction)
            
            # Print quick summary
            evo2_status = "✅ Evo2" if metrics.get("evo2_used") else "⚠️ No Evo2"
            match_status = "✅ Match" if metrics.get("drug_match") else "❌ No Match"
            print(f"   {evo2_status} | {match_status} | Top: {metrics.get('top_drug')} ({metrics.get('confidence', 0):.2f})")
            
            return {
                "case_id": case_id,
                "ground_truth": case.get("ground_truth", {}),
                "prediction_summary": {
                    "top_drug": metrics.get("top_drug"),
                    "confidence": metrics.get("confidence"),
                },
                "metrics": metrics,
                "full_prediction": prediction,
            }
    
    print(f"\n🚀 Processing {len(test_cases)} cases (max {max_concurrent} concurrent)...\n")
    
    tasks = [process_case(case) for case in test_cases]
    comparisons = await asyncio.gather(*tasks)
    results = [c for c in comparisons if c is not None]
    
    if not results:
        print("\n❌ No results collected")
        return
    
    # Aggregate metrics
    drug_matches = [r["metrics"]["drug_match"] for r in results]
    evo2_used = [r["metrics"]["evo2_used"] for r in results]
    confidences = [r["metrics"]["confidence"] for r in results]
    
    drug_accuracy = sum(drug_matches) / len(drug_matches)
    evo2_rate = sum(evo2_used) / len(evo2_used)
    avg_confidence = np.mean(confidences)
    
    # Save results
    output = {
        "date": datetime.now().isoformat(),
        "benchmark_type": "efficacy_predict",
        "test_file": str(test_file),
        "num_cases": len(results),
        "aggregate_metrics": {
            "drug_accuracy": drug_accuracy,
            "evo2_usage_rate": evo2_rate,
            "avg_confidence": avg_confidence,
        },
        "results": results,
    }
    
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    output_file = results_dir / f"benchmark_efficacy_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 70)
    print("📊 BENCHMARK RESULTS")
    print("=" * 70)
    print(f"\n✅ Processed {len(results)}/{len(test_cases)} cases")
    print(f"\n📈 Metrics:")
    print(f"   Drug Match Accuracy: {drug_accuracy:.1%}")
    print(f"   Evo2 Usage Rate:     {evo2_rate:.1%}")
    print(f"   Avg Confidence:      {avg_confidence:.2f}")
    
    if evo2_rate < 1.0:
        print(f"\n⚠️  WARNING: Evo2 was NOT used for {(1-evo2_rate)*100:.0f}% of cases!")
        print(f"   Check if the backend is properly configured.")
    
    print(f"\n💾 Results saved to: {output_file}")
    print("=" * 70)
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run efficacy benchmark (uses Evo2)")
    parser.add_argument("test_file", nargs="?", default="test_cases_pilot.json")
    parser.add_argument("--max-concurrent", type=int, default=3)
    parser.add_argument("--api-root", default="http://127.0.0.1:8000")
    
    args = parser.parse_args()
    API_ROOT = args.api_root
    
    asyncio.run(run_benchmark(args.test_file, args.max_concurrent))



