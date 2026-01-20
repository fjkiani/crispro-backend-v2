#!/usr/bin/env python3
"""
Error analysis framework for synthetic lethality predictions.

Categorizes failures:
- False positives: Predicted SL but not in ground truth
- False negatives: Ground truth SL but not predicted
- Analyzes by gene, cancer type, evidence tier
"""
import json
from pathlib import Path
from typing import List, Dict, Any
from collections import defaultdict

def categorize_errors(results: List[Dict]) -> Dict[str, Any]:
    """Categorize prediction errors."""
    false_positives = []
    false_negatives = []
    true_positives = []
    true_negatives = []
    
    for case in results:
        case_id = case.get("case_id", "unknown")
        gt = case.get("ground_truth", {})
        pred = case.get("prediction", {})
        
        sl_detected_gt = gt.get("synthetic_lethality_detected", False)
        confidence = pred.get("confidence", 0.0)
        sl_detected_pred = confidence > 0.5
        
        case_info = {
            "case_id": case_id,
            "disease": case.get("disease", "unknown"),
            "genes": [m.get("gene") for m in case.get("mutations", [])],
            "confidence": confidence,
            "ground_truth_drugs": gt.get("effective_drugs", []),
            "predicted_drugs": pred.get("recommended_drugs", [])
        }
        
        if sl_detected_gt and sl_detected_pred:
            true_positives.append(case_info)
        elif not sl_detected_gt and not sl_detected_pred:
            true_negatives.append(case_info)
        elif sl_detected_gt and not sl_detected_pred:
            false_negatives.append(case_info)
        elif not sl_detected_gt and sl_detected_pred:
            false_positives.append(case_info)
    
    return {
        "false_positives": false_positives,
        "false_negatives": false_negatives,
        "true_positives": true_positives,
        "true_negatives": true_negatives
    }

def analyze_by_gene(errors: Dict[str, List]) -> Dict[str, Any]:
    """Analyze errors by gene."""
    gene_stats = defaultdict(lambda: {"fp": 0, "fn": 0, "tp": 0, "tn": 0})
    
    for category, cases in errors.items():
        for case in cases:
            for gene in case.get("genes", []):
                if gene:
                    if category == "false_positives":
                        gene_stats[gene]["fp"] += 1
                    elif category == "false_negatives":
                        gene_stats[gene]["fn"] += 1
                    elif category == "true_positives":
                        gene_stats[gene]["tp"] += 1
                    elif category == "true_negatives":
                        gene_stats[gene]["tn"] += 1
    
    return dict(gene_stats)

def analyze_by_cancer_type(errors: Dict[str, List]) -> Dict[str, Any]:
    """Analyze errors by cancer type."""
    cancer_stats = defaultdict(lambda: {"fp": 0, "fn": 0, "tp": 0, "tn": 0})
    
    for category, cases in errors.items():
        for case in cases:
            cancer = case.get("disease", "unknown")
            if category == "false_positives":
                cancer_stats[cancer]["fp"] += 1
            elif category == "false_negatives":
                cancer_stats[cancer]["fn"] += 1
            elif category == "true_positives":
                cancer_stats[cancer]["tp"] += 1
            elif category == "true_negatives":
                cancer_stats[cancer]["tn"] += 1
    
    return dict(cancer_stats)

def analyze_errors(results_file: str = "results/benchmark_100_cached.json") -> Dict[str, Any]:
    """Perform comprehensive error analysis."""
    print(f"Analyzing errors from {results_file}...")
    
    if not Path(results_file).exists():
        print(f"❌ Results file not found: {results_file}")
        return {}
    
    with open(results_file, 'r') as f:
        results = json.load(f)
    
    predictions = results.get("predictions", [])
    if not predictions:
        print("❌ No predictions found")
        return {}
    
    # Categorize errors
    errors = categorize_errors(predictions)
    
    # Analyze by gene and cancer type
    gene_analysis = analyze_by_gene(errors)
    cancer_analysis = analyze_by_cancer_type(errors)
    
    # Summary
    total = len(predictions)
    fp_count = len(errors["false_positives"])
    fn_count = len(errors["false_negatives"])
    tp_count = len(errors["true_positives"])
    tn_count = len(errors["true_negatives"])
    
    print("=" * 60)
    print("Error Analysis Results")
    print("=" * 60)
    print(f"Total cases: {total}")
    print(f"True Positives: {tp_count} ({tp_count/total*100:.1f}%)")
    print(f"True Negatives: {tn_count} ({tn_count/total*100:.1f}%)")
    print(f"False Positives: {fp_count} ({fp_count/total*100:.1f}%)")
    print(f"False Negatives: {fn_count} ({fn_count/total*100:.1f}%)")
    
    print(f"\n🔴 Top False Positive Genes:")
    fp_genes = sorted(gene_analysis.items(), key=lambda x: x[1]["fp"], reverse=True)[:5]
    for gene, stats in fp_genes:
        if stats["fp"] > 0:
            print(f"   {gene}: {stats['fp']} FPs")
    
    print(f"\n🔴 Top False Negative Genes:")
    fn_genes = sorted(gene_analysis.items(), key=lambda x: x[1]["fn"], reverse=True)[:5]
    for gene, stats in fn_genes:
        if stats["fn"] > 0:
            print(f"   {gene}: {stats['fn']} FNs")
    
    # Save results
    analysis = {
        "summary": {
            "total": total,
            "true_positives": tp_count,
            "true_negatives": tn_count,
            "false_positives": fp_count,
            "false_negatives": fn_count
        },
        "errors": errors,
        "gene_analysis": gene_analysis,
        "cancer_analysis": cancer_analysis
    }
    
    output_file = Path("results/error_analysis.json")
    output_file.parent.mkdir(exist_ok=True)
    with open(output_file, 'w') as f:
        json.dump(analysis, f, indent=2)
    
    print(f"\n✅ Error analysis saved to {output_file}")
    
    return analysis

if __name__ == "__main__":
    import sys
    results_file = sys.argv[1] if len(sys.argv) > 1 else "results/benchmark_100_cached.json"
    analyze_errors(results_file)







