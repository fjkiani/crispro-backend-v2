# Project Data Sphere - Data Access Findings

## ✅ Connection Status
**Status:** Successfully connected with SAS credentials
- SAS Username: `mpm0fxk2`
- CAS URL: `https://mpmprodvdmml.ondemand.sas.com/cas-shared-default-http/`
- SSL Certificate: Configured

## 📊 Available Data

### Total Caslibs: 102

**Caslibs by Cancer Type:**
- Breast: 17 caslibs
- Colorec (Colorectal): 16 caslibs
- Prostat (Prostate): 19 caslibs
- LungNo (Non-small cell lung): 9 caslibs
- LungSm (Small cell lung): 6 caslibs
- Pancrea (Pancreatic): 6 caslibs
- Multiple: 6 caslibs
- Gastric: 4 caslibs
- HeadNe (Head & Neck): 4 caslibs
- Glioma: 2 caslibs
- Others: 13 caslibs

### ⚠️ Key Finding: No Explicit Ovarian Cancer Caslibs

**Observation:** Project Data Sphere does not have dedicated ovarian cancer caslibs in the current datwever:
- Ovarian cancer data may be in "Multiple" cancer type caslibs
- Data may be in general oncology caslibs
- May need to search within clinical data tables across all caslibs

## 🔍 Search Results

**Ovarian/CA-125 File Search:**
- Searched all 102 caslibs for files matching keywords: `ovarian`, `ovary`, `ov`, `ca125`, `ca-125`, `platinum`, `pfi`, `serous`, `hgsc`
- Found 3 files (likely false positives matching "ov" in other words like "Pfizer", "Pancrea")

## 📁 Data Structure

**Caslib Organization:**
- Format: `CancerType_Sponsor_Year_ID`
- Example: `Breast_Pfizer_2006_112`
- Each caslib contains:
  - Clinical data files
  - Case report forms (PDFs)
  - Data dictionaries
  - Documentation files

**File Types Found:**
- CSV files (clinical data)
- SAS datasets (.sas7bdat)
- PDF files (case report forms, documentation)
- Excel files (.xlsx)
- Word documents (.docx)

## 🎯 How to Extract Data for KELIM Validation

### Step 1: Identify Relevant Caslibs
1. Check "Multiple" cancer type caslibs for n cancer data
2. Review caslib descriptions for ovarian cancer mentions
3. Search clinical data tables for ovarian cancer patients

### Step 2: Load Clinical Data Tables
```python
# Example: Load a table from a caslib
core_train = conn.CASTable('core_train', replace=True, caslib='CASUSER')
conn.table.loadTable(
    sourceCaslib="caslib_name",
    casOut=core_train,
    path="path/to/file.csv"
)

# View data
print(core_train.head())

# Save to CSV
core_train.to_csv('output.csv')
```

### Step 3: Search for CA-125 Data
- Look for columns named: `CA125`, `CA-125`, `CA_125`, `Cancer Antigen 125`
- Check biomarker/lab result tables
- Review data dictionaries for field names

### Step 4: Extract PFI Outcomes
- Look for columns: `PFI`, `Platinum Free Interval`, `Time to Progression`, `PFS`
- Check clinical outcome tables
- Calculate PFI from treatment dates if needed

## 📋 Next Steps

1. **Explore "Multiple" Caslibs**
   - These may contain mixed cancer types including ovarian
   - Check file structures and datdictionaries

2. **Search Clinical Data Tables**
   - Load sample tables from accessible caslibs
   - Examine column names for CA-125 and PFI fields
   - Review data dictionaries

3. **Alternative Data Sources**
   - Consider that Project Data Sphere may not have ovarian cancer data
   - Focus on other sources: cBioPortal, ClinicalTrials.gov, GDC
   - Contact Project Data Sphere support to inquire about ovarian cancer datasets

## 🔧 Available Tools

**Client Script:** `scripts/data_acquisition/utils/project_data_sphere_client.py`
- Methods for listing caslibs
- Methods for listing files
- Methods for searching ovarian cancer data
- Ready to use once we identify relevant caslibs

**Exploration Script:** `scripts/data_acquisition/explore_project_data_sphere.py`
- Comprehensive exploration of all caslibs
- File structure analysis
- Data extraction capabilities

## 📝 Notes

- Some caslibs may have access restrictions
- Data may require approval for specific studies
- Clinical trial data is typically de-idfied
- Data dictionaries are essential for understanding field names
