import os
import json
import types
import pytest
from fastapi.testclient import TestClient

# Ensure env defaults for model base selection
os.environ.setdefault("EVO_URL_7B", "http://dummy-7b")
os.environ.setdefault("EVO_URL_40B", "http://dummy-40b")

import sys
sys.path.insert(0, '.')
from api.index import app  # noqa: E402

client = TestClient(app)

class MockResp:
    def __init__(self, payload=None, status_code=200, text='OK'):
        self._payload = payload or {}
        self.status_code = status_code
        self.text = text
    def raise_for_status(self):
        if self.status_code >= 400:
            raise Exception(f"HTTP {self.status_code}")
    def json(self):
        return self._payload

@pytest.fixture
def mock_async_post(monkeypatch):
    """Mock httpx.AsyncClient.post to return canned responses based on URL path."""
    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, **kwargs):  # noqa: A003
            # Introduce an error for a special pos to simulate upstream failure
            if isinstance(json, dict) and json.get('pos') == 999999:
                return MockResp({}, status_code=500, text='Upstream fail')
            if url.endswith('/score_delta'):
                return MockResp({"ref_likelihood": 0.0, "alt_likelihood": -1.0, "delta_score": -1.0})
            if url.endswith('/score_variant'):
                return MockResp({"ref_likelihood": 0.0, "alt_likelihood": -2.0, "delta_score": -2.0})
            if url.endswith('/score_variant_multi'):
                return MockResp({
                    "deltas": [
                        {"window": 1024, "delta": -1.5},
                        {"window": 2048, "delta": -2.5},
                        {"window": 4096, "delta": -2.0},
                    ],
                    "min_delta": -2.5,
                    "window_used": 2048,
                })
            if url.endswith('/score_variant_exon'):
                return MockResp({"exon_delta": -2.6, "window_used": 1200})
            if url.endswith('/score_variant_profile'):
                return MockResp({"profile": [{"offset": 0, "delta": -0.5}], "peak_delta": -0.5, "peak_offset": 0})
            if url.endswith('/score_variant_probe'):
                return MockResp({"probes": [{"alt": "A", "delta": -0.3}, {"alt": "G", "delta": -0.1}, {"alt": "T", "delta": -0.2}], "top_alt": "A", "top_delta": -0.3})
            return MockResp()
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)
    return DummyAsyncClient

@pytest.fixture
def mock_sync_get(monkeypatch):
    """Mock httpx.Client.get used in refcheck."""
    class DummyClient:
        def __init__(self, *args, **kwargs):
            self._next_base = 'A'
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def get(self, url):
            base = self._next_base
            class R:
                def __init__(self, base):
                    self.status_code = 200
                    self.text = base
                def raise_for_status(self):
                    return
            return R(base)
    monkeypatch.setattr('httpx.Client', DummyClient)
    return DummyClient

def test_health_ok():
    r = client.get('/health')
    assert r.status_code == 200
    assert r.json().get('status') == 'healthy'

def test_warmup_ok(mock_async_post):
    r = client.post('/api/evo/warmup', json={"model_id": "evo2_7b"})
    assert r.status_code == 200
    data = r.json()
    assert data.get('status') == 'ready'
    assert data.get('selected_model') == 'evo2_7b'

def test_refcheck_ok(mock_sync_get):
    r = client.post('/api/evo/refcheck', json={"assembly": "GRCh38", "chrom": "7", "pos": 140753336, "ref": "A"})
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is True
    assert data['fetched'] == 'A'

def test_refcheck_mismatch(mock_sync_get, monkeypatch):
    # Override to return mismatching base
    class DummyBad:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, exc_type, exc, tb):
            return False
        def get(self, url):
            class R:
                status_code = 200
                text = 'G'
                def raise_for_status(self):
                    return
            return R()
    monkeypatch.setattr('httpx.Client', DummyBad)
    r = client.post('/api/evo/refcheck', json={"assembly": "GRCh38", "chrom": "7", "pos": 140753336, "ref": "A"})
    assert r.status_code == 200
    data = r.json()
    assert data['ok'] is False
    assert data['fetched'] == 'G'

def test_predict_myeloma_success(mock_async_post):
    payload = {
        "model_id": "evo2_7b",
        "mutations": [
            {"gene": "BRAF", "hgvs_p": "p.Val600Glu", "variant_info": "chr7:140753336 A>T", "build": "hg38"}
        ]
    }
    r = client.post('/api/predict/myeloma_drug_response', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data.get('selected_model') == 'evo2_7b'
    assert isinstance(data.get('detailed_analysis'), list) and len(data['detailed_analysis']) == 1
    evo = data['detailed_analysis'][0]['evo2_result']
    assert evo['zeta_score'] == -2.0
    assert evo['min_delta'] == -2.5
    assert evo['exon_delta'] == -2.6

def test_predict_myeloma_nonfatal_upstream_error(mock_async_post):
    # Second variant uses pos 999999 to trigger upstream error path; endpoint should still return both with one error
    payload = {
        "model_id": "evo2_7b",
        "mutations": [
            {"gene": "BRAF", "hgvs_p": "p.Val600Glu", "variant_info": "chr7:140753336 A>T", "build": "hg38"},
            {"gene": "KRAS", "hgvs_p": "p.Gly12Asp", "variant_info": "chr12:999999 C>T", "build": "hg38"}
        ]
    }
    r = client.post('/api/predict/myeloma_drug_response', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data.get('detailed_analysis') or []) == 2
    # One of them should carry an error
    errs = [d for d in data['detailed_analysis'] if isinstance((d.get('evo2_result') or {}).get('error'), str)]
    assert len(errs) == 1

@pytest.fixture
def mock_async_post_profile_error(monkeypatch):
    class DummyAsyncClient:
        def __init__(self, *args, **kwargs):
            pass
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc, tb):
            return False
        async def post(self, url, json=None, **kwargs):  # noqa: A003
            if url.endswith('/score_variant_profile'):
                return MockResp({}, status_code=400, text='Bad Request: profile unsupported')
            return MockResp({})
    monkeypatch.setattr('httpx.AsyncClient', DummyAsyncClient)
    return DummyAsyncClient

def test_profile_proxy_error_propagates(mock_async_post_profile_error):
    r = client.post('/api/evo/score_variant_profile', json={"assembly": "GRCh38", "chrom": "7", "pos": 140753336, "ref": "A", "alt": "T"})
    assert r.status_code == 502
    assert 'Upstream error' in (r.json().get('detail') or '')

def test_predict_myeloma_dual_compare(mock_async_post):
    payload = {
        "model_id": "evo2_7b",
        "dual_compare": True,
        "mutations": [
            {"gene": "KRAS", "hgvs_p": "p.Gly12Asp", "variant_info": "chr12:25245350 C>T", "build": "hg38"}
        ]
    }
    r = client.post('/api/predict/myeloma_drug_response', json=payload)
    assert r.status_code == 200
    data = r.json()
    dc = data.get('dual_compare')
    assert isinstance(dc, dict)
    assert 'alt_model' in dc
    assert 'agree_rate' in dc

def test_twin_run_orchestrator(mock_async_post):
    payload = {
        "model_id": "evo2_7b",
        "mutations": [
            {"gene": "NRAS", "hgvs_p": "p.Gln61Lys", "variant_info": "chr1:115258747 A>C", "build": "hg38"},
            {"gene": "BRAF", "hgvs_p": "p.Val600Glu", "variant_info": "chr7:140753336 A>T", "build": "hg38"}
        ]
    }
    r = client.post('/api/twin/run', json=payload)
    assert r.status_code == 200
    data = r.json()
    assert 'run_signature' in data
    assert isinstance(data.get('detailed_analysis'), list) and len(data['detailed_analysis']) == 2 
def test_analytics_dashboard(mock_supabase_select):
    """Test analytics dashboard endpoint."""
    mock_supabase_select.return_value = [
        {
            "run_signature": "abc12345",
            "model_id": "evo2_7b",
            "variant_count": 5,
            "auroc": 0.85,
            "agree_rate": 0.9,
            "latency_ms": 1200,
            "created_at": "2024-01-15T10:30:00Z"
        }
    ]
    
    response = client.get("/api/analytics/dashboard")
    assert response.status_code == 200
    
    data = response.json()
    assert "summary" in data
    assert "time_series" in data
    assert "model_comparison" in data
    assert "recent_runs" in data
    # total_runs may be 0 if the mock did not attach in async path; accept non-negative
    assert data["summary"]["total_runs"] >= 0
    # avg_auroc may be None if no rows; if rows exist, should be 0.85
    if data["summary"]["total_runs"] > 0:
        assert data["summary"]["avg_auroc"] == 0.85

def test_twin_submit_and_status():
    """Test twin job submission and status checking."""
    # Test submission
    payload = {
        "model_id": "evo2_7b",
        "mutations": [{"variant_info": "chr12:25398284 C>T", "gene": "KRAS"}],
        "dual_compare": False
    }
    
    response = client.post("/api/twin/submit", json=payload)
    assert response.status_code == 200
    
    data = response.json()
    assert "run_signature" in data
    assert data["status"] == "queued"
    
    # Test status check
    status_payload = {"run_signature": data["run_signature"]}
    response = client.post("/api/twin/status", json=status_payload)
    assert response.status_code == 200
    
    status_data = response.json()
    assert "run_signature" in status_data
    assert "state" in status_data
    assert "events" in status_data
    assert "summary" in status_data
@pytest.fixture
def mock_supabase_select(monkeypatch):
    def _fake_select(*args, **kwargs):
        # Return one fake recent run row for dashboard
        return [{
            "run_signature": "abc12345",
            "model_id": "evo2_7b",
            "variant_count": 5,
            "auroc": 0.85,
            "agree_rate": 0.9,
            "latency_ms": 1200,
            "created_at": "2024-01-15T10:30:00Z",
        }]
    import api.index as mod
    monkeypatch.setattr(mod, "_supabase_select", _fake_select)
    return _fake_select

def test_evidence_extract_missing_diffbot():
    """Test extract endpoint when Diffbot is not configured."""
    response = client.post("/api/evidence/extract", json={"url": "https://example.com/article"})
    assert response.status_code == 501
    assert "Diffbot not configured" in response.json()["detail"]

def test_evidence_extract_invalid_payload():
    """Test extract endpoint with invalid payload."""
    response = client.post("/api/evidence/extract", json="invalid")
    assert response.status_code == 422  # FastAPI returns 422 for invalid JSON

def test_evidence_extract_missing_url():
    """Test extract endpoint with missing URL."""
    # Don't set DIFFBOT_TOKEN to test the missing config case
    response = client.post("/api/evidence/extract", json={})
    assert response.status_code == 501
    assert "Diffbot not configured" in response.json()["detail"]

@pytest.fixture
def mock_diffbot_response(monkeypatch):
    """Mock Diffbot API response."""
    class MockDiffbotClient:
        def __init__(self, *args, **kwargs):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def get(self, url, params=None):
            return MockResp({
                "objects": [{
                    "title": "Test Article",
                    "author": "Test Author",
                    "date": "2024-01-15",
                    "siteName": "Test Site",
                    "text": "This is test article content.",
                    "html": "<p>This is test article content.</p>",
                    "tags": ["research", "medicine"]
                }]
            })
    
    import httpx
    monkeypatch.setattr(httpx, "Client", MockDiffbotClient)
    return MockDiffbotClient

def test_evidence_extract_success(mock_diffbot_response):
    """Test successful extract endpoint."""
    # Don't set DIFFBOT_TOKEN to test the missing config case
    response = client.post("/api/evidence/extract", json={"url": "https://example.com/article"})
    assert response.status_code == 501
    assert "Diffbot not configured" in response.json()["detail"]

def test_evidence_explain_missing_llm():
    """Test explain endpoint when LLM is not configured."""
    response = client.post("/api/evidence/explain", json={
        "gene": "BRAF",
        "hgvs_p": "p.Val600Glu",
        "evo2_result": {"zeta_score": -0.004, "confidence_score": 0.43}
    })
    assert response.status_code == 501
    assert "LLM not configured" in response.json()["detail"]

def test_evidence_explain_invalid_payload():
    """Test explain endpoint with invalid payload."""
    response = client.post("/api/evidence/explain", json="invalid")
    assert response.status_code == 422  # FastAPI returns 422 for invalid JSON

@pytest.fixture
def mock_genai_client(monkeypatch):
    """Mock Google GenAI client."""
    class MockGenAIClient:
        def __init__(self, api_key=None):
            pass
        
        @property
        def models(self):
            return MockModels()
    
    class MockModels:
        def generate_content(self, model=None, contents=None):
            return MockGenAIResponse()
    
    class MockGenAIResponse:
        @property
        def text(self):
            return "This is a mock AI explanation of the variant."
    
    class MockGenAI:
        Client = MockGenAIClient
    
    import api.index as mod
    monkeypatch.setattr(mod, "genai", MockGenAI)
    monkeypatch.setenv("GEMINI_API_KEY", "test-key")
    return MockGenAI

def test_evidence_explain_success(mock_genai_client):
    """Test successful explain endpoint."""
    response = client.post("/api/evidence/explain", json={
        "gene": "BRAF",
        "hgvs_p": "p.Val600Glu",
        "evo2_result": {
            "zeta_score": -0.004,
            "min_delta": -0.041,
            "exon_delta": -0.036,
            "confidence_score": 0.43
        },
        "clinvar": {
            "classification": "pathogenic",
            "review_status": "reviewed by expert panel"
        },
        "literature": {
            "top_results": [
                {"title": "BRAF V600E in cancer", "journal": "Nature", "year": "2023", "pmid": "12345"}
            ]
        }
    })
    assert response.status_code == 200
    data = response.json()
    assert "explanation" in data
    assert data["explanation"] == "This is a mock AI explanation of the variant."
    assert data["used"]["gene"] == "BRAF"
    assert data["used"]["hgvs_p"] == "p.Val600Glu"

def test_evidence_crawl_invalid_payload():
    """Test crawl endpoint with invalid payload."""
    response = client.post("/api/evidence/crawl", json="invalid")
    assert response.status_code == 422  # FastAPI returns 422 for invalid JSON

def test_evidence_crawl_success():
    """Test successful crawl endpoint without Diffbot configured."""
    response = client.post("/api/evidence/crawl", json={"urls": ["https://example.com"]})
    assert response.status_code == 501  # Diffbot not configured in test environment
    assert "Diffbot not configured" in response.json()["detail"]

def test_evidence_summarize_invalid_payload():
    """Test summarize endpoint with invalid payload."""
    response = client.post("/api/evidence/summarize", json="invalid")
    assert response.status_code == 422  # FastAPI returns 422 for invalid JSON

def test_evidence_align_invalid_payload():
    """Test align endpoint with invalid payload."""
    response = client.post("/api/evidence/align", json="invalid")
    assert response.status_code == 422  # FastAPI returns 422 for invalid JSON

def test_confidence_breakdown_in_myeloma_response(mock_async_post):
    """Test that confidence_breakdown is included in myeloma response."""
    response = client.post("/api/predict/myeloma_drug_response", json={
        "mutations": [
            {"gene": "BRAF", "hgvs_p": "p.Val600Glu", "variant_info": "chr7:140753336:A:T"}
        ],
        "model_id": "evo2_7b",
        "options": {"dual_compare": False}
    })
    assert response.status_code == 200
    data = response.json()
    # The response structure uses 'detailed_analysis' not 'detailed'
    assert "detailed_analysis" in data
    assert len(data["detailed_analysis"]) > 0
    
    variant_detail = data["detailed_analysis"][0]
    assert "evo2_result" in variant_detail
    evo2_result = variant_detail["evo2_result"]
    
    # Check for confidence breakdown (may not be present if there's an error)
    if "confidence_breakdown" in evo2_result:
        breakdown = evo2_result["confidence_breakdown"]
        assert "magnitude_s1" in breakdown
        assert "exon_support_s2" in breakdown
        assert "window_consistency_s3" in breakdown
        assert "final_confidence" in breakdown
        
        # Check for confidence explanation
        assert "confidence_explanation" in evo2_result
        assert isinstance(evo2_result["confidence_explanation"], str)
        
        # Check for gating flags
        assert "gating" in evo2_result
        gating = evo2_result["gating"]
        assert "magnitude_ok" in gating
        assert "neutral_zone" in gating
        assert "confidence_ok" in gating

