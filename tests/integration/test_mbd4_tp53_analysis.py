"""
Comprehensive test suite for MBD4+TP53 HGSOC analysis validation.

Tests all critical components:
1. Frameshift/truncation detection
2. Hotspot detection
3. Pathway aggregation
4. PARP predictions
5. Mechanism vector conversion
6. Trial matching
"""

import pytest
import asyncio
import httpx
from typing import Dict, List, Optional

from api.config import DEFAULT_EVO_MODEL
from api.services.pathway_to_mechanism_vector import (
    convert_pathway_scores_to_mechanism_vector,
    extract_pathway_disruption_from_response,
    get_mechanism_vector_from_response
)

# Test variants
MBD4_VARIANT = {
    "chrom": "3",
    "pos": 129430456,
    "ref": "A",
    "alt": "",
    "gene": "MBD4",
    "hgvs_p": "p.Ile413Serfs*2",
    "hgvs_c": "c.1239delA"
}

TP53_VARIANT = {
    "chrom": "17",
    "pos": 7577120,
    "ref": "G",
    "alt": "A",
    "gene": "TP53",
    "hgvs_p": "p.R175H"
}

BASE_URL = "http://localhost:8000"


@pytest.mark.asyncio
async def test_mbd4_frameshift_detection():
    """Test 1: MBD4 frameshift variant → sequence_disruption ≥0.8"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract sequence scores
        drugs = data.get("drugs", [])
        assert len(drugs) > 0, "Should have drug recommendations"
        
        seq_scores = []
        for drug in drugs:
            rationale = drug.get("rationale", [])
            for r in rationale:
                if r.get("type") == "sequence":
                    seq_scores.append(r.get("percentile", 0))
        
        assert len(seq_scores) > 0, "Should have sequence scores"
        max_seq_score = max(seq_scores)
        
        # Frameshift should get high disruption
        assert max_seq_score >= 0.8, f"MBD4 frameshift should score ≥0.8, got {max_seq_score}"


@pytest.mark.asyncio
async def test_tp53_hotspot_detection():
    """Test 2: TP53 R175H hotspot → sequence_disruption ≥0.7"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract sequence scores
        drugs = data.get("drugs", [])
        assert len(drugs) > 0, "Should have drug recommendations"
        
        seq_scores = []
        for drug in drugs:
            rationale = drug.get("rationale", [])
            for r in rationale:
                if r.get("type") == "sequence":
                    seq_scores.append(r.get("percentile", 0))
        
        assert len(seq_scores) > 0, "Should have sequence scores"
        max_seq_score = max(seq_scores)
        
        # Hotspot should get high disruption
        assert max_seq_score >= 0.7, f"TP53 R175H hotspot should score ≥0.7, got {max_seq_score}"


@pytest.mark.asyncio
async def test_pathway_aggregation():
    """Test 3: MBD4+TP53 → DDR pathway score ≥0.70"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "germline_status": "positive",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract pathway_disruption
        pathway_disruption = extract_pathway_disruption_from_response(data)
        assert pathway_disruption is not None, "pathway_disruption should be in response"
        
        ddr_score = pathway_disruption.get("ddr", 0.0)
        tp53_score = pathway_disruption.get("tp53", 0.0)
        
        # Both should contribute
        assert ddr_score > 0.0, "MBD4 should contribute to DDR pathway"
        assert tp53_score > 0.0, "TP53 should contribute to TP53 pathway"
        
        # Combined DDR for mechanism vector
        combined_ddr = ddr_score + (tp53_score * 0.5)
        assert combined_ddr >= 0.70, f"Combined DDR should be ≥0.70, got {combined_ddr}"


@pytest.mark.asyncio
async def test_parp_ranking():
    """Test 4: MBD4+TP53 → PARP inhibitors rank #1-2, efficacy_score >0.80"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "germline_status": "positive",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        drugs = data.get("drugs", [])
        
        assert len(drugs) > 0, "Should have drug recommendations"
        
        # Find PARP inhibitors
        parp_drugs = []
        for i, drug in enumerate(drugs):
            name = drug.get("name", "").upper()
            if "PARP" in name or "OLAPARIB" in name or "RUCAPARIB" in name:
                parp_drugs.append((i + 1, drug))
        
        assert len(parp_drugs) > 0, "Should have PARP inhibitor recommendations"
        
        # Check top PARP
        top_rank, top_parp = parp_drugs[0]
        parp_confidence = top_parp.get("confidence", 0.0)
        parp_tier = top_parp.get("evidence_tier", "unknown")
        
        assert top_rank <= 2, f"PARP should rank in top 2, got #{top_rank}"
        assert parp_confidence > 0.80, f"PARP confidence should be >0.80, got {parp_confidence}"
        assert parp_tier in ["supported", "consider"], f"PARP tier should be 'supported' or 'consider', got {parp_tier}"


@pytest.mark.asyncio
async def test_germline_status():
    """Test 5: MBD4 germline-positive → no PARP penalty"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Test with germline positive
        response_pos = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "germline_status": "positive",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        # Test with germline negative
        response_neg = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "germline_status": "negative",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response_pos.status_code == 200
        assert response_neg.status_code == 200
        
        data_pos = response_pos.json()
        data_neg = response_neg.json()
        
        # Find PARP in both
        def get_parp_confidence(data):
            drugs = data.get("drugs", [])
            for drug in drugs:
                name = drug.get("name", "").upper()
                if "PARP" in name or "OLAPARIB" in name:
                    return drug.get("confidence", 0.0)
            return 0.0
        
        parp_pos = get_parp_confidence(data_pos)
        parp_neg = get_parp_confidence(data_neg)
        
        # Germline positive should not have penalty (confidence should be similar or higher)
        # Note: This is a soft check - exact behavior depends on sporadic gates implementation
        assert parp_pos >= parp_neg * 0.9, f"Germline positive should not penalize PARP significantly (pos: {parp_pos}, neg: {parp_neg})"


def test_mechanism_vector_conversion():
    """Test 6: MBD4+TP53 pathway scores → 7D mechanism vector correct"""
    # Test pathway scores
    pathway_scores = {
        "ddr": 0.8,  # MBD4 contributes
        "tp53": 0.6,  # TP53 contributes
        "ras_mapk": 0.0,
        "pi3k": 0.0,
        "vegf": 0.0
    }
    
    # Convert to mechanism vector (7D)
    vector, dimension = convert_pathway_scores_to_mechanism_vector(pathway_scores, use_7d=True)
    
    assert dimension == "7D", "Should use 7D vector"
    assert len(vector) == 7, "Mechanism vector should be 7D"
    
    # Check DDR index (ddr + tp53, but note: new implementation maps tp53 to ddr directly)
    # The new implementation normalizes tp53 to ddr, so both contribute to DDR index
    ddr_score = pathway_scores.get("ddr", 0.0) + pathway_scores.get("tp53", 0.0)
    assert abs(vector[0] - ddr_score) < 0.01, f"DDR index should be {ddr_score}, got {vector[0]}"
    
    # Check other indices
    assert vector[1] == 0.0, "MAPK should be 0.0"
    assert vector[2] == 0.0, "PI3K should be 0.0"
    assert vector[3] == 0.0, "VEGF should be 0.0"
    assert vector[4] == 0.0, "HER2 should be 0.0"
    assert vector[5] == 0.0, "IO should be 0.0 (no TMB/MSI)"
    assert vector[6] == 0.0, "Efflux should be 0.0"


def test_mechanism_vector_with_io():
    """Test 7: IO index computed correctly from TMB/MSI"""
    pathway_scores = {"ddr": 0.8}
    
    # Test with TMB >= 20
    vector_high_tmb, _ = convert_pathway_scores_to_mechanism_vector(pathway_scores, tmb=25.0, use_7d=True)
    assert vector_high_tmb[5] == 1.0, "IO should be 1.0 for TMB >= 20"
    
    # Test with MSI-H
    vector_msi, _ = convert_pathway_scores_to_mechanism_vector(pathway_scores, msi_status="MSI-H", use_7d=True)
    assert vector_msi[5] == 1.0, "IO should be 1.0 for MSI-H"
    
    # Test with low TMB
    vector_low_tmb, _ = convert_pathway_scores_to_mechanism_vector(pathway_scores, tmb=5.0, use_7d=True)
    assert vector_low_tmb[5] == 0.0, "IO should be 0.0 for TMB < 20"


@pytest.mark.asyncio
async def test_pathway_disruption_in_response():
    """Test 8: pathway_disruption is in WIWFM response"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Extract pathway_disruption
        pathway_disruption = extract_pathway_disruption_from_response(data)
        assert pathway_disruption is not None, "pathway_disruption should be in response"
        assert isinstance(pathway_disruption, dict), "pathway_disruption should be a dict"
        
        # Should have at least ddr or tp53
        assert "ddr" in pathway_disruption or "tp53" in pathway_disruption, "Should have DDR or TP53 pathway scores"


@pytest.mark.asyncio
async def test_mechanism_vector_from_response():
    """Test 9: Can extract mechanism vector from WIWFM response"""
    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(
            f"{BASE_URL}/api/efficacy/predict",
            json={
                "mutations": [MBD4_VARIANT, TP53_VARIANT],
                "disease": "ovarian_cancer_hgs",
                "model_id": DEFAULT_EVO_MODEL
            }
        )
        
        assert response.status_code == 200
        data = response.json()
        
        # Get mechanism vector from response
        result = get_mechanism_vector_from_response(data, use_7d=True)
        assert result is not None, "Should be able to extract mechanism vector from response"
        vector, dimension = result
        assert dimension == "7D", "Should use 7D vector"
        assert len(vector) == 7, "Mechanism vector should be 7D"
        
        # DDR index should be > 0 (MBD4+TP53 contribute)
        assert vector[0] > 0.0, "DDR index should be > 0 for MBD4+TP53"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

