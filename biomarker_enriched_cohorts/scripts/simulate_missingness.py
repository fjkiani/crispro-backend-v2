#!/usr/bin/env python3
"""Simulate biomarker missingness to stress-test confidence caps.

We create a copy of an enriched cohort JSON and randomly drop biomarker fields
(TMB/MSI/aneuploidy/FGA) with configurable probabilities, producing realistic L0/L1/L2 mixes.

RUO only.
"""

from __future__ import annotations

import argparse
import json
import random
from datetime import datetime
from pathlib import Path
from typing import Any


def now_utc_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + 'Z'


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument('--in_cohort', required=True, help='Path to enriched cohort JSON (v1/v2 shape)')
    ap.add_argument('--out_cohort', required=True, help='Path to write simulated cohort JSON')
    ap.add_argument('--seed', type=int, default=42)
    ap.add_argument('--drop_tmb', type=float, default=0.5)
    ap.add_argument('--drop_msi', type=float, default=0.5)
    ap.add_argument('--drop_hrd_inputs', type=float, default=0.5, help='Drop aneuploidy+FGA inputs together')
    args = ap.parse_args()

    rnd = random.Random(args.seed)

    in_path = Path(args.in_cohort)
    out_path = Path(args.out_cohort)

    obj = json.loads(in_path.read_text(encoding='utf-8'))
    pts = (obj.get('cohort') or {}).get('patients') or []

    def maybe_drop(v: Any, p: float) -> Any:
        if v is None:
            return None
        return None if rnd.random() < p else v

    dropped = {'tmb': 0, 'msi': 0, 'hrd_inputs': 0}

    for pt in pts:
        # TMB
        before = pt.get('tmb')
        pt['tmb'] = maybe_drop(before, args.drop_tmb)
        if before is not None and pt['tmb'] is None:
            dropped['tmb'] += 1

        # MSI (drop both raw scores + derived status)
        if rnd.random() < args.drop_msi:
            if pt.get('msi_score_mantis') is not None or pt.get('msi_sensor_score') is not None or pt.get('msi_status') not in (None, 'Unknown'):
                dropped['msi'] += 1
            pt['msi_score_mantis'] = None
            pt['msi_sensor_score'] = None
            pt['msi_status'] = 'Unknown'

        # HRD proxy inputs (drop both)
        if rnd.random() < args.drop_hrd_inputs:
            if pt.get('aneuploidy_score') is not None or pt.get('fraction_genome_altered') is not None:
                dropped['hrd_inputs'] += 1
            pt['aneuploidy_score'] = None
            pt['fraction_genome_altered'] = None
            pt['hrd_proxy'] = 'Unknown'

    # annotate provenance
    prov = obj.get('provenance') or {}
    prov['missingness_simulation'] = {
        'generated_at': now_utc_iso(),
        'seed': args.seed,
        'drop_tmb': args.drop_tmb,
        'drop_msi': args.drop_msi,
        'drop_hrd_inputs': args.drop_hrd_inputs,
        'dropped_counts': dropped,
        'input_path': str(in_path),
    }
    obj['provenance'] = prov

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')
    print('✅ wrote', out_path)
    print('dropped', dropped)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
