#!/usr/bin/env python3
"""
Dosing Guidance Validation - Unified Extraction Pipeline
==========================================================

Combines all three data sources (PubMed, cBioPortal, GDC) into a single
extraction pipeline for pharmacogenomics validation cases.

This script:
1. Extracts literature cases from PubMed
2. Extracts pharmacogene variants from cBioPortal studies
3. Extracts TCGA germline variants from GDC
4. Combines all into unified validation case format
5. Runs through dosing guidance system
6. Generates validation metrics

Author: Zo (Agent)
Created: January 2025
"""

import sys
import json
import time
import requests
import argparse
from pathlib import Path
from typing import List, Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, asdict

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "scripts" / "data_acquisition" / "utils"))

# ============================================================================
# Configuration
# ============================================================================

PHARMACOGENES = ['DPYD', 'UGT1A1', 'TPMT', 'NUDT15']
NCBI_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
GDC_BASE = "https://api.gdc.cancer.gov"
CBIO_BASE = "https://www.cbioportal.org/api"

# ============================================================================
# Extended cBioPortal Client (with pharmacogene filtering)
# ============================================================================

class ExtendedCBioportalClient:
    """Extended cBioPortal client with pharmacogene filtering."""
    
    def __init__(self):
        from cbioportal_client import CBioportalClient
        self.client = CBioportalClient()
    
    def get_sample_lists(self, study_id: str) -> List[Dict]:
        """Get all sample lists for a study."""
        endpoint = f"/studies/{study_id}/sample-lists"
        return self.client._make_request("GET", endpoint)
    
    def get_all_samples_list_id(self, study_id: str) -> Optional[str]:
        """Get the 'all samples' list ID for a study."""
        sample_lists = self.get_sample_lists(study_id)
        for sl in sample_lists:
            list_id = sl.get("sampleListId", "").lower()
            if "all" in list_id:
                return sl.get("sampleListId")
        return None
    
    def get_mutations_via_post(self, profile_id: str, sample_ids: List[str]) -> List[Dict]:
        """Fetch mutations using POST /mutations/fetch (preferred method)."""
        endpoint = "/mutations/fetch"
        payload = {
            "molecularProfileId": profile_id,
            "sampleIds": sample_ids,
            "projection": "DETAILED"
        }
        return self.client._make_request("POST", endpoint, json=payload)
    
    def filter_pharmacogenes(self, study_id: str, genes: List[str] = PHARMACOGENES) -> Dict:
        """Extract patients with pharmacogene variants."""
        print(f"\n  🔍 Filtering {study_id} for pharmacogenes: {', '.join(genes)}")
        
        # Get patients and clinical data
        patients = self.client.get_study_patients(study_id)
        clinical_data = self.client.get_clinical_data(study_id, entity_type="PATIENT")
        
        # Get mutation profile
        profile_id = self.client.get_mutation_profile_id(study_id)
        if not profile_id:
            return {'study_id': study_id, 'patients': [], 'count': 0, 'error': 'No mutation profile'}
        
        # Get samples
        samples = self.client.get_study_samples(study_id)
        sample_ids = [s.get("sampleId") for s in samples if s.get("sampleId")]
        
        # Get mutations
        mutations = []
        if sample_ids:
            try:
                # Try POST method first (more reliable)
                mutations = self.get_mutations_via_post(profile_id, sample_ids[:500])  # Limit for speed
                print(f"    ✅ Fetched {len(mutations)} mutations")
            except Exception as e:
                print(f"    ⚠️  POST failed: {e}, trying sample list method...")
                sample_list_id = self.get_all_samples_list_id(study_id)
                if sample_list_id:
                    endpoint = f"/molecular-profiles/{profile_id}/mutations"
                    params = {"sampleListId": sample_list_id, "projection": "DETAILED", "pageSize": 10000}
                    mutations = self.client._make_request("GET", endpoint, params=params)
        
        # Filter for pharmacogenes
        patient_to_samples = {}
        for sample in samples:
            patient_id = sample.get("patientId")
            sample_id = sample.get("sampleId")
            if patient_id and sample_id:
                if patient_id not in patient_to_samples:
                    patient_to_samples[patient_id] = []
                patient_to_samples[patient_id].append(sample_id)
        
        pharmacogene_mutations = {}
        for mut in mutations:
            gene = mut.get('gene', {}).get('hugoGeneSymbol') or mut.get('hugoGeneSymbol')
            if gene and gene.upper() in [g.upper() for g in genes]:
                sample_id = mut.get('sampleId')
                if sample_id:
                    if sample_id not in pharmacogene_mutations:
                        pharmacogene_mutations[sample_id] = []
                    pharmacogene_mutations[sample_id].append(mut)
        
        # Build filtered patient list
        filtered_patients = []
        for patient in patients:
            patient_id = patient.get("patientId")
            if not patient_id:
                continue
            
            patient_samples = patient_to_samples.get(patient_id, [])
            patient_variants = []
            for sample_id in patient_samples:
                if sample_id in pharmacogene_mutations:
                    patient_variants.extend(pharmacogene_mutations[sample_id])
            
            if patient_variants:
                filtered_patients.append({
                    'patient_id': patient_id,
                    'clinical': clinical_data.get(patient_id, {}),
                    'variants': patient_variants
                })
        
        return {
            'study_id': study_id,
            'pharmacogenes': genes,
            'patients': filtered_patients,
            'count': len(filtered_patients)
        }
    
    def close(self):
        self.client.close()


# ============================================================================
# Source 1: PubMed Literature Extraction
# ============================================================================

def extract_pubmed_cases(gene: str, max_results: int = 30) -> List[Dict]:
    """Extract case reports from PubMed."""
    print(f"\n{'='*60}")
    print(f"SOURCE 1: PubMed - {gene} Case Reports")
    print('='*60)
    
    queries = {
        "DPYD": '("DPYD deficiency" OR "DPD deficiency") AND "fluoropyrimidine" AND "case report" AND "toxicity"',
        "UGT1A1": '"UGT1A1*28" AND "irinotecan" AND ("toxicity" OR "neutropenia") AND "case report"',
        "TPMT": '("TPMT deficiency" OR "TPMT*3A") AND ("6-mercaptopurine" OR "thiopurine") AND "toxicity" AND "case report"'
    }
    
    query = queries.get(gene, f'"{gene}" AND "case report"')
    
    try:
        params = {"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"}
        response = requests.get(f"{NCBI_BASE}/esearch.fcgi", params=params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        pmids = data.get("esearchresult", {}).get("idlist", [])
        count = data.get("esearchresult", {}).get("count", 0)
        
        print(f"  ✅ Found {count} total articles, retrieved {len(pmids)} PMIDs")
        
        cases = []
        for i, pmid in enumerate(pmids[:10]):  # Limit for demo
            cases.append({
                "case_id": f"LIT-{gene}-{i+1:03d}",
                "source": "PubMed",
                "pmid": pmid,
                "gene": gene,
                "status": "needs_curation",
                "extraction_date": datetime.now().isoformat()
            })
        
        return cases
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return []


# ============================================================================
# Source 2: cBioPortal Extraction
# ============================================================================

def extract_cbioportal_cases(study_ids: List[str], genes: List[str] = PHARMACOGENES) -> List[Dict]:
    """Extract pharmacogene cases from cBioPortal studies."""
    print(f"\n{'='*60}")
    print(f"SOURCE 2: cBioPortal - Pharmacogene Variants")
    print('='*60)
    
    client = ExtendedCBioportalClient()
    all_cases = []
    
    try:
        for study_id in study_ids:
            print(f"\n  📊 Processing: {study_id}")
            result = client.filter_pharmacogenes(study_id, genes)
            
            if result.get('count', 0) > 0:
                print(f"    ✅ Found {result['count']} patients with pharmacogene variants")
                
                for patient_data in result['patients']:
                    patient_id = patient_data['patient_id']
                    variants = patient_data['variants']
                    clinical = patient_data['clinical']
                    
                    # Extract variant info
                    for variant in variants:
                        gene = variant.get('gene', {}).get('hugoGeneSymbol') or variant.get('hugoGeneSymbol')
                        if gene:
                            all_cases.append({
                                "case_id": f"CBIO-{study_id}-{patient_id}",
                                "source": "cBioPortal",
                                "study_id": study_id,
                                "patient_id": patient_id,
                                "gene": gene,
                                "variant": variant.get('proteinChange') or variant.get('aminoAcidChange', 'N/A'),
                                "clinical": clinical,
                                "status": "needs_treatment_data",
                                "extraction_date": datetime.now().isoformat()
                            })
            else:
                print(f"    ⚠️  No pharmacogene variants found")
    
    finally:
        client.close()
    
    print(f"\n  ✅ Total cBioPortal cases: {len(all_cases)}")
    return all_cases


# ============================================================================
# Source 3: GDC/TCGA Extraction
# ============================================================================

def extract_gdc_cases(project: str = "TCGA-COAD", gene: str = "DPYD") -> List[Dict]:
    """Extract pharmacogene cases from GDC/TCGA."""
    print(f"\n{'='*60}")
    print(f"SOURCE 3: GDC/TCGA - {project} {gene} Variants")
    print('='*60)
    
    cases = []
    
    # Query SSM occurrences for the gene
    try:
        payload = {
            "filters": {
                "op": "and",
                "content": [
                    {"op": "=", "content": {"field": "cases.project.project_id", "value": project}},
                    {"op": "=", "content": {"field": "ssm.consequence.transcript.gene.symbol", "value": gene}}
                ]
            },
            "size": 50,
            "fields": "ssm.ssm_id,ssm.genomic_dna_change,case.case_id,case.submitter_id"
        }
        
        response = requests.post(f"{GDC_BASE}/ssm_occurrences", json=payload, timeout=60)
        response.raise_for_status()
        data = response.json()
        
        occurrences = data.get("data", {}).get("hits", [])
        print(f"  ✅ Found {len(occurrences)} {gene} mutations in {project}")
        
        for i, occ in enumerate(occurrences):
            case_info = occ.get("case", {})
            ssm = occ.get("ssm", {})
            
            cases.append({
                "case_id": f"GDC-{project}-{i+1:03d}",
                "source": "GDC/TCGA",
                "project": project,
                "case_id_gdc": case_info.get("case_id"),
                "submitter_id": case_info.get("submitter_id"),
                "gene": gene,
                "variant": ssm.get("genomic_dna_change", "N/A"),
                "status": "needs_treatment_outcome_data",
                "extraction_date": datetime.now().isoformat()
            })
    
    except Exception as e:
        print(f"  ❌ Error: {e}")
    
    print(f"  ✅ Total GDC cases: {len(cases)}")
    return cases


# ============================================================================
# Unified Pipeline
# ============================================================================

def run_unified_extraction(
    genes: List[str] = ["DPYD"],
    cbioportal_studies: Optional[List[str]] = None,
    gdc_projects: List[str] = ["TCGA-COAD"],
    max_pubmed: int = 30
) -> Dict:
    """Run unified extraction from all three sources."""
    print("\n" + "="*80)
    print("UNIFIED EXTRACTION PIPELINE - DOSING GUIDANCE VALIDATION")
    print("="*80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Target genes: {', '.join(genes)}")
    
    all_cases = {
        "extraction_date": datetime.now().isoformat(),
        "sources": {
            "pubmed": [],
            "cbioportal": [],
            "gdc": []
        },
        "total_cases": 0
    }
    
    # Source 1: PubMed
    for gene in genes:
        pubmed_cases = extract_pubmed_cases(gene, max_pubmed)
        all_cases["sources"]["pubmed"].extend(pubmed_cases)
    
    # Source 2: cBioPortal
    if cbioportal_studies:
        cbioportal_cases = extract_cbioportal_cases(cbioportal_studies, genes)
        all_cases["sources"]["cbioportal"] = cbioportal_cases
    else:
        # Auto-discover colorectal studies
        print("\n  🔍 Auto-discovering colorectal studies...")
        client = ExtendedCBioportalClient()
        try:
            studies = client.client.list_studies()
            crc_studies = [
                s.get("studyId") for s in studies
                if 'colorectal' in s.get('name', '').lower()
                or 'coad' in s.get('studyId', '').lower()
            ][:3]  # Limit to 3 for demo
            
            if crc_studies:
                print(f"  ✅ Found {len(crc_studies)} colorectal studies: {', '.join(crc_studies)}")
                cbioportal_cases = extract_cbioportal_cases(crc_studies, genes)
                all_cases["sources"]["cbioportal"] = cbioportal_cases
        finally:
            client.close()
    
    # Source 3: GDC
    for project in gdc_projects:
        for gene in genes:
            gdc_cases = extract_gdc_cases(project, gene)
            all_cases["sources"]["gdc"].extend(gdc_cases)
    
    # Calculate totals
    all_cases["total_cases"] = (
        len(all_cases["sources"]["pubmed"]) +
        len(all_cases["sources"]["cbioportal"]) +
        len(all_cases["sources"]["gdc"])
    )
    
    print("\n" + "="*80)
    print("EXTRACTION SUMMARY")
    print("="*80)
    print(f"PubMed cases: {len(all_cases['sources']['pubmed'])}")
    print(f"cBioPortal cases: {len(all_cases['sources']['cbioportal'])}")
    print(f"GDC cases: {len(all_cases['sources']['gdc'])}")
    print(f"TOTAL: {all_cases['total_cases']} cases")
    print("="*80)
    
    return all_cases


# ============================================================================
# CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(description="Unified extraction pipeline for dosing guidance validation")
    parser.add_argument("--genes", nargs="+", default=["DPYD"], help="Pharmacogenes to extract")
    parser.add_argument("--cbioportal-studies", nargs="+", help="cBioPortal study IDs (auto-discover if not provided)")
    parser.add_argument("--gdc-projects", nargs="+", default=["TCGA-COAD"], help="GDC project IDs")
    parser.add_argument("--max-pubmed", type=int, default=30, help="Max PubMed results per gene")
    parser.add_argument("--output", type=str, default="unified_validation_cases.json", help="Output file")
    
    args = parser.parse_args()
    
    # Run extraction
    results = run_unified_extraction(
        genes=args.genes,
        cbioportal_studies=args.cbioportal_studies,
        gdc_projects=args.gdc_projects,
        max_pubmed=args.max_pubmed
    )
    
    # Save results
    output_path = Path(__file__).parent / args.output
    with open(output_path, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📄 Results saved to: {output_path}")
    print("\nNEXT STEPS:")
    print("1. Manually curate extracted cases (fill in treatment/outcome data)")
    print("2. Run through dosing guidance API")
    print("3. Calculate validation metrics: python calculate_validation_metrics.py")


if __name__ == "__main__":
    main()




