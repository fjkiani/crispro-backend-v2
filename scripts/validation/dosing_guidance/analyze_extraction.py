#!/usr/bin/env python3
"""Analyze extraction results and confirm data availability."""

import json
import sys
from pathlib import Path

file_path = Path(__file__).parent / "extraction_all_genes.json"

if not file_path.exists():
    print(f"ERROR: {file_path} not found")
    sys.exit(1)

with open(file_path, 'r') as f:
    data = json.load(f)

print("=" * 60)
print("DATA EXTRACTION ANALYSIS - CONFIRMATION")
print("=" * 60)
print(f"\nExtraction Date: {data.get('extraction_date', 'N/A')}")
print(f"Total Cases: {data['total_cases']}")
print(f"Target: N>=50 -> {'EXCEEDS' if data['total_cases'] >= 50 else 'BELOW'} TARGET\n")

print("BREAKDOWN BY SOURCE:")
print("-" * 60)
for source, cases in data['sources'].items():
    print(f"  {source.upper():15s}: {len(cases):3d} cases")
print(f"  {'TOTAL':15s}: {data['total_cases']:3d} cases\n")

print("BREAKDOWN BY PHARMACOGENE:")
print("-" * 60)
gene_counts = {}
gene_by_source = {}

for source, cases in data['sources'].items():
    for case in cases:
        gene = case.get('gene', 'Unknown')
        if gene not in gene_counts:
            gene_counts[gene] = 0
            gene_by_source[gene] = {}
        gene_counts[gene] += 1
        if source not in gene_by_source[gene]:
            gene_by_source[gene][source] = 0
        gene_by_source[gene][source] += 1

for gene in sorted(gene_counts.keys()):
    total = gene_counts[gene]
    sources = gene_by_source[gene]
    source_str = ", ".join([f"{s}({c})" for s, c in sources.items()])
    print(f"  {gene:10s}: {total:3d} total  [{source_str}]")

print("\nSAMPLE CASES:")
print("-" * 60)
if data['sources']['pubmed']:
    print(f"\n  PubMed ({len(data['sources']['pubmed'])} cases):")
    for case in data['sources']['pubmed'][:2]:
        print(f"    - {case.get('case_id')}: {case.get('gene')} | PMID: {case.get('pmid')}")

if data['sources']['cbioportal']:
    print(f"\n  cBioPortal ({len(data['sources']['cbioportal'])} cases):")
    for case in data['sources']['cbioportal'][:1]:
        print(f"    - {case.get('case_id')}: {case.get('gene')} | Study: {case.get('study_id')}")

if data['sources']['gdc']:
    print(f"\n  GDC/TCGA ({len(data['sources']['gdc'])} cases):")
    for case in data['sources']['gdc'][:3]:
        variant = str(case.get('variant', 'N/A'))[:40]
        print(f"    - {case.get('case_id')}: {case.get('gene')} | Project: {case.get('project')} | Variant: {variant}")

print("\nVALIDATION READINESS:")
print("-" * 60)
checks = []
checks.append(("Case count (N>=50)", data['total_cases'] >= 50))
checks.append(("Pharmacogene coverage (>=3)", len(gene_counts) >= 3))
checks.append(("Data source diversity (>=3)", len(data['sources']) >= 3))

for check, passed in checks:
    status = "PASS" if passed else "FAIL"
    print(f"  [{status}]: {check}")

readiness = sum(1 for _, p in checks if p) / len(checks) * 100
print(f"\n  Overall Readiness: {readiness:.0f}%")
print(f"  Status: {'READY FOR API VALIDATION' if readiness >= 66 else 'NEEDS MORE DATA'}")

print("\nFILE INFO:")
print(f"  Location: {file_path}")
print(f"  Size: {file_path.stat().st_size:,} bytes")




