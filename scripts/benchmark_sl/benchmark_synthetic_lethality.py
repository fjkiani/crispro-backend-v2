#!/usr/bin/env python3
"""
Synthetic Lethality Prediction Benchmark
Adapted from benchmark_sota_ovarian.py pattern
"""
import asyncio
import json
import sys
import argparse
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

import httpx
import numpy as np

try:
    from scipy.stats import norm
    SCIPY_AVAILABLE = True
except ImportError:
    SCIPY_AVAILABLE = False
    print("⚠️  scipy not available, using simplified confidence intervals")

API_ROOT = "http://127.0.0.1:8000"

async def predict_sl(client: httpx.AsyncClient, case: Dict[str, Any]) -> Dict[str, Any]:
    """Call synthetic lethality API."""
    try:
        payload = {
            "disease": case["disease"],
            "mutations": case["mutations"]
        }
        
        resp = await client.post(
            f"{API_ROOT}/api/guidance/synthetic_lethality",
            json=payload,
            timeout=120.0
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"❌ Error for case {case.get('case_id')}: {e}")
        return None

def calculate_metrics(gt: Dict, pred: Dict) -> Dict:
    """Calculate metrics for a single case."""
    metrics = {}
    
    # Drug match (binary) - check if suggested therapy matches any effective drug
    suggested = pred.get("suggested_therapy", "").lower()
    effective_drugs = [d.lower() for d in gt.get("effective_drugs", [])]
    
    # Check for drug name matches (e.g., "platinum" matches "platinum", "olaparib" matches "olaparib")
    drug_match = False
    if suggested and effective_drugs:
        # Check if any effective drug name appears in suggested therapy
        for drug in effective_drugs:
            if drug in suggested or suggested in drug:
                drug_match = True
                break
        # Also check common aliases
        drug_aliases = {
            "olaparib": ["parp", "lynparza"],
            "niraparib": ["parp", "zejula"],
            "rucaparib": ["parp", "rubraca"],
            "ceralasertib": ["atr"],
            "adavosertib": ["wee1"],
            "platinum": ["cisplatin", "carboplatin", "oxaliplatin"]
        }
        for drug in effective_drugs:
            if drug in drug_aliases:
                for alias in drug_aliases[drug]:
                    if alias in suggested:
                        drug_match = True
                        break
    
    metrics["drug_match"] = drug_match
    
    # SL detection (binary) - check if we detected SL when we should have
    gt_sl_detected = gt.get("synthetic_lethality_detected", False)
    # Infer SL detection from suggested therapy or essentiality scores
    pred_sl_detected = False
    if suggested:
        # If we suggest PARP/ATR/WEE1 inhibitors, likely detected SL
        sl_keywords = ["parp", "atr", "wee1", "platinum"]
        pred_sl_detected = any(kw in suggested.lower() for kw in sl_keywords)
    
    # Also check essentiality scores - high scores suggest SL
    essentiality_report = pred.get("essentiality_report", [])
    if essentiality_report:
        high_essentiality = any(
            e.get("result", {}).get("essentiality_score", 0) >= 0.7 
            for e in essentiality_report
        )
        if high_essentiality:
            pred_sl_detected = True
    
    metrics["sl_detection_tp"] = gt_sl_detected and pred_sl_detected
    metrics["sl_detection_fp"] = not gt_sl_detected and pred_sl_detected
    metrics["sl_detection_tn"] = not gt_sl_detected and not pred_sl_detected
    metrics["sl_detection_fn"] = gt_sl_detected and not pred_sl_detected
    
    # Essentiality correlation (if available)
    if "depmap_essentiality" in gt and essentiality_report:
        gt_scores = gt["depmap_essentiality"]
        pred_scores = {
            e["gene"]: e.get("result", {}).get("essentiality_score", 0)
            for e in essentiality_report
        }
        
        # Match genes
        common_genes = set(gt_scores.keys()) & set(pred_scores.keys())
        if common_genes:
            gt_vals = [gt_scores[g] for g in common_genes]
            pred_vals = [pred_scores[g] for g in common_genes]
            if len(gt_vals) > 1:
                correlation = np.corrcoef(gt_vals, pred_vals)[0, 1]
                metrics["essentiality_correlation"] = float(correlation) if not np.isnan(correlation) else None
    
    return metrics

def aggregate_metrics(results: List[Dict]) -> Dict:
    """Aggregate metrics across all cases with confidence intervals."""
    drug_matches = [r["metrics"].get("drug_match", False) for r in results]
    correlations = [r["metrics"].get("essentiality_correlation") for r in results 
                   if "essentiality_correlation" in r["metrics"] and r["metrics"]["essentiality_correlation"] is not None]
    
    # Calculate drug accuracy
    drug_accuracy = sum(drug_matches) / len(drug_matches) if drug_matches else 0.0
    n = len(drug_matches)
    
    # Wilson score interval for proportion
    if SCIPY_AVAILABLE and n > 0:
        z = norm.ppf(0.975)  # 95% CI
        p = drug_accuracy
        ci_lower = (p + z**2/(2*n) - z*np.sqrt((p*(1-p) + z**2/(4*n))/n)) / (1 + z**2/n)
        ci_upper = (p + z**2/(2*n) + z*np.sqrt((p*(1-p) + z**2/(4*n))/n)) / (1 + z**2/n)
    else:
        # Simplified CI
        ci_lower = max(0, drug_accuracy - 1.96 * np.sqrt(drug_accuracy * (1 - drug_accuracy) / n)) if n > 0 else 0
        ci_upper = min(1, drug_accuracy + 1.96 * np.sqrt(drug_accuracy * (1 - drug_accuracy) / n)) if n > 0 else 1
    
    # SL detection metrics
    tp = sum(1 for r in results if r["metrics"].get("sl_detection_tp", False))
    fp = sum(1 for r in results if r["metrics"].get("sl_detection_fp", False))
    tn = sum(1 for r in results if r["metrics"].get("sl_detection_tn", False))
    fn = sum(1 for r in results if r["metrics"].get("sl_detection_fn", False))
    
    tpr = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    fpr = fp / (fp + tn) if (fp + tn) > 0 else 0.0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tpr
    
    # Essentiality correlation
    mean_corr = np.mean(correlations) if correlations else 0.0
    std_corr = np.std(correlations) if correlations else 0.0
    corr_ci = (
        mean_corr - 1.96*std_corr/np.sqrt(len(correlations)), 
        mean_corr + 1.96*std_corr/np.sqrt(len(correlations))
    ) if correlations and len(correlations) > 1 else (0.0, 0.0)
    
    return {
        "drug_accuracy": float(drug_accuracy),
        "drug_accuracy_ci_95": (float(ci_lower), float(ci_upper)),
        "sl_detection_tpr": float(tpr),
        "sl_detection_fpr": float(fpr),
        "sl_detection_precision": float(precision),
        "sl_detection_recall": float(recall),
        "sl_detection_confusion_matrix": {
            "tp": int(tp),
            "fp": int(fp),
            "tn": int(tn),
            "fn": int(fn)
        },
        "mean_essentiality_correlation": float(mean_corr),
        "essentiality_correlation_ci_95": (float(corr_ci[0]), float(corr_ci[1])),
        "num_cases_with_correlation": len(correlations),
        "total_cases": len(results)
    }

async def run_benchmark(test_file: str, max_concurrent: int = 5, cache_file: str = None):
    """Run benchmark on all test cases with parallel execution."""
    print("=" * 60)
    print("Synthetic Lethality Benchmark")
    print("=" * 60)
    
    test_path = Path(test_file)
    if not test_path.exists():
        print(f"❌ Test file not found: {test_file}")
        return
    
    with open(test_path, 'r') as f:
        test_cases = json.load(f)
    
    print(f"✅ Loaded {len(test_cases)} test cases from {test_file}")
    
    # Load cache if exists
    cache = {}
    if cache_file and Path(cache_file).exists():
        with open(cache_file, 'r') as f:
            cache = json.load(f)
        print(f"✅ Loaded {len(cache)} cached results")
    
    results = []
    semaphore = asyncio.Semaphore(max_concurrent)
    
    async def process_case(case: Dict[str, Any]) -> Dict:
        """Process a single case with semaphore for concurrency control."""
        async with semaphore:
            case_id = case['case_id']
            
            # Check cache first
            if case_id in cache:
                print(f"📦 Using cached result for {case_id}")
                prediction = cache[case_id]
            else:
                print(f"🔄 Processing case {case_id}...")
                async with httpx.AsyncClient() as client:
                    prediction = await predict_sl(client, case)
                    if prediction and cache_file:
                        cache[case_id] = prediction
            
            if prediction is None:
                return None
            
            # Compare to ground truth
            gt = case["ground_truth"]
            comparison = {
                "case_id": case_id,
                "ground_truth": gt,
                "prediction": {
                    "suggested_therapy": prediction.get("suggested_therapy"),
                    "essentiality_scores": [
                        {
                            "gene": e["gene"],
                            "score": e.get("result", {}).get("essentiality_score", 0)
                        }
                        for e in prediction.get("essentiality_report", [])
                    ]
                },
                "metrics": calculate_metrics(gt, prediction)
            }
            return comparison
    
    # Process all cases in parallel
    print(f"\n🚀 Processing {len(test_cases)} cases (max {max_concurrent} concurrent)...\n")
    tasks = [process_case(case) for case in test_cases]
    comparisons = await asyncio.gather(*tasks)
    results = [c for c in comparisons if c is not None]
    
    # Save cache
    if cache_file:
        cache_path = Path(cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        with open(cache_path, 'w') as f:
            json.dump(cache, f, indent=2)
        print(f"\n💾 Saved cache with {len(cache)} entries to {cache_file}")
    
    if not results:
        print("\n❌ No results collected. Check API connection and test cases.")
        return
    
    # Aggregate metrics
    aggregate = aggregate_metrics(results)
    
    # Save results
    output = {
        "date": datetime.now().isoformat(),
        "test_file": str(test_file),
        "num_cases": len(results),
        "aggregate_metrics": aggregate,
        "results": results
    }
    
    results_dir = Path("results")
    results_dir.mkdir(exist_ok=True)
    output_file = results_dir / f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    # Print summary
    print("\n" + "=" * 60)
    print("📊 BENCHMARK RESULTS")
    print("=" * 60)
    print(f"\n✅ Processed {len(results)}/{len(test_cases)} cases")
    print(f"\n📈 Aggregate Metrics:")
    print(f"   Drug Match Accuracy: {aggregate['drug_accuracy']:.1%} (95% CI: {aggregate['drug_accuracy_ci_95'][0]:.1%} - {aggregate['drug_accuracy_ci_95'][1]:.1%})")
    print(f"   SL Detection TPR:   {aggregate['sl_detection_tpr']:.1%}")
    print(f"   SL Detection FPR:   {aggregate['sl_detection_fpr']:.1%}")
    print(f"   SL Detection Precision: {aggregate['sl_detection_precision']:.1%}")
    print(f"   SL Detection Recall:    {aggregate['sl_detection_recall']:.1%}")
    print(f"\n   Confusion Matrix:")
    cm = aggregate['sl_detection_confusion_matrix']
    print(f"      TP: {cm['tp']}, FP: {cm['fp']}, TN: {cm['tn']}, FN: {cm['fn']}")
    
    if aggregate['num_cases_with_correlation'] > 0:
        print(f"\n   Essentiality Correlation: {aggregate['mean_essentiality_correlation']:.3f}")
        print(f"      (95% CI: {aggregate['essentiality_correlation_ci_95'][0]:.3f} - {aggregate['essentiality_correlation_ci_95'][1]:.3f})")
        print(f"      Based on {aggregate['num_cases_with_correlation']} cases")
    
    print(f"\n💾 Results saved to: {output_file}")
    print("=" * 60)
    
    return output

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run synthetic lethality benchmark")
    parser.add_argument("test_file", nargs="?", default="test_cases_pilot.json", 
                       help="Path to test cases JSON file")
    parser.add_argument("--cache", help="Path to cache file for results")
    parser.add_argument("--max-concurrent", type=int, default=5, 
                       help="Maximum concurrent API requests (default: 5)")
    parser.add_argument("--api-root", default="http://127.0.0.1:8000",
                       help="API root URL (default: http://127.0.0.1:8000)")
    
    args = parser.parse_args()
    API_ROOT = args.api_root
    
    asyncio.run(run_benchmark(args.test_file, args.max_concurrent, args.cache))



