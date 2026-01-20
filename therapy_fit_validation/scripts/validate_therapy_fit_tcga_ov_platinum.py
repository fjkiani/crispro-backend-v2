#!/usr/bin/env python3
"""
Therapy Fit (WIWFM) — TCGA-OV Platinum Outcome Validation (Real Cohort)
======================================================================

Goal
----
Run *real* TCGA-OV platinum response cohort patients through the existing
`/api/efficacy/predict` endpoint and produce a machine-readable receipt.

This explicitly replaces any "expected confidence ranges" style validation.
We validate *outcome-linked separation* (e.g., MAPK vs WT, PI3K vs WT) using:
- cohort labels: platinum_response ∈ {sensitive,resistant,refractory}
- genomics: per-patient mutations (gene-level)

Notes
-----
- Requires the API server running at API_BASE_URL.
- Research Use Only (RUO).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx


API_BASE_URL_DEFAULT = os.environ.get("API_BASE_URL", "http://127.0.0.1:8000")
TIMEOUT_SECONDS = float(os.environ.get("THERAPY_FIT_TIMEOUT", "120"))

# Cohort expected contract:
# [
#   {"patient_id": "...", "platinum_response": "sensitive|resistant|refractory", "mutations": [{"gene": "...", ...}, ...]},
#   ...
# ]
DEFAULT_COHORT_PATHS = [
    Path("tools/benchmarks/tcga_ov_platinum_response_with_genomics.json"),
    Path("data/validation/tcga_ov_platinum_response_with_genomics.json"),
]

# Pathway gene sets aligned with existing validation scripts.
MAPK_GENES = {"KRAS", "NRAS", "BRAF", "NF1", "MAP2K1", "MAP2K2"}
PI3K_GENES = {"PIK3CA", "PIK3CB", "PIK3R1", "AKT1", "AKT2", "PTEN"}


def _now() -> str:
    return datetime.utcnow().isoformat() + "Z"


def load_cohort(path: Path) -> List[Dict[str, Any]]:
    with path.open() as f:
        data = json.load(f)

    # Support common cohort container formats
    # - list[patient]
    # - {"patients": list[patient], ...}
    # - {"cohort": {"patients": list[patient], ...}, ...}
    if isinstance(data, list):
        return data
    if isinstance(data, dict):
        if isinstance(data.get("patients"), list):
            return data["patients"]
        cohort = data.get("cohort")
        if isinstance(cohort, dict) and isinstance(cohort.get("patients"), list):
            return cohort["patients"]

    raise ValueError(f"Unexpected cohort format (expected list or dict-with-patients): {path}")


def find_cohort_path(explicit: Optional[str]) -> Path:
    if explicit:
        p = Path(explicit)
        if p.exists():
            return p
        raise FileNotFoundError(f"--cohort not found: {p}")

    for p in DEFAULT_COHORT_PATHS:
        if p.exists():
            return p
    raise FileNotFoundError(
        "Could not find TCGA-OV cohort file. Checked: "
        + ", ".join(str(p) for p in DEFAULT_COHORT_PATHS)
    )


def normalize_gene(g: Any) -> str:
    return str(g or "").strip().upper()


def patient_gene_set(patient: Dict[str, Any]) -> set[str]:
    muts = patient.get("mutations") or []
    genes = set()
    for m in muts:
        if isinstance(m, dict):
            genes.add(normalize_gene(m.get("gene")))
    genes.discard("")
    return genes


def is_resistant_label(platinum_response: str) -> Optional[bool]:
    v = (platinum_response or "").strip().lower()
    if v in {"resistant", "refractory"}:
        return True
    if v in {"sensitive"}:
        return False
    return None


@dataclass
class Contingency:
    a_exposed_event: int
    b_exposed_no_event: int
    c_unexp_event: int
    d_unexp_no_event: int

    def as_dict(self) -> Dict[str, int]:
        return {
            "a_exposed_event": self.a_exposed_event,
            "b_exposed_no_event": self.b_exposed_no_event,
            "c_unexposed_event": self.c_unexp_event,
            "d_unexposed_no_event": self.d_unexp_no_event,
        }


def contingency_for_gene_set(cohort: List[Dict[str, Any]], geneset: set[str]) -> Tuple[Contingency, Dict[str, Any]]:
    a = b = c = d = 0
    n_skipped = 0
    found_genes: set[str] = set()

    for p in cohort:
        label = is_resistant_label(p.get("platinum_response", ""))
        if label is None:
            n_skipped += 1
            continue
        gset = patient_gene_set(p)
        exposed = bool(gset & geneset)
        if exposed:
            found_genes |= (gset & geneset)
        if exposed and label:
            a += 1
        elif exposed and (not label):
            b += 1
        elif (not exposed) and label:
            c += 1
        else:
            d += 1

    meta = {
        "n_total": len(cohort),
        "n_used": len(cohort) - n_skipped,
        "n_skipped_missing_label": n_skipped,
        "genes_found": sorted(found_genes),
    }
    return Contingency(a, b, c, d), meta


def _ln(x: float) -> float:
    return math.log(x)


def compute_rr_and_ci(ct: Contingency) -> Dict[str, Any]:
    a, b, c, d = ct.a_exposed_event, ct.b_exposed_no_event, ct.c_unexp_event, ct.d_unexp_no_event
    n_exp = a + b
    n_unexp = c + d
    if n_exp == 0 or n_unexp == 0:
        return {"error": "empty_group", "action": "CANNOT_VALIDATE"}

    risk_exp = a / n_exp if n_exp else 0.0
    risk_unexp = c / n_unexp if n_unexp else 0.0
    if risk_unexp == 0:
        return {
            "error": "zero_unexposed_risk",
            "risk_exposed": risk_exp,
            "risk_unexposed": risk_unexp,
            "action": "CANNOT_VALIDATE",
        }

    rr = risk_exp / risk_unexp

    # 95% CI (log method), require a>0 and c>0 to avoid infinite SE
    ci_lo = None
    ci_hi = None
    if a > 0 and c > 0:
        se_log_rr = math.sqrt((1 / a - 1 / n_exp) + (1 / c - 1 / n_unexp))
        log_rr = _ln(rr)
        ci_lo = math.exp(log_rr - 1.96 * se_log_rr)
        ci_hi = math.exp(log_rr + 1.96 * se_log_rr)

    return {
        "relative_risk": round(rr, 4),
        "ci_lower": round(ci_lo, 4) if ci_lo is not None else None,
        "ci_upper": round(ci_hi, 4) if ci_hi is not None else None,
        "risk_exposed": round(risk_exp, 4),
        "risk_unexposed": round(risk_unexp, 4),
        "n_exposed": n_exp,
        "n_unexposed": n_unexp,
    }


async def call_wiwfm(
    client: httpx.AsyncClient,
    mutations: List[Dict[str, Any]],
    *,
    disease: str = "ovarian_cancer",
    api_base: str = API_BASE_URL_DEFAULT,
    limit_panel: int = 0,
    fast: bool = True,
) -> Dict[str, Any]:
    url = f"{api_base}/api/efficacy/predict"
    options: Dict[str, Any] = {"adaptive": True, "ensemble": False}
    if limit_panel and limit_panel > 0:
        options["limit_panel"] = int(limit_panel)
    if fast:
        options["fast"] = True
        # keep SPE default behavior but avoid slow evidence/insights fetch
        options["ablation_mode"] = "SP"
    payload = {
        "model_id": "evo2_1b",
        "mutations": mutations,
        "disease": disease,
        # ensure sporadic gates are eligible to run when relevant
        "germline_status": "unknown",
        "tumor_context": {"somatic_mutations": mutations},
        "options": options,
    }
    r = await client.post(url, json=payload, timeout=TIMEOUT_SECONDS)
    r.raise_for_status()
    return r.json()


def receipt_paths() -> Tuple[Path, Path]:
    base = Path(__file__).resolve().parent.parent  # therapy_fit_validation/
    receipts_dir = base / "receipts" / "latest"
    receipts_dir.mkdir(parents=True, exist_ok=True)
    per_patient_path = receipts_dir / "tcga_ov_platinum_wiwfm_per_patient.jsonl"
    summary_path = receipts_dir / "tcga_ov_platinum_wiwfm_summary.json"
    return per_patient_path, summary_path


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cohort", default=None, help="Path to TCGA-OV cohort json")
    ap.add_argument("--api-base", default=API_BASE_URL_DEFAULT, help="API base URL")
    ap.add_argument("--max-patients", type=int, default=200, help="Cap for runtime (debug)")
    ap.add_argument("--limit-panel", type=int, default=0, help="Limit drug panel size (debug)")
    ap.add_argument("--fast", action="store_true", help="Use fast mode (skip evidence/insights)")
    args = ap.parse_args()

    cohort_path = find_cohort_path(args.cohort)
    cohort = load_cohort(cohort_path)

    # Compute cohort-level outcome linkage (no WIWFM needed)
    mapk_ct, mapk_meta = contingency_for_gene_set(cohort, MAPK_GENES)
    pi3k_ct, pi3k_meta = contingency_for_gene_set(cohort, PI3K_GENES)

    mapk_rr = compute_rr_and_ci(mapk_ct)
    pi3k_rr = compute_rr_and_ci(pi3k_ct)

    per_patient_path, summary_path = receipt_paths()

    # Run WIWFM for a capped subset (to keep this runnable on laptops)
    # We still emit per-patient receipts for reproducibility.
    n_target = min(len(cohort), max(0, int(args.max_patients)))
    processed = 0
    errors = 0

    async with httpx.AsyncClient() as client:
        with per_patient_path.open("w") as out:
            for patient in cohort[:n_target]:
                pid = patient.get("patient_id") or patient.get("case_id") or "unknown"
                muts = patient.get("mutations") or []
                label = patient.get("platinum_response")
                try:
                    wi = await call_wiwfm(
                        client,
                        muts,
                        disease="ovarian_cancer",
                        api_base=args.api_base,
                        limit_panel=int(args.limit_panel or 0),
                        fast=bool(args.fast),
                    )
                    top = (wi.get("drugs") or [{}])[0] if isinstance(wi.get("drugs"), list) else {}
                    record = {
                        "patient_id": pid,
                        "platinum_response": label,
                        "n_mutations": len(muts),
                        "genes": sorted({normalize_gene(m.get("gene")) for m in muts if isinstance(m, dict)}),
                        "wiwfm": {
                            "top_drug": top.get("name"),
                            "top_confidence": top.get("confidence"),
                            "top_efficacy_score": top.get("efficacy_score"),
                            "top_evidence_tier": top.get("evidence_tier"),
                        },
                        "provenance": {
                            "api_base": args.api_base,
                            "timestamp": _now(),
                            "fast_mode": bool(args.fast),
                            "limit_panel": int(args.limit_panel or 0),
                        },
                    }
                    out.write(json.dumps(record) + "\n")
                    processed += 1
                except Exception as e:
                    errors += 1
                    out.write(
                        json.dumps(
                            {
                                "patient_id": pid,
                                "platinum_response": label,
                                "error": str(e),
                                "provenance": {"timestamp": _now()},
                            }
                        )
                        + "\n"
                    )

    summary = {
        "run": {
            "generated_at": _now(),
            "cohort_path": str(cohort_path),
            "api_base": args.api_base,
            "n_cohort": len(cohort),
            "n_processed": processed,
            "n_errors": errors,
            "settings": {"max_patients": n_target, "fast": bool(args.fast), "limit_panel": int(args.limit_panel or 0)},
        },
        "outcome_linkage": {
            "mapk": {"geneset": sorted(MAPK_GENES), "meta": mapk_meta, "contingency": mapk_ct.as_dict(), "rr": mapk_rr},
            "pi3k": {"geneset": sorted(PI3K_GENES), "meta": pi3k_meta, "contingency": pi3k_ct.as_dict(), "rr": pi3k_rr},
        },
        "artifacts": {"per_patient_jsonl": str(per_patient_path)},
        "notes": [
            "This receipt validates outcome-linked separation using TCGA-OV platinum response labels.",
            "Per-patient WIWFM calls are capped by --max-patients for practical runtime.",
        ],
    }

    summary_path.write_text(json.dumps(summary, indent=2))
    print(f"✅ Wrote per-patient receipt: {per_patient_path}")
    print(f"✅ Wrote summary receipt: {summary_path}")


if __name__ == "__main__":
    asyncio.run(main())

