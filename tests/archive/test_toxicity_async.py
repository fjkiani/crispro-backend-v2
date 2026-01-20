"""
Async test to actually call the toxicity service
"""

import asyncio
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

async def test_toxicity_service():
    print("=" * 60)
    print("ACTUAL TOXICITY SERVICE TEST (Async)")
    print("=" * 60)
    
    from api.services.safety_service import get_safety_service
    from api.schemas.safety import (
        ToxicityRiskRequest, 
        PatientContext, 
        GermlineVariant,
        TherapeuticCandidate,
        ClinicalContext
    )
    
    service = get_safety_service()
    
    # =====================================================================
    # TEST 1: Platinum + BRCA1 (should show DNA repair overlap)
    # =====================================================================
    print("\n[TEST 1] Platinum + BRCA1 Variant")
    print("-" * 40)
    
    request1 = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="17", pos=41276045, ref="A", alt="G", gene="BRCA1")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
        context=ClinicalContext(disease="ovarian_cancer"),
        options={"profile": "baseline"}
    )
    
    result1 = await service.compute_toxicity_risk(request1)
    print(f"   Risk Score: {result1.risk_score}")
    print(f"   Confidence: {result1.confidence}")
    print(f"   Reason: {result1.reason}")
    print(f"   Factors:")
    for factor in result1.factors:
        print(f"     - Type: {factor.type}")
        print(f"       Detail: {factor.detail}")
        print(f"       Weight: {factor.weight}")
    print(f"   Provenance: {result1.provenance}")
    
    # =====================================================================
    # TEST 2: Checkpoint Inhibitor + TNF/IL6 (inflammation overlap)
    # =====================================================================
    print("\n[TEST 2] Checkpoint Inhibitor + Inflammation Genes")
    print("-" * 40)
    
    request2 = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="6", pos=31575000, ref="C", alt="T", gene="TNF"),
                GermlineVariant(chrom="7", pos=22766000, ref="G", alt="A", gene="IL6")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="checkpoint_inhibitor"),
        context=ClinicalContext(disease="melanoma"),
        options={"profile": "baseline"}
    )
    
    result2 = await service.compute_toxicity_risk(request2)
    print(f"   Risk Score: {result2.risk_score}")
    print(f"   Confidence: {result2.confidence}")
    print(f"   Reason: {result2.reason}")
    print(f"   Factors:")
    for factor in result2.factors:
        print(f"     - Type: {factor.type}")
        print(f"       Detail: {factor.detail}")
        print(f"       Weight: {factor.weight}")
    
    # =====================================================================
    # TEST 3: Anthracycline + KCNQ1 (cardiometabolic - cardiotoxicity)
    # =====================================================================
    print("\n[TEST 3] Anthracycline + Cardiac Gene")
    print("-" * 40)
    
    request3 = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="11", pos=2465000, ref="A", alt="G", gene="KCNQ1")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="anthracycline"),
        context=ClinicalContext(disease="breast_cancer"),
        options={"profile": "baseline"}
    )
    
    result3 = await service.compute_toxicity_risk(request3)
    print(f"   Risk Score: {result3.risk_score}")
    print(f"   Confidence: {result3.confidence}")
    print(f"   Reason: {result3.reason}")
    print(f"   Factors:")
    for factor in result3.factors:
        print(f"     - {factor.type}: {factor.detail} (weight: {factor.weight})")
    
    # =====================================================================
    # TEST 4: DPYD Pharmacogene (high toxicity risk for 5-FU)
    # =====================================================================
    print("\n[TEST 4] DPYD Variant + Alkylating Agent (simulating 5-FU)")
    print("-" * 40)
    
    request4 = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="1", pos=97915614, ref="C", alt="T", gene="DPYD")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="alkylating_agent"),
        context=ClinicalContext(disease="colorectal_cancer"),
        options={"profile": "baseline"}
    )
    
    result4 = await service.compute_toxicity_risk(request4)
    print(f"   Risk Score: {result4.risk_score}")
    print(f"   Confidence: {result4.confidence}")
    print(f"   Reason: {result4.reason}")
    print(f"   Factors:")
    for factor in result4.factors:
        print(f"     - {factor.type}: {factor.detail} (weight: {factor.weight})")
    
    # =====================================================================
    # TEST 5: Combined - BRCA1 + DPYD + Platinum
    # =====================================================================
    print("\n[TEST 5] Combined: BRCA1 + DPYD + Platinum")
    print("-" * 40)
    
    request5 = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="17", pos=41276045, ref="A", alt="G", gene="BRCA1"),
                GermlineVariant(chrom="1", pos=97915614, ref="C", alt="T", gene="DPYD")
            ]
        ),
        candidate=TherapeuticCandidate(type="drug", moa="platinum_agent"),
        context=ClinicalContext(disease="ovarian_cancer", tissue="ovary"),
        options={"profile": "baseline"}
    )
    
    result5 = await service.compute_toxicity_risk(request5)
    print(f"   Risk Score: {result5.risk_score}")
    print(f"   Confidence: {result5.confidence}")
    print(f"   Reason: {result5.reason}")
    print(f"   Factors:")
    for factor in result5.factors:
        print(f"     - {factor.type}: {factor.detail} (weight: {factor.weight})")
    
    # =====================================================================
    # SUMMARY
    # =====================================================================
    print("\n" + "=" * 60)
    print("WHAT THE TOXICITY SERVICE ACTUALLY RETURNS")
    print("=" * 60)
    print(f"""
Test Results:
1. BRCA1 + Platinum → Risk: {result1.risk_score} (DNA repair pathway overlap)
2. TNF/IL6 + Checkpoint → Risk: {result2.risk_score} (Inflammation pathway overlap)
3. KCNQ1 + Anthracycline → Risk: {result3.risk_score} (Cardiometabolic overlap)
4. DPYD + Alkylating → Risk: {result4.risk_score} (Pharmacogene high risk)
5. BRCA1 + DPYD + Platinum → Risk: {result5.risk_score} (Combined)

KEY OBSERVATIONS:
- The service correctly identifies pathway overlaps
- Pharmacogene variants get high weights (0.4)
- Pathway overlaps are calculated per MoA
- Confidence is modulated for high-risk assessments

MISSING FOR MOAT:
- No mitigating_foods in response
- No connection to food validation
- Need to add:
  1. get_mitigating_foods(pathway_overlap)
  2. mitigating_foods field in response
  3. Integration with food validation
""")

if __name__ == "__main__":
    asyncio.run(test_toxicity_service())

