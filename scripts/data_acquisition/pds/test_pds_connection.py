#!/usr/bin/env python3
"""Test Project Data Sphere connection with credentials."""

import swat
import os
import json
from pathlib import Path

cas_url = "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/"
ssl_cert = "/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem"
username = "fahad@crispro.ai"
password = "Thisisfjk12345!"

os.environ["CAS_CLIENT_SSL_CA_LIST"] = ssl_cert

print("=" * 80)
print("Project Data Sphere Connection Test")
print("=" * 80)

# Test different authentication methods
print("\nMethod 1: Username/password in CAS()")
try:
    conn = swat.CAS(cas_url, 443, username=username, password=password)
    status = conn.serverstatus()
    print(f"✅ Success! Status: {status}")
    
    # List caslibs
    print("\nListing caslibs...")
    result = conn.table.caslibInfo()
    caslibs = []
    if hasattr(result, 'CASLibInfo'):
        for caslib in result.CASLibInfo:
            caslibs.append({
                'name': caslib.get('Name', ''),
                'description': caslib.get('Description', ''),
                'path': caslib.get('Path', '')
            })
    
    print(f"Found {len(caslibs)} caslibs")
    
    # Save results
    output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(output_dir / 'project_data_sphere_caslibs.json', 'w') as f:
        json.dump(caslibs, f, indent=2)
    print(f"✅ Saved caslib list to: {output_dir / 'project_data_sphere_caslibs.json'}")
    
    # Show first 30
    print("\nFirst 30 caslibs:")
    for i, caslib in enumerate(caslibs[:30], 1):
        name = caslib.get('name', 'N/A')
        desc = caslib.get('description', 'N/A')[:60] if caslib.get('description') else 'N/A'
        print(f"{i:3d}. {name:45s} | {desc}")
    
    # Search for ovarian cancer data
    print("\n" + "=" * 80)
    print("Searching for Ovarian Cancer / CA-125 Data")
    print("=" * 80)
    
    keywords = ['ovarian', 'ovary', 'ov', 'ca125', 'ca-125', 'platinum', 'pfi', 'serous', 'hgsc']
    ovarian_datasets = []
    
    for caslib in caslibs:
        caslib_name = caslib.get('name', '')
        try:
            file_result = conn.table.fileInfo(allFiles=True, caslib=caslib_name)
            files = []
            if hasattr(file_result, 'FileInfo'):
                for f in file_result.FileInfo:
                    file_name = f.get('Name', '').lower()
                    for keyword in keywords:
                        if keyword in file_name:
                            ovarian_datasets.append({
                                'caslib': caslib_name,
                                'file_name': f.get('Name', ''),
                                'matched_keyword': keyword
                            })
                            print(f"   ✅ Found: {caslib_name}/{f.get('Name', '')} ({keyword})")
                            break
        except Exception as e:
            pass  # Skip caslibs we can't access
    
    if ovarian_datasets:
        print(f"\n✅ Found {len(ovarian_datasets)} potential datasets")
        with open(output_dir / 'project_data_sphere_ovarian_datasets.json', 'w') as f:
            json.dump(ovarian_datasets, f, indent=2)
    else:
        print("\n⚠️  No ovarian cancer datasets found")
    
    conn.close()
    print("\n✅ Connection test complete!")
    
except Exception as e:
    print(f"❌ Failed: {e}")
    print(f"   Error type: {type(e).__name__}")
    
    # Try alternative method
    print("\nMethod 2: Password only (OAuth token)")
    try:
        conn = swat.CAS(cas_url, 443, password=password)
        status = conn.serverstatus()
        print(f"✅ Success with password only! Status: {status}")
        conn.close()
    except Exception as e2:
        print(f"❌ Also failed: {e2}")





