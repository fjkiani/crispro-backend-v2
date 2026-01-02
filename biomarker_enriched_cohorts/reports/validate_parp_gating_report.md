# PARP Gate Proxy Validation (HRD proxy)

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json` (sha256: `11f5428eb7c3d238efa8b2329ee8f8d6942f98a162898099ad93f7b1d2f2791d`)
- **Endpoint**: `os_days` / `os_event`
- **HRD threshold**: `0.42` (on derived `hrd_proxy_numeric`)

## Counts

- Total patients: 585
- Usable (non-missing endpoint + HRD group): 548
- HRD-high: 520
- HRD-low: 28

## Results

- Log-rank p-value: 0.553471338306195
- Median os_days (HRD-high): 1374.0
- Median os_days (HRD-low): 1449.0

## Figure

- `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/figures/figure_parp_hrd_proxy_os.png`

## Notes

- HRD proxy is a **derived** label; treat as a proxy for genomic instability.
- This does **not** validate PARP drug response; it validates biomarker stratification signal in survival endpoints.
