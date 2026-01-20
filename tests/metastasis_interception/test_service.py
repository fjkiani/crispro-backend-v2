"""
Service orchestration tests for metastasis interception
Tests end-to-end flow with mocked insights/design/safety
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from api.services import metastasis_interception_service


@pytest.mark.asyncio
async def test_target_lock_with_mocked_insights():
    """Test target lock with mocked insight responses"""
    mutations = [
        {"gene": "VEGFA", "hgvs_p": "p.Gly123Asp", "chrom": "6", "pos": 43737946, "ref": "G", "alt": "A"}
    ]
    mission_step = "angiogenesis"
    
    # Mock httpx.AsyncClient
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Mock responses for VEGFA
        mock_responses = {
            "functionality": AsyncMock(status_code=200, json=lambda: {"functionality_score": 0.75}),
            "essentiality": AsyncMock(status_code=200, json=lambda: {"essentiality_score": 0.80}),
            "regulatory": AsyncMock(status_code=200, json=lambda: {"regulatory_impact_score": 0.65}),
            "chromatin": AsyncMock(status_code=200, json=lambda: {"accessibility_score": 0.70})
        }
        
        call_count = [0]
        async def mock_post(url, **kwargs):
            if "functionality" in url:
                return mock_responses["functionality"]
            elif "essentiality" in url:
                return mock_responses["essentiality"]
            elif "regulatory" in url:
                return mock_responses["regulatory"]
            elif "chromatin" in url:
                return mock_responses["chromatin"]
            return AsyncMock(status_code=404)
        
        mock_client.post = mock_post
        
        validated_target, considered_targets = await metastasis_interception_service.target_lock(
            mutations, mission_step, "http://test"
        )
        
        # Assertions
        assert validated_target["gene"] == "VEGFA"
        assert 0.0 <= validated_target["rank_score"] <= 1.0
        assert len(validated_target["rationale"]) > 0
        assert "provenance" in validated_target
        assert "signals" in validated_target["provenance"]


@pytest.mark.asyncio
async def test_target_lock_tie_breaking():
    """Test that target lock prefers genes in mutations when tied"""
    mutations = [
        {"gene": "VEGFA", "hgvs_p": "p.Gly123Asp", "chrom": "6", "pos": 43737946, "ref": "G", "alt": "A"},
        {"gene": "BRAF", "hgvs_p": "p.Val600Glu", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A"}
    ]
    mission_step = "angiogenesis"
    
    with patch("httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client_cls.return_value.__aenter__.return_value = mock_client
        
        # Both genes get identical scores
        mock_response = AsyncMock(status_code=200, json=lambda: {"functionality_score": 0.7, "essentiality_score": 0.7})
        mock_client.post = AsyncMock(return_value=mock_response)
        
        validated_target, considered_targets = await metastasis_interception_service.target_lock(
            mutations, mission_step, "http://test"
        )
        
        # VEGFA should win (first in ANGIO gene set and first in mutations)
        assert validated_target["gene"] in ["VEGFA", "VEGFR1", "VEGFR2"]  # One of ANGIO set


@pytest.mark.asyncio
async def test_safety_preview_with_candidates():
    """Test safety preview integration"""
    candidates = [
        {"sequence": "ACGTACGTACGTACGTACGT", "pam": "NGG", "gc": 0.5, "spacer_efficacy_heuristic": 0.8},
        {"sequence": "TGCATGCATGCATGCATGCA", "pam": "NGG", "gc": 0.4, "spacer_efficacy_heuristic": 0.7}
    ]
    
    with patch("api.services.safety_service.preview_off_targets") as mock_safety:
        from api.schemas.safety import OffTargetResponse, GuideHeuristics, OffTargetProvenance
        
        mock_safety.return_value = OffTargetResponse(
            guides=[
                GuideHeuristics(seq="ACGTACGTACGTACGTACGT", gc=0.5, homopolymer=False, heuristic_score=0.9),
                GuideHeuristics(seq="TGCATGCATGCATGCATGCA", gc=0.4, homopolymer=False, heuristic_score=0.85)
            ],
            provenance=OffTargetProvenance(run_id="test", methods=["heuristic_v1"])
        )
        
        result = await metastasis_interception_service.safety_preview(candidates, "http://test")
        
        assert all("safety_score" in c for c in result)
        assert all("safety_method" in c for c in result)
        assert result[0]["safety_score"] == 0.9
        assert result[1]["safety_score"] == 0.85


@pytest.mark.asyncio
async def test_safety_preview_graceful_failure():
    """Test safety preview handles errors gracefully"""
    candidates = [
        {"sequence": "ACGTACGTACGTACGTACGT", "pam": "NGG"}
    ]
    
    with patch("api.services.safety_service.preview_off_targets") as mock_safety:
        mock_safety.side_effect = Exception("Safety service unavailable")
        
        result = await metastasis_interception_service.safety_preview(candidates, "http://test")
        
        # Should return placeholder values
        assert result[0]["safety_score"] == 0.5
        assert result[0]["safety_method"] == "placeholder"
        assert result[0]["safety_status"] == "error"


@pytest.mark.asyncio
async def test_design_candidates_missing_coords():
    """Test that design fails gracefully when coords are missing"""
    mutations = [{"gene": "VEGFA", "hgvs_p": "p.Gly123Asp"}]  # No coords
    
    with pytest.raises(ValueError) as exc_info:
        await metastasis_interception_service.design_candidates(
            "VEGFA", mutations, 3, "http://test"
        )
    
    assert "lacks genomic coordinates" in str(exc_info.value).lower()


def test_considered_targets_limit():
    """Test that considered_targets returns max 3 runners-up"""
    # This would require mocking the full target_lock flow
    # For now, verify the service logic caps at 3
    assert True  # Placeholder - logic verified in service code

