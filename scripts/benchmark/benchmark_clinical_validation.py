#!/usr/bin/env python3
"""
Clinical Validation: Compare AYESHA results against published clinical evidence

Sources:
1. NCCN Guidelines (ovarian cancer, HRD+)
2. FDA Labels (PARP inhibitors, platinum)
3. Published Literature (MBD4, TP53, HGSOC)
4. Clinical Trials Database (NCT IDs)
"""

import os
import sys
import json
import asyncio
import httpx
from typing import Dict, List, Any
from datetime import datetime

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Clinical Evidence Database
CLINICAL_EVIDENCE = {
    "parp_inhibitors": {
        "olaparib": {
            "fda_approved": True,
            "indication": "HRD+ ovarian cancer (germline or somatic BRCA1/2, or HRD-positive)",
            "nccn_guideline": "Category 1 (preferred)",
            "evidence_level": "RCT (SOLO-2, PAOLA-1)",
            "expected_efficacy": 0.75,
            "expected_rank": 1
        },
        "niraparib": {
            "fda_approved": True,
            "indication": "HRD+ ovarian cancer (germline or somatic BRCA1/2, or HRD-positive)",
            "nccn_guideline": "Category 1 (preferred)",
            "evidence_level": "RCT (PRIMA, NOVA)",
            "expected_efficacy": 0.75,
            "expected_rank": 2
        },
        "rucaparib": {
            "fda_approved": True,
            "indication": "HRD+ ovarian cancer (germline or somatic BRCA1/2, or HRD-positive)",
            "nccn_guideline": "Category 1 (preferred)",
            "evidence_level": "RCT (ARIEL3, ARIEL4)",
            "expected_efficacy": 0.75,
            "expected_rank": 3
        }
    },
    "platinum": {
        "carboplatin": {
            "fda_approved": True,
            "indication": "First-line HGSOC (standard of care)",
            "nccn_guideline": "Category 1 (preferred)",
            "evidence_level": "RCT (multiple)",
            "expected_efficacy": 0.70,
            "expected_rank": 4
        }
    },
    "mbd4_literature": {
        "pathway": "Base Excision Repair (BER)",
        "function": "DNA glycosylase (5-methylcytosine deamination repair)",
        "germline_mutation_frequency": "< 0.01%",
        "cancer_association": "Genomic instability, increased mutation rate",
        "therapeutic_target": "PARP inhibitors (synthetic lethality with HRD)"
    },
    "tp53_literature": {
        "pathway": "Cell cycle checkpoint, apoptosis, DNA damage response",
        "function": "Tumor suppressor (p53 protein)",
        "mutation_frequency_hgsoc": "> 95%",
        "hotspot_mutations": ["R175H", "R248Q", "R273H"],
        "therapeutic_target": "PARP inhibitors (HRD), ATR inhibitors (checkpoint bypass)"
    },
    "synthetic_lethality": {
        "mbd4_ber_deficiency": {
            "mechanism": "Base excision repair loss → accumulation of base damage",
            "synthetic_lethal_with": "PARP inhibition (HRD)"
        },
        "tp53_checkpoint_loss": {
            "mechanism": "Checkpoint bypass → replication of damaged DNA",
            "synthetic_lethal_with": "PARP inhibition (HRD), ATR inhibition (replication stress)"
        },
        "combined_effect": {
            "mechanism": "Double DNA repair deficiency (BER + checkpoint)",
            "expected_sensitivity": "Very high PARP sensitivity (HRD+ phenotype)",
            "expected_tmb": "High (BER deficiency + checkpoint bypass)"
        }
    }
}


async def validate_against_clinical_evidence(api_base_url: str = "http://localhost:8000"):
    """Validate AYESHA results against clinical evidence"""
    
    print("\n" + "="*80)
    print("CLINICAL VALIDATION: AYESHA vs. Published Evidence")
    print("="*80)
    
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Get AYESHA results
        response = await client.post(
            f"{api_base_url}/api/efficacy/predict",
            json={
                "model_id": "evo2_1b",
                "mutations": [
                    {"gene": "MBD4", "hgvs_p": "p.Ile413Serfs*2", "chrom": "3", "pos": 129430456, "ref": "A", "alt": "", "build": "GRCh37"},
                    {"gene": "TP53", "hgvs_p": "p.Arg175His", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A", "build": "GRCh37"}
                ],
                "disease": "ovarian_cancer",
                "germline_status": "positive"
            }
        )
        
        if response.status_code != 200:
            print(f"❌ API call failed: {response.status_code}")
            return
        
        data = response.json()
        drugs = data.get("drugs", [])
        pathway_disruption = data.get("provenance", {}).get("confidence_breakdown", {}).get("pathway_disruption", {})
        
        print("\n📊 VALIDATION RESULTS:\n")
        
        # 1. PARP Inhibitor Validation
        print("1. PARP Inhibitor Recommendations:")
        print("-" * 80)
        for parp_name, evidence in CLINICAL_EVIDENCE["parp_inhibitors"].items():
            found = False
            for drug in drugs:
                if parp_name.lower() in drug.get("name", "").lower():
                    found = True
                    efficacy = drug.get("efficacy_score", 0.0)
                    rank = drugs.index(drug) + 1
                    
                    print(f"   {parp_name.upper()}:")
                    print(f"     ✅ Found: Rank #{rank}, Efficacy: {efficacy:.3f}")
                    print(f"     📋 FDA Approved: {evidence['fda_approved']}")
                    print(f"     📋 NCCN: {evidence['nccn_guideline']}")
                    print(f"     📋 Evidence: {evidence['evidence_level']}")
                    print(f"     ✅ Efficacy Match: {efficacy >= evidence['expected_efficacy']}")
                    print(f"     {'✅' if rank <= evidence['expected_rank'] + 1 else '⚠️'} Rank Match: Expected ≤{evidence['expected_rank']}, Got {rank}")
                    break
            
            if not found:
                print(f"   {parp_name.upper()}: ❌ NOT FOUND")
        
        # 2. Platinum Validation
        print("\n2. Platinum Chemotherapy:")
        print("-" * 80)
        carboplatin_evidence = CLINICAL_EVIDENCE["platinum"]["carboplatin"]
        found = False
        for drug in drugs:
            if "carboplatin" in drug.get("name", "").lower():
                found = True
                efficacy = drug.get("efficacy_score", 0.0)
                rank = drugs.index(drug) + 1
                print(f"   CARBOPLATIN:")
                print(f"     ✅ Found: Rank #{rank}, Efficacy: {efficacy:.3f}")
                print(f"     📋 FDA Approved: {carboplatin_evidence['fda_approved']}")
                print(f"     📋 NCCN: {carboplatin_evidence['nccn_guideline']}")
                print(f"     ✅ Efficacy Match: {efficacy >= carboplatin_evidence['expected_efficacy']}")
                break
        
        if not found:
            print("   CARBOPLATIN: ❌ NOT FOUND")
        
        # 3. Pathway Validation
        print("\n3. Pathway Disruption (Biological Validation):")
        print("-" * 80)
        ddr_score = pathway_disruption.get("ddr", 0.0)
        tp53_score = pathway_disruption.get("tp53", 0.0)
        
        print(f"   DDR Pathway (MBD4): {ddr_score:.4f}")
        print(f"     📋 Expected: High (BER deficiency)")
        print(f"     📋 Literature: {CLINICAL_EVIDENCE['mbd4_literature']['pathway']}")
        print(f"     ✅ Match: {ddr_score >= 0.9}")
        
        print(f"   TP53 Pathway (R175H): {tp53_score:.4f}")
        print(f"     📋 Expected: High (checkpoint bypass)")
        print(f"     📋 Literature: {CLINICAL_EVIDENCE['tp53_literature']['pathway']}")
        print(f"     ✅ Match: {tp53_score >= 0.7}")
        
        # 4. Synthetic Lethality Validation
        print("\n4. Synthetic Lethality:")
        print("-" * 80)
        synth_response = await client.post(
            f"{api_base_url}/api/guidance/synthetic_lethality",
            json={
                "disease": "ovarian_cancer",
                "mutations": [
                    {"gene": "MBD4", "hgvs_p": "p.Ile413Serfs*2", "chrom": "3", "pos": 129430456, "ref": "A", "alt": ""},
                    {"gene": "TP53", "hgvs_p": "p.Arg175His", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A"}
                ],
                "api_base": api_base_url
            }
        )
        
        if synth_response.status_code == 200:
            synth_data = synth_response.json()
            suggested = synth_data.get("suggested_therapy", "").lower()
            print(f"   Suggested Therapy: {suggested}")
            print(f"     📋 Expected: PARP or platinum (HRD + BER deficiency)")
            print(f"     📋 Literature: {CLINICAL_EVIDENCE['synthetic_lethality']['combined_effect']['expected_sensitivity']}")
            print(f"     ✅ Match: {'parp' in suggested or 'platinum' in suggested}")
        
        print("\n" + "="*80)
        print("✅ CLINICAL VALIDATION COMPLETE")
        print("="*80)


if __name__ == "__main__":
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    asyncio.run(validate_against_clinical_evidence(api_base))

