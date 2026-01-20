#!/usr/bin/env python3
"""GEO Cohort Hunter (Ovarian, Platinum)

Automates what we did manually for GSE63885:
- Pull GSM metadata (SOFT view) for a GSE
- Detect response-related sample characteristics fields
- Summarize value distributions so we can decide whether to download expression

This answers: "Is this cohort worth downloading next?"

Example:
python3 geo_cohort_hunter_ov_platinum.py --gse GSE63885 GSE63885 GSE30161 GSE32062
"""

from __future__ import annotations

import argparse
import re
import time
from collections import Counter, defaultdict
from typing import Dict, List

import httpx


GEO_ACC = "https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi"

KEYWORDS = [
    "platinum",
    "platinium",  # misspelling appears in GEO
    "chemoresponse",
    "chemo response",
    "clinical status post",
    "response",
    "sensitive",
    "resistant",
    "refractory",
    "progress",
    "relapse",
    "pfi",
    "dfs",
    "pfs",
]


def fetch_gsm_soft(gse: str) -> str:
    params = {"acc": gse, "targ": "gsm", "form": "text", "view": "full"}
    with httpx.Client(timeout=120) as c:
        r = c.get(GEO_ACC, params=params)
        r.raise_for_status()
        return r.text


def count_samples(text: str) -> int:
    return len(re.findall(r"^!Sample_geo_accession = GSM\d+", text, re.MULTILINE))


def parse_characteristics(text: str) -> Dict[str, List[str]]:
    out: Dict[str, List[str]] = defaultdict(list)
    for ln in text.split("\n"):
        if not ln.startswith("!Sample_characteristics_ch1"):
            continue
        m = re.search(r"=\s*(.*)$", ln)
        if not m:
            continue
        payload = m.group(1).strip().strip('"').replace("\r", "")
        if ":" in payload:
            k, v = payload.split(":", 1)
            out[k.strip().lower()].append(v.strip())
    return out


def is_response_field(k: str) -> bool:
    lk = k.lower()
    return any(kw in lk for kw in KEYWORDS)


def summarize(values: List[str], top: int = 12) -> Dict[str, int]:
    c = Counter([v.strip() for v in values if v is not None])
    return dict(c.most_common(top))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gse", nargs="+", required=True)
    ap.add_argument("--sleep", type=float, default=0.5)
    args = ap.parse_args()

    for gse in args.gse:
        try:
            txt = fetch_gsm_soft(gse)
        except Exception as e:
            print(f"{gse}: ERROR {e}")
            continue

        n = count_samples(txt)
        fields = parse_characteristics(txt)
        resp = {k: v for k, v in fields.items() if is_response_field(k)}

        print("=" * 80)
        print(f"{gse}: n_samples={n}")
        print(f"response-like fields: {len(resp)}")

        # print the most informative fields (value diversity)
        ranked = sorted(resp.items(), key=lambda kv: len(set(kv[1])), reverse=True)
        for k, vals in ranked[:10]:
            print(f"\n- {k} (unique={len(set(vals))}, n={len(vals)})")
            for vv, cc in summarize(vals).items():
                print(f"    {vv}: {cc}")

        time.sleep(args.sleep)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
