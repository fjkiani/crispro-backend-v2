#!/usr/bin/env python3
"""Extract a Tier3-style TRUE-SAE cohort JSON from a cBioPortal-style study.

This is the A8 external replication enabler.

Goals (A–Z safety):
- Preflight the SAE Modal endpoint (health + one real variant call)
- Estimate runtime BEFORE making expensive calls
- Resume safely (skip already-extracted patients; cache each variant)
- Checkpoint progress (atomic writes) so failure is not costly
- Log every error to JSONL for postmortems

Produces Tier3-style cohort JSON:
  {
    "meta": {...},
    "data": {
      "PATIENT_ID": {
        "variants": [
          {"top_features": [{"index": int, "value": float}, ...]},
          ...
        ]
      }
    }
  }

Requires:
- SAE_SERVICE_URL env var pointing to Modal service

Example (safe dry run):
  export SAE_SERVICE_URL="https://...modal.run"
  python3 oncology-coPilot/oncology-backend-minimal/scripts/validation/extract_true_sae_cohort_from_cbioportal.py \
    --cbioportal_dataset data/benchmarks/cbioportal_trial_datasets_latest.json \
    --study_id ov_tcga \
    --out_cohort /tmp/OV_TRUE_SAE_smoke.json \
    --max_patients 1 --max_variants_per_patient 1 \
    --preflight_only

Then scale:
  --max_patients 200 --max_variants_per_patient 50 --concurrency 4 --checkpoint_every 10
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Allow importing oncology-backend-minimal modules
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.services.sae_model_service import SAEModelService  # noqa: E402


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _cache_key(chrom: str, pos: int, ref: str, alt: str, model_id: str, assembly: str, window: int) -> str:
    raw = f"{chrom}:{pos}:{ref}>{alt}|{model_id}|{assembly}|{window}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _normalize_chrom(chrom: str) -> str:
    """Normalize chromosome token for SAE service.

    Handles:
    - 'chr7' -> '7'
    - '23' -> 'X', '24' -> 'Y'
    - 'M'/'MT'/'25' -> 'MT'
    """
    c = str(chrom).strip()
    if c.lower().startswith("chr"):
        c = c[3:]

    # Normalize numeric sex chromosomes
    if c == "23":
        return "X"
    if c == "24":
        return "Y"

    # Mitochondrial
    if c.upper() in ("M", "MT") or c == "25":
        return "MT"

    return c


def _safe_int(x) -> Optional[int]:
    try:
        return int(x)
    except Exception:
        return None


def _atomic_write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.replace(path)


def _append_jsonl(path: Path, rec: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")


def _validate_top_features(top_features: Any) -> bool:
    if not isinstance(top_features, list) or len(top_features) == 0:
        return False
    for tf in top_features:
        if not isinstance(tf, dict):
            return False
        if "index" not in tf or "value" not in tf:
            return False
    return True


def _iter_valid_mutations(study: Dict[str, Any], limit: int = 50):
    """Yield up to `limit` mutations with chrom/pos/ref/alt."""
    seen = 0
    for p in (study.get("patients") or []):
        for m in (p.get("mutations") or []):
            if seen >= limit:
                return
            if not isinstance(m, dict):
                continue
            chrom = _normalize_chrom(m.get("chromosome"))
            pos = _safe_int(m.get("position"))
            ref = m.get("ref")
            alt = m.get("alt")
            if chrom and pos is not None and ref and alt:
                seen += 1
                yield {"patient_id": p.get("patient_id"), **m}


async def _try_variant_call(
    svc: SAEModelService,
    m: Dict[str, Any],
    model_id: str,
    assembly: str,
    window: int,
) -> Tuple[bool, float, Optional[Dict[str, Any]], Optional[str]]:
    """Attempt one variant call; return (ok, seconds, response, error_str)."""
    chrom = _normalize_chrom(m.get("chromosome"))
    pos = _safe_int(m.get("position"))
    ref = m.get("ref")
    alt = m.get("alt")
    t0 = time.time()
    try:
        resp = await svc.extract_features_from_variant(
            chrom=chrom,
            pos=int(pos),
            ref=str(ref),
            alt=str(alt),
            model_id=model_id,
            assembly=assembly,
            window=window,
        )
        dt = time.time() - t0
        top = resp.get("top_features") if isinstance(resp, dict) else None
        if not _validate_top_features(top):
            return False, dt, resp, "invalid_top_features"
        return True, dt, resp, None
    except Exception as e:
        dt = time.time() - t0
        return False, dt, None, str(e)


async def _preflight(
    svc: SAEModelService,
    study: Dict[str, Any],
    model_id: str,
    assembly: str,
    window: int,
    out_dir: Path,
    auto_assembly: bool,
    preflight_max_tries: int,
) -> str:
    """Preflight the service cheaply.

    We try:
    1) GET /health (nice-to-have; some Modal deployments may not expose it)
    2) One real variant POST /extract_features (must pass)

    If we see "Reference allele mismatch" repeatedly, we auto-try the alternate
    assembly once (GRCh37 <-> GRCh38) when `auto_assembly` is enabled.

    Returns the resolved assembly to use for the run.
    """
    log_path = out_dir / "extract_preflight.json"

    # 1) Health check (optional)
    hc = await svc.health_check()
    health_supported = True
    if hc.get("status") != "healthy":
        resp = hc.get("response")
        if isinstance(resp, str) and "Not Found" in resp:
            health_supported = False
        else:
            health_supported = False

    pre = {"time": _now_iso(), "health": hc, "health_supported": health_supported}
    _atomic_write_json(log_path, pre)

    # 2) Variant call (required) — try multiple mutations
    tries = 0
    mismatch = 0
    last_err = None

    candidates = list(_iter_valid_mutations(study, limit=max(50, preflight_max_tries)))
    if not candidates:
        raise RuntimeError("No valid mutation with chrom/pos/ref/alt found for preflight")

    def _alt(asm: str) -> str:
        return "GRCh37" if asm.upper() == "GRCH38" else "GRCh38"

    current_asm = assembly

    for m in candidates:
        if tries >= preflight_max_tries:
            break
        tries += 1

        ok, dt, resp, err = await _try_variant_call(svc, m, model_id=model_id, assembly=current_asm, window=window)
        if ok:
            top = resp.get("top_features")
            _atomic_write_json(
                log_path,
                {
                    **pre,
                    "resolved_assembly": current_asm,
                    "sample_mutation": {
                        "patient_id": m.get("patient_id"),
                        "gene": m.get("gene"),
                        "chromosome": _normalize_chrom(m.get("chromosome")),
                        "position": int(_safe_int(m.get("position"))),
                        "ref": m.get("ref"),
                        "alt": m.get("alt"),
                    },
                    "sample_call_seconds": dt,
                    "sample_top_features_len": len(top) if isinstance(top, list) else None,
                    "sample_response_keys": sorted(list(resp.keys())) if isinstance(resp, dict) else None,
                    "top_features_valid": True,
                },
            )
            return current_asm

        last_err = err
        if err and "Reference allele mismatch" in err:
            mismatch += 1

        # If mismatch-heavy and auto_assembly enabled: try alternate assembly on THIS SAME mutation once.
        if auto_assembly and err and "Reference allele mismatch" in err:
            alt_asm = _alt(current_asm)
            ok2, dt2, resp2, err2 = await _try_variant_call(svc, m, model_id=model_id, assembly=alt_asm, window=window)
            if ok2:
                top2 = resp2.get("top_features")
                _atomic_write_json(
                    log_path,
                    {
                        **pre,
                        "resolved_assembly": alt_asm,
                        "sample_mutation": {
                            "patient_id": m.get("patient_id"),
                            "gene": m.get("gene"),
                            "chromosome": _normalize_chrom(m.get("chromosome")),
                            "position": int(_safe_int(m.get("position"))),
                            "ref": m.get("ref"),
                            "alt": m.get("alt"),
                        },
                        "sample_call_seconds": dt2,
                        "sample_top_features_len": len(top2) if isinstance(top2, list) else None,
                        "sample_response_keys": sorted(list(resp2.keys())) if isinstance(resp2, dict) else None,
                        "top_features_valid": True,
                        "note": "Auto-switched assembly due to reference mismatch",
                    },
                )
                return alt_asm

    # Failure summary
    _atomic_write_json(
        log_path,
        {
            **pre,
            "resolved_assembly": None,
            "tries": tries,
            "reference_mismatch_count": mismatch,
            "last_error": last_err,
            "top_features_valid": False,
            "note": "Preflight failed; check if assembly is correct or if cbioPortal variant coordinates match reference genome.",
        },
    )

    raise RuntimeError(f"Preflight failed after {tries} tries. Last error: {last_err}")


async def _extract_one(
    svc: SAEModelService,
    mut: Dict[str, Any],
    model_id: str,
    assembly: str,
    window: int,
    cache_dir: Path,
    sem: asyncio.Semaphore,
    retries: int,
    error_log: Path,
) -> Optional[Dict[str, Any]]:
    chrom = _normalize_chrom(mut.get("chromosome"))
    pos = _safe_int(mut.get("position"))
    ref = mut.get("ref")
    alt = mut.get("alt")

    if not chrom or pos is None or not ref or not alt:
        return None

    key = _cache_key(chrom, pos, ref, alt, model_id, assembly, window)
    cache_path = cache_dir / f"{key}.json"

    if cache_path.exists():
        try:
            cached = json.loads(cache_path.read_text())
            if _validate_top_features(cached.get("top_features")):
                return cached
        except Exception:
            pass

    last_err = None
    for attempt in range(retries + 1):
        try:
            async with sem:
                resp = await svc.extract_features_from_variant(
                    chrom=chrom,
                    pos=int(pos),
                    ref=str(ref),
                    alt=str(alt),
                    model_id=model_id,
                    assembly=assembly,
                    window=window,
                )

            top = resp.get("top_features")
            if not _validate_top_features(top):
                raise RuntimeError("invalid_top_features")

            out = {
                "gene": mut.get("gene"),
                "chromosome": chrom,
                "position": int(pos),
                "ref": ref,
                "alt": alt,
                "protein_change": mut.get("protein_change"),
                "mutation_type": mut.get("mutation_type"),
                "variant_type": mut.get("variant_type"),
                "top_features": top,
                "sae_provenance": (resp.get("provenance") or {}),
            }
            cache_path.write_text(json.dumps(out))
            return out
        except Exception as e:
            last_err = str(e)
            _append_jsonl(
                error_log,
                {
                    "time": _now_iso(),
                    "attempt": attempt,
                    "error": last_err,
                    "mutation": {
                        "gene": mut.get("gene"),
                        "chromosome": chrom,
                        "position": pos,
                        "ref": ref,
                        "alt": alt,
                    },
                },
            )
            await asyncio.sleep(0.5 * (attempt + 1))

    return None


def _estimate_remaining_requests(
    patients: List[Dict[str, Any]],
    max_variants_per_patient: int,
    cache_dir: Path,
    model_id: str,
    assembly: str,
    window: int,
) -> Tuple[int, int]:
    """Return (total_planned_requests, not_cached_requests)."""
    total = 0
    not_cached = 0

    for p in patients:
        muts = (p.get("mutations") or [])
        muts = [m for m in muts if isinstance(m, dict)]
        muts = muts[:max_variants_per_patient]

        for m in muts:
            chrom = _normalize_chrom(m.get("chromosome"))
            pos = _safe_int(m.get("position"))
            ref = m.get("ref")
            alt = m.get("alt")
            if not chrom or pos is None or not ref or not alt:
                continue
            total += 1
            key = _cache_key(chrom, pos, ref, alt, model_id, assembly, window)
            if not (cache_dir / f"{key}.json").exists():
                not_cached += 1

    return total, not_cached


async def main_async(args) -> int:
    if not os.getenv("SAE_SERVICE_URL"):
        raise RuntimeError("SAE_SERVICE_URL not set. Set SAE_SERVICE_URL to the Modal SAE service URL.")

    cb_path = Path(args.cbioportal_dataset)
    out_path = Path(args.out_cohort)

    out_dir = Path(args.out_dir) if args.out_dir else out_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)

    cache_dir = Path(args.cache_dir) if args.cache_dir else (out_dir / (out_path.stem + ".cache"))
    cache_dir.mkdir(parents=True, exist_ok=True)

    error_log = out_dir / "extract_errors.jsonl"

    studies = json.loads(cb_path.read_text())
    study = next((s for s in studies if s.get("study_id") == args.study_id), None)
    if not study:
        raise ValueError(f"study_id={args.study_id} not found in {cb_path}")

    patients = [p for p in (study.get("patients") or []) if p.get("patient_id")]
    if args.max_patients is not None:
        patients = patients[: int(args.max_patients)]

    svc = SAEModelService(service_url=os.getenv("SAE_SERVICE_URL"))

    # Preflight (safe): resolve correct assembly + validate service with a real variant
    run_assembly = args.assembly
    if not args.skip_preflight:
        run_assembly = await _preflight(
            svc,
            study,
            model_id=args.model_id,
            assembly=run_assembly,
            window=int(args.window),
            out_dir=out_dir,
            auto_assembly=bool(args.auto_assembly),
            preflight_max_tries=int(args.preflight_max_tries),
        )

    if args.preflight_only:
        print(f"Preflight OK. Wrote: {out_dir / 'extract_preflight.json'}")
        return 0

    # Resume from existing cohort if present
    cohort_data: Dict[str, Any] = {}
    if args.resume and out_path.exists():
        try:
            existing = json.loads(out_path.read_text())
            cohort_data = existing.get("data", {}) if isinstance(existing, dict) else {}
        except Exception:
            cohort_data = {}

    already = set(cohort_data.keys())

    # Estimate
    total_planned, not_cached = _estimate_remaining_requests(
        patients,
        max_variants_per_patient=int(args.max_variants_per_patient),
        cache_dir=cache_dir,
        model_id=args.model_id,
        assembly=run_assembly,
        window=int(args.window),
    )

    estimate = {
        "time": _now_iso(),
        "study_id": args.study_id,
        "patients_planned": len(patients),
        "patients_already_done": len(already),
        "max_variants_per_patient": int(args.max_variants_per_patient),
        "total_variant_requests_planned": total_planned,
        "variant_requests_not_cached": not_cached,
        "concurrency": int(args.concurrency),
        "note": "Multiply not_cached by your observed seconds/variant from preflight to estimate runtime.",
    }
    _atomic_write_json(out_dir / "extract_estimate.json", estimate)

    print(json.dumps(estimate, indent=2))

    if args.estimate_only:
        return 0

    sem = asyncio.Semaphore(int(args.concurrency))

    t_start = time.time()
    errors = 0

    processed = 0
    for i, p in enumerate(patients, start=1):
        pid = p["patient_id"]
        if pid in already:
            continue

        muts = [m for m in (p.get("mutations") or []) if isinstance(m, dict)]
        muts = muts[: int(args.max_variants_per_patient)]

        tasks = [
            _extract_one(
                svc,
                mut,
                model_id=args.model_id,
                assembly=run_assembly,
                window=int(args.window),
                cache_dir=cache_dir,
                sem=sem,
                retries=int(args.retries),
                error_log=error_log,
            )
            for mut in muts
        ]

        extracted = []
        if tasks:
            res = await asyncio.gather(*tasks)
            for r in res:
                if r and _validate_top_features(r.get("top_features")):
                    extracted.append({"top_features": r["top_features"]})
                else:
                    errors += 1

        cohort_data[pid] = {"variants": extracted}
        processed += 1

        # Budget guard
        if args.budget_seconds is not None and (time.time() - t_start) > float(args.budget_seconds):
            print(f"Budget exceeded ({args.budget_seconds}s). Stopping after {processed} new patients.")
            break

        if args.max_errors is not None and errors > int(args.max_errors):
            raise RuntimeError(f"Error budget exceeded: errors={errors} > max_errors={args.max_errors}")

        # checkpoint
        if int(args.checkpoint_every) > 0 and (processed % int(args.checkpoint_every) == 0):
            out = {
                "meta": {
                    "source": "extract_true_sae_cohort_from_cbioportal",
                    "study_id": args.study_id,
                    "n_patients_planned": len(patients),
                    "n_patients_written": len(cohort_data),
                    "model_id": args.model_id,
                    "assembly": run_assembly,
                    "window": int(args.window),
                    "service_url": os.getenv("SAE_SERVICE_URL"),
                    "resume": bool(args.resume),
                    "checkpoint_every": int(args.checkpoint_every),
                    "time": _now_iso(),
                },
                "data": cohort_data,
            }
            _atomic_write_json(out_path, out)
            print(f"Checkpoint: wrote {out_path} (patients={len(cohort_data)})")

    # final write
    out = {
        "meta": {
            "source": "extract_true_sae_cohort_from_cbioportal",
            "study_id": args.study_id,
            "n_patients_planned": len(patients),
            "n_patients_written": len(cohort_data),
            "model_id": args.model_id,
            "assembly": run_assembly,
            "window": int(args.window),
            "service_url": os.getenv("SAE_SERVICE_URL"),
            "resume": bool(args.resume),
            "checkpoint_every": int(args.checkpoint_every),
            "time": _now_iso(),
            "errors_observed": int(errors),
        },
        "data": cohort_data,
    }
    _atomic_write_json(out_path, out)

    print(f"Wrote cohort: {out_path}")
    print(f"Out dir: {out_dir}")
    print(f"Cache dir: {cache_dir}")
    print(f"Errors observed (incl. missing/invalid top_features): {errors}")

    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cbioportal_dataset", required=True)
    ap.add_argument("--study_id", required=True)
    ap.add_argument("--out_cohort", required=True)

    ap.add_argument("--out_dir", default=None, help="Directory for logs/estimates (defaults to out_cohort parent)")

    ap.add_argument("--model_id", default="evo2_1b")
    ap.add_argument("--assembly", default="GRCh38")
    ap.add_argument("--window", default=8192, type=int)

    ap.add_argument("--max_patients", default=None)
    ap.add_argument("--max_variants_per_patient", default=50)

    ap.add_argument("--concurrency", default=4)
    ap.add_argument("--retries", default=2)

    ap.add_argument("--cache_dir", default=None)

    ap.add_argument("--resume", action="store_true", default=True)

    ap.add_argument("--checkpoint_every", type=int, default=10)

    ap.add_argument("--skip_preflight", action="store_true", default=False)
    ap.add_argument("--preflight_max_tries", type=int, default=10, help="Try up to N variants during preflight")
    ap.add_argument("--auto_assembly", dest="auto_assembly", action="store_true", default=True, help="Auto-switch GRCh37/GRCh38 on reference mismatches during preflight")
    ap.add_argument("--no_auto_assembly", dest="auto_assembly", action="store_false")
    ap.add_argument("--preflight_only", action="store_true", default=False)
    ap.add_argument("--estimate_only", action="store_true", default=False)

    ap.add_argument("--budget_seconds", default=None, help="Hard stop after N seconds (writes checkpoint)")
    ap.add_argument("--max_errors", default=500, help="Abort if invalid/missing features exceed this")

    args = ap.parse_args()
    return asyncio.run(main_async(args))


if __name__ == "__main__":
    raise SystemExit(main())
