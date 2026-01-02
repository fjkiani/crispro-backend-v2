#!/usr/bin/env python3
"""Build an outcome-labeled + biomarker-enriched cohort from a cBioPortal study.

Purpose
- Produce a cohort JSON artifact with the SAME shape as tcga_ov_enriched_v2.json so we can
  re-use the existing validation scripts (IO boost, confidence caps, etc.) by pointing
  COHORT_JSON at the new artifact.

Inputs
- cBioPortal study_id (e.g., coadread_tcga_pan_can_atlas_2018, ucec_tcga_pan_can_atlas_2018)

Outputs (under biomarker_enriched_cohorts/data/)
- <study_id>_enriched_v1.json
- receipts/<study_id>_enriched_v1_receipt_<YYYYMMDD>.json

Notes
- RUO only.
- Uses existing pyBioPortal-based extractor already in repo.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def out_dir(self) -> Path:
        return self.root / 'data'

    @property
    def receipts_dir(self) -> Path:
        return self.root / 'receipts'


def now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def derive_msi_status(msi_mantis: Optional[float], msi_sensor: Optional[float]) -> str:
    if msi_mantis is not None and msi_mantis > 0.4:
        return 'MSI-H'
    if msi_sensor is not None and msi_sensor > 3.5:
        return 'MSI-H'
    if (msi_mantis is not None) or (msi_sensor is not None):
        return 'MSS'
    return 'Unknown'


def derive_hrd_proxy(aneuploidy: Optional[float], fga: Optional[float]) -> str:
    # Keep identical to merge_enriched_cohort.py for consistency.
    if aneuploidy is None or fga is None:
        return 'Unknown'
    if aneuploidy >= 15 and fga >= 0.4:
        return 'HRD-High'
    if aneuploidy >= 10 or fga >= 0.3:
        return 'HRD-Intermediate'
    return 'HRD-Low'


def safe_float(v: Any) -> Optional[float]:
    try:
        if v is None:
            return None
        x = float(v)
        if pd.isna(x):
            return None
        return x
    except Exception:
        return None


def build_from_clinical_df(study_id: str, clinical_wide: pd.DataFrame) -> Dict[str, Any]:
    # Expected columns from extract_clinical_outcomes(): patientId, OS_MONTHS, OS_STATUS, PFS_MONTHS, PFS_STATUS, ...
    def parse_event(status: Any) -> Optional[bool]:
        if status is None:
            return None
        s = str(status).strip().upper()
        # common cbioportal patterns: 'DECEASED' / 'LIVING', '1:DECEASED', etc.
        if 'DECEASED' in s or s in {'1', 'TRUE'}:
            return True
        if 'LIVING' in s or s in {'0', 'FALSE'}:
            return False
        return None

    def months_to_days(m: Any) -> Optional[float]:
        x = safe_float(m)
        if x is None:
            return None
        return float(x) * 30.4375

    patients: List[Dict[str, Any]] = []
    coverage = {
        'os_days': 0,
        'pfs_days': 0,
        'tmb': 0,
        'msi_score_mantis': 0,
        'msi_sensor_score': 0,
        'aneuploidy_score': 0,
        'fraction_genome_altered': 0,
        'bmi': 0,
        'albumin': 0,
        'age': 0,
    }

    for _, row in clinical_wide.iterrows():
        pid = row.get('patientId')
        if not pid:
            continue

        os_days = months_to_days(row.get('OS_MONTHS'))
        pfs_days = months_to_days(row.get('PFS_MONTHS'))
        os_event = parse_event(row.get('OS_STATUS'))
        pfs_event = parse_event(row.get('PFS_STATUS'))

        tmb = safe_float(row.get('TMB_NONSYNONYMOUS'))
        msi_mantis = safe_float(row.get('MSI_SCORE_MANTIS'))
        msi_sensor = safe_float(row.get('MSI_SENSOR_SCORE'))
        aneuploidy = safe_float(row.get('ANEUPLOIDY_SCORE'))
        fga = safe_float(row.get('FRACTION_GENOME_ALTERED'))
        
        # Extract body composition fields for ECW/TBW surrogate
        bmi = safe_float(row.get('BMI')) or safe_float(row.get('BODY_MASS_INDEX'))
        albumin = safe_float(row.get('ALBUMIN'))
        age = safe_float(row.get('AGE')) or safe_float(row.get('AGE_AT_DIAGNOSIS'))

        if os_days is not None:
            coverage['os_days'] += 1
        if pfs_days is not None:
            coverage['pfs_days'] += 1
        if tmb is not None:
            coverage['tmb'] += 1
        if msi_mantis is not None:
            coverage['msi_score_mantis'] += 1
        if msi_sensor is not None:
            coverage['msi_sensor_score'] += 1
        if aneuploidy is not None:
            coverage['aneuploidy_score'] += 1
        if fga is not None:
            coverage['fraction_genome_altered'] += 1
        if bmi is not None:
            coverage['bmi'] += 1
        if albumin is not None:
            coverage['albumin'] += 1
        if age is not None:
            coverage['age'] += 1

        patients.append(
            {
                'patient_id': str(pid),
                'outcomes': {
                    'os_days': os_days,
                    'os_event': os_event,
                    'pfs_days': pfs_days,
                    'pfs_event': pfs_event,
                },
                'tmb': tmb,
                'msi_score_mantis': msi_mantis,
                'msi_sensor_score': msi_sensor,
                'msi_status': derive_msi_status(msi_mantis, msi_sensor),
                'aneuploidy_score': aneuploidy,
                'fraction_genome_altered': fga,
                'hrd_proxy': derive_hrd_proxy(aneuploidy, fga),
                'brca_somatic': None,
                'germline_brca_status': 'unknown',
                'bmi': bmi,
                'albumin': albumin,
                'age': age,
            }
        )

    n = len(patients)
    cov_pct = {k: (float(v) / float(n) * 100.0 if n else 0.0) for k, v in coverage.items()}

    return {
        'cohort': {
            'source': f'cBioPortal clinical attributes ({study_id})',
            'study_id': study_id,
            'n_patients': n,
            'generated_at': now_utc_iso(),
            'patients': patients,
        },
        'coverage': {
            k: {'n': int(coverage[k]), 'pct': round(cov_pct[k], 1)} for k in coverage
        },
        'provenance': {
            'builder': 'build_cbioportal_enriched_cohort.py',
            'notes': 'Derived os_days/pfs_days from OS_MONTHS/PFS_MONTHS. Derived MSI from MANTIS/MSIsensor thresholds. HRD proxy from aneuploidy+FGA thresholds (exploratory). Extracted BMI, albumin, and age for ECW/TBW surrogate computation.',
        },
    }


def main() -> None:
    import argparse

    ap = argparse.ArgumentParser()
    ap.add_argument('--study_id', required=True)
    ap.add_argument('--out_name', default=None, help='Override output base name (default: <study_id>_enriched_v1)')
    args = ap.parse_args()

    root = Path(__file__).resolve().parent.parent
    paths = Paths(root=root)
    paths.out_dir.mkdir(parents=True, exist_ok=True)
    paths.receipts_dir.mkdir(parents=True, exist_ok=True)
    # Extract clinical outcomes (PATIENT clinical attributes) via local pyBioPortal client
    import sys
    import time
    from pathlib import Path as _Path

    REPO_ROOT = _Path(__file__).resolve().parents[4]  # crispr-assistant-main
    PYBIOPORTAL_PATH = REPO_ROOT / 'oncology-coPilot' / 'oncology-backend' / 'tests' / 'pyBioPortal-master'
    if PYBIOPORTAL_PATH.exists() and str(PYBIOPORTAL_PATH) not in sys.path:
        sys.path.insert(0, str(PYBIOPORTAL_PATH))

    try:
        from pybioportal import clinical_data as cd
    except Exception as e:
        raise SystemExit(f'Failed to import pyBioPortal from {PYBIOPORTAL_PATH}: {e}')

    API_DELAY = 1.0

    def extract_clinical_outcomes(study_id: str) -> pd.DataFrame:
        """Return a patient-level wide table with outcomes (PATIENT) and biomarkers (SAMPLE when needed)."""
        print(f'   📡 Extracting clinical outcomes for {study_id}...')
        time.sleep(API_DELAY)
        patient_df = cd.get_all_clinical_data_in_study(
            study_id=study_id,
            clinical_data_type='PATIENT',
            pageSize=200000,
        )
        if patient_df is None or patient_df.empty:
            return pd.DataFrame()
        wide = None
        if 'patientId' in patient_df.columns and 'clinicalAttributeId' in patient_df.columns:
            wide = patient_df.pivot(index='patientId', columns='clinicalAttributeId', values='value')
            wide.reset_index(inplace=True)
        else:
            return pd.DataFrame()

        # Pull biomarker fields from SAMPLE clinical data (these are often sample-level in PanCan Atlas).
        wanted = ['TMB_NONSYNONYMOUS','MSI_SCORE_MANTIS','MSI_SENSOR_SCORE','ANEUPLOIDY_SCORE','FRACTION_GENOME_ALTERED']
        try:
            sample_df = cd.get_all_clinical_data_in_study(
                study_id=study_id,
                clinical_data_type='SAMPLE',
                pageSize=400000,
            )
        except Exception:
            sample_df = pd.DataFrame()

        if sample_df is not None and (not sample_df.empty) and 'patientId' in sample_df.columns:
            sdf = sample_df[sample_df['clinicalAttributeId'].isin(wanted)].copy()
            # map per-patient: first non-null value per attribute
            for attr in wanted:
                sub = sdf[sdf['clinicalAttributeId'] == attr][['patientId','value']]
                if sub.empty:
                    continue
                # take first value per patient
                m = sub.groupby('patientId')['value'].first()
                wide[attr] = wide['patientId'].map(m)

        # numeric casts (best-effort)
        # Include BMI and ALBUMIN for ECW/TBW surrogate computation
        body_comp_fields = ['BMI', 'BODY_MASS_INDEX', 'ALBUMIN', 'AGE', 'AGE_AT_DIAGNOSIS']
        for field in ['OS_MONTHS','PFS_MONTHS','DFS_MONTHS','DSS_MONTHS'] + body_comp_fields + wanted:
            if field in wide.columns:
                wide[field] = pd.to_numeric(wide[field], errors='coerce')
        return wide

    study_id = args.study_id
    print(f'📡 Fetching clinical outcomes for {study_id} ...')
    clinical_wide = extract_clinical_outcomes(study_id)
    if clinical_wide is None or clinical_wide.empty:
        raise SystemExit(f'No clinical data returned for {study_id}')

    artifact = build_from_clinical_df(study_id, clinical_wide)

    base = args.out_name or f'{study_id}_enriched_v1'
    out_path = paths.out_dir / f'{base}.json'
    out_path.write_text(json.dumps(artifact, indent=2) + '\n', encoding='utf-8')

    receipt = {
        'run': {
            'generated_at': now_utc_iso(),
            'study_id': study_id,
            'out_path': str(out_path),
        },
        'coverage': artifact.get('coverage'),
        'n_patients': (artifact.get('cohort') or {}).get('n_patients'),
    }

    stamp = datetime.utcnow().strftime('%Y%m%d')
    rec_path = paths.receipts_dir / f'{base}_receipt_{stamp}.json'
    rec_path.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')

    print('✅ wrote:', out_path)
    print('✅ receipt:', rec_path)


if __name__ == '__main__':
    main()
