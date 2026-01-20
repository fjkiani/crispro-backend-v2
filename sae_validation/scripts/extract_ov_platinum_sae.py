#!/usr/bin/env python3
"""
Extract TRUE-SAE features for OV platinum cohort.

Usage:
  python3 scripts/validation/extract_ov_platinum_sae.py \
    --out_cohort oncology-coPilot/oncology-backend-minimal/data/validation/sae_cohort/checkpoints/OV_PLATINUM_TRUE_SAE_cohort.json \
    --out_dir oncology-coPilot/oncology-backend-minimal/scripts/validation/out/ov_platinum_sae_extract \
    --max_patients 166 --max_variants_per_patient 50 --concurrency 4 --checkpoint_every 10 --budget_seconds 3600
"""
import os
import sys
import json
import asyncio
import argparse
import time
import hashlib
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from api.services.sae_model_service import SAEModelService

INPUT_FILE = "oncology-coPilot/oncology-backend-minimal/data/validation/sae_cohort/checkpoints/OV_platinum_extractor_input.json"

def _now_iso():
    import datetime
    return datetime.datetime.utcnow().isoformat()

def _cache_key(chrom, pos, ref, alt, model_id, assembly, window):
    raw = f"{chrom}:{pos}:{ref}>{alt}|{model_id}|{assembly}|{window}".encode()
    return hashlib.sha256(raw).hexdigest()[:16]

def _atomic_write_json(path, obj):
    tmp = Path(str(path) + ".tmp")
    tmp.write_text(json.dumps(obj))
    tmp.rename(path)

def _validate_top_features(tf):
    if not isinstance(tf, list) or len(tf) == 0:
        return False
    for f in tf:
        if not isinstance(f, dict) or "index" not in f or "value" not in f:
            return False
    return True

async def main_async(args):
    svc = SAEModelService()
    
    # Load input
    inp = json.loads(Path(INPUT_FILE).read_text())
    patients = inp["patients"]
    if args.max_patients:
        patients = patients[:int(args.max_patients)]
    
    out_path = Path(args.out_cohort)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_dir = Path(args.out_dir or out_path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / "cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    
    # Resume
    cohort_data = {}
    if args.resume and out_path.exists():
        try:
            prev = json.loads(out_path.read_text())
            cohort_data = prev.get("data", {})
            print(f"Resuming: {len(cohort_data)} patients already done")
        except Exception:
            pass
    
    already = set(cohort_data.keys())
    
    sem = asyncio.Semaphore(int(args.concurrency))
    t_start = time.time()
    errors = 0
    processed = 0
    
    for i, p in enumerate(patients, start=1):
        pid = p["patient_id"]
        if pid in already:
            continue
        
        muts = p.get("mutations", [])[:int(args.max_variants_per_patient)]
        extracted = []
        
        for m in muts:
            chrom = str(m["chrom"])
            # Normalize chromosome
            if chrom == "23":
                chrom = "X"
            elif chrom == "24":
                chrom = "Y"
            
            key = _cache_key(chrom, m["pos"], m["ref"], m["alt"], args.model_id, args.assembly, args.window)
            cache_file = cache_dir / f"{key}.json"
            
            if cache_file.exists():
                try:
                    cached = json.loads(cache_file.read_text())
                    if _validate_top_features(cached.get("top_features")):
                        extracted.append({"top_features": cached["top_features"]})
                        continue
                except Exception:
                    pass
            
            # Call service
            async with sem:
                try:
                    resp = await svc.extract_features_from_variant(
                        chrom=chrom,
                        pos=m["pos"],
                        ref=m["ref"],
                        alt=m["alt"],
                        model_id=args.model_id,
                        assembly=args.assembly,
                        window=int(args.window)
                    )
                    if resp and _validate_top_features(resp.get("top_features")):
                        extracted.append({"top_features": resp["top_features"]})
                        cache_file.write_text(json.dumps(resp))
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1
        
        cohort_data[pid] = {
            "variants": extracted,
            "platinum_response": p.get("platinum_response")
        }
        processed += 1
        
        # Budget
        if args.budget_seconds and (time.time() - t_start) > float(args.budget_seconds):
            print(f"Budget exceeded. Stopping after {processed} patients.")
            break
        
        # Checkpoint
        if int(args.checkpoint_every) > 0 and processed % int(args.checkpoint_every) == 0:
            out = {
                "meta": {
                    "source": "extract_ov_platinum_sae",
                    "n_patients_written": len(cohort_data),
                    "assembly": args.assembly,
                    "time": _now_iso()
                },
                "data": cohort_data
            }
            _atomic_write_json(out_path, out)
            print(f"Checkpoint: {len(cohort_data)} patients")
    
    # Final write
    out = {
        "meta": {
            "source": "extract_ov_platinum_sae",
            "n_patients_written": len(cohort_data),
            "assembly": args.assembly,
            "time": _now_iso(),
            "errors": errors
        },
        "data": cohort_data
    }
    _atomic_write_json(out_path, out)
    print(f"Wrote cohort: {out_path} ({len(cohort_data)} patients, {errors} errors)")
    return 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out_cohort", required=True)
    ap.add_argument("--out_dir", default=None)
    ap.add_argument("--model_id", default="evo2_1b")
    ap.add_argument("--assembly", default="GRCh37")
    ap.add_argument("--window", default=8192, type=int)
    ap.add_argument("--max_patients", default=None)
    ap.add_argument("--max_variants_per_patient", default=50)
    ap.add_argument("--concurrency", default=4)
    ap.add_argument("--checkpoint_every", default=10, type=int)
    ap.add_argument("--budget_seconds", default=None)
    ap.add_argument("--resume", action="store_true", default=True)
    args = ap.parse_args()
    return asyncio.run(main_async(args))

if __name__ == "__main__":
    sys.exit(main())
