## DepMap lineage-specific essentiality (publication-grade)

### Current state
- We have **DepMap CRISPRGeneEffect** matrix locally as `depmap_raw.csv`.
- We currently compute **global** gene effect summaries across *all* models (n≈1186).
- To compute **lineage-specific** summaries (e.g., Ovary vs Breast vs Prostate), we need DepMap model metadata.

### What you need to add
Download DepMap **Model.csv** from the same DepMap release as `CRISPRGeneEffect.csv` and place it at ONE of:
- `data/depmap/Model.csv` (preferred)
- `oncology-coPilot/oncology-backend-minimal/scripts/benchmark_sl/depmap_model.csv`

The file must include:
- `ModelID` (ACH-* IDs)
- `OncotreeLineage` (or another lineage column)

### Generate lineage summaries
From `oncology-coPilot/oncology-backend-minimal/scripts/benchmark_sl/`:

```bash
python3 generate_depmapy_lineage.py
```

Outputs:
- `depmap_essentiality_by_context.json`
  - `global` (always)
  - `by_lineage` (only if Model.csv present)

### Use in dataset
`create_100_case_dataset.py` now prefers:
- lineage-specific essentiality if available (Ovary/Breast/Prostate mapping)
- otherwise falls back to global.

To regenerate dataset:

```bash
python3 create_100_case_dataset.py
python3 validate_test_cases.py test_cases_100.json
```
