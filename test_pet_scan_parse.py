#!/usr/bin/env python3
"""
Test script to parse PET Scan PDF and extract structured data
"""
import PyPDF2
import re
import json
from datetime import datetime

pdf_path = '/Users/fahadkiani/.cursor/worktrees/crispr-assistant-main/ebi/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/PET Scan.pdf'

print("=" * 60)
print("PET Scan PDF - Structured Data Extraction")
print("=" * 60)
print()

with open(pdf_path, 'rb') as f:
    reader = PyPDF2.PdfReader(f)
    text = ''
    for page in reader.pages:
        text += page.extract_text()

# Extract PII (to be removed)
pii_patterns = {
    'name': r'Name:\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)',
    'dob': r'DOB:\s*(\d{1,2}/\d{1,2}/\d{4})',
    'mrn': r'MRN:\s*(\d+)',
    'pcp': r'PCP:\s*([^|]+)',
}

print("🔴 PII DETECTED (To be removed):")
print("-" * 60)
for pii_type, pattern in pii_patterns.items():
    match = re.search(pattern, text)
    if match:
        print(f"{pii_type.upper()}: {match.group(1)}")

print()
print("=" * 60)
print("📋 CLINICAL DATA EXTRACTED:")
print("=" * 60)

# Extract report type
report_type = "IMAGING"
if "PET" in text or "CT" in text:
    exam_type = "PET-CT"
else:
    exam_type = "Unknown"

# Extract exam date
date_match = re.search(r'Scan on (\d{1,2}/\d{1,2}/\d{4})', text)
exam_date = date_match.group(1) if date_match else None

# Extract clinical indication
indication_match = re.search(r'CLINICAL INFORMATION:\s*(.*?)(?:\n|TECHNIQUE:)', text, re.DOTALL)
indication = indication_match.group(1).strip() if indication_match else None

# Extract findings
findings_match = re.search(r'FINDINGS:\s*(.*?)(?:\n\nIMPRESSION:)', text, re.DOTALL)
findings = findings_match.group(1).strip() if findings_match else None

# Extract impression
impression_match = re.search(r'IMPRESSION:\s*(.*?)(?:\n\nElectronically)', text, re.DOTALL)
impression = impression_match.group(1).strip() if impression_match else None

# Extract key clinical findings
clinical_data = {
    "report_type": report_type,
    "exam_type": exam_type,
    "exam_date": exam_date,
    "indication": indication[:200] if indication else None,
    "findings_summary": findings[:500] if findings else None,
    "impression": impression[:500] if impression else None,
}

# Key clinical findings (structured)
key_findings = {
    "extensive_carcinomatosis": "extensive carcinomatosis" in text.lower() or "carcinomatosis" in text.lower(),
    "ascites": "ascites" in text.lower(),
    "pleural_effusions": "pleural effusions" in text.lower() or "pleural" in text.lower(),
    "lymph_node_metastases": "lymph nodes" in text.lower() and "FDG-avid" in text,
    "gynecologic_primary_suspected": "gynecologic primary" in text.lower() or "adnexal" in text.lower(),
    "suv_max": None,
}

# Extract SUV max values
suv_matches = re.findall(r'SUV\s*(?:max\s*)?(\d+(?:\.\d+)?)', text, re.IGNORECASE)
if suv_matches:
    key_findings["suv_max"] = max([float(s) for s in suv_matches])

# Extract locations
locations = []
if "cervical" in text.lower():
    locations.append("cervical_nodes")
if "mediastinal" in text.lower():
    locations.append("mediastinal_nodes")
if "abdominopelvic" in text.lower() or "abdomen" in text.lower():
    locations.append("abdominopelvic")
if "pleural" in text.lower():
    locations.append("pleural")
if "pericardial" in text.lower():
    locations.append("pericardial")

key_findings["disease_locations"] = locations

result = {
    "report_metadata": {
        "report_type": report_type,
        "exam_type": exam_type,
        "exam_date": exam_date,
        "extraction_date": datetime.now().isoformat(),
    },
    "clinical_data": clinical_data,
    "key_findings": key_findings,
    "de_identified": False,  # Still contains PII - needs stripping
}

print(json.dumps(result, indent=2))
print()
print("=" * 60)
print("✅ Extraction complete - Contains PII, needs de-identification")
print("=" * 60)
