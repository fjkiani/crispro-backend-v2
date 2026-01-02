# Confidence Caps — Completeness Tier Variability Check

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/tcga_ov_enriched_v2.json` (sha256: `11f5428eb7c3d238efa8b2329ee8f8d6942f98a162898099ad93f7b1d2f2791d`)
- **Endpoint**: `os_days`
- **L2 rule**: ≥2 biomarkers present

## Tier counts (usable rows)

{'L2': 547, 'L1': 21, 'L0': 3}

## Variability by tier

### L0
- n: 3
- median: 338.0
- IQR: 384.0
- mean: 567.3333333333334
- std: 432.32086849160237
- CV: 0.7620226824176305

### L1
- n: 21
- median: 1452.0
- IQR: 833.0
- mean: 1384.0
- std: 743.4032553062974
- CV: 0.5371410804236253

### L2
- n: 547
- median: 1000.0
- IQR: 1198.5
- mean: 1180.0237659963436
- std: 939.7660985303543
- CV: 0.796395907956032

## Notes
- These tiers are used to justify conservative confidence caps on incomplete data.
