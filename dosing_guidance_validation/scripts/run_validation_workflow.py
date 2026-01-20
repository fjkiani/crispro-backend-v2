#!/usr/bin/env python3
"""
Dosing Guidance Validation - Complete Workflow
===============================================

Complete validation workflow that:
1. Extracts cases from all sources (PubMed, cBioPortal, GDC)
2. Runs cases through dosing guidance API
3. Calculates validation metrics
4. Generates final validation report

Author: Zo (Agent)
Created: January 2025
"""

import sys
import json
import argparse
import requests
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "data_acquisition" / "utils"))

from unified_extraction_pipeline import run_unified_extraction
from calculate_validation_metrics import calculate_metrics, generate_report

# ============================================================================
# Configuration
# ============================================================================

DOSING_API_BASE = "http://localhost:8000"  # Default - can be overridden
PHARMACOGENES = ['DPYD', 'UGT1A1', 'TPMT']

# Drug mapping for extracted cases
DRUG_MAPPING = {
    "DPYD": ["5-fluorouracil", "5-fu", "capecitabine", "fluoropyrimidine"],
    "UGT1A1": ["irinotecan", "camptosar"],
    "TPMT": ["6-mercaptopurine", "6-mp", "azathioprine", "thiopurine"]
}


# ============================================================================
# Step 2: Run Cases Through Dosing Guidance API
# ============================================================================

def map_variant_to_diplotype(gene: str, variant: str) -> str:
    """Map variant notation to diplotype format for API."""
    # Handle common variant formats
    variant_upper = variant.upper()
    
    if "*" in variant:
        # Already in star notation (e.g., "*2A", "*28/*28")
        return variant
    elif "c." in variant or "p." in variant:
        # HGVS notation - extract star allele if possible
        if "DPYD" in gene.upper():
            if "1905+1G>A" in variant or "*2A" in variant_upper:
                return "*2A/*2A"  # Default to homozygous for safety
            elif "2846A>T" in variant or "D949V" in variant_upper:
                return "*9/*9"  # D949V is *9
        elif "UGT1A1" in gene.upper():
            if "*28" in variant_upper or "(TA)7" in variant:
                return "*28/*28"
        elif "TPMT" in gene.upper():
            if "*3A" in variant_upper or "*3B" in variant_upper or "*3C" in variant_upper:
                return "*3A/*3A"
    
    # Default: assume heterozygous if not specified
    return f"{variant}/{variant}" if variant else "Unknown/Unknown"


def get_drug_for_gene(gene: str) -> str:
    """Get default drug for a pharmacogene."""
    mapping = {
        "DPYD": "5-fluorouracil",
        "UGT1A1": "irinotecan",
        "TPMT": "6-mercaptopurine"
    }
    return mapping.get(gene.upper(), "unknown")


def run_case_through_dosing_api(case: Dict, api_base: str = DOSING_API_BASE) -> Optional[Dict]:
    """Run a single case through the dosing guidance API."""
    gene = case.get("gene", "").upper()
    variant = case.get("variant", "")
    drug = case.get("drug") or get_drug_for_gene(gene)
    
    # Map variant to diplotype
    diplotype = map_variant_to_diplotype(gene, variant)
    
    # Build API request
    request_payload = {
        "gene": gene,
        "variant": diplotype,
        "drug": drug,
        "treatment_line": case.get("treatment_line", 1),
        "prior_therapies": case.get("prior_therapies", []),
        "standard_dose": case.get("standard_dose")
    }
    
    try:
        response = requests.post(
            f"{api_base}/api/dosing/guidance",
            json=request_payload,
            timeout=30
        )
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"  ⚠️  API call failed for {case.get('case_id', 'unknown')}: {e}")
        return None


def run_all_cases_through_api(cases: List[Dict], api_base: str = DOSING_API_BASE) -> List[Dict]:
    """Run all cases through dosing guidance API and add predictions."""
    print(f"\n{'='*60}")
    print("STEP 2: Running Cases Through Dosing Guidance API")
    print('='*60)
    print(f"API Base: {api_base}")
    print(f"Total cases: {len(cases)}")
    
    enriched_cases = []
    
    for i, case in enumerate(cases, 1):
        print(f"\n  [{i}/{len(cases)}] Processing: {case.get('case_id', 'unknown')}")
        
        # Run through API
        api_response = run_case_through_dosing_api(case, api_base)
        
        if api_response:
            # Extract key predictions
            recommendations = api_response.get("recommendations", [])
            if recommendations:
                rec = recommendations[0]  # Take first recommendation
                case["our_prediction"] = {
                    "recommended_dose": rec.get("recommended_dose", "N/A"),
                    "adjustment_factor": rec.get("adjustment_factor", 1.0),
                    "risk_level": rec.get("risk_level", "UNKNOWN"),
                    "would_have_flagged": rec.get("adjustment_factor", 1.0) < 1.0,
                    "alternatives": rec.get("alternatives", []),
                    "cpic_level": rec.get("cpic_level", "UNKNOWN")
                }
            else:
                case["our_prediction"] = {
                    "recommended_dose": "N/A",
                    "adjustment_factor": 1.0,
                    "risk_level": "UNKNOWN",
                    "would_have_flagged": False,
                    "alternatives": [],
                    "cpic_level": "UNKNOWN"
                }
            
            case["api_response"] = api_response
            enriched_cases.append(case)
        else:
            # Keep case but mark as failed
            case["our_prediction"] = None
            case["api_error"] = True
            enriched_cases.append(case)
    
    print(f"\n  ✅ Processed {len(enriched_cases)} cases")
    print(f"  ✅ Successful API calls: {sum(1 for c in enriched_cases if c.get('our_prediction'))}")
    
    return enriched_cases


# ============================================================================
# Step 3: Assess Concordance
# ============================================================================

def assess_concordance(case: Dict) -> Dict:
    """Compare our prediction with actual clinical decision and outcome."""
    prediction = case.get("our_prediction")
    treatment = case.get("treatment", {})
    outcome = case.get("outcome", {})
    
    if not prediction:
        return {
            "matched_clinical_decision": False,
            "our_recommendation_safer": False,
            "prevented_toxicity_possible": False,
            "notes": "No prediction available"
        }
    
    # Did clinical match our recommendation?
    clinical_adjusted = treatment.get("dose_adjustment_made", False)
    we_would_adjust = prediction.get("adjustment_factor", 1.0) < 1.0
    matched = clinical_adjusted == we_would_adjust
    
    # Would we have been safer?
    our_safer = False
    prevented_possible = False
    
    if outcome.get("toxicity_occurred", False):
        if not clinical_adjusted and we_would_adjust:
            our_safer = True
            prevented_possible = True
    
    notes = []
    if our_safer:
        notes.append(f"We would have recommended {prediction.get('adjustment_factor', 1.0)*100:.0f}% dose")
    if outcome.get("toxicity_occurred"):
        notes.append(f"Toxicity grade {outcome.get('toxicity_grade', 'N/A')} occurred")
    
    return {
        "matched_clinical_decision": matched,
        "our_recommendation_safer": our_safer,
        "prevented_toxicity_possible": prevented_possible,
        "notes": "; ".join(notes) if notes else "Standard care matched"
    }


# ============================================================================
# Complete Workflow
# ============================================================================

def run_complete_validation_workflow(
    genes: List[str] = PHARMACOGENES,
    cbioportal_studies: Optional[List[str]] = None,
    gdc_projects: List[str] = ["TCGA-COAD"],
    max_pubmed: int = 30,
    api_base: str = DOSING_API_BASE,
    skip_extraction: bool = False,
    extraction_file: Optional[str] = None
) -> Dict:
    """Run complete validation workflow."""
    print("\n" + "="*80)
    print("COMPLETE DOSING GUIDANCE VALIDATION WORKFLOW")
    print("="*80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Step 1: Extract cases (or load from file)
    if skip_extraction and extraction_file:
        print(f"\n📁 Loading cases from: {extraction_file}")
        with open(extraction_file, 'r') as f:
            extraction_results = json.load(f)
    else:
        print("\n📊 STEP 1: Extracting cases from all sources...")
        extraction_results = run_unified_extraction(
            genes=genes,
            cbioportal_studies=cbioportal_studies,
            gdc_projects=gdc_projects,
            max_pubmed=max_pubmed
        )
    
    # Combine all cases
    all_cases = []
    all_cases.extend(extraction_results["sources"]["pubmed"])
    all_cases.extend(extraction_results["sources"]["cbioportal"])
    all_cases.extend(extraction_results["sources"]["gdc"])
    
    print(f"\n📊 Total cases extracted: {len(all_cases)}")
    
    # Step 2: Run through dosing guidance API
    enriched_cases = run_all_cases_through_api(all_cases, api_base)
    
    # Step 3: Assess concordance for each case
    print(f"\n{'='*60}")
    print("STEP 3: Assessing Concordance")
    print('='*60)
    
    for case in enriched_cases:
        case["concordance"] = assess_concordance(case)
    
    # Step 4: Calculate metrics
    print(f"\n{'='*60}")
    print("STEP 4: Calculating Validation Metrics")
    print('='*60)
    
    # Convert to format expected by metrics calculator
    metrics_cases = []
    for case in enriched_cases:
        if case.get("our_prediction"):
            metrics_cases.append({
                "case_id": case.get("case_id", "unknown"),
                "gene": case.get("gene", "unknown"),
                "our_risk_level": case["our_prediction"].get("risk_level", "UNKNOWN"),
                "our_adjustment_factor": case["our_prediction"].get("adjustment_factor", 1.0),
                "toxicity_occurred": case.get("outcome", {}).get("toxicity_occurred", False),
                "concordance": case.get("concordance", {}).get("matched_clinical_decision", False)
            })
    
    # Calculate metrics using the function from calculate_validation_metrics
    metrics = calculate_metrics(metrics_cases)
    
    # Step 5: Generate final report
    print(f"\n{'='*60}")
    print("STEP 5: Generating Final Report")
    print('='*60)
    
    report_data = {
        "validation_date": datetime.now().isoformat(),
        "total_cases": len(enriched_cases),
        "cases_with_predictions": len(metrics_cases),
        "metrics": metrics,
        "cases": enriched_cases
    }
    
    return report_data


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Complete dosing guidance validation workflow")
    parser.add_argument("--genes", nargs="+", default=PHARMACOGENES, help="Pharmacogenes to validate")
    parser.add_argument("--cbioportal-studies", nargs="+", help="cBioPortal study IDs")
    parser.add_argument("--gdc-projects", nargs="+", default=["TCGA-COAD"], help="GDC project IDs")
    parser.add_argument("--max-pubmed", type=int, default=30, help="Max PubMed results per gene")
    parser.add_argument("--api-base", type=str, default=DOSING_API_BASE, help="Dosing guidance API base URL")
    parser.add_argument("--skip-extraction", action="store_true", help="Skip extraction, use existing file")
    parser.add_argument("--extraction-file", type=str, help="Path to existing extraction results JSON")
    parser.add_argument("--output", type=str, default="validation_report.json", help="Output file")
    parser.add_argument("--report", type=str, default="validation_report.md", help="Markdown report file")
    
    args = parser.parse_args()
    
    # Run workflow
    results = run_complete_validation_workflow(
        genes=args.genes,
        cbioportal_studies=args.cbioportal_studies,
        gdc_projects=args.gdc_projects,
        max_pubmed=args.max_pubmed,
        api_base=args.api_base,
        skip_extraction=args.skip_extraction,
        extraction_file=args.extraction_file
    )
    
    # Save JSON results
    output_path = Path(__file__).parent / args.output
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Results saved to: {output_path}")
    
    # Generate markdown report
    report_path = Path(__file__).parent / args.report
    generate_report(results["metrics"], str(report_path))
    print(f"📄 Report saved to: {report_path}")
    
    # Print summary
    print("\n" + "="*80)
    print("VALIDATION COMPLETE")
    print("="*80)
    print(f"Total cases: {results['total_cases']}")
    print(f"Cases with predictions: {results['cases_with_predictions']}")
    print(f"Concordance rate: {results['metrics'].get('concordance_rate', 0)*100:.1f}%")
    print(f"Sensitivity: {results['metrics'].get('sensitivity', 0)*100:.1f}%")
    print(f"Specificity: {results['metrics'].get('specificity', 0)*100:.1f}%")
    print("="*80)


if __name__ == "__main__":
    main()

