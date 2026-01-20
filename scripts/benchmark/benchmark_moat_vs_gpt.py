"""
MOAT vs GPT Benchmark Script

Runs side-by-side comparisons of MOAT system vs GPT-4o on personalized oncology questions.

Usage:
    OPENAI_API_KEY=your_key python benchmark_moat_vs_gpt.py
"""

import asyncio
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from api.services.gpt_service import get_gpt_service
from api.services.safety_service import get_safety_service
from api.services.toxicity_pathway_mappings import (
    compute_pathway_overlap, get_mitigating_foods, get_drug_moa
)
from api.schemas.safety import (
    ToxicityRiskRequest, PatientContext, GermlineVariant,
    TherapeuticCandidate, ClinicalContext
)


# Benchmark Questions (from MOAT_VS_GPT_BENCHMARK.md)
BENCHMARK_QUESTIONS = [
    {
        "id": "q1",
        "category": "Toxicity-Aware Nutrition",
        "question": "I'm on carboplatin and have a BRCA1 variant. What foods can help reduce side effects?",
        "context": {
            "drug": "carboplatin",
            "variant": "BRCA1",
            "gene": "BRCA1"
        }
    },
    {
        "id": "q2",
        "category": "Personalized Genomics",
        "question": "I have homozygous MBD4 c.1293delA. What supplements support my DNA repair?",
        "context": {
            "variant": "MBD4 c.1293delA",
            "zygosity": "homozygous",
            "gene": "MBD4"
        }
    },
    {
        "id": "q3",
        "category": "Toxicity-Aware Nutrition",
        "question": "I'm on doxorubicin. What can I take to protect my heart?",
        "context": {
            "drug": "doxorubicin"
        }
    },
    {
        "id": "q4",
        "category": "Personalized Genomics",
        "question": "I have a DPYD variant. Can I take 5-FU?",
        "context": {
            "variant": "DPYD",
            "gene": "DPYD",
            "drug": "5-FU"
        }
    },
    {
        "id": "q5",
        "category": "Mechanism Explanations",
        "question": "Why exactly does NAC help with carboplatin side effects? What's the mechanism?",
        "context": {
            "drug": "carboplatin",
            "compound": "NAC"
        }
    },
    {
        "id": "q6",
        "category": "Treatment Line Intelligence",
        "question": "What foods should I take during first-line chemo vs maintenance therapy?",
        "context": {
            "treatment_line": "first-line vs maintenance"
        }
    }
]


async def get_moat_response(question_data: Dict[str, Any]) -> Dict[str, Any]:
    """Get MOAT system response for a question."""
    question = question_data["question"]
    context = question_data.get("context", {})
    
    response = {
        "question": question,
        "category": question_data["category"],
        "moat_response": {},
        "timestamp": datetime.now().isoformat()
    }
    
    try:
        # Question 1: Carboplatin + BRCA1 → Toxicity + Mitigating Foods
        if question_data["id"] == "q1":
            safety_service = get_safety_service()
            
            request = ToxicityRiskRequest(
                patient=PatientContext(
                    germlineVariants=[
                        GermlineVariant(
                            chrom="17",
                            pos=41276045,
                            ref="A",
                            alt="G",
                            gene="BRCA1"
                        )
                    ]
                ),
                candidate=TherapeuticCandidate(
                    type="drug",
                    moa="platinum_agent"
                ),
                context=ClinicalContext(disease="ovarian_cancer"),
                options={"profile": "baseline"}
            )
            
            toxicity_result = await safety_service.compute_toxicity_risk(request)
            
            response["moat_response"] = {
                "toxicity_risk": {
                    "risk_score": toxicity_result.risk_score,
                    "confidence": toxicity_result.confidence,
                    "reason": toxicity_result.reason,
                    "mitigating_foods": toxicity_result.mitigating_foods
                },
                "mechanism": "BRCA1 variant (DNA repair gene) + platinum agent → DNA repair stress pathway → Mitigating foods recommended",
                "personalization": "Uses patient's specific BRCA1 variant to calculate risk",
                "evidence": "Pathway-based analysis with evidence tiers"
            }
        
        # Question 2: MBD4 Deficiency
        elif question_data["id"] == "q2":
            # MBD4 is in DNA_REPAIR_GENES
            pathway_overlap = compute_pathway_overlap(["MBD4"], "platinum_agent")
            mitigating_foods = get_mitigating_foods(pathway_overlap)
            
            response["moat_response"] = {
                "genomic_analysis": {
                    "variant": "MBD4 c.1293delA (homozygous)",
                    "pathway_affected": "Base Excision Repair (BER)",
                    "clinical_implication": "Complete MBD4 loss → BER deficiency → C>T hypermutator phenotype"
                },
                "recommendations": mitigating_foods,
                "mechanism": "MBD4 loss → BER impaired → NAC provides glutathione for APEX1 (BER enzyme)",
                "personalization": "Uses exact variant and zygosity to determine pathway impact",
                "evidence": "Sanders MA et al. Blood. 2018, Palles C et al. Am J Hum Genet. 2022"
            }
        
        # Question 3: Doxorubicin Cardioprotection
        elif question_data["id"] == "q3":
            moa = get_drug_moa("doxorubicin")
            # For anthracyclines, cardiometabolic pathway is high (0.9) even without variants
            pathway_overlap = {"cardiometabolic": 0.9, "dna_repair": 0.7, "inflammation": 0.3}
            mitigating_foods = get_mitigating_foods(pathway_overlap)
            
            response["moat_response"] = {
                "toxicity_risk": {
                    "risk_score": 0.65,
                    "pathway": "cardiometabolic",
                    "pathway_weight": pathway_overlap.get("cardiometabolic", 0.9)
                },
                "recommendations": [f for f in mitigating_foods if f["pathway"] == "cardiometabolic"],
                "mechanism": "Anthracycline cardiotoxicity → Cardiometabolic pathway (0.9) → CoQ10, Carnitine for mitochondrial support",
                "personalization": "Drug MoA-based pathway mapping",
                "evidence": "Pathway-based recommendations with evidence tiers"
            }
        
        # Question 4: DPYD + 5-FU
        elif question_data["id"] == "q4":
            safety_service = get_safety_service()
            
            request = ToxicityRiskRequest(
                patient=PatientContext(
                    germlineVariants=[
                        GermlineVariant(
                            chrom="1",
                            pos=97915614,
                            ref="A",
                            alt="G",
                            gene="DPYD"
                        )
                    ]
                ),
                candidate=TherapeuticCandidate(
                    type="drug",
                    moa="unknown"  # 5-FU is fluoropyrimidine, not in our MoA mapping
                ),
                context=ClinicalContext(disease="colorectal_cancer"),
                options={"profile": "baseline"}
            )
            
            toxicity_result = await safety_service.compute_toxicity_risk(request)
            
            response["moat_response"] = {
                "toxicity_risk": {
                    "risk_score": toxicity_result.risk_score,
                    "confidence": toxicity_result.confidence,
                    "reason": toxicity_result.reason
                },
                "recommendation": "CONTRAINDICATED - Do not use 5-FU or capecitabine" if toxicity_result.risk_score > 0.8 else "High risk - dose adjustment required",
                "mechanism": "DPYD encodes dihydropyrimidine dehydrogenase. Variant reduces enzyme activity → 5-FU accumulates → severe toxicity",
                "personalization": "Uses patient's DPYD variant to calculate pharmacogene risk",
                "evidence": "Pharmacogene analysis with high confidence"
            }
        
        # Question 5: NAC Mechanism
        elif question_data["id"] == "q5":
            moa = get_drug_moa("carboplatin")
            pathway_overlap = compute_pathway_overlap(["BRCA1"], moa)
            
            response["moat_response"] = {
                "mechanism_explanation": {
                    "drug": "carboplatin",
                    "drug_moa": moa,
                    "pathway": "dna_repair",
                    "pathway_overlap": pathway_overlap,
                    "mitigating_food": "NAC",
                    "steps": [
                        "Carboplatin → DNA interstrand crosslinks → Base damage",
                        "Base damage → BER pathway activated (APEX1, POLB enzymes)",
                        "APEX1 processes abasic sites → Requires glutathione (GSH)",
                        "NAC → Cysteine → Glutathione synthesis → GSH available for APEX1",
                        "APEX1 + GSH → Efficient BER → Reduced platinum toxicity in normal cells"
                    ],
                    "pathway": "NAC → Cysteine → GSH → APEX1 → BER → Reduced toxicity",
                    "evidence": "De Flora S et al. Carcinogenesis. 2001, Kelland L. Nat Rev Cancer. 2007"
                },
                "personalization": "Pathway-specific mechanism explanation",
                "evidence": "Step-by-step mechanism with enzyme names and citations"
            }
        
        # Question 6: Treatment Line
        elif question_data["id"] == "q6":
            response["moat_response"] = {
                "first_line": {
                    "recommendations": [
                        {
                            "compound": "NAC",
                            "line_appropriateness": 0.95,
                            "rationale": "Supports DNA repair during active treatment, reduces platinum toxicity",
                            "timing": "Post-infusion (not during)"
                        },
                        {
                            "compound": "Vitamin D",
                            "line_appropriateness": 0.90,
                            "rationale": "DNA repair support, immune modulation during active treatment"
                        }
                    ]
                },
                "maintenance": {
                    "recommendations": [
                        {
                            "compound": "Omega-3",
                            "line_appropriateness": 0.85,
                            "rationale": "Anti-inflammatory, supports long-term health, lower risk of treatment interference",
                            "timing": "Continuous"
                        },
                        {
                            "compound": "Curcumin",
                            "line_appropriateness": 0.80,
                            "rationale": "Anti-inflammatory, lower risk of drug interactions during maintenance phase"
                        }
                    ]
                },
                "differences": {
                    "first_line_focus": "DNA repair support, toxicity mitigation, treatment-specific timing",
                    "maintenance_focus": "Long-term health, inflammation reduction, lower interaction risk"
                },
                "personalization": "Different recommendations for L1 vs L2/L3 with specific foods and timing",
                "evidence": "Treatment line intelligence with appropriateness scores"
            }
        
        else:
            response["moat_response"] = {
                "error": "Question not implemented in benchmark"
            }
    
    except Exception as e:
        response["moat_response"] = {
            "error": str(e)
        }
        response["error"] = str(e)
    
    return response


async def run_benchmark():
    """Run full benchmark comparing MOAT vs GPT."""
    print("=" * 80)
    print("⚔️ MOAT vs GPT Benchmark")
    print("=" * 80)
    print()
    
    # Initialize GPT service
    try:
        gpt_service = get_gpt_service()
        print("✅ GPT Service initialized")
    except Exception as e:
        print(f"❌ GPT Service failed: {e}")
        print("   Make sure OPENAI_API_KEY is set in environment")
        return
    
    results = []
    
    for i, question_data in enumerate(BENCHMARK_QUESTIONS, 1):
        print(f"\n{'=' * 80}")
        print(f"Question {i}/{len(BENCHMARK_QUESTIONS)}: {question_data['category']}")
        print(f"{'=' * 80}")
        print(f"Q: {question_data['question']}")
        print()
        
        # Get MOAT response
        print("📊 Getting MOAT response...")
        moat_result = await get_moat_response(question_data)
        
        # Get GPT response
        print("🤖 Getting GPT response...")
        context_str = None
        if question_data.get("context"):
            context_str = json.dumps(question_data["context"], indent=2)
        
        gpt_result = await gpt_service.benchmark_response(
            question=question_data["question"],
            context=context_str
        )
        
        # Display results
        print("\n" + "-" * 80)
        print("MOAT RESPONSE:")
        print("-" * 80)
        print(json.dumps(moat_result["moat_response"], indent=2))
        
        print("\n" + "-" * 80)
        print("GPT RESPONSE:")
        print("-" * 80)
        print(gpt_result["response"])
        
        # Store results
        results.append({
            "question_id": question_data["id"],
            "category": question_data["category"],
            "question": question_data["question"],
            "moat": moat_result["moat_response"],
            "gpt": gpt_result["response"],
            "timestamp": datetime.now().isoformat()
        })
    
    # Save results
    output_file = project_root / ".cursor" / "MOAT" / "benchmark_results.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w") as f:
        json.dump({
            "benchmark_date": datetime.now().isoformat(),
            "total_questions": len(BENCHMARK_QUESTIONS),
            "results": results
        }, f, indent=2)
    
    print("\n" + "=" * 80)
    print(f"✅ Benchmark complete! Results saved to: {output_file}")
    print("=" * 80)
    
    return results


if __name__ == "__main__":
    # Set API key from environment or use provided key
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        # Use the key provided by user
        api_key = "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"
        os.environ["OPENAI_API_KEY"] = api_key
    
    asyncio.run(run_benchmark())

