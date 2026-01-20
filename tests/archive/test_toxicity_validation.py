"""
Quick validation tests for Toxicity System
- Test pathway mappings
- Test safety service
- Understand actual data flow
"""

import sys
import json
from pathlib import Path

# Add the backend to path
sys.path.insert(0, str(Path(__file__).parent))

print("=" * 60)
print("TOXICITY SYSTEM VALIDATION TESTS")
print("=" * 60)

# ============================================================================
# TEST 1: Import and inspect toxicity_pathway_mappings
# ============================================================================
print("\n[TEST 1] Toxicity Pathway Mappings")
print("-" * 40)

try:
    from api.services.toxicity_pathway_mappings import (
        DNA_REPAIR_GENES,
        INFLAMMATION_GENES,
        CARDIOMETABOLIC_GENES,
        PHARMACOGENES,
        MOA_TO_TOXIC_PATHWAYS,
        compute_pathway_overlap,
        is_pharmacogene,
        get_pharmacogene_risk_weight,
        get_moa_toxicity_weights
    )
    
    print(f"✅ DNA_REPAIR_GENES: {len(DNA_REPAIR_GENES)} genes")
    print(f"   Sample: {list(DNA_REPAIR_GENES)[:5]}")
    
    print(f"✅ INFLAMMATION_GENES: {len(INFLAMMATION_GENES)} genes")
    print(f"   Sample: {list(INFLAMMATION_GENES)[:5]}")
    
    print(f"✅ CARDIOMETABOLIC_GENES: {len(CARDIOMETABOLIC_GENES)} genes")
    print(f"   Sample: {list(CARDIOMETABOLIC_GENES)[:5]}")
    
    print(f"✅ PHARMACOGENES: {len(PHARMACOGENES)} genes")
    print(f"   Sample: {list(PHARMACOGENES)[:5]}")
    
    print(f"\n✅ MOA_TO_TOXIC_PATHWAYS: {len(MOA_TO_TOXIC_PATHWAYS)} MoA patterns")
    for moa, weights in MOA_TO_TOXIC_PATHWAYS.items():
        print(f"   {moa}: {weights}")

except Exception as e:
    print(f"❌ Failed to import toxicity_pathway_mappings: {e}")

# ============================================================================
# TEST 2: Test pharmacogene detection
# ============================================================================
print("\n[TEST 2] Pharmacogene Detection")
print("-" * 40)

try:
    test_genes = ["DPYD", "TPMT", "CYP2D6", "UGT1A1", "BRCA1", "TP53", "RANDOM_GENE"]
    
    for gene in test_genes:
        is_pgx = is_pharmacogene(gene)
        weight = get_pharmacogene_risk_weight(gene)
        print(f"   {gene}: is_pharmacogene={is_pgx}, risk_weight={weight}")

except Exception as e:
    print(f"❌ Pharmacogene test failed: {e}")

# ============================================================================
# TEST 3: Test MoA → Toxicity Weights
# ============================================================================
print("\n[TEST 3] MoA → Toxicity Weights")
print("-" * 40)

try:
    test_moas = ["platinum_agent", "anthracycline", "PARP_inhibitor", "checkpoint_inhibitor", "unknown_drug"]
    
    for moa in test_moas:
        weights = get_moa_toxicity_weights(moa)
        print(f"   {moa}: {weights}")

except Exception as e:
    print(f"❌ MoA weights test failed: {e}")

# ============================================================================
# TEST 4: Test compute_pathway_overlap (THE KEY FUNCTION)
# ============================================================================
print("\n[TEST 4] Compute Pathway Overlap")
print("-" * 40)

try:
    # Scenario: Patient with BRCA1 variant on platinum
    patient_genes_1 = ["BRCA1"]
    moa_1 = "platinum_agent"
    overlap_1 = compute_pathway_overlap(patient_genes_1, moa_1)
    print(f"   Scenario 1: BRCA1 + platinum_agent")
    print(f"   Overlap: {overlap_1}")
    
    # Scenario: Patient with DPYD variant on 5-FU (need to check if 5-FU MoA exists)
    patient_genes_2 = ["DPYD", "TPMT"]
    moa_2 = "alkylating_agent"
    overlap_2 = compute_pathway_overlap(patient_genes_2, moa_2)
    print(f"\n   Scenario 2: DPYD + TPMT + alkylating_agent")
    print(f"   Overlap: {overlap_2}")
    
    # Scenario: Patient with inflammation genes on checkpoint inhibitor
    patient_genes_3 = ["TNF", "IL6", "NFKB1"]
    moa_3 = "checkpoint_inhibitor"
    overlap_3 = compute_pathway_overlap(patient_genes_3, moa_3)
    print(f"\n   Scenario 3: TNF + IL6 + NFKB1 + checkpoint_inhibitor")
    print(f"   Overlap: {overlap_3}")

except Exception as e:
    print(f"❌ Pathway overlap test failed: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 5: Test Safety Service (if available)
# ============================================================================
print("\n[TEST 5] Safety Service")
print("-" * 40)

try:
    from api.services.safety_service import SafetyService, get_safety_service
    from api.schemas.safety import (
        ToxicityRiskRequest, 
        PatientContext, 
        GermlineVariant,
        TherapeuticCandidate,
        ClinicalContext
    )
    
    print("✅ Safety service imports successful")
    
    # Create a test request
    test_request = ToxicityRiskRequest(
        patient=PatientContext(
            germlineVariants=[
                GermlineVariant(chrom="17", pos=41276045, ref="A", alt="G", gene="BRCA1", hgvs_p="V600E"),
                GermlineVariant(chrom="1", pos=97915614, ref="C", alt="T", gene="DPYD", hgvs_p="D949V")
            ]
        ),
        candidate=TherapeuticCandidate(
            type="drug",
            moa="platinum_agent"
        ),
        context=ClinicalContext(
            disease="ovarian_cancer",
            tissue="ovary"
        ),
        options={"evidence": True, "profile": "baseline"}
    )
    
    print(f"   Test request created:")
    print(f"   - Germline variants: BRCA1, DPYD")
    print(f"   - Drug MoA: platinum_agent")
    print(f"   - Disease: ovarian_cancer")
    
    # We can't run async here easily, so just verify the structure
    service = get_safety_service()
    print(f"✅ Safety service instance: {type(service)}")
    print(f"   Has compute_toxicity_risk: {hasattr(service, 'compute_toxicity_risk')}")
    print(f"   Has preview_off_targets: {hasattr(service, 'preview_off_targets')}")

except Exception as e:
    print(f"❌ Safety service test failed: {e}")
    import traceback
    traceback.print_exc()

# ============================================================================
# TEST 6: Check what's actually in ToxicityRiskResponse
# ============================================================================
print("\n[TEST 6] ToxicityRiskResponse Schema")
print("-" * 40)

try:
    from api.schemas.safety import ToxicityRiskResponse, ToxicityFactor
    
    # Inspect the fields
    print("   ToxicityRiskResponse fields:")
    for field_name, field_info in ToxicityRiskResponse.model_fields.items():
        print(f"   - {field_name}: {field_info.annotation}")
    
    print("\n   ToxicityFactor fields:")
    for field_name, field_info in ToxicityFactor.model_fields.items():
        print(f"   - {field_name}: {field_info.annotation}")
    
    # Check if mitigating_foods exists
    if "mitigating_foods" in ToxicityRiskResponse.model_fields:
        print("\n   ✅ mitigating_foods field EXISTS")
    else:
        print("\n   ❌ mitigating_foods field DOES NOT EXIST (needs to be added)")

except Exception as e:
    print(f"❌ Schema inspection failed: {e}")

# ============================================================================
# TEST 7: Check PharmGKB router
# ============================================================================
print("\n[TEST 7] PharmGKB Metabolizer Status")
print("-" * 40)

try:
    from api.routers.pharmgkb import (
        CYP2D6_PHENOTYPES,
        CYP2C19_PHENOTYPES,
        DRUG_GENE_INTERACTIONS,
        get_metabolizer_status
    )
    
    print(f"   CYP2D6 diplotypes: {len(CYP2D6_PHENOTYPES)}")
    for diplotype, info in list(CYP2D6_PHENOTYPES.items())[:3]:
        print(f"     {diplotype}: {info}")
    
    print(f"\n   CYP2C19 diplotypes: {len(CYP2C19_PHENOTYPES)}")
    
    print(f"\n   Drug-Gene Interactions: {len(DRUG_GENE_INTERACTIONS)}")
    for key, info in DRUG_GENE_INTERACTIONS.items():
        print(f"     {key}: {info['type']} - {info['significance']}")
    
    # Test metabolizer status
    status_1 = get_metabolizer_status("CYP2D6", "*4/*4")
    print(f"\n   CYP2D6 *4/*4: {status_1}")
    
    status_2 = get_metabolizer_status("CYP2D6", "*1/*1")
    print(f"   CYP2D6 *1/*1: {status_2}")

except Exception as e:
    print(f"❌ PharmGKB test failed: {e}")

# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "=" * 60)
print("SUMMARY: What I Actually Learned")
print("=" * 60)

print("""
1. TOXICITY PATHWAY MAPPINGS:
   - 5 gene sets (DNA repair, inflammation, cardiometabolic, pharmacogenes, + MMR in DNA repair)
   - 11 MoA → pathway weights (confirmed)
   - compute_pathway_overlap() works by:
     a) Get MoA weights (e.g., platinum_agent → {dna_repair: 0.9, ...})
     b) For each pathway, count overlap between patient genes and pathway genes
     c) Return weighted overlap scores

2. PHARMACOGENE DETECTION:
   - is_pharmacogene() checks against static list
   - get_pharmacogene_risk_weight() returns 0.2-0.4 based on gene impact
   - High impact: DPYD, TPMT, UGT1A1, G6PD, NUDT15, HLA-B (0.4)
   - CYP enzymes: 0.3
   - Others: 0.2

3. SAFETY SERVICE:
   - Combines pharmacogene risk + pathway overlap + tissue context
   - Returns: risk_score, confidence, reason, factors, evidence, provenance
   - ❌ Does NOT currently return mitigating_foods

4. PHARMGKB:
   - Metabolizer status prediction (CYP2D6, CYP2C19)
   - Drug-gene interactions (tamoxifen+CYP2D6, clopidogrel+CYP2C19, warfarin+CYP2C9/VKORC1)
   - Dose adjustment recommendations

5. WHAT'S MISSING FOR MOAT:
   - No get_mitigating_foods() function
   - No mitigating_foods field in ToxicityRiskResponse
   - No connection between toxicity and food validation
""")

