#!/usr/bin/env python3
"""
Dosing Guidance Validation - Offline Workflow
================================================

Runs validation by directly importing the dosing guidance service,
bypassing the API. This works even when the backend isn't running.

Author: Zo (Agent)
Created: January 2025
"""

import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "oncology-coPilot" / "oncology-backend-minimal"))

# Import dosing guidance service directly
from api.services.dosing_guidance_service import DosingGuidanceService
from api.schemas.dosing import DosingGuidanceRequest

# Import metrics calculator
sys.path.insert(0, str(Path(__file__).parent))
from calculate_validation_metrics import calculate_metrics, generate_report

# ============================================================================
# Configuration
# ============================================================================

PHARMACOGENES = ['DPYD', 'UGT1A1', 'TPMT']

# Drug mapping
DRUG_MAPPING = {
    "DPYD": "5-fluorouracil",
    "UGT1A1": "irinotecan",
    "TPMT": "6-mercaptopurine"
}

# ============================================================================
# Text Extraction Functions
# ============================================================================

import re

def extract_variant_from_text(text: str, gene: str) -> Optional[str]:
    """Extract variant notation from title/abstract text."""
    if not text or not gene:
        return None
    
    gene_upper = gene.upper()
    text_upper = text.upper()
    
    # Pattern 1: "DPYD c.2846A>T" (gene followed by c. notation)
    pattern1 = rf"{gene_upper}.*?c\.([0-9]+[A-Za-z]?[+\-]?[0-9]*[A-Za-z]?[<>]?[A-Za-z]?)"
    match1 = re.search(pattern1, text_upper, re.IGNORECASE)
    if match1:
        return f"c.{match1.group(1)}"
    
    # Pattern 2: "DPYD *2A" (gene followed by star allele)
    pattern2 = rf"{gene_upper}.*?\*([0-9]+[A-Za-z]?)"
    match2 = re.search(pattern2, text_upper, re.IGNORECASE)
    if match2:
        return f"*{match2.group(1)}"
    
    # Pattern 3: "c.2846A>T" near gene name (within 100 chars, fallback)
    pattern3 = r"c\.([0-9]+[A-Za-z]?[+\-]?[0-9]*[A-Za-z]?[<>]?[A-Za-z]?)"
    matches3 = re.finditer(pattern3, text_upper)
    for match in matches3:
        start = max(0, match.start() - 100)
        end = min(len(text), match.end() + 100)
        context = text_upper[start:end]
        if gene_upper in context:
            return f"c.{match.group(1)}"
    
    # Pattern 4: Clinical deficiency mention (for safety-critical flagging)
    # "DPYD deficiency", "DPD deficiency", "dihydropyrimidine dehydrogenase deficiency"
    if gene_upper == "DPYD":
        deficiency_patterns = [
            r"DPYD.*?DEFICIENCY",
            r"DPD.*?DEFICIENCY",
            r"DIHYDROPYRIMIDINE.*?DEHYDROGENASE.*?DEFICIENCY",
        ]
        for pattern in deficiency_patterns:
            if re.search(pattern, text_upper):
                return "DEFICIENCY"  # Special marker for deficiency
    
    return None

def extract_drug_from_text(text: str) -> Optional[str]:
    """Extract drug name from title/abstract text."""
    if not text:
        return None
    
    text_lower = text.lower()
    
    drug_keywords = {
        "5-fluorouracil": ["5-fluorouracil", "5-fu", "fluorouracil"],
        "capecitabine": ["capecitabine", "xeloda"],
        "irinotecan": ["irinotecan", "camptosar", "cpt-11"],
        "mercaptopurine": ["mercaptopurine", "6-mp", "6mp"],
        "azathioprine": ["azathioprine", "imuran"],
        "thioguanine": ["thioguanine", "6-tg", "6tg"],
    }
    
    for drug, keywords in drug_keywords.items():
        for keyword in keywords:
            if keyword in text_lower:
                return drug
    
    return None

def enrich_case_with_text_extraction(case: Dict) -> Dict:
    """Extract variant and drug from text if not present."""
    gene = case.get('gene', '')
    variant = case.get('variant')
    drug = case.get('drug')
    
    # Check if variant/drug need extraction
    needs_variant = not variant or str(variant).upper() in ['N/A', 'NONE', 'NULL', '']
    needs_drug = not drug or str(drug).upper() in ['N/A', 'NONE', 'NULL', '']
    
    if needs_variant or needs_drug:
        title = case.get('fetched_title', '') or case.get('title', '')
        abstract = case.get('fetched_abstract', '') or case.get('abstract', '')
        text = f"{title} {abstract}"
        
        if needs_variant and gene:
            extracted_variant = extract_variant_from_text(text, gene)
            if extracted_variant:
                case['variant'] = extracted_variant
        
        if needs_drug:
            extracted_drug = extract_drug_from_text(text)
            if extracted_drug:
                case['drug'] = extracted_drug
    
    return case


# ============================================================================
# Variant Mapping
# ============================================================================

def map_variant_to_diplotype(gene: str, variant: str) -> str:
    """Map variant notation to diplotype format."""
    variant_upper = str(variant).upper() if variant else ""
    gene_upper = gene.upper() if gene else ""
    
    # If already a star allele, return as-is
    if "*" in variant_upper:
        # Ensure proper format: *1/*X for heterozygous, *X/*X for homozygous
        if "/" in variant:
            return variant
        else:
            # Single allele - assume heterozygous with *1
            return f"*1/{variant}"
    
    if "DPYD" in gene_upper:
        # DPYD high-risk variants (CPIC Level A evidence)
        # c.1905+1G>A = *2A (no activity)
        if "1905+1G>A" in variant_upper or "1905+1G" in variant_upper:
            return "*1/*2A"  # Heterozygous - 50% reduction
        # c.1679T>G = *13 (no activity)
        elif "1679T>G" in variant_upper:
            return "*1/*13"  # Heterozygous - 50% reduction
        # c.2846A>T = D949V (reduced activity)
        elif "2846A>T" in variant_upper or "D949V" in variant_upper:
            return "*1/*D949V"  # Heterozygous - 25-50% reduction
        # c.1236G>A = E412E (reduced activity)
        elif "1236G>A" in variant_upper:
            return "*1/*5"  # Reduced activity
        # c.2872A>G (compound heterozygous with others = high risk)
        elif "2872A>G" in variant_upper:
            return "*2A/*2A"  # Treat as high risk
        # c.1903A>G (also known as c.1903+1G>A in some papers - high risk)
        elif "1903" in variant_upper:
            return "*1/*2A"  # Treat as high risk variant
        # Clinical deficiency mentioned - treat as high risk
        elif "DEFICIENCY" in variant_upper:
            return "*2A/*2A"  # DPD deficiency = avoid drug
        # For unknown DPYD variants, default to normal (conservative approach)
        # Only flag for known high-risk variants
        else:
            return "*1/*1"  # Normal for unknown variants
    
    elif "UGT1A1" in gene_upper:
        if "*28" in variant_upper or "(TA)7" in variant_upper or "TA7" in variant_upper:
            return "*28/*28"  # Homozygous - 30% reduction
        elif "*6" in variant_upper:
            return "*1/*6"  # Heterozygous
        else:
            return "*1/*1"  # Normal for unknown variants
    
    elif "TPMT" in gene_upper:
        if "*3A" in variant_upper:
            return "*1/*3A"  # Heterozygous - 50% reduction
        elif "*3B" in variant_upper:
            return "*1/*3B"
        elif "*3C" in variant_upper:
            return "*1/*3C"
        elif "*2" in variant_upper:
            return "*1/*2"
        else:
            return "*1/*1"  # Normal for unknown variants
    
    return "*1/*1"  # Default to normal


def get_drug_for_gene(gene: str) -> str:
    """Get default drug for a pharmacogene."""
    return DRUG_MAPPING.get(gene.upper(), "unknown")


# ============================================================================
# Run Case Through Service
# ============================================================================

async def run_case_through_service(case: Dict, service: DosingGuidanceService) -> Optional[Dict]:
    """Run a single case through the dosing guidance service."""
    # Enrich case with text extraction if variant/drug are missing
    case = enrich_case_with_text_extraction(case)
    
    gene = case.get("gene", "").upper()
    variant = case.get("variant", "") or ""
    drug = case.get("drug") or get_drug_for_gene(gene)
    
    # Map variant to diplotype
    diplotype = map_variant_to_diplotype(gene, variant)
    
    # Build request
    request = DosingGuidanceRequest(
        gene=gene,
        variant=diplotype,
        drug=drug,
        treatment_line=case.get("treatment_line", 1),
        prior_therapies=case.get("prior_therapies", []),
        standard_dose=case.get("standard_dose")
    )
    
    try:
        response = await service.get_dosing_guidance(request)
        
        # Extract predictions
        recommendations = response.recommendations
        if recommendations:
            rec = recommendations[0]
            adj_factor = rec.adjustment_factor if rec.adjustment_factor is not None else 1.0
            return {
                "recommended_dose": rec.recommendation or "N/A",
                "adjustment_factor": adj_factor,
                "risk_level": "HIGH" if adj_factor < 0.5 else "MODERATE" if adj_factor < 1.0 else "LOW",
                "would_have_flagged": adj_factor < 1.0,
                "alternatives": rec.alternatives or [],
                "cpic_level": rec.cpic_level.value if rec.cpic_level else "UNKNOWN",
                "adjustment_type": rec.adjustment_type.value if rec.adjustment_type else "UNKNOWN"
            }
        else:
            return {
                "recommended_dose": "N/A",
                "adjustment_factor": 1.0,
                "risk_level": "UNKNOWN",
                "would_have_flagged": False,
                "alternatives": [],
                "cpic_level": "UNKNOWN"
            }
    except Exception as e:
        print(f"  ⚠️  Service call failed for {case.get('case_id', 'unknown')}: {type(e).__name__}: {e}")
        import traceback
        if "recommended_dose" in str(e):
            traceback.print_exc()
        return None


async def run_all_cases_through_service(cases: List[Dict]) -> List[Dict]:
    """Run all cases through dosing guidance service."""
    print(f"\n{'='*60}")
    print("STEP 2: Running Cases Through Dosing Guidance Service")
    print('='*60)
    print(f"Total cases: {len(cases)}")
    
    service = DosingGuidanceService()
    enriched_cases = []
    
    for i, case in enumerate(cases, 1):
        if i % 10 == 0:
            print(f"  Processing {i}/{len(cases)}...")
        
        prediction = await run_case_through_service(case, service)
        
        if prediction:
            case["our_prediction"] = prediction
            enriched_cases.append(case)
        else:
            case["our_prediction"] = None
            case["api_error"] = True
            enriched_cases.append(case)
    
    print(f"\n  ✅ Processed {len(enriched_cases)} cases")
    print(f"  ✅ Successful predictions: {sum(1 for c in enriched_cases if c.get('our_prediction'))}")
    
    return enriched_cases


# ============================================================================
# Assess Concordance
# ============================================================================

def assess_concordance(case: Dict) -> Dict:
    """Compare our prediction with actual clinical decision."""
    prediction = case.get("our_prediction")
    
    # Check if case already has curated concordance data
    if "concordance_details" in case and case.get("toxicity_occurred") is not None:
        # Use curated data
        curated = case["concordance_details"]
        return {
            "matched_clinical_decision": curated.get("concordant", False),
            "our_recommendation_safer": curated.get("our_recommendation_safer", False),
            "prevented_toxicity_possible": curated.get("prevented_toxicity_possible", False),
            "notes": curated.get("notes", "Curated data")
        }
    
    # Fallback to original logic if no curated data
    treatment = case.get("treatment", {})
    outcome = case.get("outcome", {})
    
    if not prediction:
        return {
            "matched_clinical_decision": False,
            "our_recommendation_safer": False,
            "prevented_toxicity_possible": False,
            "notes": "No prediction available"
        }
    
    # Check for curated toxicity_occurred field
    toxicity_occurred = case.get("toxicity_occurred") if "toxicity_occurred" in case else outcome.get("toxicity_occurred", False)
    
    # Did clinical match our recommendation?
    clinical_adjusted = treatment.get("dose_adjustment_made", False)
    we_would_adjust = prediction.get("adjustment_factor", 1.0) < 1.0 or prediction.get("would_have_flagged", False)
    matched = clinical_adjusted == we_would_adjust
    
    # Would we have been safer?
    our_safer = False
    prevented_possible = False
    
    if toxicity_occurred:
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

async def run_complete_validation_offline(
    extraction_file: str,
    output_file: str = "validation_report.json",
    report_file: str = "validation_report.md"
) -> Dict:
    """Run complete validation workflow offline."""
    print("\n" + "="*80)
    print("OFFLINE DOSING GUIDANCE VALIDATION WORKFLOW")
    print("="*80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    
    # Load extraction results
    print(f"\n📁 Loading cases from: {extraction_file}")
    with open(extraction_file, 'r') as f:
        extraction_results = json.load(f)
    
    # Handle both original extraction format and curated format
    if "cases" in extraction_results:
        # Curated format - cases already combined
        print("📋 Detected curated format (cases list)")
        all_cases = extraction_results["cases"]
    elif "sources" in extraction_results:
        # Original format - combine from sources
        print("📋 Detected original format (sources dict)")
        all_cases = []
        all_cases.extend(extraction_results["sources"].get("pubmed", []))
        all_cases.extend(extraction_results["sources"].get("cbioportal", []))
        all_cases.extend(extraction_results["sources"].get("gdc", []))
    else:
        raise ValueError(f"Unknown file format: expected 'cases' or 'sources' key")
    
    print(f"📊 Total cases loaded: {len(all_cases)}")
    
    # Run through service
    enriched_cases = await run_all_cases_through_service(all_cases)
    
    # Assess concordance
    print(f"\n{'='*60}")
    print("STEP 3: Assessing Concordance")
    print('='*60)
    
    for case in enriched_cases:
        case["concordance"] = assess_concordance(case)
    
    # Calculate metrics
    print(f"\n{'='*60}")
    print("STEP 4: Calculating Validation Metrics")
    print('='*60)
    
    # Convert to format expected by metrics calculator
    metrics_cases = []
    for case in enriched_cases:
        if case.get("our_prediction"):
            # Check toxicity_occurred at case level (curated format) or outcome level (original format)
            toxicity = case.get("toxicity_occurred")
            if toxicity is None:
                toxicity = case.get("outcome", {}).get("toxicity_occurred", False)
            
            metrics_cases.append({
                "case_id": case.get("case_id", "unknown"),
                "gene": case.get("gene", "unknown"),
                "our_risk_level": case["our_prediction"].get("risk_level", "UNKNOWN"),
                "our_adjustment_factor": case["our_prediction"].get("adjustment_factor", 1.0),
                "toxicity_occurred": toxicity,
                "concordance": case.get("concordance", {}).get("matched_clinical_decision", False),
                "our_prediction": case.get("our_prediction", {})
            })
    
    metrics = calculate_metrics(metrics_cases)
    
    # Generate report
    print(f"\n{'='*60}")
    print("STEP 5: Generating Final Report")
    print('='*60)
    
    report_data = {
        "validation_date": datetime.now().isoformat(),
        "validation_mode": "offline",
        "total_cases": len(enriched_cases),
        "cases_with_predictions": len(metrics_cases),
        "metrics": metrics,
        "cases": enriched_cases
    }
    
    # Save JSON
    output_path = Path(__file__).parent / output_file
    with open(output_path, 'w') as f:
        json.dump(report_data, f, indent=2, default=str)
    print(f"📄 Results saved to: {output_path}")
    
    # Generate markdown report
    report_path = Path(__file__).parent / report_file
    generate_report(metrics, str(report_path))
    print(f"📄 Report saved to: {report_path}")
    
    return report_data


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Offline dosing guidance validation workflow")
    parser.add_argument("--extraction-file", type=str, default="extraction_all_genes.json",
                        help="Path to extraction results JSON")
    parser.add_argument("--output", type=str, default="validation_report.json",
                        help="Output JSON file")
    parser.add_argument("--report", type=str, default="validation_report.md",
                        help="Markdown report file")
    
    args = parser.parse_args()
    
    # Run workflow
    results = asyncio.run(run_complete_validation_offline(
        extraction_file=args.extraction_file,
        output_file=args.output,
        report_file=args.report
    ))
    
    # Print summary
    print("\n" + "="*80)
    print("VALIDATION COMPLETE")
    print("="*80)
    print(f"Total cases: {results['total_cases']}")
    print(f"Cases with predictions: {results['cases_with_predictions']}")
    if results['metrics']:
        print(f"Concordance rate: {results['metrics'].get('concordance_rate', 0)*100:.1f}%")
        print(f"Sensitivity: {results['metrics'].get('sensitivity', 0)*100:.1f}%")
        print(f"Specificity: {results['metrics'].get('specificity', 0)*100:.1f}%")
    print("="*80)


if __name__ == "__main__":
    main()

