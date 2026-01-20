# Project Data Sphere API Access Guide

## Status
✅ **Client Created** - `scripts/data_acquisition/utils/project_data_sphere_client.py`
✅ **SSL Certificate** - Located at `/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem`
⚠️ **Authentication Required** - Need username/password or OAuth token

## Connection Details

**CAS Server URL:** `https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/`
**Port:** 443
**SSL Certificate:** `/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem`

## Usage

### Basic Connection Test
```bash
python3 scripts/data_acquisition/utils/project_data_sphere_client.py \
  --cas-url "https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/" \
  --ssl-cert "/Users/fahadkiani/Desktop/development/cristant-main/data/certs/trustedcerts.pem" \
  --username YOUR_USERNAME \
  --password YOUR_PASSWORD
```

### Python API Usage
```python
from scripts.data_acquisition.utils.project_data_sphere_client import ProjectDataSphereClient

client = ProjectDataSphereClient(
    cas_url="https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/",
    ssl_cert_path="/Users/fahadkiani/Desktop/development/crispr-assistant-main/data/certs/trustedcerts.pem"
)

if client.connect(username="YOUR_USERNAME", password="YOUR_PASSWORD"):
    # List all caslibs (data libraries)
    caslibs = client.list_caslibs()
    
    # List files in a caslib
    files = client.list_files_in_caslib("caslib_name")
    
    # Search for ovarian cancer data
    ovarian_data = client.search_for_ovarian_cancer_data()
    
    client.disconnect()
```

## Available Methods

### `list_caslibs()`
Returns list of all available caslibs (data libraries) with:
- `name`: Caslib name
- `description`: Description
- `path`: File system path

### `list_files_in_caslib(caslib_name, path=None)`
Lists all files in a caslib:
- `name`: File name
- `path`: File path within caslib
- `size`: File size in bytes

### `search_for_ovarian_cancer_data()`
Searches all caslibs for files matching ovarian cancer keywords:
- Keywords: 'ovarian', 'ovary', 'ov', 'ca125', 'ca-125', 'platinum', 'pfi', 'serous', 'hgsc'
- Returns list of matching datasets with caslib name, file name, and matched keyword

## Next Steps

1. **Get Credentials**: Obtain username/password or OAuth token for Project Data Sphere
2. **Explore Caslibs**: Once connected, list all available caslibs to understand data structure
3. **Search for Ovarian Cancer Data**: Use the search function to find relevant datasets
4. **Examine File Structure**: For promising caslibs, list files to understand data organization
5. **Load and Analyze**: Use CAS table loading methods to extract data for KELIM validation

## Data Structure

Project Data Sphere uses SAS CAS (Cloud Analytics Services) which organizes data into:
- **Caslibs**: Data libraries (like databases)
- **Tables**: Data tables within caslibs (CSV, SAS datasets, etc.)
- **Files**: Individual data files

## Example Workflow

```python
# 1. Connect
client.connect(username="user", password="pass")

# 2. Find relevant caslibs
caslibs = client.list_caslibs()
ovarian_caslibs = [c for c in caslibs if 'ovarian' in c.get('name', '').lower()]

# 3. Explore files
for caslib in ovarian_caslibs:
    files = client.list_files_in_caslib(caslib['name'])
    print(f"Caslib {caslib['name']} has {len(files)} files")

# 4. Load a table (example from original script)
# core_train = client.conn.CASTable('core_train', replace=True, caslib='CASUSER')
# client.conn.table.loadTable(sourceCaslib="Prostat_na_2006_149", casOut=core_train, path="dataFiles_859/CoreTable_training.csv")
# print(core_train.head())
```

## Notes

- The original example script shows loading tables from caslibs into CAS memory
- Tables can be saved as CSV or SAS datasets
- Clinical trial data may be organized by study or disease type
- CA-125 data may be in biomarker or laboratory result tables
