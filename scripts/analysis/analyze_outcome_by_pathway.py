#!/usr/bin/env python3
"""
Analyze Outcome by Pathway: Correlate pathway scores with clinical outcomes.

Analyzes which pathways (DDR, MAPK, PI3K, etc.) predict PFS/OS outcomes.
"""

import sys
import json
import numpy as np
from scipy import stats
from pathlib import Path
from typing import List, Dict, Any

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal"))


def load_benchmark_results(results_file: str) -> tuple[List[Dict], List[Dict]]:
    """
    Load benchmark results and patient data.
    
    Args:
        results_file: Path to benchmark results JSON
        
    Returns:
        (predictions, patients) tuple
    """
    with open(results_file, 'r') as f:
        data = json.load(f)
    
    # Handle different file formats
    if isinstance(data, dict):
        predictions = data.get("predictions", [])
        patients = data.get("patients", [])
    elif isinstance(data, list):
        # Assume it's a list of predictions
        predictions = data
        # Try to load patients from separate file
        patients_file = results_file.replace("_results.json", "_patients.json")
        if Path(patients_file).exists():
            with open(patients_file, 'r') as pf:
                patients_data = json.load(pf)
                patients = patients_data.get("patients", []) if isinstance(patients_data, dict) else patients_data
        else:
            patients = []
    else:
        raise ValueError(f"Unexpected data format: {type(data)}")
    
    return predictions, patients


def analyze_outcome_by_pathway(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Analyze outcomes (PFS/OS) by pathway scores.
    
    Args:
        predictions: List of API responses with pathway_disruption
        patients: List of patient dicts with clinical_outcomes
        
    Returns:
        Dict with pathway→outcome correlation analysis
    """
    print("\n📊 PATHWAY → OUTCOME ANALYSIS")
    print("=" * 60)
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Extract pathway scores and outcomes
    pathway_data = []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        # Extract pathway scores from API response
        # Note: In actual benchmark, we need to store full API response
        # For now, assume pathway_disruption is in a stored response
        pathway_scores = {}
        
        # Try to get from stored response (if benchmark script stores full response)
        if "api_response" in pred:
            api_response = pred["api_response"]
            pathway_scores = (
                api_response.get("provenance", {})
                .get("confidence_breakdown", {})
                .get("pathway_disruption", {})
            )
        else:
            # Fallback: pathway scores not available in this prediction
            continue
        
        outcomes = patient.get("clinical_outcomes") or patient.get("outcomes", {})
        
        pathway_data.append({
            "patient_id": patient_id,
            "ddr": pathway_scores.get("ddr", 0.0),
            "mapk": pathway_scores.get("ras_mapk", pathway_scores.get("mapk", 0.0)),
            "pi3k": pathway_scores.get("pi3k", 0.0),
            "vegf": pathway_scores.get("vegf", 0.0),
            "tp53": pathway_scores.get("tp53", 0.0),
            "pfs_months": outcomes.get("PFS_MONTHS"),
            "os_months": outcomes.get("OS_MONTHS"),
        })
    
    if len(pathway_data) < 20:
        print(f"⚠️  Insufficient data: {len(pathway_data)} patients (need >= 20)")
        return {"error": f"Insufficient data: {len(pathway_data)} patients"}
    
    print(f"   Analyzing {len(pathway_data)} patients...")
    
    # Analyze each pathway
    results = {}
    
    pathways = ["ddr", "mapk", "pi3k", "vegf", "tp53"]
    
    for pathway in pathways:
        pathway_scores = [p[pathway] for p in pathway_data]
        
        # PFS correlation
        pfs_months = [p["pfs_months"] for p in pathway_data if p["pfs_months"] is not None]
        pfs_scores = [pathway_data[i][pathway] for i, p in enumerate(pathway_data) if p["pfs_months"] is not None]
        
        if len(pfs_months) >= 20:
            pfs_corr, pfs_p = stats.pearsonr(pfs_scores, pfs_months)
            results[f"{pathway}_pfs_correlation"] = float(pfs_corr)
            results[f"{pathway}_pfs_p_value"] = float(pfs_p)
        else:
            results[f"{pathway}_pfs_correlation"] = None
            results[f"{pathway}_pfs_p_value"] = None
        
        # OS correlation
        os_months = [p["os_months"] for p in pathway_data if p["os_months"] is not None]
        os_scores = [pathway_data[i][pathway] for i, p in enumerate(pathway_data) if p["os_months"] is not None]
        
        if len(os_months) >= 20:
            os_corr, os_p = stats.pearsonr(os_scores, os_months)
            results[f"{pathway}_os_correlation"] = float(os_corr)
            results[f"{pathway}_os_p_value"] = float(os_p)
        else:
            results[f"{pathway}_os_correlation"] = None
            results[f"{pathway}_os_p_value"] = None
        
        # Group analysis (high vs low pathway)
        pathway_median = np.median(pathway_scores)
        high_pathway = [p for p in pathway_data if p[pathway] > pathway_median]
        low_pathway = [p for p in pathway_data if p[pathway] <= pathway_median]
        
        high_pfs = [p["pfs_months"] for p in high_pathway if p["pfs_months"] is not None]
        low_pfs = [p["pfs_months"] for p in low_pathway if p["pfs_months"] is not None]
        
        if len(high_pfs) > 0 and len(low_pfs) > 0:
            high_pfs_mean = np.mean(high_pfs)
            low_pfs_mean = np.mean(low_pfs)
            results[f"{pathway}_high_pfs_mean"] = float(high_pfs_mean)
            results[f"{pathway}_low_pfs_mean"] = float(low_pfs_mean)
            results[f"{pathway}_pfs_difference"] = float(high_pfs_mean - low_pfs_mean)
        
        # Print summary
        print(f"\n   {pathway.upper()} Pathway:")
        if results.get(f"{pathway}_pfs_correlation") is not None:
            print(f"      PFS Correlation: r={results[f'{pathway}_pfs_correlation']:.3f}, p={results[f'{pathway}_pfs_p_value']:.4f}")
        if results.get(f"{pathway}_os_correlation") is not None:
            print(f"      OS Correlation: r={results[f'{pathway}_os_correlation']:.3f}, p={results[f'{pathway}_os_p_value']:.4f}")
        if results.get(f"{pathway}_pfs_difference") is not None:
            print(f"      PFS Difference: High={results[f'{pathway}_high_pfs_mean']:.1f}mo, Low={results[f'{pathway}_low_pfs_mean']:.1f}mo, Δ={results[f'{pathway}_pfs_difference']:.1f}mo")
    
    results["n_patients"] = len(pathway_data)
    
    return results


def main():
    """Main analysis function."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Analyze pathway→outcome correlations")
    parser.add_argument(
        "results_file",
        type=str,
        help="Path to benchmark results JSON file"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for analysis results (JSON)"
    )
    
    args = parser.parse_args()
    
    # Load data
    print(f"📂 Loading benchmark results from: {args.results_file}")
    predictions, patients = load_benchmark_results(args.results_file)
    print(f"   Loaded {len(predictions)} predictions, {len(patients)} patients")
    
    # Analyze
    results = analyze_outcome_by_pathway(predictions, patients)
    
    # Save results
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(results, f, indent=2)
        print(f"\n💾 Results saved to: {args.output}")
    else:
        print("\n📊 ANALYSIS RESULTS:")
        print(json.dumps(results, indent=2))
    
    return 0


if __name__ == "__main__":
    sys.exit(main())

