#!/usr/bin/env python3
"""Generate figures for publications/sporadic_cancer.

Path-robust: can be run from any working directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.patches as patches
import matplotlib.pyplot as plt
import seaborn as sns


def newest(base: Path, glob_pat: str) -> Path:
    paths = list((base / "data").glob(glob_pat))
    if not paths:
        raise FileNotFoundError(f"No files matched {(base / 'data' / glob_pat)}")
    return max(paths, key=lambda p: p.stat().st_mtime)


def main() -> int:
    sns.set(style="whitegrid")

    base = Path(__file__).resolve().parent
    figs = base / "figures"
    figs.mkdir(exist_ok=True)

    scenario_path = newest(base, "scenario_suite_25_*.json")
    j = json.loads(scenario_path.read_text(encoding="utf-8"))

    # Figure 1: architecture diagram
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.axis("off")

    def box(x: float, y: float, w: float, h: float, label: str) -> None:
        r = patches.FancyBboxPatch(
            (x, y),
            w,
            h,
            boxstyle="round,pad=0.02",
            linewidth=1.2,
            edgecolor="#444",
            facecolor="#f5f5f5",
        )
        ax.add_patch(r)
        ax.text(x + w / 2, y + h / 2, label, ha="center", va="center", fontsize=10)

    box(0.02, 0.62, 0.28, 0.28, "Inputs\n- Germline status\n- Tumor biomarkers (optional)\n- Disease/stage")
    box(0.36, 0.62, 0.28, 0.28, "TumorContext\n(TMB/MSI/HRD + completeness -> L0/L1/L2)")
    box(0.70, 0.62, 0.28, 0.28, "Efficacy Orchestrator\nBase ranking -> per-drug gates")

    box(0.02, 0.10, 0.28, 0.40, "Quick Intake\n(no NGS required)")
    box(0.36, 0.10, 0.28, 0.40, "Sporadic Gates\n- PARP penalty/rescue\n- IO boost\n- Confidence caps")
    box(0.70, 0.10, 0.28, 0.40, "Outputs\n- efficacy/confidence\n- sporadic_gates_provenance\n- receipts")

    ax.annotate("", xy=(0.36, 0.76), xytext=(0.30, 0.76), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.annotate("", xy=(0.70, 0.76), xytext=(0.64, 0.76), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.annotate("", xy=(0.36, 0.30), xytext=(0.30, 0.30), arrowprops=dict(arrowstyle="->", lw=1.5))
    ax.annotate("", xy=(0.70, 0.30), xytext=(0.64, 0.30), arrowprops=dict(arrowstyle="->", lw=1.5))

    plt.tight_layout()
    plt.savefig(figs / "figure_1_architecture.png", dpi=220)
    plt.close()

    # Figure 2: PARP gate effects
    parp = [c for c in j["cases"] if c["label"] == "PARP_gate"]
    groups: list[str] = []
    vals: list[float] = []

    for c in parp:
        ctx = c["input"].get("tumor_context") or {}
        hrd = ctx.get("hrd_score")
        germ = c["input"]["germline_status"]

        if germ == "negative" and (hrd is not None) and (hrd >= 42):
            grp = "HRD rescue (germline-, HRD>=42)"
        elif germ == "negative":
            grp = "Penalty (germline-, HRD<42 or unknown)"
        elif germ == "positive":
            grp = "Germline+ (no penalty)"
        else:
            grp = "Unknown germline (conservative)"

        groups.append(grp)
        vals.append(float(c["output"]["efficacy_score"]))

    plt.figure(figsize=(10, 5))
    sns.stripplot(x=groups, y=vals, jitter=0.15, size=7)
    sns.boxplot(x=groups, y=vals, whis=1.5, showcaps=True, boxprops={"alpha": 0.25})
    plt.xticks(rotation=20, ha="right")
    plt.ylim(0, 1.0)
    plt.ylabel("Adjusted efficacy score")
    plt.title("Figure 2. PARP gate effects")
    plt.tight_layout()
    plt.savefig(figs / "figure_2_parp_gates.png", dpi=220)
    plt.close()

    # Figure 3: Confidence caps by completeness
    conf_cases = [c for c in j["cases"] if c["label"] == "CONF_cap"]
    points: list[tuple[float, float, str]] = []

    for c in conf_cases:
        comp = float(c["input"]["tumor_context"]["completeness_score"])
        out_conf = float(c["output"]["confidence"])
        level = "L0" if comp < 0.3 else ("L1" if comp < 0.7 else "L2")
        points.append((comp, out_conf, level))

    plt.figure(figsize=(8, 5))
    for level, color in [("L0", "#d32f2f"), ("L1", "#f57c00"), ("L2", "#2e7d32")]:
        xs = [p[0] for p in points if p[2] == level]
        ys = [p[1] for p in points if p[2] == level]
        plt.scatter(xs, ys, label=f"{level} adjusted", s=70, color=color)

    plt.axhline(0.4, color="#d32f2f", linestyle="--", linewidth=1, label="L0 cap = 0.4")
    plt.axhline(0.6, color="#f57c00", linestyle="--", linewidth=1, label="L1 cap = 0.6")
    plt.axvline(0.3, color="gray", linestyle=":", linewidth=1)
    plt.axvline(0.7, color="gray", linestyle=":", linewidth=1)
    plt.ylim(0, 1.0)
    plt.xlim(0, 1.0)
    plt.xlabel("Completeness score")
    plt.ylabel("Adjusted confidence")
    plt.title("Figure 3. Confidence caps by completeness")
    plt.legend(loc="lower right", fontsize=8)
    plt.tight_layout()
    plt.savefig(figs / "figure_3_confidence_caps.png", dpi=220)
    plt.close()

    print(f"wrote: {figs / 'figure_1_architecture.png'}")
    print(f"wrote: {figs / 'figure_2_parp_gates.png'}")
    print(f"wrote: {figs / 'figure_3_confidence_caps.png'}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
