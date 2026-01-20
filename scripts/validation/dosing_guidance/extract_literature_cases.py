#!/usr/bin/env python3
"""
Dosing Guidance Validation - Literature Case Extraction
========================================================
Extracts pharmacogenomics case reports from PubMed for clinical validation.
Target: 20-30 cases with known gene variants and toxicity outcomes

Usage:
    python extract_literature_cases.py --gene DPYD --output validation_cases_dpyd.json
"""

import json
import time
import argparse
import requests
from typing import List, Dict, Optional
from dataclasses import dataclass, asdict
from datetime import datetime

NCBI_BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

PUBMED_QUERIES = {
    "DPYD": '("DPYD deficiency" OR "DPD deficiency") AND ("fluoropyrimidine" OR "5-fluorouracil") AND "case report" AND "toxicity"',
    "UGT1A1": '("UGT1A1*28" OR "Gilbert syndrome") AND "irinotecan" AND ("toxicity" OR "neutropenia") AND "case report"',
    "TPMT": '("TPMT deficiency" OR "TPMT*3A") AND ("6-mercaptopurine" OR "thiopurine") AND "toxicity" AND "case report"'
}

ACTIONABLE_VARIANTS = {
    "DPYD": [
        {"rsid": "rs3918290", "star": "*2A", "phenotype": "No Function"},
        {"rsid": "rs55886062", "star": "*13", "phenotype": "No Function"},
        {"rsid": "rs67376798", "star": "D949V", "phenotype": "Decreased Function"},
    ],
    "UGT1A1": [{"rsid": "rs8175347", "star": "*28", "phenotype": "Intermediate Metabolizer"}],
    "TPMT": [{"rsid": "rs1142345", "star": "*3C", "phenotype": "No Function"}]
}

@dataclass
class ValidationCase:
    case_id: str
    source: str
    pmid: Optional[str]
    gene: str
    variant: str
    zygosity: str
    drug: str
    dose_given: str
    toxicity_occurred: bool
    toxicity_grade: Optional[int]
    our_adjustment_factor: float
    our_risk_level: str
    concordance: bool
    notes: str
    extraction_date: str = None
    
    def __post_init__(self):
        if self.extraction_date is None:
            self.extraction_date = datetime.now().isoformat()

def search_pubmed(query: str, max_results: int = 50) -> List[str]:
    """Search PubMed and return PMIDs"""
    url = f"{NCBI_BASE_URL}/esearch.fcgi"
    params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        return response.json().get("esearchresult", {}).get("idlist", [])
    except Exception as e:
        print(f"Error: {e}")
        return []

def get_dosing_prediction(gene: str, zygosity: str) -> tuple:
    """Return (adjustment_factor, risk_level) based on gene/zygosity"""
    if gene == "DPYD":
        if zygosity == "homozygous":
            return (0.0, "HIGH")  # Contraindicated
        elif zygosity == "heterozygous":
            return (0.5, "HIGH")  # 50% dose
    elif gene == "UGT1A1":
        if zygosity == "homozygous":
            return (0.7, "MODERATE")
    elif gene == "TPMT":
        if zygosity == "homozygous":
            return (0.1, "HIGH")
        elif zygosity == "heterozygous":
            return (0.5, "MODERATE")
    return (1.0, "LOW")

def main():
    parser = argparse.ArgumentParser(description="Extract literature cases for dosing guidance validation")
    parser.add_argument("--gene", choices=["DPYD", "UGT1A1", "TPMT", "all"], default="all")
    parser.add_argument("--output", type=str, default="validation_cases.json")
    parser.add_argument("--max-pubmed", type=int, default=30)
    args = parser.parse_args()
    
    genes = ["DPYD", "UGT1A1", "TPMT"] if args.gene == "all" else [args.gene]
    all_cases = []
    
    for gene in genes:
        print(f"\n{'='*50}\nSearching {gene} cases...\n{'='*50}")
        query = PUBMED_QUERIES.get(gene, f'"{gene}" AND "case report"')
        pmids = search_pubmed(query, args.max_pubmed)
        print(f"Found {len(pmids)} articles")
        
        # TODO: Agent Jr - implement abstract parsing to extract case details
        for i, pmid in enumerate(pmids[:5]):  # Demo limit
            adj, risk = get_dosing_prediction(gene, "heterozygous")
            case = ValidationCase(
                case_id=f"LIT-{gene}-{i+1:03d}",
                source="PubMed",
                pmid=pmid,
                gene=gene,
                variant="TODO: Extract from abstract",
                zygosity="TODO",
                drug="TODO",
                dose_given="TODO",
                toxicity_occurred=True,
                toxicity_grade=None,
                our_adjustment_factor=adj,
                our_risk_level=risk,
                concordance=False,
                notes="Placeholder - needs manual curation"
            )
            all_cases.append(case)
    
    output = {"extraction_date": datetime.now().isoformat(), "total_cases": len(all_cases), 
              "cases": [asdict(c) for c in all_cases]}
    with open(args.output, 'w') as f:
        json.dump(output, f, indent=2)
    print(f"\n✅ Saved {len(all_cases)} cases to {args.output}")

if __name__ == "__main__":
    main()





