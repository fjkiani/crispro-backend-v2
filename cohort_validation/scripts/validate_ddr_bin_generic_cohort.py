#!/usr/bin/env python3
"""
DDR_bin Generic Cohort Validator (External Replication Harness)

Purpose:
  Run the same DDR_bin validation logic on ANY cohort that matches the Tier-3
  cohort schema, linked to ANY cBioPortal-style clinical+mutation dataset.

This is the external-validation harness (A8) that lets us replicate the analysis
once we have a new cohort extracted (e.g., ICGC-OV).

Inputs:
  --cohort_json: Tier3-style cohort json:
      { "data": { "<patient_id>": { "variants": [...], "outcome": <optional> } } }
  --cbioportal_dataset: list of studies (same format as data/benchmarks/cbioportal_trial_datasets_latest.json)
  --study_id: which study to use from the dataset
  --diamond_mapping: mapping file with {"features": [{"feature_index": ...}, ...]}
  --out_dir: where to write report + linked CSV

Outputs:
  - report.json
  - linked_patients.csv

Notes:
  - A3 platinum-response AUROC is only computed if cohort_json includes outcome labels.
  - This script is deterministic/offline.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Optional

import numpy as np
import scipy.stats


def parse_event_status(status_str: Optional[str]) -> Optional[int]:
    if not status_str or not isinstance(status_str, str):
        return None
    if status_str.startswith("1:"):
        return 1
    if status_str.startswith("0:"):
        return 0
    return None


def parse_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, str):
        if value.lower() in ("nan", "none", ""):
            return None
        try:
            return float(value)
        except ValueError:
            return None
    try:
        fval = float(value)
        if math.isnan(fval):
            return None
        return fval
    except (ValueError, TypeError):
        return None


def auroc_rank(y: np.ndarray, score: np.ndarray) -> float:
    """AUROC using Mann–Whitney rank formulation with tie-aware average ranks.

    Critical: if scores are tied (e.g., all zeros), AUROC must be 0.5.
    """
    y = np.asarray(y).astype(int)
    score = np.asarray(score).astype(float)
    pos = score[y == 1]
    neg = score[y == 0]
    if len(pos) == 0 or len(neg) == 0:
        return float("nan")

    allv = np.concatenate([pos, neg])
    # rankdata assigns average ranks to ties => constant scores => AUROC=0.5
    ranks = scipy.stats.rankdata(allv, method="average")
    rpos = ranks[: len(pos)].sum()
    auc = (rpos - len(pos) * (len(pos) + 1) / 2.0) / (len(pos) * len(neg))
    return float(auc)



def load_diamond_indices(mapping_path: Path) -> List[int]:
    """Load diamond feature indices from mapping file.
    
    Supports two formats:
    1. {"features": [{"feature_index": N}, ...]}  (legacy)
    2. {"features": {"diamond_features": [N, ...], "feature_list": [N, ...]}}  (current)
    """
    with open(mapping_path) as f:
        mapping = json.load(f)
    features = mapping.get("features", {})
    
    # Try new format first: features.diamond_features or features.feature_list
    if isinstance(features, dict):
        diamond_list = features.get("diamond_features", [])
        if diamond_list:
            return sorted(set(int(x) for x in diamond_list))
        feature_list = features.get("feature_list", [])
        if feature_list:
            return sorted(set(int(x) for x in feature_list))
    
    # Fall back to legacy format: features = [{"feature_index": N}, ...]
    if isinstance(features, list):
        idxs = [int(feat["feature_index"]) for feat in features if isinstance(feat, dict) and "feature_index" in feat]
        if idxs:
            return sorted(set(idxs))
    
    raise ValueError(f"No diamond features found in {mapping_path}. Expected 'features.diamond_features' or 'features' list.")


def compute_ddr_bin(patient_data: Dict, diamond_indices: List[int]) -> Dict:
    """Compute patient DDR_bin (max_of_max) + coverage metrics."""
    variants = patient_data.get("variants", []) or []
    if not variants:
        return {"ddr_bin": 0.0, "ddr_bin_coverage": 0.0, "ddr_bin_num_variants": 0}

    diamond_set = set(diamond_indices)
    variant_scores = []
    variants_with_diamond = 0

    for v in variants:
        top = v.get("top_features", []) or []
        if not top:
            continue
        mx = 0.0
        has = False
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
            mx = max(mx, abs(val))
            has = True
        if has:
            variants_with_diamond += 1
        variant_scores.append(float(mx))

    ddr_bin = max(variant_scores) if variant_scores else 0.0
    coverage = variants_with_diamond / len(variants) if variants else 0.0
    return {"ddr_bin": float(ddr_bin), "ddr_bin_coverage": float(coverage), "ddr_bin_num_variants": int(len(variants))}


def compute_gene_ddr_flag(mutations: List[Dict], ddr_genes: List[str]) -> int:
    if not mutations:
        return 0
    genes = set()
    for mut in mutations:
        if isinstance(mut, dict):
            g = mut.get("gene")
            if g:
                genes.add(str(g).upper())
        elif isinstance(mut, str):
            genes.add(mut.upper())
    return 1 if bool(genes & set(x.upper() for x in ddr_genes)) else 0


def link_patients(
    cohort_path: Path,
    cbioportal_dataset_path: Path,
    study_id: str,
    diamond_mapping: Path,
    ddr_genes: List[str],
) -> List[Dict]:
    with open(cohort_path) as f:
        cohort = json.load(f)
    patients = cohort.get("data", {})
    if not isinstance(patients, dict) or not patients:
        raise ValueError(f"Invalid cohort format: {cohort_path} (expected {{'data': {{...}}}})")

    with open(cbioportal_dataset_path) as f:
        studies = json.load(f)
    study = next((s for s in studies if s.get("study_id") == study_id), None)
    if not study:
        raise ValueError(f"study_id={study_id} not found in {cbioportal_dataset_path}")

    cbio_patients = {p.get("patient_id"): p for p in study.get("patients", []) if p.get("patient_id")}

    diamond_indices = load_diamond_indices(diamond_mapping)

    linked = []
    for pid, pdata in patients.items():
        cb = cbio_patients.get(pid)
        if not cb:
            continue
        ddr_bin_info = compute_ddr_bin(pdata, diamond_indices)

        outcomes = cb.get("clinical_outcomes", {}) or {}
        pfs_months = parse_float(outcomes.get("PFS_MONTHS"))
        pfs_event = parse_event_status(outcomes.get("PFS_STATUS"))
        os_months = parse_float(outcomes.get("OS_MONTHS"))
        os_event = parse_event_status(outcomes.get("OS_STATUS"))

        mutations = cb.get("mutations", []) or []
        gene_ddr = compute_gene_ddr_flag(mutations, ddr_genes)

        linked.append(
            {
                "patient_id": pid,
                "ddr_bin": ddr_bin_info["ddr_bin"],
                "ddr_bin_coverage": ddr_bin_info["ddr_bin_coverage"],
                "ddr_bin_num_variants": ddr_bin_info["ddr_bin_num_variants"],
                "platinum_response": pdata.get("platinum_response") or pdata.get("outcome"),  # optional
                "pfs_months": pfs_months,
                "pfs_event": pfs_event,
                "os_months": os_months,
                "os_event": os_event,
                "gene_ddr": gene_ddr,
                "stage": outcomes.get("CLINICAL_STAGE"),
                "age": parse_float(outcomes.get("AGE")),
                "residual_tumor": outcomes.get("RESIDUAL_TUMOR"),
            }
        )

    return linked


def analyze_survival(linked: List[Dict], endpoint: str) -> Dict:
    months_key = f"{endpoint}_months"
    event_key = f"{endpoint}_event"
    usable = [p for p in linked if p.get(months_key) is not None and p.get(event_key) is not None]
    if len(usable) < 10:
        return {"usable": len(usable), "spearman_rho": None, "spearman_p": None}
    ddr = np.array([p["ddr_bin"] for p in usable], dtype=float)
    time = np.array([p[months_key] for p in usable], dtype=float)
    rho, p = scipy.stats.spearmanr(ddr, time)
    return {"usable": len(usable), "spearman_rho": float(rho), "spearman_p": float(p)}


def _roc_points(y: np.ndarray, s: np.ndarray) -> List[Dict[str, float]]:
    """Compute ROC points for score>=threshold => positive."""
    y = np.asarray(y).astype(int)
    s = np.asarray(s).astype(float)
    thresholds = sorted(set(float(x) for x in s))
    # Add sentinels to ensure full curve coverage
    thresholds = [min(thresholds) - 1.0] + thresholds + [max(thresholds) + 1.0]
    out: List[Dict[str, float]] = []
    for thr in thresholds:
        pred = (s >= thr).astype(int)
        tp = int(((pred == 1) & (y == 1)).sum())
        fp = int(((pred == 1) & (y == 0)).sum())
        tn = int(((pred == 0) & (y == 0)).sum())
        fn = int(((pred == 0) & (y == 1)).sum())
        tpr = tp / max(1, (tp + fn))
        fpr = fp / max(1, (fp + tn))
        out.append({"threshold": float(thr), "tpr": float(tpr), "fpr": float(fpr)})
    # Sort by fpr ascending for plotting
    out.sort(key=lambda d: (d["fpr"], d["tpr"]))
    return out


def _best_youden(points: List[Dict[str, float]]) -> Dict[str, float]:
    best = {"youden_j": -1.0, "threshold": float('nan'), "tpr": float('nan'), "fpr": float('nan')}
    for p in points:
        j = float(p["tpr"] - p["fpr"])
        if j > best["youden_j"]:
            best = {"youden_j": j, "threshold": float(p["threshold"]), "tpr": float(p["tpr"]), "fpr": float(p["fpr"])}
    return best


def analyze_platinum_response(linked: List[Dict]) -> Dict:
    usable = [p for p in linked if p.get("platinum_response") in ("sensitive", "resistant", "refractory")]
    if len(usable) < 10:
        return {
            "usable": len(usable),
            "n_total": len(usable),
            "n_sensitive": None,
            "n_resistant": None,
            "auroc_resistant": None,
            "auroc_sensitive": None,
            "positive_class": "resistant_refractory",
            "note": "No/insufficient platinum labels in cohort_json",
        }

    y = np.array([1 if p["platinum_response"] in ("resistant", "refractory") else 0 for p in usable], dtype=int)
    s = np.array([p["ddr_bin"] for p in usable], dtype=float)

    n_total = int(len(usable))
    n_resistant = int((y == 1).sum())
    n_sensitive = int((y == 0).sum())

    # AUROC for predicting resistant/refractory (higher DDR_bin => more resistant)
    auc_res = auroc_rank(y, s)

    # AUROC for predicting sensitive (use inverted score for clarity)
    y_sens = (1 - y).astype(int)
    s_sens = (-s).astype(float)
    auc_sens = auroc_rank(y_sens, s_sens)

    pts = _roc_points(y, s)
    best = _best_youden(pts)

    # best threshold is for resistant (positive=y==1): predict resistant if score>=threshold
    sensitivity = float(best["tpr"])
    specificity = float(1.0 - best["fpr"])

    return {
        "usable": n_total,
        "n_total": n_total,
        "n_sensitive": n_sensitive,
        "n_resistant": n_resistant,
        "auroc_resistant": float(auc_res),
        "auroc_sensitive": float(auc_sens),
        "positive_class": "resistant_refractory",
        "optimal_threshold": float(best["threshold"]),
        "sensitivity_at_optimal": float(sensitivity),
        "specificity_at_optimal": float(specificity),
        "youden_j": float(best["youden_j"]),
        "roc_points": pts,
        "interpretation": "DDR_bin behaves as a platinum-resistance score (higher => more resistant)",
    }



def main() -> int:

    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort_json", required=True, help="Tier3-style cohort json with variants/top_features")
    ap.add_argument("--cbioportal_dataset", required=True, help="cBioPortal study dataset json (list of studies)")
    ap.add_argument("--study_id", required=True, help="study_id inside cbioportal dataset (e.g. ov_tcga)")
    ap.add_argument("--diamond_mapping", required=True, help="diamond mapping json (feature_index list)")
    ap.add_argument("--out_dir", required=True, help="output directory for report + linked csv")
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    ddr_genes = [
        "BRCA1", "BRCA2", "ATM", "ATR", "CHEK2", "RAD51C", "RAD51D",
        "PALB2", "BARD1", "BRIP1", "FANCA", "FANCD2", "NBN", "MRE11A",
        "TP53", "MBD4",
    ]

    linked = link_patients(
        cohort_path=Path(args.cohort_json),
        cbioportal_dataset_path=Path(args.cbioportal_dataset),
        study_id=args.study_id,
        diamond_mapping=Path(args.diamond_mapping),
        ddr_genes=ddr_genes,
    )

    # Save linked csv
    csv_path = out_dir / "linked_patients.csv"
    fields = [
        "patient_id", "ddr_bin", "ddr_bin_coverage", "ddr_bin_num_variants",
        "platinum_response",
        "pfs_months", "pfs_event", "os_months", "os_event",
        "gene_ddr", "stage", "age", "residual_tumor",
    ]
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(linked)

    report = {
        "run_meta": {
            "study_id": args.study_id,
            "cohort_json": args.cohort_json,
            "cbioportal_dataset": args.cbioportal_dataset,
            "diamond_mapping": args.diamond_mapping,
            "linked_patients": len(linked),
        },
        "pfs": analyze_survival(linked, "pfs"),
        "os": analyze_survival(linked, "os"),
        "platinum_response": analyze_platinum_response(linked),
    }

    with open(out_dir / "report.json", "w") as f:
        json.dump(report, f, indent=2)

    print(f"Linked patients: {len(linked)}")
    print(f"Wrote: {csv_path}")
    print(f"Wrote: {out_dir / 'report.json'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())


