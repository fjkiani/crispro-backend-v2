# Confidence Caps — CompletenTier Variability Check ({tag})

- **Cohort**: `/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/biomarker_enriched_cohorts/data/ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json` (sha256: `54cc8e04917b097e7f1ee888dd262f4a8eae4d4ea41651f3682313ce4b23429a`)
- **Endpoint**: `os_days`
- **L2 rule**: ≥2 biomarkers present

## Tier counts (usable rows)

{'L2': 228, 'L1': 214, 'L0': 86}

## Variability by tier

### L0
- n: 86
- median: 930.6267875853125
- IQR: 1280.3623385664064
- mean: 1338.482878687256
- std: 1164.8560844910617
- CV: 0.8702809001438387

### L1
- n: 214
- median: 912.1143193121875
- IQR: 922.6213959798436
- mean: 1074.9062044741936
- std: 809.8117804727581
- CV: 0.7533790177245182

### L2
- n: 228
- median: 906.6106123884374
- IQR: 1229.8283032626564
- mean: 1145.2274640062653
- std: 883.7896561226369
- CV: 0.7717153874662945

## Notes
- These tiers are used to justify conservative confidence caps on incomplete data.
