#!/usr/bin/env python3
import json
import os
import sys
import urllib.request
import urllib.error

def post_json(url: str, payload: dict, timeout: int = 600) -> dict:
    data = json.dumps(payload).encode('utf-8')
    req = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode('utf-8')
        return json.loads(body)

def main():
    base = os.environ.get(
        'VERCEL_BASE',
        'https://crispro-oncology-backend-minimal-1c5441zho-fjkianis-projects.vercel.app',
    )
    url = f"{base.rstrip('/')}/api/predict/myeloma_drug_response"

    print(f"Testing live endpoint: {url}")
    payload = {
        "gene": "KRAS",
        "hgvs_p": "p.Gly12Asp",
        "variant_info": "chr12:25245350 C>T",
        "build": "hg38",
    }

    try:
        result = post_json(url, payload)
    except urllib.error.HTTPError as e:
        print("HTTPError:", e.code, e.reason)
        print("Body:", e.read().decode('utf-8'))
        sys.exit(1)
    except Exception as e:
        print("Request failed:", e)
        sys.exit(1)

    # Basic validations
    assert isinstance(result, dict), "Response is not a JSON object"
    assert result.get('mode') == 'live', f"Expected mode=live, got {result.get('mode')}"
    da = result.get('detailed_analysis') or []
    assert len(da) >= 1, "No detailed_analysis entries"
    evo = da[0].get('evo2_result') or {}
    assert 'zeta_score' in evo, "Missing zeta_score in evo2_result"
    assert isinstance(evo['zeta_score'], (int, float)), "zeta_score is not numeric"

    print("OK. mode=live, zeta_score=", evo['zeta_score'])

if __name__ == '__main__':
    main() 