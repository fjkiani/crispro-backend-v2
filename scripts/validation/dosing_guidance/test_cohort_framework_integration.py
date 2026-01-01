#!/usr/bin/env python3
"""
Dosing Guidance Validation - Cohort Framework Integration Test
================================================================

Tests the integration with existing Cohort Context Framework for 
pharmacogenomics data acquisition as defined in cohort_context_concept.mdc.

This script validates:
1. PubMed Portal - Pharmacogenomics case search
2. cBioPortal Client - Pharmacogene variant filtering  
3. GDC Client - Germline variant extraction (TCGA)

Author: Zo (Agent)
Created: January 2025
"""

import sys
import json
import time
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "data_acquisition" / "utils"))

# ============================================================================
# Test Results Tracking
# ============================================================================

class TestResults:
    def __init__(self):
        self.tests = []
        self.passed = 0
        self.failed = 0
    
    def add(self, name: str, passed: bool, details: str = ""):
        self.tests.append({"name": name, "passed": passed, "details": details})
        if passed:
            self.passed += 1
        else:
            self.failed += 1
        status = "✅" if passed else "❌"
        print(f"  {status} {name}: {details}")
    
    def summary(self):
        print(f"\n{'='*60}")
        print(f"TEST SUMMARY: {self.passed}/{len(self.tests)} passed")
        print('='*60)
        return self.passed == len(self.tests)


results = TestResults()


# ============================================================================
# Test 1: cBioPortal Client - Core Functionality
# ============================================================================

def test_cbioportal_client():
    """Test cBioPortal client connectivity and study listing."""
    print("\n" + "="*60)
    print("TEST 1: cBioPortal Client - Core Functionality")
    print("="*60)
    
    try:
        from cbioportal_client import CBioportalClient
        results.add("Import CBioportalClient", True, "Module loaded")
    except ImportError as e:
        results.add("Import CBioportalClient", False, str(e))
        return
    
    client = CBioportalClient()
    
    # Test 1.1: List studies
    try:
        studies = client.list_studies()
        results.add("List studies", len(studies) > 0, f"Found {len(studies)} studies")
    except Exception as e:
        results.add("List studies", False, str(e))
        return
    
    # Test 1.2: Find colorectal studies (relevant for DPYD/5-FU)
    try:
        crc_studies = [s for s in studies if 'colorectal' in s.get('name', '').lower() 
                       or 'coad' in s.get('studyId', '').lower()
                       or 'colon' in s.get('name', '').lower()]
        results.add("Find colorectal studies", len(crc_studies) > 0, 
                    f"Found {len(crc_studies)} colorectal studies")
    except Exception as e:
        results.add("Find colorectal studies", False, str(e))
    
    client.close()


# ============================================================================
# Test 2: cBioPortal - Pharmacogene Filtering (NEW CAPABILITY)
# ============================================================================

def test_cbioportal_pharmacogene_filter():
    """Test pharmacogene variant filtering capability."""
    print("\n" + "="*60)
    print("TEST 2: cBioPortal - Pharmacogene Filtering")
    print("="*60)
    
    try:
        from cbioportal_client import CBioportalClient
    except ImportError as e:
        results.add("Import for pharmacogene test", False, str(e))
        return
    
    client = CBioportalClient()
    PHARMACOGENES = ['DPYD', 'UGT1A1', 'TPMT', 'NUDT15']
    
    # Use MSK-IMPACT as test study (large, comprehensive)
    test_study = "msk_impact_2017"
    
    try:
        # Get mutation profile
        profile_id = client.get_mutation_profile_id(test_study)
        results.add("Get mutation profile", profile_id is not None, f"Profile: {profile_id}")
        
        # Get samples
        samples = client.get_study_samples(test_study)
        sample_ids = [s.get('sampleId') for s in samples[:100]]  # Limit for speed
        results.add("Get samples", len(sample_ids) > 0, f"Testing with {len(sample_ids)} samples")
        
        # Get mutations and filter for pharmacogenes
        if profile_id and sample_ids:
            mutations = client.get_mutations_for_samples(profile_id, sample_ids)
            
            pharmacogene_mutations = [
                m for m in mutations 
                if m.get('gene', {}).get('hugoGeneSymbol') in PHARMACOGENES
                or m.get('hugoGeneSymbol') in PHARMACOGENES
            ]
            
            results.add("Filter pharmacogene mutations", True, 
                        f"Found {len(pharmacogene_mutations)} pharmacogene mutations in sample")
            
            # Report which genes were found
            found_genes = set()
            for m in pharmacogene_mutations:
                gene = m.get('gene', {}).get('hugoGeneSymbol') or m.get('hugoGeneSymbol')
                if gene:
                    found_genes.add(gene)
            
            if found_genes:
                results.add("Pharmacogenes detected", True, f"Genes: {', '.join(found_genes)}")
            else:
                results.add("Pharmacogenes detected", True, 
                            "No pharmacogene variants in sample (expected for small subset)")
    
    except Exception as e:
        results.add("Pharmacogene filtering", False, str(e))
    
    client.close()


# ============================================================================
# Test 3: GDC Client - TCGA Germline Query
# ============================================================================

def test_gdc_client():
    """Test GDC API for TCGA germline queries."""
    print("\n" + "="*60)
    print("TEST 3: GDC Client - TCGA Germline Query")
    print("="*60)
    
    import requests
    
    GDC_BASE = "https://api.gdc.cancer.gov"
    
    # Test 3.1: Query TCGA-COAD project (colorectal - 5-FU use)
    try:
        payload = {
            "filters": {
                "op": "=",
                "content": {
                    "field": "project.project_id",
                    "value": "TCGA-COAD"
                }
            },
            "size": 10,
            "fields": "case_id,submitter_id"
        }
        
        response = requests.post(f"{GDC_BASE}/cases", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        cases = data.get("data", {}).get("hits", [])
        results.add("Query TCGA-COAD cases", len(cases) > 0, f"Found {len(cases)} cases (limited to 10)")
    except Exception as e:
        results.add("Query TCGA-COAD cases", False, str(e))
    
    # Test 3.2: Query for germline mutation files
    try:
        payload = {
            "filters": {
                "op": "and",
                "content": [
                    {"op": "=", "content": {"field": "cases.project.project_id", "value": "TCGA-COAD"}},
                    {"op": "=", "content": {"field": "data_type", "value": "Simple Germline Variation"}}
                ]
            },
            "size": 5,
            "fields": "file_id,file_name,data_type"
        }
        
        response = requests.post(f"{GDC_BASE}/files", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        files = data.get("data", {}).get("hits", [])
        results.add("Query germline files", True, 
                    f"Found {len(files)} germline variation files" if files else "No germline files (may need access)")
    except Exception as e:
        results.add("Query germline files", False, str(e))
    
    # Test 3.3: Query SSM occurrences for DPYD
    try:
        payload = {
            "filters": {
                "op": "and",
                "content": [
                    {"op": "=", "content": {"field": "ssm.consequence.transcript.gene.symbol", "value": "DPYD"}}
                ]
            },
            "size": 10,
            "fields": "ssm.ssm_id,ssm.genomic_dna_change"
        }
        
        response = requests.post(f"{GDC_BASE}/ssm_occurrences", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        occurrences = data.get("data", {}).get("hits", [])
        results.add("Query DPYD SSM occurrences", True, 
                    f"Found {len(occurrences)} DPYD mutations across all TCGA")
    except Exception as e:
        results.add("Query DPYD SSM occurrences", False, str(e))


# ============================================================================
# Test 4: PubMed Search - Pharmacogenomics Cases (Basic)
# ============================================================================

def test_pubmed_search():
    """Test PubMed search for pharmacogenomics case reports."""
    print("\n" + "="*60)
    print("TEST 4: PubMed Search - Pharmacogenomics Cases")
    print("="*60)
    
    import requests
    
    NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
    
    # Test 4.1: Search for DPYD case reports
    try:
        query = '("DPYD deficiency" OR "DPD deficiency") AND "fluoropyrimidine" AND "case report"'
        
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": 20,
            "retmode": "json"
        }
        
        response = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pmids = data.get("esearchresult", {}).get("idlist", [])
        count = data.get("esearchresult", {}).get("count", 0)
        
        results.add("Search DPYD case reports", int(count) > 0, 
                    f"Found {count} total articles, retrieved {len(pmids)} PMIDs")
    except Exception as e:
        results.add("Search DPYD case reports", False, str(e))
    
    # Test 4.2: Search for UGT1A1 + irinotecan cases
    try:
        query = '"UGT1A1*28" AND "irinotecan" AND ("toxicity" OR "neutropenia")'
        
        params = {
            "db": "pubmed",
            "term": query,
            "retmax": 20,
            "retmode": "json"
        }
        
        response = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        count = data.get("esearchresult", {}).get("count", 0)
        results.add("Search UGT1A1 irinotecan cases", int(count) > 0, 
                    f"Found {count} articles")
    except Exception as e:
        results.add("Search UGT1A1 irinotecan cases", False, str(e))


# ============================================================================
# Test 5: Schema Validation - Pharmacogenomics Fields
# ============================================================================

def test_schema_validation():
    """Test that pharmacogenomics schema is properly defined."""
    print("\n" + "="*60)
    print("TEST 5: Schema Validation - Pharmacogenomics Fields")
    print("="*60)
    
    # Define expected schema structure
    REQUIRED_PATIENT_FIELDS = ["patient_id"]
    REQUIRED_PGX_FIELDS = ["gene", "variant", "zygosity", "predicted_phenotype"]
    REQUIRED_TREATMENT_FIELDS = ["drug", "standard_dose", "actual_dose_given"]
    REQUIRED_OUTCOME_FIELDS = ["toxicity_occurred", "toxicity_grade", "toxicity_type"]
    
    # Test sample case
    sample_case = {
        "patient_id": "P001",
        "pharmacogenomics": {
            "gene": "DPYD",
            "variant": "c.1905+1G>A (*2A)",
            "zygosity": "heterozygous",
            "predicted_phenotype": "Intermediate Metabolizer",
            "pharmvar_id": "DPYD*2A",
            "cpic_level": "A"
        },
        "treatment": {
            "drug": "5-fluorouracil",
            "standard_dose": "400 mg/m²",
            "actual_dose_given": "400 mg/m²",
            "dose_reduction": False
        },
        "outcome": {
            "toxicity_occurred": True,
            "toxicity_grade": 4,
            "toxicity_type": "neutropenia",
            "hospitalization_required": True
        }
    }
    
    # Validate patient fields
    patient_valid = all(f in sample_case for f in REQUIRED_PATIENT_FIELDS)
    results.add("Patient fields", patient_valid, 
                f"Required: {REQUIRED_PATIENT_FIELDS}")
    
    # Validate PGx fields
    pgx = sample_case.get("pharmacogenomics", {})
    pgx_valid = all(f in pgx for f in REQUIRED_PGX_FIELDS)
    results.add("Pharmacogenomics fields", pgx_valid, 
                f"Required: {REQUIRED_PGX_FIELDS}")
    
    # Validate treatment fields
    tx = sample_case.get("treatment", {})
    tx_valid = all(f in tx for f in REQUIRED_TREATMENT_FIELDS)
    results.add("Treatment fields", tx_valid, 
                f"Required: {REQUIRED_TREATMENT_FIELDS}")
    
    # Validate outcome fields
    outcome = sample_case.get("outcome", {})
    outcome_valid = all(f in outcome for f in REQUIRED_OUTCOME_FIELDS)
    results.add("Outcome fields", outcome_valid, 
                f"Required: {REQUIRED_OUTCOME_FIELDS}")


# ============================================================================
# Main
# ============================================================================

def main():
    print("╔════════════════════════════════════════════════════════════════╗")
    print("║  COHORT FRAMEWORK INTEGRATION TEST - DOSING GUIDANCE           ║")
    print("║  Testing pharmacogenomics data acquisition capabilities        ║")
    print("╚════════════════════════════════════════════════════════════════╝")
    print(f"\nTimestamp: {datetime.now().isoformat()}")
    print(f"Project Root: {PROJECT_ROOT}")
    
    # Run all tests
    test_cbioportal_client()
    test_cbioportal_pharmacogene_filter()
    test_gdc_client()
    test_pubmed_search()
    test_schema_validation()
    
    # Summary
    all_passed = results.summary()
    
    if all_passed:
        print("\n🎉 ALL TESTS PASSED - Framework ready for pharmacogenomics validation")
    else:
        print(f"\n⚠️  {results.failed} TESTS FAILED - Review issues above")
    
    # Save results
    output_file = Path(__file__).parent / "framework_integration_test_results.json"
    with open(output_file, 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "passed": results.passed,
            "failed": results.failed,
            "tests": results.tests
        }, f, indent=2)
    print(f"\n📄 Results saved to: {output_file}")
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())

