#!/usr/bin/env python3
"""Generate publication-ready comparison table.

Consumes doctrine-aligned benchmark reports.
"""

import json
from pathlib import Path
from typing import Any, Dict


def load_json(file_path: Path) -> Dict[str, Any]:
    if file_path.exists():
        with open(file_path, "r") as f:
            return json.load(f)
    return {}


def pct(x: float) -> str:
    return f"{100.0 * float(x):.1f}%"


def generate_comparison_table() -> str:
    print("=" * 60)
    print("Generating Comparison Table")
    print("=" * 60)

    baseline = load_json(Path("results/baseline_comparison_cached.json"))
    benchmark = load_json(Path("results/benchmark_100_cached.json"))

    rows = []

    if baseline:
        metrics = ((baseline.get("summary") or {}).get("metrics")) or {}

        rows.append("## Baseline Comparison (Positives + Negatives)\n")
        rows.append("| Method | Pos Class@1 | Pos Drug@1 | Neg PARP FP | Notes |")
        rows.append("|--------|------------:|----------:|------------:|-------|")

        def add_row(key: str, label: str, note: str = ""):
            m = metrics.get(key) or {}
            pos = (m.get("positive") or {})
            neg = (m.get("negative") or {})
            rows.append(
                f"| {label} | {pct(pos.get('class_at1', 0))} | {pct(pos.get('drug_at1', 0))} | {pct(neg.get('parp_fp_rate', 0))} | {note} |"
            )

        add_row("random", "Random", "Random drug selection")
        add_row("rule", "Rule", "IF DDR gene THEN PARP")

        spe_note_parts = []
        spe_pos = ((metrics.get("spe") or {}).get("positive") or {})
        if "cache_miss_rate" in spe_pos:
            spe_note_parts.append(f"cache_miss={pct(spe_pos.get('cache_miss_rate', 0))}")
        spe_note = ", ".join(spe_note_parts)
        add_row("spe", "S/P/E (cached)", spe_note)

        rows.append("")

    if benchmark:
        summary = benchmark.get("summary") or {}
        rows.append("## Full Benchmark (100 Cases)\n")
        rows.append("| Metric | Value |")
        rows.append("|--------|-------|")
        rows.append(f"| Total Cases | {summary.get('total_cases', 0)} |")
        rows.append(f"| Correct | {summary.get('correct', 0)} |")
        rows.append(f"| Accuracy | {pct(summary.get('accuracy', 0))} |")
        rows.append("")

    markdown = "\n".join(rows)

    out_path = Path("results/comparison_table.md")
    out_path.parent.mkdir(exist_ok=True)
    out_path.write_text(markdown)

    print("✅ Comparison table generated")
    print(f"   Saved to: {out_path}\n")
    print(markdown)

    return markdown


if __name__ == "__main__":
    generate_comparison_table()
