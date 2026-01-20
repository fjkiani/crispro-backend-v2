"""
Unit tests for target lock logic in metastasis interception
"""
import pytest
from api.services import metastasis_interception_service


def test_load_ruleset():
    """Test ruleset loading and structure"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert ruleset["version"] == "metastasis_interception_v0.1"
    assert "weights" in ruleset
    assert "target_lock" in ruleset["weights"]
    assert "assassin" in ruleset["weights"]
    assert "gene_sets" in ruleset
    assert "ANGIO" in ruleset["gene_sets"]
    assert "mission_to_gene_sets" in ruleset
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]


def test_target_lock_weights():
    """Test that target lock weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["target_lock"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Target lock weights sum to {total}, expected 1.0"


def test_assassin_weights():
    """Test that assassin weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Assassin weights sum to {total}, expected 1.0"


def test_gene_set_mapping():
    """Test mission step to gene set mapping"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    # Angiogenesis should map to ANGIO gene set
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]
    assert "ANGIO" in ruleset["mission_to_gene_sets"]["angiogenesis"]
    
    # Local invasion (EMT) should map to EMT_TF
    assert "local_invasion" in ruleset["mission_to_gene_sets"]
    assert "EMT_TF" in ruleset["mission_to_gene_sets"]["local_invasion"]


def test_threshold_values():
    """Test that all thresholds are reasonable (0-1 range)"""
    ruleset = metastasis_interception_service.load_ruleset()
    thresholds = ruleset["thresholds"]
    
    for signal, threshold in thresholds.items():
        assert 0.0 <= threshold <= 1.0, f"Threshold for {signal} is {threshold}, expected 0-1"
        assert threshold == 0.6, f"Default threshold for {signal} should be 0.6"


@pytest.mark.asyncio
async def test_assassin_score_calculation():
    """Test assassin score computation with known inputs"""
    candidates = [
        {
            "sequence": "ACGTACGTACGTACGTACGT",
            "spacer_efficacy_heuristic": 0.8,
            "safety_score": 0.7
        },
        {
            "sequence": "TGCATGCATGCATGCATGCA",
            "spacer_efficacy_heuristic": 0.6,
            "safety_score": 0.9
        }
    ]
    
    target_lock_score = 0.75
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # Check all candidates have assassin_score
    assert all("assassin_score" in c for c in result)
    
    # Check scores are in valid range
    for cand in result:
        assert 0.0 <= cand["assassin_score"] <= 1.0
    
    # Check sorting (descending)
    scores = [c["assassin_score"] for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_assassin_score_weighting():
    """Test that assassin score correctly applies weights"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    candidates = [{
        "spacer_efficacy_heuristic": 1.0,
        "safety_score": 1.0
    }]
    
    target_lock_score = 1.0
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # With all perfect scores (1.0 each), assassin_score should be:
    # 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.0
    assert abs(result[0]["assassin_score"] - 1.0) < 0.01


def test_num_candidates_config():
    """Test that num_candidates is configurable"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert "num_candidates_per_target" in ruleset
    assert ruleset["num_candidates_per_target"] == 3



"""
import pytest
from api.services import metastasis_interception_service


def test_load_ruleset():
    """Test ruleset loading and structure"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert ruleset["version"] == "metastasis_interception_v0.1"
    assert "weights" in ruleset
    assert "target_lock" in ruleset["weights"]
    assert "assassin" in ruleset["weights"]
    assert "gene_sets" in ruleset
    assert "ANGIO" in ruleset["gene_sets"]
    assert "mission_to_gene_sets" in ruleset
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]


def test_target_lock_weights():
    """Test that target lock weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["target_lock"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Target lock weights sum to {total}, expected 1.0"


def test_assassin_weights():
    """Test that assassin weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Assassin weights sum to {total}, expected 1.0"


def test_gene_set_mapping():
    """Test mission step to gene set mapping"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    # Angiogenesis should map to ANGIO gene set
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]
    assert "ANGIO" in ruleset["mission_to_gene_sets"]["angiogenesis"]
    
    # Local invasion (EMT) should map to EMT_TF
    assert "local_invasion" in ruleset["mission_to_gene_sets"]
    assert "EMT_TF" in ruleset["mission_to_gene_sets"]["local_invasion"]


def test_threshold_values():
    """Test that all thresholds are reasonable (0-1 range)"""
    ruleset = metastasis_interception_service.load_ruleset()
    thresholds = ruleset["thresholds"]
    
    for signal, threshold in thresholds.items():
        assert 0.0 <= threshold <= 1.0, f"Threshold for {signal} is {threshold}, expected 0-1"
        assert threshold == 0.6, f"Default threshold for {signal} should be 0.6"


@pytest.mark.asyncio
async def test_assassin_score_calculation():
    """Test assassin score computation with known inputs"""
    candidates = [
        {
            "sequence": "ACGTACGTACGTACGTACGT",
            "spacer_efficacy_heuristic": 0.8,
            "safety_score": 0.7
        },
        {
            "sequence": "TGCATGCATGCATGCATGCA",
            "spacer_efficacy_heuristic": 0.6,
            "safety_score": 0.9
        }
    ]
    
    target_lock_score = 0.75
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # Check all candidates have assassin_score
    assert all("assassin_score" in c for c in result)
    
    # Check scores are in valid range
    for cand in result:
        assert 0.0 <= cand["assassin_score"] <= 1.0
    
    # Check sorting (descending)
    scores = [c["assassin_score"] for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_assassin_score_weighting():
    """Test that assassin score correctly applies weights"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    candidates = [{
        "spacer_efficacy_heuristic": 1.0,
        "safety_score": 1.0
    }]
    
    target_lock_score = 1.0
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # With all perfect scores (1.0 each), assassin_score should be:
    # 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.0
    assert abs(result[0]["assassin_score"] - 1.0) < 0.01


def test_num_candidates_config():
    """Test that num_candidates is configurable"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert "num_candidates_per_target" in ruleset
    assert ruleset["num_candidates_per_target"] == 3





"""
import pytest
from api.services import metastasis_interception_service


def test_load_ruleset():
    """Test ruleset loading and structure"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert ruleset["version"] == "metastasis_interception_v0.1"
    assert "weights" in ruleset
    assert "target_lock" in ruleset["weights"]
    assert "assassin" in ruleset["weights"]
    assert "gene_sets" in ruleset
    assert "ANGIO" in ruleset["gene_sets"]
    assert "mission_to_gene_sets" in ruleset
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]


def test_target_lock_weights():
    """Test that target lock weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["target_lock"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Target lock weights sum to {total}, expected 1.0"


def test_assassin_weights():
    """Test that assassin weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Assassin weights sum to {total}, expected 1.0"


def test_gene_set_mapping():
    """Test mission step to gene set mapping"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    # Angiogenesis should map to ANGIO gene set
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]
    assert "ANGIO" in ruleset["mission_to_gene_sets"]["angiogenesis"]
    
    # Local invasion (EMT) should map to EMT_TF
    assert "local_invasion" in ruleset["mission_to_gene_sets"]
    assert "EMT_TF" in ruleset["mission_to_gene_sets"]["local_invasion"]


def test_threshold_values():
    """Test that all thresholds are reasonable (0-1 range)"""
    ruleset = metastasis_interception_service.load_ruleset()
    thresholds = ruleset["thresholds"]
    
    for signal, threshold in thresholds.items():
        assert 0.0 <= threshold <= 1.0, f"Threshold for {signal} is {threshold}, expected 0-1"
        assert threshold == 0.6, f"Default threshold for {signal} should be 0.6"


@pytest.mark.asyncio
async def test_assassin_score_calculation():
    """Test assassin score computation with known inputs"""
    candidates = [
        {
            "sequence": "ACGTACGTACGTACGTACGT",
            "spacer_efficacy_heuristic": 0.8,
            "safety_score": 0.7
        },
        {
            "sequence": "TGCATGCATGCATGCATGCA",
            "spacer_efficacy_heuristic": 0.6,
            "safety_score": 0.9
        }
    ]
    
    target_lock_score = 0.75
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # Check all candidates have assassin_score
    assert all("assassin_score" in c for c in result)
    
    # Check scores are in valid range
    for cand in result:
        assert 0.0 <= cand["assassin_score"] <= 1.0
    
    # Check sorting (descending)
    scores = [c["assassin_score"] for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_assassin_score_weighting():
    """Test that assassin score correctly applies weights"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    candidates = [{
        "spacer_efficacy_heuristic": 1.0,
        "safety_score": 1.0
    }]
    
    target_lock_score = 1.0
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # With all perfect scores (1.0 each), assassin_score should be:
    # 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.0
    assert abs(result[0]["assassin_score"] - 1.0) < 0.01


def test_num_candidates_config():
    """Test that num_candidates is configurable"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert "num_candidates_per_target" in ruleset
    assert ruleset["num_candidates_per_target"] == 3



"""
import pytest
from api.services import metastasis_interception_service


def test_load_ruleset():
    """Test ruleset loading and structure"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert ruleset["version"] == "metastasis_interception_v0.1"
    assert "weights" in ruleset
    assert "target_lock" in ruleset["weights"]
    assert "assassin" in ruleset["weights"]
    assert "gene_sets" in ruleset
    assert "ANGIO" in ruleset["gene_sets"]
    assert "mission_to_gene_sets" in ruleset
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]


def test_target_lock_weights():
    """Test that target lock weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["target_lock"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Target lock weights sum to {total}, expected 1.0"


def test_assassin_weights():
    """Test that assassin weights sum to 1.0"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    total = sum(weights.values())
    assert abs(total - 1.0) < 0.01, f"Assassin weights sum to {total}, expected 1.0"


def test_gene_set_mapping():
    """Test mission step to gene set mapping"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    # Angiogenesis should map to ANGIO gene set
    assert "angiogenesis" in ruleset["mission_to_gene_sets"]
    assert "ANGIO" in ruleset["mission_to_gene_sets"]["angiogenesis"]
    
    # Local invasion (EMT) should map to EMT_TF
    assert "local_invasion" in ruleset["mission_to_gene_sets"]
    assert "EMT_TF" in ruleset["mission_to_gene_sets"]["local_invasion"]


def test_threshold_values():
    """Test that all thresholds are reasonable (0-1 range)"""
    ruleset = metastasis_interception_service.load_ruleset()
    thresholds = ruleset["thresholds"]
    
    for signal, threshold in thresholds.items():
        assert 0.0 <= threshold <= 1.0, f"Threshold for {signal} is {threshold}, expected 0-1"
        assert threshold == 0.6, f"Default threshold for {signal} should be 0.6"


@pytest.mark.asyncio
async def test_assassin_score_calculation():
    """Test assassin score computation with known inputs"""
    candidates = [
        {
            "sequence": "ACGTACGTACGTACGTACGT",
            "spacer_efficacy_heuristic": 0.8,
            "safety_score": 0.7
        },
        {
            "sequence": "TGCATGCATGCATGCATGCA",
            "spacer_efficacy_heuristic": 0.6,
            "safety_score": 0.9
        }
    ]
    
    target_lock_score = 0.75
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # Check all candidates have assassin_score
    assert all("assassin_score" in c for c in result)
    
    # Check scores are in valid range
    for cand in result:
        assert 0.0 <= cand["assassin_score"] <= 1.0
    
    # Check sorting (descending)
    scores = [c["assassin_score"] for c in result]
    assert scores == sorted(scores, reverse=True)


@pytest.mark.asyncio
async def test_assassin_score_weighting():
    """Test that assassin score correctly applies weights"""
    ruleset = metastasis_interception_service.load_ruleset()
    weights = ruleset["weights"]["assassin"]
    
    candidates = [{
        "spacer_efficacy_heuristic": 1.0,
        "safety_score": 1.0
    }]
    
    target_lock_score = 1.0
    
    result = await metastasis_interception_service.assassin_score(candidates, target_lock_score)
    
    # With all perfect scores (1.0 each), assassin_score should be:
    # 0.4*1.0 + 0.3*1.0 + 0.3*1.0 = 1.0
    assert abs(result[0]["assassin_score"] - 1.0) < 0.01


def test_num_candidates_config():
    """Test that num_candidates is configurable"""
    ruleset = metastasis_interception_service.load_ruleset()
    
    assert "num_candidates_per_target" in ruleset
    assert ruleset["num_candidates_per_target"] == 3




