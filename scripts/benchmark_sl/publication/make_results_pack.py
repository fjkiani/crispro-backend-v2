#!/usr/bin/env python3
"""Create a publication-ready results pack from a publication_suite JSON.

Outputs (in publication/):
- results_pack.md
- error_analysis.md
- confusion_breakdown.csv
- figure_bar_chart.svg (text-based)

This is designed to be copy/paste friendly for a manuscript.
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


@dataclass
class MethodSummary:
    name: str
    pos_class_at1: float
    pos_class_ci: Tuple[float, float]
    pos_drug_at1: float
    pos_drug_ci: Tuple[float, float]
    neg_parp_fp: float
    neg_parp_ci: Tuple[float, float]
    n_pos: int
    n_neg: int


def _pct(x: float) -> str:
    return f"{x*100:.1f}%"


def load_report(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def extract_method_summaries(report: Dict[str, Any]) -> List[MethodSummary]:
    out: List[MethodSummary] = []
    for m in report.get("methods", []):
        s = m.get("summary", {})
        pos = s.get("positive", {})
        neg = s.get("negative", {})
        out.append(
            MethodSummary(
                name=m.get("name", ""),
                pos_class_at1=float(pos.get("class_at1") or 0.0),
                pos_class_ci=tuple(pos.get("class_at1_ci95") or (0.0, 0.0)),
                pos_drug_at1=float(pos.get("drug_at1") or 0.0),
                pos_drug_ci=tuple(pos.get("drug_at1_ci95") or (0.0, 0.0)),
                neg_parp_fp=float(neg.get("parp_fp_rate") or 0.0),
                neg_parp_ci=tuple(neg.get("parp_fp_rate_ci95") or (0.0, 0.0)),
                n_pos=int(s.get("n_positive") or 0),
                n_neg=int(s.get("n_negative") or 0),
            )
        )
    return out


def write_results_md(report: Dict[str, Any], methods: List[MethodSummary], out_path: Path) -> None:
    lines: List[str] = []
    lines.append("## Results pack (synthetic lethality publication suite)\n\n")
    lines.append(f"- **Run ID**: `{report.get('run_id')}`\n")
    lines.append(f"- **Dataset**: `{report.get('dataset_file')}`\n")
    lines.append(f"- **API**: `{report.get('api_root')}`\n")
    lines.append(f"- **Model**: `{report.get('model_id')}`\n")
    lines.append(f"- **Bootstrap seed**: `{report.get('seed')}`\n\n")

    lines.append("### Primary table (SL-positive vs SL-negative)\n\n")
    lines.append("| Method | Pos Class@1 | 95% CI | Pos Drug@1 | 95% CI | Neg PARP FP | 95% CI | n_pos | n_neg |\n")
    lines.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|\n")

    for m in methods:
        lines.append(
            "| {name} | {pc} | [{pcl}, {pch}] | {pd} | [{pdl}, {pdh}] | {nf} | [{nfl}, {nfh}] | {n_pos} | {n_neg} |\n".format(
                name=m.name,
                pc=_pct(m.pos_class_at1),
                pcl=_pct(m.pos_class_ci[0]),
                pch=_pct(m.pos_class_ci[1]),
                pd=_pct(m.pos_drug_at1),
                pdl=_pct(m.pos_drug_ci[0]),
                pdh=_pct(m.pos_drug_ci[1]),
                nf=_pct(m.neg_parp_fp),
                nfl=_pct(m.neg_parp_ci[0]),
                nfh=_pct(m.neg_parp_ci[1]),
                n_pos=m.n_pos,
                n_neg=m.n_neg,
            )
        )

    out_path.write_text("".join(lines), encoding="utf-8")


def write_error_analysis(report: Dict[str, Any], out_md: Path, out_csv: Path, cases_path: Path) -> None:
    # load dataset for gene attribution
    cases = json.loads(Path(cases_path).read_text(encoding="utf-8"))
    by_id = {c.get("case_id"): c for c in cases}

    # Focus on Model SPE as primary method
    method = None
    for m in report.get("methods", []):
        if m.get("name") == "Model SPE":
            method = m
            break
    if method is None:
        out_md.write_text("No Model SPE method found in report.\n", encoding="utf-8")
        return

    rows = method.get("cases", [])

    failures = []
    for r in rows:
        ev = r.get("eval") or {}
        if ev.get("is_positive") and not ev.get("class_at1"):
            cid = r.get("case_id")
            c = by_id.get(cid) or {}
            gene = ((c.get("mutations") or [{}])[0].get("gene") or "").upper()
            failures.append(
                {
                    "case_id": cid,
                    "disease": r.get("disease"),
                    "gene": gene,
                    "pred_top_drug": (r.get("prediction") or {}).get("top_drug"),
                    "pred_top_class": (r.get("prediction") or {}).get("top_class"),
                    "gt_drugs": ";".join(ev.get("gt_drugs") or []),
                    "gt_classes": ";".join(ev.get("gt_classes") or []),
                }
            )

    # write csv
    out_csv.parent.mkdir(exist_ok=True)
    with out_csv.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "case_id",
                "disease",
                "gene",
                "pred_top_drug",
                "pred_top_class",
                "gt_drugs",
                "gt_classes",
            ],
        )
        w.writeheader()
        for row in failures:
            w.writerow(row)

    lines = []
    lines.append("## Error analysis (Model SPE)\n\n")
    lines.append(f"- **Total positive class failures**: {len(failures)}\n\n")
    lines.append(f"- CSV: `{out_csv}`\n\n")

    # quick breakdown
    from collections import Counter

    by_gene = Counter([f["gene"] for f in failures])
    by_pred = Counter([str(f["pred_top_drug"]).lower() for f in failures])

    lines.append("### Top failure genes\n\n")
    for g, n in by_gene.most_common(15):
        lines.append(f"- **{g}**: {n}\n")

    lines.append("\n### Top incorrect predictions\n\n")
    for d, n in by_pred.most_common(15):
        lines.append(f"- **{d}**: {n}\n")

    out_md.write_text("".join(lines), encoding="utf-8")


def write_bar_svg(methods: List[MethodSummary], out_svg: Path) -> None:
    # Simple, text-only SVG bar chart for Pos Drug@1
    # Scale width to 400px for 100%
    w = 700
    h = 40 + 30 * len(methods)
    x0 = 220
    bar_w = 420

    def bar_len(p: float) -> int:
        return int(bar_w * max(0.0, min(1.0, p)))

    y = 30
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}">']
    parts.append('<style>text{font-family: ui-sans-serif, system-ui, -apple-system; font-size: 12px;} .lab{font-weight:600}</style>')
    parts.append('<text x="10" y="18" class="lab">Pos Drug@1 (with 95% CI)</text>')

    for m in methods:
        y += 28
        parts.append(f'<text x="10" y="{y}" class="lab">{m.name}</text>')
        # bar
        bl = bar_len(m.pos_drug_at1)
        parts.append(f'<rect x="{x0}" y="{y-12}" width="{bar_w}" height="10" fill="#eee"/>')
        parts.append(f'<rect x="{x0}" y="{y-12}" width="{bl}" height="10" fill="#4f46e5"/>')
        # CI whisker
        ci_l = x0 + bar_len(m.pos_drug_ci[0])
        ci_h = x0 + bar_len(m.pos_drug_ci[1])
        parts.append(f'<line x1="{ci_l}" y1="{y-7}" x2="{ci_h}" y2="{y-7}" stroke="#111" stroke-width="2"/>')
        parts.append(f'<text x="{x0+bar_w+10}" y="{y}" fill="#111">{_pct(m.pos_drug_at1)}</text>')

    parts.append('</svg>')
    out_svg.write_text("\n".join(parts), encoding="utf-8")


def main() -> int:
    suite = Path("../results/publication_suite_20251230_131605.json").resolve()
    # Allow running from benchmark_sl dir
    if not suite.exists():
        # fallback: try relative
        suite = Path("results/publication_suite_20251230_131605.json")

    report = load_report(suite)
    methods = extract_method_summaries(report)

    out_dir = Path(__file__).parent
    out_results = out_dir / "results_pack.md"
    out_errors = out_dir / "error_analysis.md"
    out_csv = out_dir / "confusion_breakdown.csv"
    out_svg = out_dir / "figure_bar_chart.svg"

    # dataset path from report
    dataset_file = Path(report.get("dataset_file") or "test_cases_100.json")
    if not dataset_file.exists():
        dataset_file = Path(__file__).parent.parent / "test_cases_100.json"

    write_results_md(report, methods, out_results)
    write_error_analysis(report, out_errors, out_csv, dataset_file)
    write_bar_svg(methods, out_svg)

    print(f"✅ wrote {out_results}")
    print(f"✅ wrote {out_errors}")
    print(f"✅ wrote {out_csv}")
    print(f"✅ wrote {out_svg}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
