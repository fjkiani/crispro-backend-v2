#!/usr/bin/env python3
"""
Dosing Guidance Validation - Metrics Calculator
================================================
Computes validation metrics from extracted case data.

Usage:
    python calculate_validation_metrics.py --input validation_cases.json --output validation_report.md
"""

import json
import argparse
from datetime import datetime

def calculate_metrics(cases):
    """Calculate all validation metrics from case data"""
    metrics = {
        "total_cases": len(cases),
        "by_gene": {},
        "concordance": {"matches": 0, "total": 0},
        "toxicity_prediction": {"tp": 0, "tn": 0, "fp": 0, "fn": 0},
        "prevented_possible": 0
    }
    
    for case in cases:
        gene = case.get("gene", "Unknown")
        metrics["by_gene"][gene] = metrics["by_gene"].get(gene, 0) + 1
        
        # Concordance
        metrics["concordance"]["total"] += 1
        # Check curated concordance field (boolean) or concordance_details
        concordance = case.get("concordance")
        if concordance is None:
            # Check concordance_details dict
            concordance_details = case.get("concordance_details", {})
            concordance = concordance_details.get("concordant", False)
        if concordance:
            metrics["concordance"]["matches"] += 1
        
        # Toxicity prediction
        # Check if we flagged (would have recommended dose reduction)
        prediction = case.get("our_prediction", {})
        flagged = prediction.get("would_have_flagged", False) or (prediction.get("adjustment_factor", 1.0) < 1.0)
        
        # Get toxicity_occurred - check curated field first, then outcome
        toxicity = case.get("toxicity_occurred")
        if toxicity is None:
            # Fallback to outcome field
            outcome = case.get("outcome", {})
            toxicity = outcome.get("toxicity_occurred", False)
        # Convert None to False for metrics calculation
        if toxicity is None:
            toxicity = False
        
        if flagged and toxicity:
            metrics["toxicity_prediction"]["tp"] += 1
        elif not flagged and not toxicity:
            metrics["toxicity_prediction"]["tn"] += 1
        elif flagged and not toxicity:
            metrics["toxicity_prediction"]["fp"] += 1
        else:
            metrics["toxicity_prediction"]["fn"] += 1
        
        # Prevention possible
        if toxicity and flagged and not case.get("concordance"):
            metrics["prevented_possible"] += 1
    
    # Calculate rates
    tp = metrics["toxicity_prediction"]
    metrics["sensitivity"] = tp["tp"] / (tp["tp"] + tp["fn"]) if (tp["tp"] + tp["fn"]) > 0 else 0
    metrics["specificity"] = tp["tn"] / (tp["tn"] + tp["fp"]) if (tp["tn"] + tp["fp"]) > 0 else 0
    metrics["concordance_rate"] = metrics["concordance"]["matches"] / metrics["concordance"]["total"] if metrics["concordance"]["total"] > 0 else 0
    
    return metrics

def generate_report(metrics, output_file):
    """Generate markdown report"""
    report = [
        "# Dosing Guidance Validation Report",
        f"\n**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"\n**Total Cases:** {metrics['total_cases']}",
        "\n## Summary\n",
        "| Metric | Value | Target | Status |",
        "|--------|-------|--------|--------|",
        f"| Concordance | {metrics['concordance_rate']*100:.1f}% | ≥70% | {'✅' if metrics['concordance_rate'] >= 0.7 else '❌'} |",
        f"| Sensitivity | {metrics['sensitivity']*100:.1f}% | ≥75% | {'✅' if metrics['sensitivity'] >= 0.75 else '❌'} |",
        f"| Specificity | {metrics['specificity']*100:.1f}% | ≥60% | {'✅' if metrics['specificity'] >= 0.6 else '❌'} |",
        f"| Prevention Possible | {metrics['prevented_possible']} | N/A | 📊 |",
        "\n## By Gene\n",
        "| Gene | Cases |",
        "|------|-------|"
    ]
    
    for gene, count in metrics["by_gene"].items():
        report.append(f"| {gene} | {count} |")
    
    with open(output_file, 'w') as f:
        f.write('\n'.join(report))
    print(f"📄 Report saved to {output_file}")

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="validation_report.md")
    args = parser.parse_args()
    
    with open(args.input) as f:
        data = json.load(f)
    
    metrics = calculate_metrics(data.get("cases", []))
    generate_report(metrics, args.output)
    
    print(f"\n{'='*50}")
    print(f"Total: {metrics['total_cases']} | Concordance: {metrics['concordance_rate']*100:.1f}% | Sensitivity: {metrics['sensitivity']*100:.1f}%")

if __name__ == "__main__":
    main()


