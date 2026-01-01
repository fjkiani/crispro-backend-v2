#!/usr/bin/env python3
"""
Manual Review Helper for Dosing Guidance Validation Cases

This script helps you manually review cases that need toxicity outcome data.
It provides an interactive interface to:
1. View cases needing review
2. Mark toxicity_occurred (true/false)
3. Update concordance fields
4. Save updates and re-run validation

Usage:
    python3 manual_review_helper.py [--case-id CASE_ID] [--gene GENE] [--source SOURCE]
"""

import json
import sys
import argparse
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any, Optional

# Configuration
CURATED_FILE = "extraction_all_genes_curated.json"
BACKUP_FILE = "extraction_all_genes_curated.backup.json"

def load_curated_data() -> Dict:
    """Load the curated cases file."""
    with open(CURATED_FILE, 'r') as f:
        return json.load(f)

def save_curated_data(data: Dict) -> None:
    """Save curated data with backup."""
    # Create backup
    if Path(CURATED_FILE).exists():
        with open(CURATED_FILE, 'r') as f:
            backup_data = json.load(f)
        with open(BACKUP_FILE, 'w') as f:
            json.dump(backup_data, f, indent=2)
        print(f"✅ Backup created: {BACKUP_FILE}")
    
    # Save updated data
    with open(CURATED_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"✅ Saved updates to: {CURATED_FILE}")

def get_cases_needing_review(data: Dict, case_id: Optional[str] = None, 
                            gene: Optional[str] = None, 
                            source: Optional[str] = None) -> List[Dict]:
    """Get cases that need manual review."""
    cases = data.get('cases', [])
    
    # Filter cases needing review
    needs_review = []
    for case in cases:
        # Check if needs review
        status = case.get('status', '')
        toxicity = case.get('toxicity_occurred')
        
        needs_review_flag = (
            status == 'needs_manual_review' or 
            toxicity is None or
            (toxicity is False and case.get('source') != 'pubmed')  # GDC/cBioPortal defaults
        )
        
        if not needs_review_flag:
            continue
        
        # Apply filters
        if case_id and case.get('case_id') != case_id:
            continue
        if gene and case.get('gene', '').upper() != gene.upper():
            continue
        if source and case.get('source', '').lower() != source.lower():
            continue
        
        needs_review.append(case)
    
    return needs_review

def display_case(case: Dict, index: int, total: int) -> None:
    """Display a single case for review."""
    print("\n" + "="*70)
    print(f"CASE {index + 1} of {total}".center(70))
    print("="*70)
    print(f"Case ID: {case.get('case_id', 'N/A')}")
    print(f"Source: {case.get('source', 'N/A').upper()}")
    print(f"Gene: {case.get('gene', 'N/A')}")
    print(f"Variant: {case.get('variant', 'N/A')}")
    print(f"Drug: {case.get('drug', 'N/A')}")
    print(f"Status: {case.get('status', 'N/A')}")
    print()
    
    # Show available data
    if case.get('source') == 'pubmed':
        print("📄 PubMed Data:")
        print(f"   PMID: {case.get('pmid', 'N/A')}")
        title = case.get('title') or case.get('fetched_title', 'N/A')
        abstract = case.get('abstract') or case.get('fetched_abstract', 'N/A')
        print(f"   Title: {title[:100]}..." if len(title) > 100 else f"   Title: {title}")
        if abstract and abstract != 'N/A':
            print(f"   Abstract: {abstract[:300]}..." if len(abstract) > 300 else f"   Abstract: {abstract}")
    else:
        print("📊 Genomic Data:")
        print(f"   Study: {case.get('study_id', 'N/A')}")
        print(f"   Patient ID: {case.get('patient_id', 'N/A')}")
        print(f"   Variant Details: {json.dumps(case.get('variant_details', {}), indent=6)}")
    
    print()
    
    # Show current prediction
    prediction = case.get('our_prediction', {})
    if prediction:
        print("🤖 Our Prediction:")
        print(f"   Would Flag: {prediction.get('would_have_flagged', False)}")
        print(f"   Adjustment Factor: {prediction.get('adjustment_factor', 1.0)}")
        print(f"   Risk Level: {prediction.get('risk_level', 'N/A')}")
        print(f"   CPIC Level: {prediction.get('cpic_level', 'N/A')}")
    
    print()
    
    # Show current curation
    print("📝 Current Curation:")
    toxicity = case.get('toxicity_occurred')
    print(f"   Toxicity Occurred: {toxicity} ({'✅ Set' if toxicity is not None else '❌ Not Set'})")
    concordance = case.get('concordance', {})
    print(f"   Matched Clinical Decision: {concordance.get('matched_clinical_decision', False)}")
    print(f"   Our Recommendation Safer: {concordance.get('our_recommendation_safer', False)}")
    print(f"   Notes: {concordance.get('notes', 'N/A')}")

def review_case_interactive(case: Dict) -> Dict:
    """Interactive review of a single case."""
    print("\n" + "="*70)
    print("MANUAL REVIEW".center(70))
    print("="*70)
    
    # Question 1: Did toxicity occur?
    print("\n❓ Did toxicity occur in this case?")
    print("   [y] Yes - toxicity occurred")
    print("   [n] No - no toxicity occurred")
    print("   [s] Skip - cannot determine")
    print("   [q] Quit review")
    
    response = input("\nYour answer: ").strip().lower()
    
    if response == 'q':
        return None  # Signal to quit
    elif response == 's':
        case['toxicity_occurred'] = None
        case['status'] = 'skipped_manual_review'
        return case
    elif response == 'y':
        case['toxicity_occurred'] = True
    elif response == 'n':
        case['toxicity_occurred'] = False
    else:
        print("⚠️  Invalid response. Skipping case.")
        return case
    
    # Question 2: Concordance assessment
    prediction = case.get('our_prediction', {})
    we_would_flag = prediction.get('would_have_flagged', False)
    toxicity = case.get('toxicity_occurred')
    
    print("\n❓ Did our prediction match the clinical decision?")
    if toxicity:
        if we_would_flag:
            print("   ✅ Our system WOULD have flagged (recommended dose reduction)")
            print("   ✅ Toxicity occurred")
            print("   → This is CONCORDANT (we caught it)")
        else:
            print("   ❌ Our system would NOT have flagged")
            print("   ⚠️  Toxicity occurred")
            print("   → This is a MISSED OPPORTUNITY (we should have caught it)")
    else:
        if not we_would_flag:
            print("   ✅ Our system would NOT have flagged")
            print("   ✅ No toxicity occurred")
            print("   → This is CONCORDANT (correct negative)")
        else:
            print("   ⚠️  Our system WOULD have flagged")
            print("   ✅ No toxicity occurred")
            print("   → This is a FALSE POSITIVE (we flagged unnecessarily)")
    
    print("\n   [y] Yes - matched clinical decision")
    print("   [n] No - did not match")
    print("   [s] Skip")
    
    concordance_response = input("\nYour answer: ").strip().lower()
    
    if concordance_response == 'y':
        matched = True
        our_safer = False
        prevented = False
    elif concordance_response == 'n':
        matched = False
        # Determine if our recommendation was safer
        if toxicity and not we_would_flag:
            our_safer = True
            prevented = True
        else:
            our_safer = False
            prevented = False
    else:
        matched = False
        our_safer = False
        prevented = False
    
    # Question 3: Additional notes
    print("\n❓ Any additional notes? (Press Enter to skip)")
    notes = input("Notes: ").strip()
    
    # Update concordance
    existing_notes = case.get('concordance', {}).get('notes', '')
    if notes:
        final_notes = f"{existing_notes}; {notes}" if existing_notes else notes
    else:
        final_notes = existing_notes
    
    case['concordance'] = {
        "matched_clinical_decision": matched,
        "our_recommendation_safer": our_safer,
        "prevented_toxicity_possible": prevented,
        "notes": final_notes
    }
    
    # Update status
    case['status'] = 'manually_reviewed'
    case['curated_date'] = datetime.now().isoformat()
    case['curated_by'] = 'manual_review'
    
    return case

def batch_update_mode(cases: List[Dict], data: Dict) -> None:
    """Batch update mode - review all cases one by one."""
    print(f"\n📋 Found {len(cases)} cases needing review")
    print("Starting interactive review...")
    print("(Press 'q' at any time to quit and save progress)\n")
    
    updated_count = 0
    skipped_count = 0
    
    for i, case in enumerate(cases):
        display_case(case, i, len(cases))
        
        updated_case = review_case_interactive(case)
        
        if updated_case is None:
            print("\n⚠️  Review interrupted. Saving progress...")
            break
        elif updated_case.get('status') == 'skipped_manual_review':
            skipped_count += 1
        else:
            updated_count += 1
        
        # Update in data
        case_id = case.get('case_id')
        for j, c in enumerate(data['cases']):
            if c.get('case_id') == case_id:
                data['cases'][j] = updated_case
                break
    
    # Save updates
    save_curated_data(data)
    
    print(f"\n✅ Review complete!")
    print(f"   Updated: {updated_count} cases")
    print(f"   Skipped: {skipped_count} cases")
    print(f"   Remaining: {len(cases) - updated_count - skipped_count} cases")

def summary_mode(data: Dict) -> None:
    """Display summary of cases needing review."""
    cases = data.get('cases', [])
    needs_review = get_cases_needing_review(data)
    
    print("\n" + "="*70)
    print("MANUAL REVIEW SUMMARY".center(70))
    print("="*70)
    print(f"\n📊 Total Cases: {len(cases)}")
    print(f"📊 Cases Needing Review: {len(needs_review)}")
    print()
    
    # Breakdown by source
    by_source = {}
    by_gene = {}
    by_status = {}
    
    for case in needs_review:
        source = case.get('source', 'unknown')
        gene = case.get('gene', 'unknown')
        status = case.get('status', 'unknown')
        
        by_source[source] = by_source.get(source, 0) + 1
        by_gene[gene] = by_gene.get(gene, 0) + 1
        by_status[status] = by_status.get(status, 0) + 1
    
    print("📋 Breakdown by Source:")
    for source, count in sorted(by_source.items()):
        print(f"   {source.upper()}: {count}")
    
    print("\n📋 Breakdown by Gene:")
    for gene, count in sorted(by_gene.items()):
        print(f"   {gene}: {count}")
    
    print("\n📋 Breakdown by Status:")
    for status, count in sorted(by_status.items()):
        print(f"   {status}: {count}")
    
    print("\n💡 To review cases, run:")
    print("   python3 manual_review_helper.py --interactive")
    print("\n   Or filter by:")
    print("   python3 manual_review_helper.py --interactive --gene DPYD")
    print("   python3 manual_review_helper.py --interactive --source cbioportal")

def main():
    parser = argparse.ArgumentParser(description="Manual review helper for dosing guidance validation")
    parser.add_argument('--interactive', action='store_true', help='Start interactive review mode')
    parser.add_argument('--summary', action='store_true', help='Show summary of cases needing review')
    parser.add_argument('--case-id', type=str, help='Review specific case ID')
    parser.add_argument('--gene', type=str, help='Filter by gene (e.g., DPYD, UGT1A1)')
    parser.add_argument('--source', type=str, help='Filter by source (pubmed, cbioportal, gdc)')
    
    args = parser.parse_args()
    
    # Load data
    if not Path(CURATED_FILE).exists():
        print(f"❌ Error: {CURATED_FILE} not found!")
        sys.exit(1)
    
    data = load_curated_data()
    
    # Show summary by default
    if not args.interactive:
        summary_mode(data)
        return
    
    # Interactive mode
    cases = get_cases_needing_review(data, args.case_id, args.gene, args.source)
    
    if not cases:
        print("✅ No cases need review!")
        return
    
    batch_update_mode(cases, data)

if __name__ == "__main__":
    main()

