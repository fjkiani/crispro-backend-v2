#!/usr/bin/env python3
"""Test cBioPortal API access and data availability for enrichment"""
import httpx
import json

CBIO_BASE = "https://www.cbioportal.org/api"
STUDY_ID = "ov_tcga_pan_can_atlas_2018"

print("=" * 80)
print("TESTING cBioPortal DATA AVAILABILITY")
print("=" * 80)
print()

# Test 1: Check study exists
print("1. Testing study access...")
try:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{CBIO_BASE}/studies/{STUDY_ID}")
        r.raise_for_status()
        study = r.json()
        print(f"   ✅ Study found: {study.get('name', 'Unknown')}")
except Exception as e:
    print(f"   ❌ Failed: {e}")
    exit(1)

# Test 2: Check clinical attributes
print("\n2. Testing clinical attributes...")
try:
    with httpx.Client(timeout=30.0) as client:
        r = client.get(f"{CBIO_BASE}/studies/{STUDY_ID}/clinical-attributes")
        r.raise_for_status()
        attributes = r.json() or []
        
        hrd_attrs = [a for a in attributes if any(term in a.get("clinicalAttributeId", "").upper() for term in ["HRD", "GIS", "HOMOLOGOUS"])]
        tmb_attrs = [a for a in attributes if "TMB" in a.get("clinicalAttributeId", "").upper()]
        msi_attrs = [a for a in attributes if "MSI" in a.get("clinicalAttributeId", "").upper()]
        
        print(f"   ✅ Total attributes: {len(attributes)}")
        print(f"   ✅ HRD-related: {len(hrd_attrs)}")
        if hrd_attrs:
            for attr in hrd_attrs[:3]:
                print(f"      - {attr.get('clinicalAttributeId')}")
        print(f"   ✅ TMB-related: {len(tmb_attrs)}")
        if tmb_attrs:
            for attr in tmb_attrs[:3]:
                print(f"      - {attr.get('clinicalAttributeId')}")
        print(f"   ✅ MSI-related: {len(msi_attrs)}")
        if msi_attrs:
            for attr in msi_attrs[:3]:
                print(f"      - {attr.get('clinicalAttributeId')}")
except Exception as e:
    print(f"   ⚠️  Warning: {e}")

print("\n✅ Data sources accessible")
