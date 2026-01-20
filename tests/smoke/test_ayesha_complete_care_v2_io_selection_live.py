"""Live smoke test (requires running backend server).

Why this exists:
- complete_care_v2 orchestrator makes HTTP calls to other endpoints.
- A pure TestClient unit test can't exercise that without heavy mocking.

Run:
  API_BASE=http://127.0.0.1:8003 PYTHONPATH=. python3 tests/smoke/test_ayesha_complete_care_v2_io_selection_live.py
"""

import os
import sys
import json
import requests


def main() -> None:
    api_base = os.environ.get("API_BASE", "http://127.0.0.1:8000").rstrip("/")

    payload = {
        "stage": "IVB",
        "treatment_line": "either",
        "germline_status": "positive",
        "patient_age": 40,
        "autoimmune_history": [],
        "tumor_context": {
            "pd_l1": {"status": "POSITIVE", "cps": 10},
            "pd_l1_cps": 10,
            "mmr_status": "PRESERVED",
            "msi_status": "MSS",
            "tmb": None,
            "somatic_mutations": [{"gene": "TP53"}],
            "completeness_score": 0.55,
        },
        "germline_variants": [
            {"gene": "MBD4", "variant": "c.1293delA", "classification": "pathogenic", "zygosity": "homozygous"},
            {"gene": "PDGFRA", "variant": "c.2263T>C", "classification": "VUS", "zygosity": "heterozygous"},
        ],
        "include_trials": True,
        "include_soc": True,
        "include_ca125": True,
        "include_wiwfm": True,
        "include_io_selection": True,
        "include_food": True,
        "include_resistance": True,
        "include_resistance_prediction": True,
        "max_trials": 5,
    }

    url = f"{api_base}/api/ayesha/complete_care_v2"
    r = requests.post(url, json=payload, timeout=120)
    if r.status_code >= 400:
        print(r.text)
        raise SystemExit(f"HTTP {r.status_code} calling {url}")

    data = r.json()

    assert "io_selection" in data, "io_selection missing from response"
    io_sel = data.get("io_selection") or {}

    assert io_sel.get("eligible") in (True, False)
    assert "eligibility_quality" in io_sel, "eligibility_quality missing"

    if io_sel.get("eligible"):
        ss = io_sel.get("selected_safest") or {}
        assert ss.get("selected"), "selected_safest.selected missing"

    print("✅ LIVE SMOKE OK: complete_care_v2 includes io_selection")
    print(json.dumps({"io_selection": io_sel}, indent=2)[:2000])


if __name__ == "__main__":
    main()
