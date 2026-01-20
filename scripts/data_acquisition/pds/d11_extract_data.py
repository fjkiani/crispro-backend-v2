#!/usr/bin/env python3
"""D11: Project Data Sphere - Data Extraction Pipeline"""

import swat
import os
import json
from pathlib import Path
from datetime import datetime

cas_url = "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/"
ssl_cert = "/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem"
sas_username = "mpm0fxk2"
password = "Thisisfjk12345!"

os.environ["CAS_CLIENT_SSL_CA_LIST"] = ssl_cert

print("=" * 80)
print("D11: Data Extraction Pipeline")
print("=" * 80)

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

# Load D9 results
d9_file = output_dir / 'd9_project_data_sphere_multiple_caslibs_analysis.json'
with open(d9_file, 'r') as f:
    d9_data = json.load(f)

target_caslibs = ['Multiple_MerckKG_2008_441', 'Multiple_Brigham_454', 'Multiple_Allianc_2002_213']

ca125_keywords = ['ca125', 'ca-125', 'ca_125', 'cancer antigen 125']
pfi_keywords = ['pfi', 'platinum free interval', 'platinum-free', 'time to progression', 'ttp']
ovarian_keywords = ['ovarian', 'ovary', 'ov', 'gynecologic', 'gyn']

try:
    conn = swat.CAS(cas_url, 443, username=sas_username, password=password)
    print("✅ Connected!")
    
    extraction_results = []
    all_extracted_data = []
    
    for caslib_name in target_caslibs:
        print(f"\n📁 Processing: {caslib_name}")
        
        d9_caslib = next((r for r in d9_data.get('results', []) if r.get('caslib_name') == caslib_name), None)
        if not d9_caslib:
            print(f"  ⚠️  No D9 data")
            continue
        
        files = d9_caslib.get('files', [])
        data_files = [f for f in files if any(ext in f.get('name', '').lower() for ext in ['.csv', '.sas7bdat', '.xpt', '.txt'])]
        
        print(f"  Found {len(data_files)} data files")
        
        result = {
            'caslib_name': caslib_name,
            'files_attempted': [],
            'files_loaded': [],
            'ca125_found': False,
            'pfi_found': False,
            'errors': []
        }
        
        for file_info in data_files[:2]:  # Try first 2
            file_name = file_info.get('name', '')
            if not file_name:
                continue
            
            print(f"  🔄 Loading: {file_name}")
            result['files_attempted'].append(file_name)
            
            try:
                table_name = f"loaded_{file_name.replace('.', '_').replace('-', '_')[:40]}"
                loaded_table = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                
                try:
                    conn.table.loadTable(sourceCaslib=caslib_name, casOut=loaded_table, path=file_name)
                    print(f"    ✅ Loaded")
                    
                    columns = loaded_table.columns.tolist()
                    print(f"    Columns: {len(columns)}")
                    
                    ca125_cols = [c for c in columns if any(kw in str(c).lower() for kw in ca125_keywords)]
                    pfi_cols = [c for c in columns if any(kw in str(c).lower() for kw in pfi_keywords)]
                    
                    if ca125_cols:
                        print(f"    ⭐ CA-125 columns: {ca125_cols}")
                        result['ca125_found'] = True
                    
                    if pfi_cols:
                        print(f"    ⭐ PFI columns: {pfi_cols}")
                        result['pfi_found'] = True
                    
                    if ca125_cols or pfi_cols:
                        try:
                            sample = loaded_table.head(5)
                            extracted = {
                                'caslib': caslib_name,
                                'file': file_name,
                                'ca125_columns': ca125_cols,
                                'pfi_columns': pfi_cols,
                                'sample_rows': len(sample) if hasattr(sample, '__len__') else 0
                            }
                            all_extracted_data.append(extracted)
                        except:
                            pass
                    
                    result['files_loaded'].append(file_name)
                    loaded_table.table.dropTable()
                    
                except Exception as e:
                    print(f"    ⚠️  Could not load: {e}")
                    result['errors'].append(str(e))
            except Exception as e:
                result['errors'].append(str(e))
        
        extraction_results.append(result)
    
    output = {
        'metadata': {'date': datetime.now().isoformat()},
        'summary': {
            'files_attempted': sum(len(r.get('files_attempted', [])) for r in extraction_results),
            'files_loaded': sum(len(r.get('files_loaded', [])) for r in extraction_results),
            'ca125_found': len([r for r in extraction_results if r.get('ca125_found')]),
            'pfi_found': len([r for r in extraction_results if r.get('pfi_found')])
        },
        'extracted_data': all_extracted_data,
        'details': extraction_results
    }
    
    output_file = output_dir / 'd11_project_data_sphere_extraction_results.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    
    print(f"\n✅ Complete!")
    print(f"   Files loaded: {output['summary']['files_loaded']}")
    print(f"   CA-125 found: {output['summary']['ca125_found']} caslibs")
    print(f"   PFI found: {output['summary']['pfi_found']} caslibs")
    print(f"   Saved to: {output_file}")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()





