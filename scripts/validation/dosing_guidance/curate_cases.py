#!/usr/bin/env python3
"""
Curate validation cases by adding toxicity_occurred and concordance fields.

This script:
1. Fetches PubMed abstracts for PubMed cases
2. Analyzes abstracts for toxicity keywords
3. Determines toxicity_occurred based on case data
4. Calculates concordance based on our predictions
5. Saves curated data
"""

import json
import sys
import os
from typing import Dict, List, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../'))

import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET

PUBMED_AVAILABLE = True

# Toxicity keywords for abstract analysis
TOXICITY_KEYWORDS = [
    'toxicity', 'toxic', 'adverse', 'side effect', 'severe', 'grade 3', 'grade 4',
    'neutropenia', 'thrombocytopenia', 'diarrhea', 'mucositis', 'hand-foot syndrome',
    'dose reduction', 'dose reduction', 'treatment discontinuation', 'hospitalization',
    'death', 'fatal', 'lethal', 'life-threatening'
]

# Gene-specific toxicity patterns
GENE_TOXICITY_PATTERNS = {
    'DPYD': ['fluoropyrimidine toxicity', '5-fu toxicity', 'capecitabine toxicity', 'severe diarrhea'],
    'UGT1A1': ['irinotecan toxicity', 'severe neutropenia', 'diarrhea', 'irinotecan-induced'],
    'TPMT': ['mercaptopurine toxicity', '6-mp toxicity', 'azathioprine toxicity', 'myelosuppression']
}


def fetch_pubmed_abstract(pmid: str) -> Optional[Dict]:
    """Fetch abstract for a PubMed ID using NCBI E-utils."""
    if not PUBMED_AVAILABLE:
        return None
    
    try:
        # Use NCBI E-utils efetch API
        base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        params = {
            'db': 'pubmed',
            'id': pmid,
            'retmode': 'xml',
            'rettype': 'abstract'
        }
        
        url = f"{base_url}?{urllib.parse.urlencode(params)}"
        
        with urllib.request.urlopen(url, timeout=10) as response:
            xml_data = response.read()
        
        # Parse XML
        root = ET.fromstring(xml_data)
        
        # Extract title and abstract
        title = ""
        abstract = ""
        
        # Find PubmedArticle
        article = root.find('.//PubmedArticle')
        if article is not None:
            # Get title
            title_elem = article.find('.//ArticleTitle')
            if title_elem is not None:
                title = ''.join(title_elem.itertext()).strip()
            
            # Get abstract
            abstract_elem = article.find('.//AbstractText')
            if abstract_elem is not None:
                abstract = ''.join(abstract_elem.itertext()).strip()
        
        if not abstract and not title:
            return None
        
        return {
            'pmid': pmid,
            'title': title,
            'abstract': abstract
        }
    except Exception as e:
        print(f"  ⚠️  Failed to fetch PMID {pmid}: {e}")
        return None


def analyze_toxicity_from_abstract(abstract: str, gene: str) -> Dict:
    """
    Analyze abstract for toxicity indicators.
    Returns dict with toxicity_occurred, severity, and evidence.
    """
    abstract_lower = abstract.lower()
    
    # Check for gene-specific patterns
    gene_patterns = GENE_TOXICITY_PATTERNS.get(gene, [])
    gene_specific_hits = sum(1 for pattern in gene_patterns if pattern in abstract_lower)
    
    # Check for general toxicity keywords
    general_hits = sum(1 for keyword in TOXICITY_KEYWORDS if keyword in abstract_lower)
    
    # Strong indicators
    strong_indicators = ['grade 3', 'grade 4', 'severe', 'life-threatening', 'fatal', 'death']
    has_strong_indicator = any(indicator in abstract_lower for indicator in strong_indicators)
    
    # Determine toxicity_occurred
    # If gene-specific pattern + general toxicity keywords, likely toxicity occurred
    if gene_specific_hits > 0 and (general_hits >= 2 or has_strong_indicator):
        toxicity_occurred = True
        confidence = 'high' if has_strong_indicator else 'moderate'
    elif general_hits >= 3:
        toxicity_occurred = True
        confidence = 'moderate'
    elif gene_specific_hits > 0:
        toxicity_occurred = True
        confidence = 'low'
    else:
        toxicity_occurred = False
        confidence = 'low'
    
    return {
        'toxicity_occurred': toxicity_occurred,
        'confidence': confidence,
        'gene_specific_hits': gene_specific_hits,
        'general_hits': general_hits,
        'has_strong_indicator': has_strong_indicator
    }


def determine_concordance(case: Dict, prediction: Dict) -> Dict:
    """
    Determine if our prediction was concordant with clinical decision.
    
    Concordance means:
    - If toxicity occurred AND we flagged (would_have_flagged=True) → CONCORDANT
    - If toxicity occurred AND we didn't flag → NOT CONCORDANT (missed case)
    - If no toxicity AND we didn't flag → CONCORDANT
    - If no toxicity AND we flagged → NOT CONCORDANT (false positive)
    """
    toxicity_occurred = case.get('toxicity_occurred', False)
    would_have_flagged = prediction.get('would_have_flagged', False)
    adjustment_factor = prediction.get('adjustment_factor', 1.0)
    
    # We "flag" if we recommend dose reduction (adjustment_factor < 1.0)
    actually_flagged = adjustment_factor < 1.0 or would_have_flagged
    
    if toxicity_occurred and actually_flagged:
        # Toxicity occurred, we would have prevented it → CONCORDANT
        concordant = True
        prevented_toxicity_possible = True
        notes = "Toxicity occurred; our prediction would have recommended dose reduction"
    elif toxicity_occurred and not actually_flagged:
        # Toxicity occurred, we didn't flag → NOT CONCORDANT (missed case)
        concordant = False
        prevented_toxicity_possible = False
        notes = "Toxicity occurred; our prediction did not recommend dose reduction (missed case)"
    elif not toxicity_occurred and not actually_flagged:
        # No toxicity, we didn't flag → CONCORDANT
        concordant = True
        prevented_toxicity_possible = False
        notes = "No toxicity; standard dosing appropriate"
    else:  # not toxicity_occurred and actually_flagged
        # No toxicity, we flagged → NOT CONCORDANT (false positive)
        concordant = False
        prevented_toxicity_possible = False
        notes = "No toxicity; our prediction recommended dose reduction (false positive)"
    
    return {
        'concordant': concordant,
        'prevented_toxicity_possible': prevented_toxicity_possible,
        'notes': notes,
        'toxicity_occurred': toxicity_occurred,
        'our_recommendation_safer': actually_flagged
    }


def curate_cases():
    """Main curation function."""
    print("=" * 70)
    print("DOSING GUIDANCE CASE CURATION")
    print("=" * 70)
    print()
    
    # Load extraction file
    extraction_path = 'extraction_all_genes.json'
    print(f"📂 Loading extraction file: {extraction_path}")
    with open(extraction_path, 'r') as f:
        extraction = json.load(f)
    
    # Load validation report to get predictions
    report_path = 'validation_report.json'
    print(f"📂 Loading validation report: {report_path}")
    with open(report_path, 'r') as f:
        report = json.load(f)
    
    # Create prediction lookup
    predictions_by_case_id = {c['case_id']: c.get('our_prediction', {}) for c in report.get('cases', [])}
    
    print(f"\n📊 Found {extraction['total_cases']} total cases")
    print(f"📊 Found {len(predictions_by_case_id)} predictions")
    print()
    
    curated_cases = []
    stats = {
        'pubmed_curated': 0,
        'cbioportal_curated': 0,
        'gdc_curated': 0,
        'toxicity_detected': 0,
        'concordant': 0
    }
    
    # Process PubMed cases
    print("🔬 Processing PubMed cases...")
    pubmed_cases = extraction['sources'].get('pubmed', [])
    for case in pubmed_cases:
        case_id = case['case_id']
        gene = case['gene']
        pmid = case.get('pmid')
        
        print(f"  📄 {case_id} (PMID: {pmid})")
        
        # Fetch abstract if available
        abstract_text = ""
        if pmid and PUBMED_AVAILABLE:
            abstract_data = fetch_pubmed_abstract(pmid)
            if abstract_data:
                # Combine title and abstract for analysis
                title = abstract_data.get('title', '')
                abstract = abstract_data.get('abstract', '')
                abstract_text = f"{title} {abstract}".strip()
                case['fetched_title'] = title
                case['fetched_abstract'] = abstract
        
        # Analyze for toxicity
        if abstract_text:
            toxicity_analysis = analyze_toxicity_from_abstract(abstract_text, gene)
            case['toxicity_occurred'] = toxicity_analysis['toxicity_occurred']
            case['toxicity_confidence'] = toxicity_analysis['confidence']
            case['abstract_analyzed'] = True
            if toxicity_analysis['toxicity_occurred']:
                stats['toxicity_detected'] += 1
        else:
            # No abstract - mark as needs manual review
            case['toxicity_occurred'] = None
            case['toxicity_confidence'] = 'unknown'
            case['abstract_analyzed'] = False
            print(f"    ⚠️  No abstract available - marked for manual review")
        
        # Get prediction
        prediction = predictions_by_case_id.get(case_id, {})
        
        # Determine concordance
        if case.get('toxicity_occurred') is not None:
            concordance = determine_concordance(case, prediction)
            case['concordance'] = concordance['concordant']
            case['concordance_details'] = concordance
            if concordance['concordant']:
                stats['concordant'] += 1
        else:
            case['concordance'] = None
            case['concordance_details'] = {'notes': 'Needs manual review'}
        
        case['curated_date'] = datetime.now().isoformat()
        curated_cases.append(case)
        stats['pubmed_curated'] += 1
    
    # Process cBioPortal cases
    print(f"\n🔬 Processing cBioPortal cases...")
    cbioportal_cases = extraction['sources'].get('cbioportal', [])
    for case in cbioportal_cases:
        case_id = case['case_id']
        print(f"  📄 {case_id}")
        
        # cBioPortal cases typically don't have outcome data
        case['toxicity_occurred'] = None
        case['toxicity_confidence'] = 'unknown'
        case['abstract_analyzed'] = False
        
        # Get prediction
        prediction = predictions_by_case_id.get(case_id, {})
        case['concordance'] = None
        case['concordance_details'] = {'notes': 'No outcome data available - needs manual review'}
        
        case['curated_date'] = datetime.now().isoformat()
        curated_cases.append(case)
        stats['cbioportal_curated'] += 1
    
    # Process GDC cases
    print(f"\n🔬 Processing GDC/TCGA cases...")
    gdc_cases = extraction['sources'].get('gdc', [])
    for case in gdc_cases:
        case_id = case['case_id']
        print(f"  📄 {case_id}")
        
        # GDC cases typically don't have treatment/outcome data
        case['toxicity_occurred'] = None
        case['toxicity_confidence'] = 'unknown'
        case['abstract_analyzed'] = False
        
        # Get prediction
        prediction = predictions_by_case_id.get(case_id, {})
        case['concordance'] = None
        case['concordance_details'] = {'notes': 'No outcome data available - needs manual review'}
        
        case['curated_date'] = datetime.now().isoformat()
        curated_cases.append(case)
        stats['gdc_curated'] += 1
    
    # Save curated data
    curated_output = {
        'curation_date': datetime.now().isoformat(),
        'total_cases': len(curated_cases),
        'curation_stats': stats,
        'cases': curated_cases
    }
    
    output_path = 'extraction_all_genes_curated.json'
    print(f"\n💾 Saving curated data to: {output_path}")
    with open(output_path, 'w') as f:
        json.dump(curated_output, f, indent=2)
    
    print("\n" + "=" * 70)
    print("CURATION COMPLETE")
    print("=" * 70)
    print(f"\n📊 Statistics:")
    print(f"   PubMed cases curated: {stats['pubmed_curated']}")
    print(f"   cBioPortal cases curated: {stats['cbioportal_curated']}")
    print(f"   GDC cases curated: {stats['gdc_curated']}")
    print(f"   Toxicity detected: {stats['toxicity_detected']}")
    print(f"   Concordant predictions: {stats['concordant']}")
    print(f"\n📄 Output: {output_path}")
    print("\n⚠️  Note: Cases without abstracts/outcome data marked for manual review")
    print("   Review extraction_all_genes_curated.json and add toxicity_occurred manually")
    
    return curated_output


if __name__ == '__main__':
    try:
        curated = curate_cases()
        print("\n✅ Curation complete!")
    except Exception as e:
        print(f"\n❌ Error during curation: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

