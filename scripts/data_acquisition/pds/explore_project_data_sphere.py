#!/usr/bin/env python3
"""Explore Project Data Sphere for ovarian cancer and CA-125 data."""

import swat
import os
import json
from pathlib import Path

cas_url = "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/"
ssl_cert = "/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem"
sas_username = "mpm0fxk2"
password = "Thisisfjk12345!"

os.environ["CAS_CLIENT_SSL_CA_LIST"] = ssl_cert

print("=" * 80)
print("Project Data Sphere - Comprehensive Exploration")
print("=" * 80)

conn = swat.CAS(cas_url, 443, username=sas_username, password=password)
print("✅ Connected!")

# Get caslibs
result = conn.table.caslibInfo()
caslib_df = result.CASLibInfo
caslibs = caslib_df.to_dict('records')

print(f"\n✅ Found {len(caslibs)} caslibs")

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')
output_dir.mkdir(parents=True, exist_ok=True)

# Save caslibs
with open(output_dir / 'project_data_sphere_caslibs.json', 'w') as f:
    json.dump(caslibs, f, indent=2)

# Find ovarian cancer related caslibs
print("\n" + "=" * 80)
print("Searching for Ovarian Cancer Caslibs")
print("=" * 80)

ovarian_keywords = ['ovarian', 'ovary', 'ov', 'gynecologic', 'gyn']
ovarian_caslibs = []

for caslib in caslibs:
    name = caslib.get('Name', '').lower()
    desc = (caslib.get('Description', '') or '').lower()
    if any(kw in name or kw in desc for kw in ovarian_keywords):
        ovarian_caslibs.append(caslib)
        print(f"  ✅ Found: {caslib.get('Name', 'N/A')}")

print(f"\nFound {len(ovarian_caslibs)} ovarian cancer caslibs")

# Search for CA-125 related files
print("\n" + "=" * 80)
print("Searching for CA-125 Related Files")
print("=" * 80)

ca125_keywords = ['ca125', 'ca-125', 'ca_125', 'cancer antigen 125']
all_keywords = ovarian_keywords + ca125_keywords
ovarian_datasets = []

# Check all caslibs for ovarian/CA-125 files
print(f"Scanning {len(caslibs)} caslibs for relevant files...")
for i, caslib in enumerate(caslibs, 1):
    caslib_name = caslib.get('Name', '')
    if i % 20 == 0:
        print(f"  Progress: {i}/{len(caslibs)} caslibs scanned...")
    
    try:
        file_result = conn.table.fileInfo(allFiles=True, caslib=caslib_name)
        if hasattr(file_result, 'FileInfo'):
            file_df = file_result.FileInfo
            if hasattr(file_df, 'to_dict'):
                files = file_df.to_dict('records')
                for f in files:
                    file_name = (f.get('Name', '') or '').lower()
                    for keyword in all_keywords:
                        if keyword in file_name:
                            ovarian_datasets.append({
                                'caslib': caslib_name,
                                'file_name': f.get('Name', ''),
                                'file_path': f.get('Path', ''),
                                'file_size': f.get('Size', 0),
                                'matched_keyword': keyword
                            })
                            print(f"  ✅ {caslib_name}/{f.get('Name', '')} ({keyword})")
                            break
    except Exception as e:
        pass

if ovarian_datasets:
    print(f"\n✅ Found {len(ovarian_datasets)} potential datasets")
    with open(output_dir / 'project_data_sphere_ovarian_datasets.json', 'w') as f:
        json.dump(ovarian_datasets, f, indent=2)
else:
    print("\n⚠️  No ovarian/CA-125 datasets found")

# Explore promising caslibs in detail
print("\n" + "=" * 80)
print("Exploring Caslib Contents")
print("=" * 80)

exploration_results = []
relevant_keywords = ['clinical', 'trial', 'patient', 'cancer', 'oncology'] + ovarian_keywords

# Find relevant caslibs
promising = [c for c in caslibs if any(kw in c.get('Name', '').lower() for kw in relevant_keywords)]

print(f"Exploring {min(25, len(promising))} relevant caslibs...")

for caslib in promising[:25]:
    name = caslib.get('Name', 'N/A')
    print(f"\n📁 {name}")
    try:
        file_result = conn.table.fileInfo(allFiles=True, caslib=name)
        if hasattr(file_result, 'FileInfo'):
            file_df = file_result.FileInfo
            files = file_df.to_dict('records') if hasattr(file_df, 'to_dict') else []
            print(f"   Found {len(files)} files")
            exploration_results.append({
                'caslib_name': name,
                'description': caslib.get('Description', ''),
                'file_count': len(files),
                'files': files[:30]
            })
            for f in files[:10]:
                print(f"      - {f.get('Name', 'N/A')}")
    except Exception as e:
        print(f"   Error: {e}")

with open(output_dir / 'project_data_sphere_exploration.json', 'w') as f:
    json.dump(exploration_results, f, indent=2)

conn.close()

print("\n" + "=" * 80)
print("✅ Exploration Complete!")
print("=" * 80)
print(f"Summary:")
print(f"  - Total caslibs: {len(caslibs)}")
print(f"  - Ovarian caslibs: {len(ovarian_caslibs)}")
print(f"  - Ovarian/CA-125 datasets: {len(ovarian_datasets)}")
print(f"  - Explored caslibs: {len(exploration_results)}")
print(f"\n📁 Results saved to: {output_dir}")





