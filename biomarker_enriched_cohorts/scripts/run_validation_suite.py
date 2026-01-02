#!/usr/bin/env python3
"""Run the biomarker_enriched_cohorts validation suite end-to-end.

This is intended to produce receipts + figures for publication packaging.

RUO only.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'


def run(cmd: list[str], env: dict | None = None) -> None:
    print('\n$ ' + ' '.join(cmd))
    e = os.environ.copy()
    if env:
        e.update(env)
    subprocess.run(cmd, check=True, env=e)


def main() -> int:
    # 1) Build cohorts
    run(['python3', str(ROOT / 'scripts' / 'build_cbioportal_enriched_cohort.py'), '--study_id', 'ucec_tcga_pan_can_atlas_2018'])
    run(['python3', str(ROOT / 'scripts' / 'build_cbioportal_enriched_cohort.py'), '--study_id', 'coadread_tcga_pan_can_atlas_2018'])

    # 2) IO validation on OS
    run(
        ['python3', str(ROOT / 'scripts' / 'validate_io_boost.py'), '--time_col', 'os_days', '--event_col', 'os_event'],
        env={'COHORT_JSON': str(DATA / 'ucec_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_ucec'},
    )
    run(
        ['python3', str(ROOT / 'scripts' / 'validate_io_boost.py'), '--time_col', 'os_days', '--event_col', 'os_event'],
        env={'COHORT_JSON': str(DATA / 'coadread_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_coadread'},
    )



    # 2b) Nature-tier add-ons (UCEC + COADREAD)
    # - Threshold sweep (TMB cutoffs) + baseline comparison (TMB-only vs MSI-only vs OR)
    run(
        ['python3', str(ROOT / 'scripts' / 'tmb_threshold_sweep.py'), '--time_col', 'os_days', '--event_col', 'os_event'],
        env={'COHORT_JSON': str(DATA / 'ucec_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_ucec'},
    )
    run(
        ['python3', str(ROOT / 'scripts' / 'baseline_comparison_io.py'), '--time_col', 'os_days', '--event_col', 'os_event', '--tmb_threshold', '20'],
        env={'COHORT_JSON': str(DATA / 'ucec_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_ucec'},
    )

    run(
        ['python3', str(ROOT / 'scripts' / 'tmb_threshold_sweep.py'), '--time_col', 'os_days', '--event_col', 'os_event'],
        env={'COHORT_JSON': str(DATA / 'coadread_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_coadread'},
    )
    run(
        ['python3', str(ROOT / 'scripts' / 'baseline_comparison_io.py'), '--time_col', 'os_days', '--event_col', 'os_event', '--tmb_threshold', '20'],
        env={'COHORT_JSON': str(DATA / 'coadread_tcga_pan_can_atlas_2018_enriched_v1.json'), 'COHORT_TAG': 'tcga_coadread'},
    )
    # 3) Confidence caps stress-test via simulated missingness (use UCEC)
    missing = DATA / 'ucec_tcga_pan_can_atlas_2018_enriched_v1_missingness.json'
    run(
        ['python3', str(ROOT / 'scripts' / 'simulate_missingness.py'),
         '--in_cohort', str(DATA / 'ucec_tcga_pan_can_atlas_2018_enriched_v1.json'),
         '--out_cohort', str(missing),
         '--seed', '42', '--drop_tmb', '0.55', '--drop_msi', '0.55', '--drop_hrd_inputs', '0.55']
    )
    run(
        ['python3', str(ROOT / 'scripts' / 'validate_confidence_caps.py'), '--endpoint', 'os_days', '--k', '2'],
        env={'COHORT_JSON': str(missing), 'COHORT_TAG': 'tcga_ucec_missingness'},
    )


    # 4) Plot S1 tier distribution for missingness
    run(
        ['python3', str(ROOT / 'scripts' / 'plot_confidence_caps_missingness.py')]
    )

    # 5) Regenerate manuscript docs from latest reports/figures
    run(
        ['python3', str(ROOT / 'scripts' / 'generate_manuscript_docs.py')]
    )

    print('\n✅ validation suite complete')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())