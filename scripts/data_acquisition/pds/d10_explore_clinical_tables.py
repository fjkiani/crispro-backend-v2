#!/usr/bin/env python3
"""D10: Project Data Sphere - Clinical Data Table Exploration"""

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
print("D10: Clinical Data Table Exploration")
print("=" * 80)

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

# Load D9 results
d9_file = output_dir / 'd9_project_data_sphere_multiple_caslibs_analysis.json'
with open(d9_file, 'r') as f:
    d9_data = json.load(f)

high_priority = ['Multiple_MerckKG_2008_441', 'Multiple_SanofiU_2008_119', 'Multiple_Brigham_454', 'Multiple_Allianc_2002_213']

try:
    conn = swat.CAS(cas_url, 443, username=sas_username, password=password)
    print("✅ Connected!")
    
    ca125_keywords = ['ca125', 'ca-125', 'ca_125', 'cancer antigen 125', 'muc16']
    pfi_keywords = ['pfi', 'platinum free interval', 'platinum-free', 'time to progression', 'ttp', 'progression free', 'pfs']
    ovarian_keywords = ['ovarian', 'ovary', 'ov', 'gynecologic', 'gyn', 'serous']
    
    results = []
    all_ca125 = []
    all_pfi = []
    all_ovarian = []
    
    for caslib_name in high_priority:
        print(f"\n📁 Exploring: {caslib_name}")
        result = {
            'caslib_name': caslib_name,
            'tables': [],
            'accessible_tables': [],
            'ca125_fields': [],
            'pfi_fields': [],
            'ovarian_indicators': [],
            'errors': []
        }
        
        try:
            # List tables
            table_result = conn.table.tableInfo(caslib=caslib_name)
            if hasattr(table_result, 'TableInfo'):
                tables = table_result.TableInfo.to_dict('records')
                result['tables'] = [t.get('Name', '') for t in tables]
                print(f"  Found {len(tables)} tables")
                
                # Examine first 5 tables
                for table_info in tables[:5]:
                    table_name = table_info.get('Name', '')
                    if not table_name:
                        continue
                    
                    try:
                        print(f"    🔍 Examining: {table_name}")
                        sample = conn.CASTable(table_name, caslib=caslib_name)
                        columns = sample.columns.tolist()
                        
                        table_analysis = {
                            'table_name': table_name,
                            'column_count': len(columns),
                            'columns': columns[:20],  # First 20 columns
                            'ca125_columns': [],
                            'pfi_columns': [],
                            'ovarian_columns': []
                        }
                        
                        for col in columns:
                            col_lower = str(col).lower()
                            
                            if any(kw in col_lower for kw in ca125_keywords):
                                table_analysis['ca125_columns'].append(col)
                                result['ca125_fields'].append({'table': table_name, 'column': col})
                                all_ca125.append({'caslib': caslib_name, 'table': table_name, 'column': col})
                                print(f"      ⭐ CA-125: {col}")
                            
                            if any(kw in col_lower for kw in pfi_keywords):
                                table_analysis['pfi_columns'].append(col)
                                result['pfi_fields'].append({'table': table_name, 'column': col})
                                all_pfi.append({'caslib': caslib_name, 'table': table_name, 'column': col})
                                print(f"      ⭐ PFI: {col}")
                            
                            if any(kw in col_lower for kw in ovarian_keywords):
                                table_analysis['ovarian_columns'].append(col)
                                result['ovarian_indicators'].append({'table': table_name, 'column': col})
                                all_ovarian.append({'caslib': caslib_name, 'table': table_name, 'column': col})
                                print(f"      ⭐ Ovarian: {col}")
                        
                        result['accessible_tables'].append(table_analysis)
                    except Exception as e:
                        error_msg = f"Could not access {table_name}: {str(e)}"
                        print(f"    ⚠️  {error_msg}")
                        result['errors'].append(error_msg)
            else:
                print(f"  ⚠️  No tables found or access denied")
                result['errors'].append("No tables found or access denied")
        except Exception as e:
            error_msg = f"Error listing tables: {str(e)}"
            print(f"  ❌ {error_msg}")
            result['errors'].append(error_msg)
        
        results.append(result)
    
    # Save results
    output = {
        'metadata': {
            'exploration_date': datetime.now().isoformat(),
            'caslibs_explored': len(high_priority),
            'ca125_keywords': ca125_keywords,
            'pfi_keywords': pfi_keywords,
            'ovarian_keywords': ovarian_keywords
        },
        'summary': {
            'total_ca125_fields': len(all_ca125),
            'total_pfi_fields': len(all_pfi),
            'total_ovarian_indicators': len(all_ovarian),
            'caslibs_with_ca125': len([r for r in results if r.get('ca125_fields')]),
            'caslibs_with_pfi': len([r for r in results if r.get('pfi_fields')]),
            'caslibs_with_ovarian': len([r for r in results if r.get('ovarian_indicators')])
        },
        'field_mapping': {
            'ca125_fields': all_ca125,
            'pfi_fields': all_pfi,
            'ovarian_indicators': all_ovarian
        },
        'caslib_details': results
    }
    
    output_file = output_dir / 'd10_project_data_sphere_clinical_data_mapping.json'
    with open(output_file, 'w') as f:
        json.dump(output, f, indent=2)
    
    print(f"\n{'='*80}")
    print("✅ D10 EXPLORATION COMPLETE")
    print(f"{'='*80}")
    print(f"\n📊 Summary:")
    print(f"   - Caslibs explored: {len(high_priority)}")
    print(f"   - CA-125 fields found: {len(all_ca125)}")
    print(f"   - PFI fields found: {len(all_pfi)}")
    print(f"   - Ovarian indicators found: {len(all_ovarian)}")
    print(f"\n💾 Results saved to: {output_file}")
    
    conn.close()
    
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()





