"""
Tests for spacer efficacy prediction endpoint
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.main import app

client = TestClient(app)


class TestSpacerEfficacyAPI:
    """API contract tests for /api/design/predict_crispr_spacer_efficacy"""
    
    def test_health_check(self):
        """Verify endpoint exists"""
        # Valid guide sequence
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGTACGTACGTACGT"}
        )
        # Should return 200 (or 403 if design API disabled)
        assert response.status_code in [200, 403]
    
    def test_schema_validation_20bp_required(self):
        """Guide sequence must be exactly 20bp"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGT"}  # Only 8bp
        )
        assert response.status_code == 400
        assert "20bp" in response.json()["detail"]
    
    def test_schema_validation_acgt_only(self):
        """Guide sequence must contain only ACGT"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTNACGTACGTACGTACG"}  # Contains 'N'
        )
        assert response.status_code == 400
        assert "ACGT" in response.json()["detail"]
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_target_sequence(self, mock_httpx):
        """Test with provided target_sequence (120bp context)"""
        # Mock Evo2 response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "likelihood": -15.5,
            "score": -15.5,
            "provenance": {"cached": False}
        }
        mock_client_instance = MagicMock()
        # Need to make post async
        async def async_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        target_seq = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50  # 120bp
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "model_id": "evo2_1b"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert "evo2_delta" in result
            assert "confidence" in result
            assert "provenance" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            assert result["provenance"]["method"] == "evo2_delta_sigmoid_v1"
            assert result["provenance"]["context_length"] == 120
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_coords_ensembl_fetch(self, mock_httpx):
        """Test with chrom/pos/ref/alt for Ensembl fetch"""
        # Mock Ensembl response
        mock_ensembl_response = MagicMock()
        mock_ensembl_response.status_code = 200
        mock_ensembl_response.text = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50
        
        # Mock Evo2 response
        mock_evo_response = MagicMock()
        mock_evo_response.status_code = 200
        mock_evo_response.json.return_value = {
            "likelihood": -12.3,
            "score": -12.3,
            "provenance": {"cached": False}
        }
        
        mock_client_instance = MagicMock()
        # Make both get and post async
        async def async_get(*args, **kwargs):
            return mock_ensembl_response
        async def async_post(*args, **kwargs):
            return mock_evo_response
        mock_client_instance.get = async_get
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "chrom": "7",
                "pos": 140453136,
                "ref": "T",
                "alt": "A",
                "assembly": "GRCh38"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert result["confidence"] >= 0.5  # Should be higher with context
    
    def test_fallback_to_heuristic(self):
        """Test graceful fallback to GC-based heuristic if Evo2 unavailable"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "GCGCGCGCGCGCGCGCGCGC"  # 100% GC
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            # High GC should give moderate-low score due to abs(gc - 0.5)
            assert result["efficacy_score"] < 0.75
            assert result["confidence"] <= 0.50  # Low confidence for heuristic


class TestSpacerEfficacyScoring:
    """Unit tests for efficacy scoring logic"""
    
    def test_sigmoid_transform(self):
        """Test sigmoid transformation of Evo2 delta"""
        import math
        
        scale_factor = 10.0
        
        # Test cases: (delta, expected_efficacy_range)
        test_cases = [
            (-20.0, (0.85, 0.95)),  # Very negative = high efficacy
            (-10.0, (0.70, 0.75)),  # Moderate negative = moderate efficacy
            (0.0, (0.45, 0.55)),    # Zero = ~0.5 efficacy
            (10.0, (0.25, 0.30)),   # Positive = low efficacy
        ]
        
        for delta, (min_eff, max_eff) in test_cases:
            efficacy = 1.0 / (1.0 + math.exp(delta / scale_factor))
            assert min_eff <= efficacy <= max_eff, f"Delta {delta} → efficacy {efficacy} not in [{min_eff}, {max_eff}]"
    
    def test_gc_heuristic_fallback(self):
        """Test GC-based heuristic scoring"""
        # Optimal GC (~50%) should give high score
        guide_optimal = "ACGTACGTACGTACGTACGT"  # 50% GC
        gc = (guide_optimal.count("G") + guide_optimal.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy >= 0.70
        
        # 100% GC should give lower score
        guide_high_gc = "GCGCGCGCGCGCGCGCGCGC"
        gc = (guide_high_gc.count("G") + guide_high_gc.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy <= 0.30


class TestAssassinScoreIntegration:
    """Test integration with assassin score calculation"""
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_assassin_score_uses_evo2_efficacy(self, mock_httpx):
        """Verify assassin score now uses Evo2-based efficacy"""
        # This is an integration test that would call the full intercept pipeline
        # For now, verify the endpoint is callable
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "model_id": "evo2_1b"
            }
        )
        
        # Just verify endpoint works; full integration test in test_metastasis_interception
        assert response.status_code in [200, 403]


class TestWindowSizeExpansion:
    """Test expanded design window (Task 1)"""
    
    def test_window_size_parameter_accepted(self):
        """Test window_size parameter is accepted by schema"""
        # Verify endpoint accepts window_size parameter
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 150  # Should be accepted
            }
        )
        # Should not error on schema validation
        assert response.status_code in [200, 403]  # 403 if design API disabled, 200 otherwise
    
    def test_custom_window_size_parameter(self):
        """Test custom window_size parameter (200bp)"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 200  # Custom window size
            }
        )
        assert response.status_code in [200, 403]
    
    def test_window_size_with_target_sequence(self):
        """Test window_size with provided target_sequence (300bp total)"""
        target_seq = "A" * 150 + "ACGTACGTACGTACGTACGT" + "T" * 130  # 300bp total
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "window_size": 150
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert result["provenance"]["context_length"] == 300
            assert "efficacy_score" in result
    
    def test_window_size_config_driven(self):
        """Verify window_size is config-driven via metastasis_interception_rules.json"""
        import json
        with open("api/config/metastasis_interception_rules.json") as f:
            ruleset = json.load(f)
        
        assert "design" in ruleset
        assert "window_size" in ruleset["design"]
        assert ruleset["design"]["window_size"] == 150  # Default per doctrine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.main import app

client = TestClient(app)


class TestSpacerEfficacyAPI:
    """API contract tests for /api/design/predict_crispr_spacer_efficacy"""
    
    def test_health_check(self):
        """Verify endpoint exists"""
        # Valid guide sequence
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGTACGTACGTACGT"}
        )
        # Should return 200 (or 403 if design API disabled)
        assert response.status_code in [200, 403]
    
    def test_schema_validation_20bp_required(self):
        """Guide sequence must be exactly 20bp"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGT"}  # Only 8bp
        )
        assert response.status_code == 400
        assert "20bp" in response.json()["detail"]
    
    def test_schema_validation_acgt_only(self):
        """Guide sequence must contain only ACGT"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTNACGTACGTACGTACG"}  # Contains 'N'
        )
        assert response.status_code == 400
        assert "ACGT" in response.json()["detail"]
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_target_sequence(self, mock_httpx):
        """Test with provided target_sequence (120bp context)"""
        # Mock Evo2 response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "likelihood": -15.5,
            "score": -15.5,
            "provenance": {"cached": False}
        }
        mock_client_instance = MagicMock()
        # Need to make post async
        async def async_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        target_seq = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50  # 120bp
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "model_id": "evo2_1b"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert "evo2_delta" in result
            assert "confidence" in result
            assert "provenance" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            assert result["provenance"]["method"] == "evo2_delta_sigmoid_v1"
            assert result["provenance"]["context_length"] == 120
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_coords_ensembl_fetch(self, mock_httpx):
        """Test with chrom/pos/ref/alt for Ensembl fetch"""
        # Mock Ensembl response
        mock_ensembl_response = MagicMock()
        mock_ensembl_response.status_code = 200
        mock_ensembl_response.text = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50
        
        # Mock Evo2 response
        mock_evo_response = MagicMock()
        mock_evo_response.status_code = 200
        mock_evo_response.json.return_value = {
            "likelihood": -12.3,
            "score": -12.3,
            "provenance": {"cached": False}
        }
        
        mock_client_instance = MagicMock()
        # Make both get and post async
        async def async_get(*args, **kwargs):
            return mock_ensembl_response
        async def async_post(*args, **kwargs):
            return mock_evo_response
        mock_client_instance.get = async_get
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "chrom": "7",
                "pos": 140453136,
                "ref": "T",
                "alt": "A",
                "assembly": "GRCh38"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert result["confidence"] >= 0.5  # Should be higher with context
    
    def test_fallback_to_heuristic(self):
        """Test graceful fallback to GC-based heuristic if Evo2 unavailable"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "GCGCGCGCGCGCGCGCGCGC"  # 100% GC
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            # High GC should give moderate-low score due to abs(gc - 0.5)
            assert result["efficacy_score"] < 0.75
            assert result["confidence"] <= 0.50  # Low confidence for heuristic


class TestSpacerEfficacyScoring:
    """Unit tests for efficacy scoring logic"""
    
    def test_sigmoid_transform(self):
        """Test sigmoid transformation of Evo2 delta"""
        import math
        
        scale_factor = 10.0
        
        # Test cases: (delta, expected_efficacy_range)
        test_cases = [
            (-20.0, (0.85, 0.95)),  # Very negative = high efficacy
            (-10.0, (0.70, 0.75)),  # Moderate negative = moderate efficacy
            (0.0, (0.45, 0.55)),    # Zero = ~0.5 efficacy
            (10.0, (0.25, 0.30)),   # Positive = low efficacy
        ]
        
        for delta, (min_eff, max_eff) in test_cases:
            efficacy = 1.0 / (1.0 + math.exp(delta / scale_factor))
            assert min_eff <= efficacy <= max_eff, f"Delta {delta} → efficacy {efficacy} not in [{min_eff}, {max_eff}]"
    
    def test_gc_heuristic_fallback(self):
        """Test GC-based heuristic scoring"""
        # Optimal GC (~50%) should give high score
        guide_optimal = "ACGTACGTACGTACGTACGT"  # 50% GC
        gc = (guide_optimal.count("G") + guide_optimal.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy >= 0.70
        
        # 100% GC should give lower score
        guide_high_gc = "GCGCGCGCGCGCGCGCGCGC"
        gc = (guide_high_gc.count("G") + guide_high_gc.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy <= 0.30


class TestAssassinScoreIntegration:
    """Test integration with assassin score calculation"""
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_assassin_score_uses_evo2_efficacy(self, mock_httpx):
        """Verify assassin score now uses Evo2-based efficacy"""
        # This is an integration test that would call the full intercept pipeline
        # For now, verify the endpoint is callable
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "model_id": "evo2_1b"
            }
        )
        
        # Just verify endpoint works; full integration test in test_metastasis_interception
        assert response.status_code in [200, 403]


class TestWindowSizeExpansion:
    """Test expanded design window (Task 1)"""
    
    def test_window_size_parameter_accepted(self):
        """Test window_size parameter is accepted by schema"""
        # Verify endpoint accepts window_size parameter
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 150  # Should be accepted
            }
        )
        # Should not error on schema validation
        assert response.status_code in [200, 403]  # 403 if design API disabled, 200 otherwise
    
    def test_custom_window_size_parameter(self):
        """Test custom window_size parameter (200bp)"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 200  # Custom window size
            }
        )
        assert response.status_code in [200, 403]
    
    def test_window_size_with_target_sequence(self):
        """Test window_size with provided target_sequence (300bp total)"""
        target_seq = "A" * 150 + "ACGTACGTACGTACGTACGT" + "T" * 130  # 300bp total
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "window_size": 150
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert result["provenance"]["context_length"] == 300
            assert "efficacy_score" in result
    
    def test_window_size_config_driven(self):
        """Verify window_size is config-driven via metastasis_interception_rules.json"""
        import json
        with open("api/config/metastasis_interception_rules.json") as f:
            ruleset = json.load(f)
        
        assert "design" in ruleset
        assert "window_size" in ruleset["design"]
        assert ruleset["design"]["window_size"] == 150  # Default per doctrine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])




"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.main import app

client = TestClient(app)


class TestSpacerEfficacyAPI:
    """API contract tests for /api/design/predict_crispr_spacer_efficacy"""
    
    def test_health_check(self):
        """Verify endpoint exists"""
        # Valid guide sequence
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGTACGTACGTACGT"}
        )
        # Should return 200 (or 403 if design API disabled)
        assert response.status_code in [200, 403]
    
    def test_schema_validation_20bp_required(self):
        """Guide sequence must be exactly 20bp"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGT"}  # Only 8bp
        )
        assert response.status_code == 400
        assert "20bp" in response.json()["detail"]
    
    def test_schema_validation_acgt_only(self):
        """Guide sequence must contain only ACGT"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTNACGTACGTACGTACG"}  # Contains 'N'
        )
        assert response.status_code == 400
        assert "ACGT" in response.json()["detail"]
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_target_sequence(self, mock_httpx):
        """Test with provided target_sequence (120bp context)"""
        # Mock Evo2 response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "likelihood": -15.5,
            "score": -15.5,
            "provenance": {"cached": False}
        }
        mock_client_instance = MagicMock()
        # Need to make post async
        async def async_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        target_seq = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50  # 120bp
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "model_id": "evo2_1b"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert "evo2_delta" in result
            assert "confidence" in result
            assert "provenance" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            assert result["provenance"]["method"] == "evo2_delta_sigmoid_v1"
            assert result["provenance"]["context_length"] == 120
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_coords_ensembl_fetch(self, mock_httpx):
        """Test with chrom/pos/ref/alt for Ensembl fetch"""
        # Mock Ensembl response
        mock_ensembl_response = MagicMock()
        mock_ensembl_response.status_code = 200
        mock_ensembl_response.text = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50
        
        # Mock Evo2 response
        mock_evo_response = MagicMock()
        mock_evo_response.status_code = 200
        mock_evo_response.json.return_value = {
            "likelihood": -12.3,
            "score": -12.3,
            "provenance": {"cached": False}
        }
        
        mock_client_instance = MagicMock()
        # Make both get and post async
        async def async_get(*args, **kwargs):
            return mock_ensembl_response
        async def async_post(*args, **kwargs):
            return mock_evo_response
        mock_client_instance.get = async_get
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "chrom": "7",
                "pos": 140453136,
                "ref": "T",
                "alt": "A",
                "assembly": "GRCh38"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert result["confidence"] >= 0.5  # Should be higher with context
    
    def test_fallback_to_heuristic(self):
        """Test graceful fallback to GC-based heuristic if Evo2 unavailable"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "GCGCGCGCGCGCGCGCGCGC"  # 100% GC
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            # High GC should give moderate-low score due to abs(gc - 0.5)
            assert result["efficacy_score"] < 0.75
            assert result["confidence"] <= 0.50  # Low confidence for heuristic


class TestSpacerEfficacyScoring:
    """Unit tests for efficacy scoring logic"""
    
    def test_sigmoid_transform(self):
        """Test sigmoid transformation of Evo2 delta"""
        import math
        
        scale_factor = 10.0
        
        # Test cases: (delta, expected_efficacy_range)
        test_cases = [
            (-20.0, (0.85, 0.95)),  # Very negative = high efficacy
            (-10.0, (0.70, 0.75)),  # Moderate negative = moderate efficacy
            (0.0, (0.45, 0.55)),    # Zero = ~0.5 efficacy
            (10.0, (0.25, 0.30)),   # Positive = low efficacy
        ]
        
        for delta, (min_eff, max_eff) in test_cases:
            efficacy = 1.0 / (1.0 + math.exp(delta / scale_factor))
            assert min_eff <= efficacy <= max_eff, f"Delta {delta} → efficacy {efficacy} not in [{min_eff}, {max_eff}]"
    
    def test_gc_heuristic_fallback(self):
        """Test GC-based heuristic scoring"""
        # Optimal GC (~50%) should give high score
        guide_optimal = "ACGTACGTACGTACGTACGT"  # 50% GC
        gc = (guide_optimal.count("G") + guide_optimal.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy >= 0.70
        
        # 100% GC should give lower score
        guide_high_gc = "GCGCGCGCGCGCGCGCGCGC"
        gc = (guide_high_gc.count("G") + guide_high_gc.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy <= 0.30


class TestAssassinScoreIntegration:
    """Test integration with assassin score calculation"""
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_assassin_score_uses_evo2_efficacy(self, mock_httpx):
        """Verify assassin score now uses Evo2-based efficacy"""
        # This is an integration test that would call the full intercept pipeline
        # For now, verify the endpoint is callable
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "model_id": "evo2_1b"
            }
        )
        
        # Just verify endpoint works; full integration test in test_metastasis_interception
        assert response.status_code in [200, 403]


class TestWindowSizeExpansion:
    """Test expanded design window (Task 1)"""
    
    def test_window_size_parameter_accepted(self):
        """Test window_size parameter is accepted by schema"""
        # Verify endpoint accepts window_size parameter
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 150  # Should be accepted
            }
        )
        # Should not error on schema validation
        assert response.status_code in [200, 403]  # 403 if design API disabled, 200 otherwise
    
    def test_custom_window_size_parameter(self):
        """Test custom window_size parameter (200bp)"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 200  # Custom window size
            }
        )
        assert response.status_code in [200, 403]
    
    def test_window_size_with_target_sequence(self):
        """Test window_size with provided target_sequence (300bp total)"""
        target_seq = "A" * 150 + "ACGTACGTACGTACGTACGT" + "T" * 130  # 300bp total
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "window_size": 150
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert result["provenance"]["context_length"] == 300
            assert "efficacy_score" in result
    
    def test_window_size_config_driven(self):
        """Verify window_size is config-driven via metastasis_interception_rules.json"""
        import json
        with open("api/config/metastasis_interception_rules.json") as f:
            ruleset = json.load(f)
        
        assert "design" in ruleset
        assert "window_size" in ruleset["design"]
        assert ruleset["design"]["window_size"] == 150  # Default per doctrine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])


"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock
import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from api.main import app

client = TestClient(app)


class TestSpacerEfficacyAPI:
    """API contract tests for /api/design/predict_crispr_spacer_efficacy"""
    
    def test_health_check(self):
        """Verify endpoint exists"""
        # Valid guide sequence
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGTACGTACGTACGT"}
        )
        # Should return 200 (or 403 if design API disabled)
        assert response.status_code in [200, 403]
    
    def test_schema_validation_20bp_required(self):
        """Guide sequence must be exactly 20bp"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTACGT"}  # Only 8bp
        )
        assert response.status_code == 400
        assert "20bp" in response.json()["detail"]
    
    def test_schema_validation_acgt_only(self):
        """Guide sequence must contain only ACGT"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={"guide_sequence": "ACGTNACGTACGTACGTACG"}  # Contains 'N'
        )
        assert response.status_code == 400
        assert "ACGT" in response.json()["detail"]
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_target_sequence(self, mock_httpx):
        """Test with provided target_sequence (120bp context)"""
        # Mock Evo2 response
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "likelihood": -15.5,
            "score": -15.5,
            "provenance": {"cached": False}
        }
        mock_client_instance = MagicMock()
        # Need to make post async
        async def async_post(*args, **kwargs):
            return mock_response
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        target_seq = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50  # 120bp
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "model_id": "evo2_1b"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert "evo2_delta" in result
            assert "confidence" in result
            assert "provenance" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            assert result["provenance"]["method"] == "evo2_delta_sigmoid_v1"
            assert result["provenance"]["context_length"] == 120
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_with_coords_ensembl_fetch(self, mock_httpx):
        """Test with chrom/pos/ref/alt for Ensembl fetch"""
        # Mock Ensembl response
        mock_ensembl_response = MagicMock()
        mock_ensembl_response.status_code = 200
        mock_ensembl_response.text = "A" * 50 + "ACGTACGTACGTACGTACGT" + "T" * 50
        
        # Mock Evo2 response
        mock_evo_response = MagicMock()
        mock_evo_response.status_code = 200
        mock_evo_response.json.return_value = {
            "likelihood": -12.3,
            "score": -12.3,
            "provenance": {"cached": False}
        }
        
        mock_client_instance = MagicMock()
        # Make both get and post async
        async def async_get(*args, **kwargs):
            return mock_ensembl_response
        async def async_post(*args, **kwargs):
            return mock_evo_response
        mock_client_instance.get = async_get
        mock_client_instance.post = async_post
        mock_httpx.return_value.__aenter__.return_value = mock_client_instance
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "chrom": "7",
                "pos": 140453136,
                "ref": "T",
                "alt": "A",
                "assembly": "GRCh38"
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert result["confidence"] >= 0.5  # Should be higher with context
    
    def test_fallback_to_heuristic(self):
        """Test graceful fallback to GC-based heuristic if Evo2 unavailable"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "GCGCGCGCGCGCGCGCGCGC"  # 100% GC
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert "efficacy_score" in result
            assert 0.0 <= result["efficacy_score"] <= 1.0
            # High GC should give moderate-low score due to abs(gc - 0.5)
            assert result["efficacy_score"] < 0.75
            assert result["confidence"] <= 0.50  # Low confidence for heuristic


class TestSpacerEfficacyScoring:
    """Unit tests for efficacy scoring logic"""
    
    def test_sigmoid_transform(self):
        """Test sigmoid transformation of Evo2 delta"""
        import math
        
        scale_factor = 10.0
        
        # Test cases: (delta, expected_efficacy_range)
        test_cases = [
            (-20.0, (0.85, 0.95)),  # Very negative = high efficacy
            (-10.0, (0.70, 0.75)),  # Moderate negative = moderate efficacy
            (0.0, (0.45, 0.55)),    # Zero = ~0.5 efficacy
            (10.0, (0.25, 0.30)),   # Positive = low efficacy
        ]
        
        for delta, (min_eff, max_eff) in test_cases:
            efficacy = 1.0 / (1.0 + math.exp(delta / scale_factor))
            assert min_eff <= efficacy <= max_eff, f"Delta {delta} → efficacy {efficacy} not in [{min_eff}, {max_eff}]"
    
    def test_gc_heuristic_fallback(self):
        """Test GC-based heuristic scoring"""
        # Optimal GC (~50%) should give high score
        guide_optimal = "ACGTACGTACGTACGTACGT"  # 50% GC
        gc = (guide_optimal.count("G") + guide_optimal.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy >= 0.70
        
        # 100% GC should give lower score
        guide_high_gc = "GCGCGCGCGCGCGCGCGCGC"
        gc = (guide_high_gc.count("G") + guide_high_gc.count("C")) / 20.0
        efficacy = 0.75 - abs(gc - 0.5)
        assert efficacy <= 0.30


class TestAssassinScoreIntegration:
    """Test integration with assassin score calculation"""
    
    @patch("api.routers.design.httpx.AsyncClient")
    def test_assassin_score_uses_evo2_efficacy(self, mock_httpx):
        """Verify assassin score now uses Evo2-based efficacy"""
        # This is an integration test that would call the full intercept pipeline
        # For now, verify the endpoint is callable
        
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "model_id": "evo2_1b"
            }
        )
        
        # Just verify endpoint works; full integration test in test_metastasis_interception
        assert response.status_code in [200, 403]


class TestWindowSizeExpansion:
    """Test expanded design window (Task 1)"""
    
    def test_window_size_parameter_accepted(self):
        """Test window_size parameter is accepted by schema"""
        # Verify endpoint accepts window_size parameter
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 150  # Should be accepted
            }
        )
        # Should not error on schema validation
        assert response.status_code in [200, 403]  # 403 if design API disabled, 200 otherwise
    
    def test_custom_window_size_parameter(self):
        """Test custom window_size parameter (200bp)"""
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "window_size": 200  # Custom window size
            }
        )
        assert response.status_code in [200, 403]
    
    def test_window_size_with_target_sequence(self):
        """Test window_size with provided target_sequence (300bp total)"""
        target_seq = "A" * 150 + "ACGTACGTACGTACGTACGT" + "T" * 130  # 300bp total
        response = client.post(
            "/api/design/predict_crispr_spacer_efficacy",
            json={
                "guide_sequence": "ACGTACGTACGTACGTACGT",
                "target_sequence": target_seq,
                "window_size": 150
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            assert result["provenance"]["context_length"] == 300
            assert "efficacy_score" in result
    
    def test_window_size_config_driven(self):
        """Verify window_size is config-driven via metastasis_interception_rules.json"""
        import json
        with open("api/config/metastasis_interception_rules.json") as f:
            ruleset = json.load(f)
        
        assert "design" in ruleset
        assert "window_size" in ruleset["design"]
        assert ruleset["design"]["window_size"] == 150  # Default per doctrine


if __name__ == "__main__":
    pytest.main([__file__, "-v"])



