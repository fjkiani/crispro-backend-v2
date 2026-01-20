#!/usr/bin/env python3
"""Generate DepMap essentiality summaries by lineage/context.

Inputs
- depmap_raw.csv: DepMap CRISPRGeneEffect matrix (rows: ModelID (ACH-*), cols: "GENE (ENTREZ)")
- depmap_model.csv (optional) OR ../../../../data/depmap/Model.csv (optional): DepMap model metadata

Outputs
- depmap_essentiality_by_context.json

Notes
- If Model.csv is not present, we still emit global summaries and a clear warning.
- For publication, lineage-specific summaries are preferred (e.g., Ovary vs Breast vs Prostate).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Any, List, Optional


GENES_DEFAULT = [
    "ARID1A",
    "ATM",
    "ATR",
    "BRCA1",
    "BRCA2",
    "CDK12",
    "CHEK2",
    "EGFR",
    "KRAS",
    "MBD4",
    "PALB2",
    "PARP1",
    "RAD51C",
    "RAD51D",
    "TP53",
    "WEE1",
]


def _find_model_csv() -> Optional[Path]:
    candidates = [
        Path(__file__).parent / "depmap_model.csv",
        (Path(__file__).parent / "../../../../data/depmap/Model.csv").resolve(),
        (Path(__file__).parent / "../../../../data/depmap/model.csv").resolve(),
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _load_header_cols(raw_path: Path) -> List[str]:
    with raw_path.open("r", encoding="utf-8", errors="replace") as f:
        return f.readline().strip().split(",")


def _map_gene_to_depmap_col(header: List[str], gene: str) -> Optional[str]:
    gene_u = gene.upper()
    for col in header[1:]:
        if col.upper().startswith(gene_u + " "):
            return col
    return None


def _summarize_series(s) -> Dict[str, Any]:
    import pandas as pd

    ss = pd.to_numeric(s, errors="coerce").dropna()
    if ss.empty:
        return {"n_models": 0}

    mean = float(ss.mean())
    return {
        "depmap_mean_effect": mean,
        "depmap_median_effect": float(ss.median()),
        "depmap_p25_effect": float(ss.quantile(0.25)),
        "depmap_p75_effect": float(ss.quantile(0.75)),
        "essentiality_score": float(max(0.0, min(1.0, -mean))),
        "n_models": int(ss.shape[0]),
    }


def main() -> int:
    try:
        import pandas as pd
    except Exception:
        raise SystemExit("pandas is required: pip install pandas")

    raw_path = Path(__file__).parent / "depmap_raw.csv"
    if not raw_path.exists():
        raise SystemExit("Missing depmap_raw.csv. Copy DepMap CRISPRGeneEffect.csv to this directory as depmap_raw.csv")

    genes = GENES_DEFAULT
    header = _load_header_cols(raw_path)

    # Determine which DepMap columns to load
    gene_to_col: Dict[str, str] = {}
    for g in genes:
        col = _map_gene_to_depmap_col(header, g)
        if col:
            gene_to_col[g] = col

    # Build integer usecols list for pandas efficiency
    name_to_idx = {name: i for i, name in enumerate(header)}
    usecols_idx = [0] + [name_to_idx[c] for c in gene_to_col.values()]

    df = pd.read_csv(raw_path, header=0, usecols=usecols_idx)
    df = df.rename(columns={df.columns[0]: "ModelID"})
    # Rename DepMap columns to gene symbols
    for g, col in gene_to_col.items():
        if col in df.columns:
            df = df.rename(columns={col: g})

    model_csv = _find_model_csv()
    model_meta = None
    lineage_map = None

    if model_csv is not None:
        model_df = pd.read_csv(model_csv)
        # We accept either DepMap portal "Model.csv" (column ModelID) or a simplified mapping
        model_id_col = None
        for cand in ["ModelID", "model_id", "DepMap_ID", "depmap_id", "ACH_ID", "Achilles_ID"]:
            if cand in model_df.columns:
                model_id_col = cand
                break
        if model_id_col is None:
            raise SystemExit(f"Could not find ModelID column in {model_csv}. Columns: {list(model_df.columns)[:30]}")

        lineage_col = None
        for cand in ["OncotreeLineage", "lineage", "Lineage", "OncotreeLineage"]:
            if cand in model_df.columns:
                lineage_col = cand
                break
        if lineage_col is None:
            # still allow global summaries
            lineage_col = None

        if lineage_col:
            lineage_map = dict(zip(model_df[model_id_col].astype(str), model_df[lineage_col].astype(str)))
            model_meta = {
                "path": str(model_csv),
                "model_id_col": model_id_col,
                "lineage_col": lineage_col,
                "n_rows": int(model_df.shape[0]),
            }

    out: Dict[str, Any] = {
        "_meta": {
            "raw_file": str(raw_path.resolve()),
            "model_metadata": model_meta,
            "genes": sorted(list(gene_to_col.keys())),
            "note": "If model_metadata is null, only global summaries are available. Add DepMap Model.csv to enable lineage summaries.",
        },
        "global": {},
        "by_lineage": {},
    }

    # Global summaries
    for g in gene_to_col.keys():
        out["global"][g] = _summarize_series(df[g])
        out["global"][g]["source"] = "DepMap CRISPRGeneEffect.csv"

    # Lineage summaries
    if lineage_map:
        df["lineage"] = df["ModelID"].astype(str).map(lineage_map)
        # only keep rows with lineage assigned
        dfx = df.dropna(subset=["lineage"]).copy()
        for lineage, group in dfx.groupby("lineage"):
            lineage = str(lineage)
            out["by_lineage"][lineage] = {}
            for g in gene_to_col.keys():
                out["by_lineage"][lineage][g] = _summarize_series(group[g])
                out["by_lineage"][lineage][g]["source"] = "DepMap CRISPRGeneEffect.csv"

    out_path = Path(__file__).parent / "depmap_essentiality_by_context.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"✅ wrote {out_path} (global genes={len(out['global'])}, lineages={len(out['by_lineage'])})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
