#!/usr/bin/env python3
"""Generate sporadic_cancer_manuscript.md from receipts.

Goal: keep the manuscript receipt-backed and portable (no absolute paths), while
presenting real behavioral results (scenario-suite effects + conformance), not
just unit-test status.
"""

from __future__ import annotations

import json
from pathlib import Path


def newest(base: Path, glob_pat: str) -> Path:
    paths = list((base / "data").glob(glob_pat))
    if not paths:
        raise FileNotFoundError(f"No files matched {(base / 'data' / glob_pat)}")
    return max(paths, key=lambda p: p.stat().st_mtime)


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def rel(base: Path, p: Path) -> str:
    """Return repo-portable relative path from the publication bundle root."""
    try:
        return p.resolve().relative_to(base.resolve()).as_posix()
    except Exception:
        # Fall back to just the name if relative conversion fails.
        return p.name


def main() -> int:
    base = Path(__file__).resolve().parent

    scenario_path = newest(base, "scenario_suite_25_*.json")
    bench_path = base / "receipts" / "benchmark_gate_effects.json"
    bench = load_json(bench_path)
    s = bench.get("stats", {})

    # Prefer stats from receipt, but fall back gracefully
    n_cases = int(s.get("n_cases") or 25)
    changed_eff = int(s.get("changed_eff_cases") or 0)
    changed_conf = int(s.get("changed_conf_cases") or 0)
    agree_eff = int(s.get("agreement_naive_vs_system_eff") or 0)
    agree_conf = int(s.get("agreement_naive_vs_system_conf") or 0)

    scenario_rel = rel(base, scenario_path)
    bench_rel = rel(base, bench_path)

    md: list[str] = []

    md.append(
        "# Conservative tumor-context gating for sporadic cancers: a provenance-first approach for precision oncology without tumor NGS"
    )
    md.append("")

    md.append("## Abstract")
    md.append("")

    md.append(
        "**Background:** Most oncology patients are germline-negative (sporadic) and frequently lack immediately available tumor NGS at the time therapy options are discussed. In this setting, decision support systems can silently extrapolate from incomplete inputs and emit overconfident recommendations."
    )
    md.append("")

    md.append(
        "**Methods:** We implemented a conservative, provenance-first tumor-context layer consisting of (i) a structured `TumorContext` schema with explicit biomarker fields (TMB, MSI status, HRD score) and a completeness score mapped to three intake levels (L0/L1/L2); (ii) a Quick Intake pathway that creates `TumorContext` under partial information; and (iii) deterministic sporadic gates applied per drug to adjust efficacy and/or confidence. Gates include a PARP inhibitor penalty for germline-negative, HRD-low contexts with rescue for HRD-high tumors; an immunotherapy (checkpoint inhibitor) boost for strong tumor biomarkers; and confidence caps based on `TumorContext` completeness. Each adjustment emits structured provenance (`sporadic_gates_provenance`)."
    )
    md.append("")

    md.append(
        "**Results (non-outcome validation):** We validate behavioral correctness and reproducibility, not clinical outcomes. "
        + f"A {n_cases}-case scenario suite exercising threshold boundaries (`{scenario_rel}`) shows sporadic gates modified efficacy in **{changed_eff}/{n_cases}** cases and confidence in **{changed_conf}/{n_cases}** cases, with conformance to a naive reference implementation in **{agree_eff}/{n_cases}** efficacy outcomes and **{agree_conf}/{n_cases}** confidence outcomes (receipt `receipts/benchmark_gate_effects.json`). "
        + "Quick Intake executed successfully for **15/15** cancer types (receipt `receipts/quick_intake_15cancers.json`). "
        + "An end-to-end smoke test (Quick Intake → efficacy prediction) produced provenance-bearing drug outputs (receipts `receipts/e2e_tumor_context.json`, `receipts/e2e_ficacy_response.json`, `receipts/e2e_sporadic_workflow.txt`)."
    )
    md.append("")

    md.append(
        "**Conclusions:** A conservative tumor-context gating layer provides transparent, reproducible adjustments that reduce overconfidence under incomplete intake and clearly communicate which biomarkers drove changes. This design supports safe iteration toward full tumor NGS integration while remaining operational for the sporadic majority."
    )

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 1. Scope and claims")
    md.append("")
    md.append("This manuscript is provenance-first and receipt-backed.")
    md.append("")

    md.append("**Validated here (non-outcome):**")
    md.append("- Deterministic gate behavior (penalty/boost/caps) under controlled inputs.")
    md.append("- Conformance to a reference implementation over a scenario suite.")
    md.append("- Reproducible execution producing stable receipts.")
    md.append("")

    md.append("**Explicitly not validated here:**")
    md.append("- Clinical outcomes, enrollment lift, or patient benefit.")
    md.append("- Comparative performance vs human trial navigators.")
    md.append("- Retrospective enrollment-ground-truth evaluation (not available in this bundle).")

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 2. Methods")
    md.append("")

    md.append("### 2.1 TumorContext schema and intake levels")
    md.append(
        "`TumorContext` captures tumor biomarkers as explicit fields (e.g., TMB, MSI status, HRD score) and computes a completeness score mapped to three intake levels:"
    )
    md.append("- **L0:** minimal / mostly priors")
    md.append("- **L1:** partial biomarker availability")
    md.append("- **L2:** near-complete tumor context")
    md.append("")
    md.append(
        "This allows the system to gate confidence based on what is actually known rather than implicitly assuming missing values."
    )
    md.append("")

    md.append("### 2.2 Deterministic sporadic gates")
    md.append("Sporadic gates deterministically adjust per-drug outputs based on germline status and tumor biomarkers:")
    md.append("- **PARP penalty + HRD rescue:** penalize PARP under germline-negative + HRD-low; rescue when HRD-high.")
    md.append("- **Checkpoint boost:** boost IO confidence/efficacy under strong IO biomarkers (TMB/MSI).")
    md.append("- **Confidence caps:** cap confidence under incomplete `TumorContext` (L0/L1).")
    md.append("")
    md.append(
        "Each application emits `sporadic_gates_provenance`, including inputs used, thresholds, and the applied adjustment."
    )
    md.append("")

    md.append("### 2.3 Scenario suite and reference implementation")
    md.append(
        "We evaluate a scenario suite designed to stress threshold boundaries (e.g., HRD near rescue threshold, TMB near IO threshold, and varying completeness levels). A naive reference implementation encodes the same policy rules; conformance testing ensures observed adjustments match expected rule application."
    )

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 3. Results (receipt-backed)")
    md.append("")

    md.append("### 3.1 Scenario-suite behavior and conformance")
    md.append(f"On the {n_cases}-case scenario suite:")
    md.append(f"- Gate-modified efficacy: **{changed_eff}/{n_cases}**")
    md.append(f"- Gate-modified confidence: **{changed_conf}/{n_cases}**")
    md.append("- Conformance vs naive reference:")
    md.append(f"  - **{agree_eff}/{n_cases}** efficacy outcomes")
    md.append(f"  - **{agree_conf}/{n_cases}** confidence outcomes")
    md.append("")
    md.append("**Receipts:**")
    md.append(f"- Scenario suite input: `{scenario_rel}`")
    md.append(f"- Benchmark receipt: `{bench_rel}`")
    md.append("")

    md.append("### 3.2 Quick Intake coverage")
    md.append("Quick Intake produced valid `TumorContext` objects for **15/15** cancer types tested.")
    md.append("")
    md.append("**Receipt:** `receipts/quick_intake_15cancers.json`")
    md.append("")

    md.append("### 3.3 End-to-end smoke test with provenance")
    md.append("A smoke test exercising Quick Intake → efficacy prediction produced:")
    md.append("- A populated `TumorContext` object")
    md.append("- An efficacy response whose drugs include explicit sporadic provenance fields")
    md.append("")
    md.append("**Receipts:**")
    md.append("- `receipts/e2e_tumor_context.json`")
    md.append("- `receipts/e2e_efficacy_response.json`")
    md.append("- `receipts/e2e_sporadic_workflow.txt`")

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 4. Figures")
    md.append("")
    md.append("- Figure 1: `figures/figure_1_architecture.png`")
    md.append("- Figure 2: `figures/figure_2_parp_gates.png`")
    md.append("- Figure 3: `figures/figure_3_confidence_caps.png`")

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 5. Reproducibility")
    md.append("")
    md.append("From the repo root:")
    md.append("")
    md.append("```bh")
    md.append("python3 publications/sporadic_cancer/make_figures.py")
    md.append("python3 publications/sporadic_cancer/make_manuscript.py")
    md.append("```")
    md.append("")
    md.append("Primary receipts referenced here:")
    md.append("- `receipts/pytest_sporadic_gates.txt`")
    md.append("- `receipts/validate_sporadic_gates.txt`")
    md.append("- `receipts/validate_sporadic_gates_report.json`")
    md.append("- `receipts/quick_intake_15cancers.json`")
    md.append("- `receipts/e2e_tumor_context.json`")
    md.append("- `receipts/e2e_efficacy_response.json`")
    md.append("- `receipts/e2e_sporadic_workflow.txt`")
    md.append("- `receipts/benchmark_gate_effects.json`")

    md.append("")
    md.append("---")
    md.append("")

    md.append("## 6. Limitations and next steps")
    md.append("")
    md.append("- No outcomes are evaluated in this bundle; future work requires prospective logging or retrospective enrollment mapping.")
    md.append("- Thresholds and caps are policy levers; the scenario suite should expand as policy evolves.")
    md.append("- Quick Intake is an operational bridge; full tumor NGS ingestion is required for robust L2 completeness in real workflows.")

    out = base / "sporadic_cancer_manuscript.md"
    out.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"wrote: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
