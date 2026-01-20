#!/usr/bin/env python3
"""Resolve Project Data Sphere File Loading Challenges"""

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
print("Resolving Project Data Sphere File Loading Challenges")
print("=" * 80)

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

with open(output_dir / 'd9_project_data_sphere_multiple_caslibs_analysis.json', 'r') as f:
    d9_data = json.load(f)

target_caslib = 'Multiple_MerckKG_2008_441'
d9_caslib = next((r for r in d9_data.get('results', []) if r.get('caslib_name') == target_caslib), None)

if not d9_caslib:
    print("❌ Caslib not found")
    exit(1)

try:
    conn = swat.CAS(cas_url, 443, username=sas_username, password=password)
    print("✅ Connected!")
    
    print(f"\n📁 Exploring: {target_caslib}")
    
    # Get detailed file information
    print("\n1. Getting file information...")
    file_result = conn.table.fileInfo(allFiles=True, caslib=target_caslib)
    
    if hasattr(file_result, 'FileInfo'):
        files = file_result.FileInfo.to_dict('records')
        print(f"   ✅ Found {len(files)} files")
        
        # Categorize files
        simple_files = [f for f in files if any(ext in f.get('Name', '').lower() for ext in ['.csv', '.txt', '.tsv'])]
        xpt_files = [f for f in files if '.xpt' in f.get('Name', '').lower()]
        sas_files = [f for f in files if '.sas7bdat' in f.get('Name', '').lower()]
        
        print(f"   - CSV/TXT: {len(simple_files)}")
        print(f"   - XPT: {len(xpt_files)}")
        print(f"   - SAS: {len(sas_files)}")
        
        # Try loading simple files
        if simple_files:
            test_file = simple_files[0]
            file_name = test_file.get('Name', '')
            file_path = test_file.get('Path', '')
            
            print(f"\n2. Testing file: {file_name}")
            print(f"   Path: {file_path}")
            
            success = False
            methods_tried = []
            
            # Method 1: Filename only
            try:
                table_name = "test_1"
                loaded = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                conn.table.loadTable(sourceCaslib=target_caslib, casOut=loaded, path=file_name)
                print(f"   ✅ Method 1 SUCCESS: Filename only")
                cols = loaded.columns.tolist()
                print(f"   Columns: {len(cols)}")
                success = True
                methods_tried.append({'method': 'filename_only', 'success': True, 'columns': len(cols)})
                loaded.table.dropTable()
            except Exception as e1:
                methods_tried.append({'method': 'filename_only', 'success': False, 'error': str(e1)})
                print(f"   ❌ Method 1 failed: {e1}")
            
            # Method 2: Full path
            if not success and file_path:
                try:
                    table_name = "test_2"
                    loaded = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                    conn.table.loadTable(sourceCaslib=target_caslib, casOut=loaded, path=file_path)
                    print(f"   ✅ Method 2 SUCCESS: Full path")
                    cols = loaded.columns.tolist()
                    print(f"   Columns: {len(cols)}")
                    success = True
                    methods_tried.append({'method': 'full_path', 'success': True, 'columns': len(cols)})
                    loaded.table.dropTable()
                except Exception as e2:
                    methods_tried.append({'method': 'full_path', 'success': False, 'error': str(e2)})
                    print(f"   ❌ Method 2 failed: {e2}")
            
            # Method 3: Try different path variations
            if not success:
                path_variations = [
                    file_name,
                    f"dataFiles/{file_name}",
                    f"dataFiles_*/{file_name}",
                    file_path if file_path else file_name
                ]
                
                for i, path_var in enumerate(path_variations, 3):
                    if path_var == file_name and i > 3:
                        continue  # Already tried
                    try:
                        table_name = f"test_{i}"
                        loaded = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                        conn.table.loadTable(sourceCaslib=target_caslib, casOut=loaded, path=path_var)
                        print(f"   ✅ Method {i} SUCCESS: {path_var}")
                        cols = loaded.columns.tolist()
                        print(f"   Columns: {len(cols)}")
                        success = True
                        methods_tried.append({'method': f'path_variation_{i}', 'path': path_var, 'success': True, 'columns': len(cols)})
                        loaded.table.dropTable()
                        break
                    except Exception as e:
                        methods_tried.append({'method': f'path_variation_{i}', 'path': path_var, 'success': False, 'error': str(e)})
        
        # Try XPT file with CIMPORT
        if xpt_files and not success:
            print(f"\n3. Trying XPT file...")
            xpt_file = xpt_files[0]
            xpt_name = xpt_file.get('Name', '')
            print(f"   File: {xpt_name}")
            
            try:
                # Try using PROC CIMPORT or direct XPT read
                conn.loadactionset('dataStep')
                table_name = "test_xpt"
                loaded = conn.CASTable(table_name, replace=True, caslib='CASUSER')
                
                # Try to import XPT
                code = f'''
                    proc cimport infile="{target_caslib}.{xpt_name}" memtype=data;
                    run;
                '''
                result = conn.dataStep.runCode(code)
                print(f"   ✅ XPT loaded")
                success = True
            except Exception as e:
                print(f"   ⚠️  XPT needs different approach: {e}")
        
        # Check subdirectories
        print(f"\n4. Checking subdirectories...")
        subdirs_to_check = ['dataFiles', 'dataFiles_*', 'data', 'files']
        subdir_files_found = []
        
        for subdir in subdirs_to_check:
            try:
                subdir_result = conn.table.fileInfo(allFiles=True, caslib=target_caslib, path=subdir)
                if hasattr(subdir_result, 'FileInfo'):
                    subdir_files = subdir_result.FileInfo.to_dict('records')
                    if subdir_files:
                        print(f"   ✅ Found {len(subdir_files)} files in {subdir}")
                        subdir_files_found.extend(subdir_files[:5])
            except:
                pass
        
        # Save results
        resolution_results = {
            'metadata': {'date': datetime.now().isoformat(), 'caslib': target_caslib},
            'file_analysis': {
                'total_files': len(files),
                'simple_files': len(simple_files),
                'xpt_files': len(xpt_files),
                'sas_files': len(sas_files)
            },
            'loading_methods_tried': methods_tried,
            'subdirectory_files': subdir_files_found,
            'success': success
        }
        
        output_file = output_dir / 'pds_loading_resolution_results.json'
        with open(output_file, 'w') as f:
            json.dump(resolution_results, f, indent=2, default=str)
        
        print(f"\n💾 Results saved to: {output_file}")
        
        if success:
            print(f"\n✅ SUCCESS! Found working loading method")
        else:
            print(f"\n⚠️  Could not load files with tested methods")
            print(f"   Recommendation: Contact PDS support or try alternative approaches")
    
    conn.close()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()





