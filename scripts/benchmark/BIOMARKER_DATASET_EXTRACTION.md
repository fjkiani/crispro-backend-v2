# Biomarker Dataset Extraction Guide

## Overview

The enhanced biomarker extraction validation requires a dataset with patient-level data including:
- Mutations (gene, variant_type, etc.)
- Clinical outcomes (PFS_MONTHS, OS_MONTHS, PFS_STATUS, OS_STATUS)
- Optional: TMB, HRD, MSI direct fields (if available)

## Quick Start

### Option 1: Use the Extraction Script (Recommended)

```bash
# From project root
python oncology-coPilot/oncology-backend-minimal/scripts/benchmark/extract_dataset_for_biomarker_validation.py --study ov_tcga_pan_can_atlas_2018
```

This will:
1. Check if dataset already exists (uses existing if found)
2. Extract data from cBioPortal using pybioportal
3. Save to `data/benchmarks/cbioportal_trial_datasets_latest.json`

### Option 2: Use the Full Extraction Script

```bash
# From project root
python oncology-coPilot/oncology-backend-minimal/scripts/benchmark/extract_cbioportal_trial_datasets.py --study ov_tcga_pan_can_atlas_2018
```

### Option 3: Manual Extraction with pybioportal

If you need more control, you can use pybioportal directly:

```python
import sys
from pathlib import Path

# Add pybioportal to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent
PYBIOPORTAL_PATH = PROJECT_ROOT / "oncology-coPilot" / "oncology-backend" / "tests" / "pyBioPortal-master"
sys.path.insert(0, str(PYBIOPORTAL_PATH))

from pybioportal import studies as st
from pybioportal import molecular_profiles as mp
from pybioportal import sample_lists as sl
from pybioportal import mutations as mut
from pybioportal import clinical_data as cd

# Extract data for a study
study_id = "ov_tcga_pan_can_atlas_2018"

# 1. Get patients
patients_df = st.get_all_patients_in_study(study_id)

# 2. Get mutations
profile_id = "ov_tcga_pan_can_atlas_2018_mutations"  # Find this first
sample_list_id = "ov_tcga_pan_can_atlas_2018_all"  # Find this first
mutations_df = mut.get_muts_in_mol_prof_by_sample_list_id(profile_id, sample_list_id)

# 3. Get clinical data
clinical_df = cd.get_all_clinical_data_in_study(study_id, clinical_data_type="PATIENT")

# 4. Combine and save (format as expected by validation script)
# ... (see extract_cbioportal_trial_datasets.py for full implementation)
```

## Dataset Format

The validation script expects a JSON file with the following structure:

```json
[
  {
    "patient_id": "TCGA-XX-XXXX",
    "study_id": "ov_tcga_pan_can_atlas_2018",
    "mutations": [
      {
        "gene": "BRCA1",
        "variant_type": "Nonsense",
        "protein_change": "p.R123*",
        "chromosome": "17",
        "start_position": 43044295,
        "end_position": 43044295,
        "reference_allele": "C",
        "variant_allele": "T",
        "clinvar_classification": "Pathogenic",
        "vep_impact": "HIGH",
        "maf": 0.0001
      }
    ],
    "clinical_outcomes": {
      "PFS_MONTHS": 12.5,
      "PFS_STATUS": "1:Recurred/Progressed",
      "OS_MONTHS": 24.3,
      "OS_STATUS": "1:Deceased",
      "TMB_NONSYNONYMOUS": 2.5,
      "HRD_SCORE": 45.0,
      "MSI_STATUS": "MSS"
    }
  }
]
```

## Key pybioportal Functions

### Patients
- `st.get_all_patients_in_study(study_id)` - Get all patients in a study
- `st.get_patient_in_study(study_id, patient_id)` - Get specific patient

### Mutations
- `mut.get_muts_in_mol_prof_by_sample_list_id(profile_id, sample_list_id)` - Get mutations for a sample list
- `mut.fetch_muts_in_mol_prof(profile_id, sample_ids=...)` - Fetch mutations for specific samples

### Clinical Data
- `cd.get_all_clinical_data_in_study(study_id, clinical_data_type="PATIENT")` - Get all patient-level clinical data
- `cd.fetch_clinical_data(attribute_ids, entity_study_ids, clinical_data_type="PATIENT")` - Fetch specific clinical attributes

### Molecular Profiles
- `mp.get_all_molecular_profiles_in_study(study_id)` - Find mutation profile ID

### Sample Lists
- `sl.get_all_sample_lists_in_study(study_id)` - Find sample list ID (usually ends with "_all")

## Available Studies

Common TCGA studies for ovarian cancer:
- `ov_tcga_pan_can_atlas_2018` - TCGA Ovarian Cancer PanCan Atlas (recommended)
- `ov_tcga` - TCGA Ovarian Cancer (original)

## Running Validation

Once the dataset is extracted:

```bash
python scripts/benchmark/validate_enhanced_biomarkers.py --dataset data/benchmarks/cbioportal_trial_datasets_latest.json
```

## Troubleshooting

### pybioportal Not Found

If you get an import error:
1. Check that pybioportal exists at: `oncology-coPilot/oncology-backend/tests/pyBioPortal-master`
2. The extraction script automatically adds it to the path

### API Rate Limiting

cBioPortal API has rate limits. The extraction script includes delays (`API_DELAY = 1.0` seconds) between calls.

### Missing Data

Some studies may not have all fields:
- TMB, HRD, MSI direct fields are rare in TCGA data
- The enhanced extraction will estimate from mutations when direct fields are unavailable
- This is expected and the validation script will report coverage

## Next Steps

After extraction:
1. Run validation: `python scripts/benchmark/validate_enhanced_biomarkers.py`
2. Review coverage report (HRD: 15-20%, MSI: 3-5% expected)
3. Re-run audit: `python scripts/benchmark/audit_tcga_biomarkers.py`
4. Proceed with benchmarks using enhanced biomarkers

