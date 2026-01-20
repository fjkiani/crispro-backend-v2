import asyncio
import types
import pytest

from api.services.efficacy_orchestrator import create_efficacy_orchestrator, EfficacyRequest
from api.services.efficacy_orchestrator.models import DrugScoreResult


class FakeSeqScore:
    def __init__(self):
        self.variant = {"gene": "BRAF"}
        self.scoring_mode = "evo2"
        self.scoring_strategy = {"source": "test", "models_tested": [], "windows_tested": []}
        self.calibrated_seq_percentile = 0.6
        self.sequence_disruption = 0.00008


@pytest.mark.asyncio
async def test_ablation_mode_s_only(monkeypatch):
    orch = create_efficacy_orchestrator()

    async def fake_score_sequences(request, feature_flags):
        return [FakeSeqScore()]

    async def fake_score_drug(drug, seq_scores, pathway_scores, evidence_result, clinvar_result, insights, cfg, disease, include_fda_badges=False):
        return DrugScoreResult(
            name=drug["name"],
            moa=drug["moa"],
            efficacy_score=0.2,
            confidence=0.5,
            evidence_tier="insufficient",
            badges=[],
            evidence_strength=0.0,
            citations=[],
            citations_count=0,
            clinvar={"classification": None, "review_status": None, "prior": 0.0},
            evidence_manifest={},
            insights={"functionality": 0.6, "chromatin": 0.6, "essentiality": 0.35, "regulatory": 0.1},
            rationale=[],
            meets_evidence_gate=False,
            insufficient_signal=True,
        )

    monkeypatch.setattr(orch.sequence_processor, "score_sequences", fake_score_sequences)
    monkeypatch.setattr(orch.drug_scorer, "score_drug", fake_score_drug)

    req = EfficacyRequest(
        mutations=[{"gene": "BRAF", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A"}],
        options={"adaptive": False, "ensemble": False, "include_fda_badges": False},
        ablation_mode="S_only",
        include_calibration_snapshot=False,
    )

    resp = await orch.predict(req)
    assert resp.scoring_strategy.get("ablation_mode") == "S_ONLY"
    assert isinstance(resp.drugs, list)


@pytest.mark.asyncio
async def test_calibration_snapshot_included(monkeypatch):
    orch = create_efficacy_orchestrator()

    async def fake_score_sequences(request, feature_flags):
        return [FakeSeqScore()]

    async def fake_score_drug(drug, seq_scores, pathway_scores, evidence_result, clinvar_result, insights, cfg, disease, include_fda_badges=False):
        return DrugScoreResult(
            name=drug["name"],
            moa=drug["moa"],
            efficacy_score=0.2,
            confidence=0.5,
            evidence_tier="insufficient",
            badges=[],
            evidence_strength=0.0,
            citations=[],
            citations_count=0,
            clinvar={"classification": None, "review_status": None, "prior": 0.0},
            evidence_manifest={},
            insights={"functionality": 0.6, "chromatin": 0.6, "essentiality": 0.35, "regulatory": 0.1},
            rationale=[],
            meets_evidence_gate=False,
            insufficient_signal=True,
        )

    monkeypatch.setattr(orch.sequence_processor, "score_sequences", fake_score_sequences)
    monkeypatch.setattr(orch.drug_scorer, "score_drug", fake_score_drug)

    req = EfficacyRequest(
        mutations=[{"gene": "BRAF", "chrom": "7", "pos": 140453136, "ref": "T", "alt": "A"}],
        options={"adaptive": False, "ensemble": False},
        ablation_mode="SPE",
        include_calibration_snapshot=True,
    )

    resp = await orch.predict(req)
    assert resp.calibration_snapshot is not None
    assert "sequence_calibration" in resp.calibration_snapshot
    assert "pathway_calibration" in resp.calibration_snapshot

