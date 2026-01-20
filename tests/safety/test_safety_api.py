"""
API integration tests for safety endpoints.

Tests:
- /api/safety/health
- /api/safety/toxicity_risk
- /api/safety/off_target_preview
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestSafetyAPIHealth:
    """Test safety API health check."""
    
    def test_health_check(self):
        """Test /api/safety/health endpoint."""
        response = client.get("/api/safety/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "safety"
        assert data["ruo"] is True
        assert "endpoints" in data


class TestToxicityRiskAPI:
    """Test toxicity risk assessment API."""
    
    def test_toxicity_risk_happy_path(self):
        """Test toxicity risk with valid payload."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "1", "pos": 97450058, "ref": "C", "alt": "T", "gene": "DPYD"}
                ]
            },
            "candidate": {
                "type": "drug",
                "moa": "platinum_agent"
            },
            "context": {
                "disease": "ovarian"
            }
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check schema
        assert "risk_score" in data
        assert "confidence" in data
        assert "reason" in data
        assert "factors" in data
        assert "provenance" in data
        
        # Check values
        assert 0.0 <= data["risk_score"] <= 1.0
        assert 0.0 <= data["confidence"] <= 1.0
        assert isinstance(data["factors"], list)
        assert len(data["factors"]) > 0  # Should detect DPYD
        
        # Check provenance
        assert "run_id" in data["provenance"]
        assert "methods" in data["provenance"]
    
    def test_toxicity_risk_no_germline(self):
        """Test toxicity risk with no germline variants."""
        payload = {
            "patient": {"germlineVariants": []},
            "candidate": {"type": "drug", "moa": "BRAF_inhibitor"},
            "context": {"disease": "melanoma"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] >= 0.0
        assert len(data["factors"]) == 0  # No germline factors
    
    def test_toxicity_risk_with_profile(self):
        """Test toxicity risk respects profile parameter."""
        payload = {
            "patient": {"germlineVariants": []},
            "candidate": {"type": "drug", "moa": "MEK_inhibitor"},
            "context": {"disease": "MM"},
            "options": {"profile": "richer", "evidence": True}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["provenance"]["profile"] == "richer"
    
    def test_toxicity_risk_multiple_pharmacogenes(self):
        """Test toxicity risk with multiple pharmacogene variants."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "1", "pos": 97450058, "ref": "C", "alt": "T", "gene": "DPYD"},
                    {"chrom": "6", "pos": 18138997, "ref": "G", "alt": "A", "gene": "TPMT"},
                ]
            },
            "candidate": {"type": "drug", "moa": "alkylating_agent"},
            "context": {"disease": "leukemia"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] > 0.3  # Should flag both
        assert len([f for f in data["factors"] if f["type"] == "germline"]) >= 2
    
    def test_toxicity_risk_pathway_overlap(self):
        """Test toxicity risk detects pathway overlap."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "17", "pos": 43044295, "ref": "G", "alt": "A", "gene": "BRCA1"},
                    {"chrom": "13", "pos": 32379913, "ref": "C", "alt": "T", "gene": "BRCA2"},
                    {"chrom": "11", "pos": 108236285, "ref": "A", "alt": "G", "gene": "ATM"}
                ]
            },
            "candidate": {"type": "drug", "moa": "PARP_inhibitor"},
            "context": {"disease": "ovarian"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        # PARP inhibitors + DNA repair germline variants = pathway overlap
        pathway_factors = [f for f in data["factors"] if f["type"] == "pathway"]
        assert len(pathway_factors) > 0


class TestOffTargetPreviewAPI:
    """Test off-target preview API."""
    
    def test_off_target_preview_single_guide(self):
        """Test off-target preview with single guide."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NGG"}
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check schema
        assert "guides" in data
        assert "summary" in data
        assert "provenance" in data
        assert "note" in data
        
        # Check guide scoring
        assert len(data["guides"]) == 1
        guide = data["guides"][0]
        assert "heuristic_score" in guide
        assert "risk_level" in guide
        assert "gc_content" in guide
        assert "warnings" in guide
        
        # Check provenance
        assert "run_id" in data["provenance"]
        assert "methods" in data["provenance"]
    
    def test_off_target_preview_optimal_guide(self):
        """Test off-target preview scores optimal guide well."""
        payload = {
            "guides": [
                {"seq": "GCTAGCTACGATCGATCGAT", "pam": "NGG"}  # Balanced GC, no homopolymers
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["heuristic_score"] > 0.5
        assert guide["risk_level"] in ["low", "medium"]
    
    def test_off_target_preview_poor_guide(self):
        """Test off-target preview flags poor guide."""
        payload = {
            "guides": [
                {"seq": "AAAAAAAAAAAAAAAAAAAA", "pam": "NGG"}  # All A's, terrible
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["heuristic_score"] < 0.5
        assert guide["risk_level"] in ["medium", "high"]
        assert guide["homopolymer"] is True
        assert len(guide["warnings"]) > 0
    
    def test_off_target_preview_multiple_guides(self):
        """Test off-target preview with multiple guides."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NGG"},
                {"seq": "GGGGCCCGGGGCCCGGGGCC", "pam": "NGG"},
                {"seq": "AAAATTTAAATTTAAATTAA", "pam": "NGG"}
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["guides"]) == 3
        assert data["summary"]["total_guides"] == 3
        assert "avg_heuristic_score" in data["summary"]
        assert "low_risk_count" in data["summary"]
    
    def test_off_target_preview_custom_pam(self):
        """Test off-target preview with custom PAM."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NAG"}  # Custom PAM
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["pam"] == "NAG"


class TestSafetyAPIEdgeCases:
    """Test edge cases and error handling."""
    
    def test_toxicity_risk_missing_required_fields(self):
        """Test toxicity risk with missing required fields."""
        payload = {
            "patient": {"germlineVariants": []},
            # Missing candidate and context
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        # Should return 422 validation error
        assert response.status_code == 422
    
    def test_off_target_preview_empty_guides(self):
        """Test off-target preview with no guides."""
        payload = {"guides": []}
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        # Should work but return empty results
        assert response.status_code == 200
        data = response.json()
        assert len(data["guides"]) == 0
        assert data["summary"]["total_guides"] == 0

API integration tests for safety endpoints.

Tests:
- /api/safety/health
- /api/safety/toxicity_risk
- /api/safety/off_target_preview
"""

import pytest
from fastapi.testclient import TestClient
from api.main import app

client = TestClient(app)


class TestSafetyAPIHealth:
    """Test safety API health check."""
    
    def test_health_check(self):
        """Test /api/safety/health endpoint."""
        response = client.get("/api/safety/health")
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "safety"
        assert data["ruo"] is True
        assert "endpoints" in data


class TestToxicityRiskAPI:
    """Test toxicity risk assessment API."""
    
    def test_toxicity_risk_happy_path(self):
        """Test toxicity risk with valid payload."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "1", "pos": 97450058, "ref": "C", "alt": "T", "gene": "DPYD"}
                ]
            },
            "candidate": {
                "type": "drug",
                "moa": "platinum_agent"
            },
            "context": {
                "disease": "ovarian"
            }
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check schema
        assert "risk_score" in data
        assert "confidence" in data
        assert "reason" in data
        assert "factors" in data
        assert "provenance" in data
        
        # Check values
        assert 0.0 <= data["risk_score"] <= 1.0
        assert 0.0 <= data["confidence"] <= 1.0
        assert isinstance(data["factors"], list)
        assert len(data["factors"]) > 0  # Should detect DPYD
        
        # Check provenance
        assert "run_id" in data["provenance"]
        assert "methods" in data["provenance"]
    
    def test_toxicity_risk_no_germline(self):
        """Test toxicity risk with no germline variants."""
        payload = {
            "patient": {"germlineVariants": []},
            "candidate": {"type": "drug", "moa": "BRAF_inhibitor"},
            "context": {"disease": "melanoma"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] >= 0.0
        assert len(data["factors"]) == 0  # No germline factors
    
    def test_toxicity_risk_with_profile(self):
        """Test toxicity risk respects profile parameter."""
        payload = {
            "patient": {"germlineVariants": []},
            "candidate": {"type": "drug", "moa": "MEK_inhibitor"},
            "context": {"disease": "MM"},
            "options": {"profile": "richer", "evidence": True}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["provenance"]["profile"] == "richer"
    
    def test_toxicity_risk_multiple_pharmacogenes(self):
        """Test toxicity risk with multiple pharmacogene variants."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "1", "pos": 97450058, "ref": "C", "alt": "T", "gene": "DPYD"},
                    {"chrom": "6", "pos": 18138997, "ref": "G", "alt": "A", "gene": "TPMT"},
                ]
            },
            "candidate": {"type": "drug", "moa": "alkylating_agent"},
            "context": {"disease": "leukemia"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        assert data["risk_score"] > 0.3  # Should flag both
        assert len([f for f in data["factors"] if f["type"] == "germline"]) >= 2
    
    def test_toxicity_risk_pathway_overlap(self):
        """Test toxicity risk detects pathway overlap."""
        payload = {
            "patient": {
                "germlineVariants": [
                    {"chrom": "17", "pos": 43044295, "ref": "G", "alt": "A", "gene": "BRCA1"},
                    {"chrom": "13", "pos": 32379913, "ref": "C", "alt": "T", "gene": "BRCA2"},
                    {"chrom": "11", "pos": 108236285, "ref": "A", "alt": "G", "gene": "ATM"}
                ]
            },
            "candidate": {"type": "drug", "moa": "PARP_inhibitor"},
            "context": {"disease": "ovarian"}
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        # PARP inhibitors + DNA repair germline variants = pathway overlap
        pathway_factors = [f for f in data["factors"] if f["type"] == "pathway"]
        assert len(pathway_factors) > 0


class TestOffTargetPreviewAPI:
    """Test off-target preview API."""
    
    def test_off_target_preview_single_guide(self):
        """Test off-target preview with single guide."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NGG"}
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        # Check schema
        assert "guides" in data
        assert "summary" in data
        assert "provenance" in data
        assert "note" in data
        
        # Check guide scoring
        assert len(data["guides"]) == 1
        guide = data["guides"][0]
        assert "heuristic_score" in guide
        assert "risk_level" in guide
        assert "gc_content" in guide
        assert "warnings" in guide
        
        # Check provenance
        assert "run_id" in data["provenance"]
        assert "methods" in data["provenance"]
    
    def test_off_target_preview_optimal_guide(self):
        """Test off-target preview scores optimal guide well."""
        payload = {
            "guides": [
                {"seq": "GCTAGCTACGATCGATCGAT", "pam": "NGG"}  # Balanced GC, no homopolymers
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["heuristic_score"] > 0.5
        assert guide["risk_level"] in ["low", "medium"]
    
    def test_off_target_preview_poor_guide(self):
        """Test off-target preview flags poor guide."""
        payload = {
            "guides": [
                {"seq": "AAAAAAAAAAAAAAAAAAAA", "pam": "NGG"}  # All A's, terrible
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["heuristic_score"] < 0.5
        assert guide["risk_level"] in ["medium", "high"]
        assert guide["homopolymer"] is True
        assert len(guide["warnings"]) > 0
    
    def test_off_target_preview_multiple_guides(self):
        """Test off-target preview with multiple guides."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NGG"},
                {"seq": "GGGGCCCGGGGCCCGGGGCC", "pam": "NGG"},
                {"seq": "AAAATTTAAATTTAAATTAA", "pam": "NGG"}
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        
        assert len(data["guides"]) == 3
        assert data["summary"]["total_guides"] == 3
        assert "avg_heuristic_score" in data["summary"]
        assert "low_risk_count" in data["summary"]
    
    def test_off_target_preview_custom_pam(self):
        """Test off-target preview with custom PAM."""
        payload = {
            "guides": [
                {"seq": "AGCTGCTAGCTGCTAGCTGC", "pam": "NAG"}  # Custom PAM
            ]
        }
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        assert response.status_code == 200
        data = response.json()
        guide = data["guides"][0]
        assert guide["pam"] == "NAG"


class TestSafetyAPIEdgeCases:
    """Test edge cases and error handling."""
    
    def test_toxicity_risk_missing_required_fields(self):
        """Test toxicity risk with missing required fields."""
        payload = {
            "patient": {"germlineVariants": []},
            # Missing candidate and context
        }
        
        response = client.post("/api/safety/toxicity_risk", json=payload)
        
        # Should return 422 validation error
        assert response.status_code == 422
    
    def test_off_target_preview_empty_guides(self):
        """Test off-target preview with no guides."""
        payload = {"guides": []}
        
        response = client.post("/api/safety/off_target_preview", json=payload)
        
        # Should work but return empty results
        assert response.status_code == 200
        data = response.json()
        assert len(data["guides"]) == 0
        assert data["summary"]["total_guides"] == 0

















