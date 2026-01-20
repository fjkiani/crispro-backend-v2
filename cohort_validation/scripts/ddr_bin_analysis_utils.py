"""Shared utilities for DDR_bin Phase-2/3 analyses.

Keep dependencies minimal (numpy + stdlib).
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np


def auroc_rank(y: np.ndarray, score: np.ndarray) -> float:
    """AUROC using Mann–Whitney rank formulation."""
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = score[y == 1]
    neg = score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")

    allv = np.concatenate([pos, neg])
    ranks = allv.argsort().argsort().astype(float) + 1.0
    rpos = ranks[: len(pos)].sum()
    auc = (rpos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
    return float(auc)


def platinum_to_y(platinum_response: str) -> Optional[int]:
    if platinum_response not in ("sensitive", "resistant", "refractory"):
        return None
    return 1 if platinum_response in ("resistant", "refractory") else 0


def parse_stage_group(stage: Optional[str]) -> Optional[str]:
    """Coarse stage bucket: III or IV.

    Accepts strings like 'Stage IIIC', 'Stage IV', etc.
    """
    if not stage:
        return None
    s = str(stage).upper()
    # Prefer IV match first.
    if "IV" in s:
        return "IV"
    if "III" in s:
        return "III"
    return None


def patient_diamond_value(patient: Dict, diamond_idx: int) -> float:
    """Patient-level value for a single diamond: max abs(feature) across variants."""
    variants = patient.get("variants", []) or []
    best = 0.0
    for v in variants:
        top = v.get("top_features", []) or []
        if not top:
            continue
        # build lookup for this variant
        for tf in top:
            try:
                idx = int(tf.get("index"))
            except Exception:
                continue
            if idx != int(diamond_idx):
                continue
            try:
                val = float(tf.get("value") or 0.0)
            except Exception:
                val = 0.0
            best = max(best, abs(val))
    return float(best)


def variant_ddr_scores(patient: Dict, diamond_indices: Sequence[int]) -> Tuple[List[float], List[float]]:
    """Return per-variant (max_of_diamonds, sum_of_diamonds) scores.

    - max_of_diamonds: max abs across diamond indices present in that variant
    - sum_of_diamonds: sum abs across diamond indices present in that variant
    """
    variants = patient.get("variants", []) or []
    v_max: List[float] = []
    v_sum: List[float] = []

    diamond_set = set(int(x) for x in diamond_indices)

    for v in variants:
        top = v.get("top_features", []) or []
        if not top:
            continue
        mx = 0.0
        sm = 0.0
        for tf in top:
            try:
                idx = int(tf.get("index"))
            except Exception:
                continue
            if idx not in diamond_set:
                continue
            try:
                val = float(tf.get("value") or 0.0)
            except Exception:
                val = 0.0
            aval = abs(val)
            mx = max(mx, aval)
            sm += aval
        v_max.append(float(mx))
        v_sum.append(float(sm))

    return v_max, v_sum
