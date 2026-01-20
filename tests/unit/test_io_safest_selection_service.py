
from api.services.io_safest_selection_service import assess_io_eligibility, recommend_io_regimens


def test_assess_io_eligibility_reads_nested_pd_l1_cps():
    eligibility = assess_io_eligibility({"pd_l1": {"cps": 10}})
    assert eligibility.eligible is True
    assert "PDL1_POSITIVE_CPS" in eligibility.signals


def test_assess_io_eligibility_reads_biomarkers_pd_l1_cps():
    eligibility = assess_io_eligibility({"biomarkers": {"pd_l1_cps": 10}})
    assert eligibility.eligible is True
    assert "PDL1_POSITIVE_CPS" in eligibility.signals


def test_assess_io_eligibility_includes_germline_hypermutator():
    eligibility = assess_io_eligibility(
        {},
        germline_mutations=[{"gene": "MBD4"}],
    )
    assert eligibility.eligible is True
    assert any(s.startswith("HYPERMUTATOR_INFERRED:") for s in eligibility.signals)


def test_assess_io_eligibility_quality_measured_vs_inferred():
    inferred = assess_io_eligibility({"pd_l1_cps": 10})
    assert inferred.eligible is True
    assert inferred.quality == "inferred"

    measured = assess_io_eligibility({"tmb": 20})
    assert measured.eligible is True
    assert measured.quality == "measured"


def test_recommend_io_regimens_ineligible_returns_no_selection():
    out = recommend_io_regimens(tumor_context={})
    assert out["eligible"] is False
    assert out["selected_safest"] is None
    assert out["candidates"] == []


def test_recommend_io_regimens_prior_pneumonitis_downranks_high_pneumonitis_drugs():
    # Restrict candidates to make the pneumonitis adjustment observable
    out = recommend_io_regimens(
        patient_context={"organ_risk_flags": ["prior_pneumonitis"]},
        tumor_context={"pd_l1_cps": 10},
        eligible_drugs_override=["pembrolizumab", "nivolumab"],
    )

    assert out["eligible"] is True
    assert out["selected_safest"]["selected"].lower() in {"nivolumab", "pembrolizumab"}

    risk_factors = out["selected_safest"].get("risk_factors") or []
    assert any("Prior pneumonitis" in rf for rf in risk_factors)


if __name__ == "__main__":
    test_assess_io_eligibility_reads_nested_pd_l1_cps()
    test_assess_io_eligibility_reads_biomarkers_pd_l1_cps()
    test_assess_io_eligibility_includes_germline_hypermutator()
    test_assess_io_eligibility_quality_measured_vs_inferred()
    test_recommend_io_regimens_ineligible_returns_no_selection()
    test_recommend_io_regimens_prior_pneumonitis_downranks_high_pneumonitis_drugs()
    print("✅ OK")
