from fastapi.testclient import TestClient

from main_minimal import app


def test_io_selection_endpoint_ayesha_like_payload():
    client = TestClient(app)

    payload = {
        "patient_age": 40,
        "autoimmune_history": [],
        "tumor_context": {
            "biomarkers": {"pd_l1_cps": 10, "mmr_status": "PRESERVED", "msi_status": "MSS"},
            "tmb": None,
            "somatic_mutations": [{"gene": "TP53"}],
        },
        "germline_mutations": [{"gene": "MBD4", "hgvs_p": "p.K431Nfs*54"}],
    }

    r = client.post("/api/io/select", json=payload)
    assert r.status_code == 200, r.text

    data = r.json()
    assert data["eligible"] is True
    assert data["selected_safest"] is not None

    # Based on IO_DRUG_PROFILES: avelumab has the lowest grade3+ irAE rate in our list
    assert (data["selected_safest"].get("selected") or "").lower() == "avelumab"


if __name__ == "__main__":
    test_io_selection_endpoint_ayesha_like_payload()
    print("✅ OK")
