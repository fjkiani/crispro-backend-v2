#!/usr/bin/env python3
"""Resolve Project Data Sphere Loading Challenges - Try All Methods"""

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
print("Resolving PDS Loading Challenges")
print("=" * 80)

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

caslibs_to_try = ['Multiple_Brigham_454', 'Multiple_Allianc_2002_213', 'Multiple_MerckKG_2008_441']

try:
    conn = swat.CAS(cas_url, 443, username=sas_username, password=password)
    print("✅ Connected!")
    
    resolution = {'success': False, 'method': None, 'caslib': None, 'file': None, 'columns': [], 'ca125': [], 'pfi': []}
    
    for caslib_name in caslibs_to_try:
        print(f"\n📁 Trying: {caslib_name}")
        
        try:
            file_result = conn.table.fileInfo(allFiles=True, caslib=caslib_name)
            if hasattr(file_result, 'FileInfo'):
                files = file_result.FileInfo.to_dict('records')
                
                # Find Excel files
                excel_files = [f for f in files if '.xlsx' in f.get('Name', '').lower() or '.xls' in f.get('Name', '').lower()]
                
                if excel_files:
                    excel_file = excel_files[0]
                    file_name = excel_file.get('Name', '')
                    print(f"  Trying Excel: {file_name}")
                    
                    try:
                        table_name = "test_excel"
                        loaded = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                        conn.table.loadTable(sourceCaslib=caslib_name, casOut=loaded, path=file_name, importOptions={'fileType': 'EXCEL'})
                        print(f"  ✅ SUCCESS!")
                        
                        cols = loaded.columns.tolist()
                        print(f"  Columns: {len(cols)}")
                        
                        ca125_cols = [c for c in cols if any(kw in str(c).lower() for kw in ['ca125', 'ca-125'])]
                        pfi_cols = [c for c in cols if any(kw in str(c).lower() for kw in ['pfi', 'platinum'])]
                        
                        if ca125_cols:
                            print(f"  ⭐ CA-125: {ca125_cols}")
                        if pfi_cols:
                            print(f"  ⭐ PFI: {pfi_cols}")
                        
                        resolution['success'] = True
                        resolution['method'] = 'Excel loadTable'
                        resolution['caslib'] = caslib_name
                        resolution['file'] = file_name
                        resolution['columns'] = cols[:20]
                        resolution['ca125'] = ca125_cols
                        resolution['pfi'] = pfi_cols
                        
                        loaded.table.dropTable()
                        break
                    except Exception as e:
                        print(f"  ❌ Failed: {e}")
        except Exception as e:
            print(f"  Error: {e}")
    
    # Save results
    output_file = output_dir / 'pds_loading_resolution_results.json'
    with open(output_file, 'w') as f:
        json.dump(resolution, f, indent=2, default=str)
    
    print(f"\n{'='*80}")
    if resolution['success']:
        print("✅ RESOLUTION SUCCESSFUL!")
        print(f"   Method: {resolution['method']}")
        print(f"   File: {resolution['file']}")
        print(f"   CA-125 columns: {len(resolution['ca125'])}")
        print(f"   PFI columns: {len(resolution['pfi'])}")
    else:
        print("⚠️  Could not resolve - switching to alternative approaches")
    
    conn.close()
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()





