#!/usr/bin/env python3
"""
AYESHA: MBD4+TP53 HGSOC Analysis - Consistency & Alignment Benchmark

⚠️ IMPORTANT: This is NOT an accuracy benchmark against real patient outcomes.
MBD4+TP53 is too rare to have published case studies or real outcome data.

What We're Actually Testing:
1. Internal Consistency: Does the system work as designed?
   - Pathway scores match variant types (frameshift = 1.0, hotspot = 0.8)
   - Mechanism vectors match pathway scores (DDR = 1.0 + 0.8×0.5 = 1.4)
   - Drug recommendations match pathway disruption (DDR high → PARP)

2. Clinical Alignment: Do recommendations match guidelines?
   - PARP inhibitors recommended (NCCN Category 1 for HRD+)
   - Platinum recommended (Standard of care for HGSOC)
   - Evidence tiers match guideline strength

3. Biological Soundness: Do mechanisms match literature?
   - MBD4 → BER deficiency (literature-supported)
   - TP53 → Checkpoint bypass (literature-supported)
   - Combined → Synthetic lethality (mechanism-supported)

Ground Truth Sources (NOT Real Patient Outcomes):
- Biology-Based Expected Values: Frameshift = 1.0, hotspot = 0.8 (our assumptions)
- NCCN Guidelines: General HRD+ ovarian cancer (not MBD4+TP53 specific)
- FDA Labels: PARP inhibitors for HRD+ (not MBD4+TP53 specific)
- Published Literature: Mechanism knowledge (not outcome data)

What We're NOT Testing:
- ❌ Real-world accuracy (no patient outcomes available)
- ❌ Predictive performance (no outcome data to compare)
- ❌ Comparative performance (no gold standard system)

For real accuracy validation, see: BRCA+TP53 proxy benchmark (has published data)
"""

import os
import sys
import json
import asyncio
import httpx
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.pathway_to_mechanism_vector import convert_pathway_scores_to_mechanism_vector

# Ground Truth: Expected Results for MBD4+TP53 HGSOC
GROUND_TRUTH = {
    "patient_id": "AYESHA-001",
    "variants": {
        "mbd4": {
            "gene": "MBD4",
            "hgvs_p": "p.Ile413Serfs*2",
            "expected_pathway": "ddr",
            "expected_pathway_score": 1.0,  # Frameshift → complete loss
            "expected_functionality": "loss_of_function",
            "expected_essentiality": "high",  # BER pathway dependency
            "expected_evidence_tier": "strong"  # Homozygous frameshift = pathogenic
        },
        "tp53": {
            "gene": "TP53",
            "hgvs_p": "p.Arg175His",
            "expected_pathway": "tp53",
            "expected_pathway_score": 0.7,  # Hotspot → high disruption (80th percentile)
            "expected_functionality": "loss_of_function",
            "expected_essentiality": "high",  # Checkpoint dependency
            "expected_evidence_tier": "strong"  # Well-characterized hotspot
        }
    },
    "expected_drugs": {
        "tier1": [
            {"name": "olaparib", "min_efficacy": 0.75, "expected_rank": 1},
            {"name": "niraparib", "min_efficacy": 0.75, "expected_rank": 2},
            {"name": "rucaparib", "min_efficacy": 0.75, "expected_rank": 3},
            {"name": "carboplatin", "min_efficacy": 0.70, "expected_rank": 4}
        ],
        "tier2": [
            {"name": "berzosertib", "min_efficacy": 0.60},  # ATR inhibitor
            {"name": "adavosertib", "min_efficacy": 0.55}   # WEE1 inhibitor
        ]
    },
    "expected_pathway_disruption": {
        "ddr": {"min": 0.9, "max": 1.0},      # MBD4 frameshift → BER deficiency
        "tp53": {"min": 0.7, "max": 0.9}      # TP53 R175H hotspot → checkpoint bypass
    },
    "expected_mechanism_vector": {
        "ddr": {"min": 1.2, "max": 1.5},      # DDR + 50% TP53 = 1.0 + (0.8 × 0.5) = 1.4
        "mapk": {"min": 0.0, "max": 0.1},
        "pi3k": {"min": 0.0, "max": 0.1},
        "vegf": {"min": 0.0, "max": 0.2},
        "her2": {"min": 0.0, "max": 0.1},
        "io": {"min": 0.0, "max": 0.5},       # TMB may be high (BER + checkpoint loss)
        "efflux": {"min": 0.0, "max": 0.1}
    },
    "expected_synthetic_lethality": {
        "suggested_therapy": ["olaparib", "platinum", "parp"],
        "vulnerabilities": ["PARP", "ATR", "WEE1", "DNA-PK"]
    },
    "expected_trials": {
        "min_count": 5,
        "expected_types": ["basket", "biomarker_driven", "rare_disease"],
        "expected_biomarkers": ["HRD+", "TP53 mutation", "DNA repair deficiency"]
    }
}


@dataclass
class BenchmarkResult:
    """Single benchmark test result"""
    test_name: str
    passed: bool
    score: float  # 0.0 to 1.0
    expected: Any
    actual: Any
    error: Optional[str] = None


class AccuracyBenchmark:
    """Benchmark framework for MBD4+TP53 analysis accuracy"""
    
    def __init__(self, api_base_url: str = "http://localhost:8000"):
        self.api_base_url = api_base_url
        self.results: List[BenchmarkResult] = []
        self.client = None
    
    async def __aenter__(self):
        self.client = httpx.AsyncClient(timeout=120.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()
    
    def add_result(self, test_name: str, passed: bool, score: float, 
                   expected: Any, actual: Any, error: Optional[str] = None):
        """Add a benchmark result"""
        self.results.append(BenchmarkResult(
            test_name=test_name,
            passed=passed,
            score=score,
            expected=expected,
            actual=actual,
            error=error
        ))
    
    def print_summary(self):
        """Print benchmark summary"""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        avg_score = sum(r.score for r in self.results) / total if total > 0 else 0.0
        
        print("\n" + "="*80)
        print("AYESHA MBD4+TP53 ACCURACY BENCHMARK RESULTS")
        print("="*80)
        print(f"\nTotal Tests: {total}")
        print(f"Passed: {passed} ({passed/total*100:.1f}%)")
        print(f"Failed: {total - passed} ({(total-passed)/total*100:.1f}%)")
        print(f"Average Score: {avg_score:.3f}")
        print("\n" + "-"*80)
        
        for result in self.results:
            status = "✅ PASS" if result.passed else "❌ FAIL"
            print(f"{status} | {result.test_name}")
            print(f"      Score: {result.score:.3f}")
            if not result.passed:
                print(f"      Expected: {result.expected}")
                print(f"      Actual: {result.actual}")
                if result.error:
                    print(f"      Error: {result.error}")
            print()
        
        print("="*80)
        return {
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "pass_rate": passed / total if total > 0 else 0.0,
            "avg_score": avg_score
        }
    
    # =========================================================================
    # TEST 1: Pathway Accuracy
    # =========================================================================
    
    async def test_pathway_accuracy(self):
        """Test pathway disruption scores match expected biological pathways"""
        print("\n🧪 TEST 1: Pathway Accuracy")
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/efficacy/predict",
                json={
                    "model_id": "evo2_1b",
                    "mutations": [
                        {
                            "gene": "MBD4",
                            "hgvs_p": "p.Ile413Serfs*2",
                            "chrom": "3",
                            "pos": 129430456,
                            "ref": "A",
                            "alt": "",
                            "build": "GRCh37"
                        },
                        {
                            "gene": "TP53",
                            "hgvs_p": "p.Arg175His",
                            "chrom": "17",
                            "pos": 7577120,
                            "ref": "G",
                            "alt": "A",
                            "build": "GRCh37"
                        }
                    ],
                    "disease": "ovarian_cancer",
                    "germline_status": "positive",
                    "tumor_context": {"disease": "ovarian_cancer"}
                }
            )
            
            if response.status_code != 200:
                self.add_result(
                    "Pathway Accuracy - API Call",
                    False, 0.0,
                    "200 OK",
                    f"{response.status_code}",
                    f"API call failed: {response.text[:200]}"
                )
                return
            
            data = response.json()
            pathway_disruption = data.get("provenance", {}).get("confidence_breakdown", {}).get("pathway_disruption", {})
            
            if not pathway_disruption:
                self.add_result(
                    "Pathway Accuracy - Data Present",
                    False, 0.0,
                    "pathway_disruption dict",
                    "None",
                    "pathway_disruption not found in response"
                )
                return
            
            # Test DDR pathway (MBD4)
            ddr_score = pathway_disruption.get("ddr", 0.0)
            ddr_expected = GROUND_TRUTH["expected_pathway_disruption"]["ddr"]
            ddr_passed = ddr_expected["min"] <= ddr_score <= ddr_expected["max"]
            ddr_score_normalized = min(1.0, max(0.0, 
                (ddr_score - ddr_expected["min"]) / (ddr_expected["max"] - ddr_expected["min"])))
            
            self.add_result(
                "Pathway Accuracy - DDR (MBD4)",
                ddr_passed, ddr_score_normalized,
                f"{ddr_expected['min']:.1f}-{ddr_expected['max']:.1f}",
                f"{ddr_score:.4f}"
            )
            
            # Test TP53 pathway
            tp53_score = pathway_disruption.get("tp53", 0.0)
            tp53_expected = GROUND_TRUTH["expected_pathway_disruption"]["tp53"]
            tp53_passed = tp53_expected["min"] <= tp53_score <= tp53_expected["max"]
            tp53_score_normalized = min(1.0, max(0.0,
                (tp53_score - tp53_expected["min"]) / (tp53_expected["max"] - tp53_expected["min"])))
            
            self.add_result(
                "Pathway Accuracy - TP53 (R175H)",
                tp53_passed, tp53_score_normalized,
                f"{tp53_expected['min']:.1f}-{tp53_expected['max']:.1f}",
                f"{tp53_score:.4f}"
            )
            
        except Exception as e:
            self.add_result(
                "Pathway Accuracy - Exception",
                False, 0.0,
                "No exception",
                str(e),
                f"Exception: {e}"
            )
    
    # =========================================================================
    # TEST 2: Drug Recommendation Accuracy
    # =========================================================================
    
    async def test_drug_accuracy(self):
        """Test drug recommendations match NCCN/FDA guidelines"""
        print("\n🧪 TEST 2: Drug Recommendation Accuracy")
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/efficacy/predict",
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
                self.add_result(
                    "Drug Accuracy - API Call",
                    False, 0.0,
                    "200 OK",
                    f"{response.status_code}",
                    f"API call failed"
                )
                return
            
            data = response.json()
            drugs = data.get("drugs", [])
            
            if not drugs:
                self.add_result(
                    "Drug Accuracy - Drugs Present",
                    False, 0.0,
                    "Non-empty drugs list",
                    "Empty list",
                    "No drugs returned"
                )
                return
            
            # Test Tier 1 drugs (PARP inhibitors + Platinum)
            tier1_expected = GROUND_TRUTH["expected_drugs"]["tier1"]
            tier1_found = []
            tier1_scores = []
            
            for expected_drug in tier1_expected:
                drug_name = expected_drug["name"]
                found = False
                for drug in drugs:
                    if drug.get("name", "").lower() == drug_name.lower():
                        found = True
                        efficacy = drug.get("efficacy_score", 0.0)
                        tier1_found.append(drug_name)
                        tier1_scores.append(efficacy)
                        
                        # Check efficacy threshold
                        passed = efficacy >= expected_drug["min_efficacy"]
                        self.add_result(
                            f"Drug Accuracy - {drug_name} Efficacy",
                            passed, efficacy,
                            f">= {expected_drug['min_efficacy']:.2f}",
                            f"{efficacy:.3f}"
                        )
                        break
                
                if not found:
                    self.add_result(
                        f"Drug Accuracy - {drug_name} Present",
                        False, 0.0,
                        "Found in top drugs",
                        "Not found",
                        f"{drug_name} not in drug recommendations"
                    )
            
            # Test ranking (PARP should be #1-3)
            if len(tier1_found) >= 3:
                top3_names = [d.get("name", "").lower() for d in drugs[:3]]
                parp_in_top3 = any("parp" in name or name in ["olaparib", "niraparib", "rucaparib"] for name in top3_names)
                self.add_result(
                    "Drug Accuracy - PARP in Top 3",
                    parp_in_top3, 1.0 if parp_in_top3 else 0.0,
                    "PARP inhibitor in top 3",
                    f"Top 3: {top3_names}",
                    None if parp_in_top3 else "PARP not in top 3"
                )
            
        except Exception as e:
            self.add_result(
                "Drug Accuracy - Exception",
                False, 0.0,
                "No exception",
                str(e),
                f"Exception: {e}"
            )
    
    # =========================================================================
    # TEST 3: Mechanism Vector Accuracy
    # =========================================================================
    
    async def test_mechanism_vector_accuracy(self):
        """Test mechanism vector matches expected clinical mechanisms"""
        print("\n🧪 TEST 3: Mechanism Vector Accuracy")
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/efficacy/predict",
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
                self.add_result(
                    "Mechanism Vector - API Call",
                    False, 0.0,
                    "200 OK",
                    f"{response.status_code}",
                    "API call failed"
                )
                return
            
            data = response.json()
            pathway_disruption = data.get("provenance", {}).get("confidence_breakdown", {}).get("pathway_disruption", {})
            
            if not pathway_disruption:
                self.add_result(
                    "Mechanism Vector - Pathway Data",
                    False, 0.0,
                    "pathway_disruption dict",
                    "None",
                    "pathway_disruption not found"
                )
                return
            
            # Convert to mechanism vector
            mechanism_vector, dimension = convert_pathway_scores_to_mechanism_vector(
                pathway_scores=pathway_disruption,
                use_7d=True
            )
            
            # Test DDR mechanism (should be 1.0 + 0.8*0.5 = 1.4)
            ddr_expected = GROUND_TRUTH["expected_mechanism_vector"]["ddr"]
            ddr_actual = mechanism_vector[0]
            ddr_passed = ddr_expected["min"] <= ddr_actual <= ddr_expected["max"]
            ddr_score = min(1.0, max(0.0,
                (ddr_actual - ddr_expected["min"]) / (ddr_expected["max"] - ddr_expected["min"])))
            
            self.add_result(
                "Mechanism Vector - DDR",
                ddr_passed, ddr_score,
                f"{ddr_expected['min']:.1f}-{ddr_expected['max']:.1f}",
                f"{ddr_actual:.4f}",
                None if ddr_passed else f"Expected DDR=1.4 (1.0 + 0.8*0.5), got {ddr_actual:.4f}"
            )
            
            # Test other pathways should be low
            for idx, (pathway, expected) in enumerate([
                ("MAPK", 1), ("PI3K", 2), ("VEGF", 3), ("HER2", 4), ("IO", 5), ("Efflux", 6)
            ]):
                expected_range = GROUND_TRUTH["expected_mechanism_vector"][pathway.lower()]
                actual_value = mechanism_vector[idx + 1] if idx < 6 else mechanism_vector[5]
                passed = expected_range["min"] <= actual_value <= expected_range["max"]
                score = 1.0 if passed else max(0.0, 1.0 - abs(actual_value - expected_range["max"]))
                
                self.add_result(
                    f"Mechanism Vector - {pathway}",
                    passed, score,
                    f"{expected_range['min']:.1f}-{expected_range['max']:.1f}",
                    f"{actual_value:.4f}"
                )
            
        except Exception as e:
            self.add_result(
                "Mechanism Vector - Exception",
                False, 0.0,
                "No exception",
                str(e),
                f"Exception: {e}"
            )
    
    # =========================================================================
    # TEST 4: Synthetic Lethality Accuracy
    # =========================================================================
    
    async def test_synthetic_lethality_accuracy(self):
        """Test synthetic lethality correctly identifies PARP sensitivity"""
        print("\n🧪 TEST 4: Synthetic Lethality Accuracy")
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/guidance/synthetic_lethality",
                json={
                    "disease": "ovarian_cancer",
                    "mutations": [
                        {"gene": "MBD4", "hgvs_p": "p.Ile413Serfs*2", "chrom": "3", "pos": 129430456, "ref": "A", "alt": ""},
                        {"gene": "TP53", "hgvs_p": "p.Arg175His", "chrom": "17", "pos": 7577120, "ref": "G", "alt": "A"}
                    ],
                    "api_base": self.api_base_url
                }
            )
            
            if response.status_code != 200:
                self.add_result(
                    "Synthetic Lethality - API Call",
                    False, 0.0,
                    "200 OK",
                    f"{response.status_code}",
                    "API call failed"
                )
                return
            
            data = response.json()
            suggested_therapy = data.get("suggested_therapy", "").lower()
            
            expected_therapies = GROUND_TRUTH["expected_synthetic_lethality"]["suggested_therapy"]
            passed = any(exp.lower() in suggested_therapy for exp in expected_therapies)
            score = 1.0 if passed else 0.0
            
            self.add_result(
                "Synthetic Lethality - Suggested Therapy",
                passed, score,
                f"One of: {expected_therapies}",
                suggested_therapy,
                None if passed else f"Expected PARP/platinum, got: {suggested_therapy}"
            )
            
        except Exception as e:
            self.add_result(
                "Synthetic Lethality - Exception",
                False, 0.0,
                "No exception",
                str(e),
                f"Exception: {e}"
            )
    
    # =========================================================================
    # TEST 5: Clinical Evidence Alignment
    # =========================================================================
    
    async def test_evidence_alignment(self):
        """Test evidence tier matches expected clinical evidence strength"""
        print("\n🧪 TEST 5: Clinical Evidence Alignment")
        
        try:
            response = await self.client.post(
                f"{self.api_base_url}/api/efficacy/predict",
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
                return
            
            data = response.json()
            drugs = data.get("drugs", [])
            
            # Test PARP inhibitors have appropriate evidence tier
            parp_drugs = [d for d in drugs if "parp" in d.get("name", "").lower() or d.get("name", "").lower() in ["olaparib", "niraparib", "rucaparib"]]
            
            if parp_drugs:
                top_parp = parp_drugs[0]
                evidence_tier = top_parp.get("evidence_tier", "").lower()
                
                # PARP should be "supported" or "consider" (not "insufficient")
                passed = evidence_tier in ["supported", "consider"]
                score = 1.0 if passed else 0.5 if evidence_tier == "insufficient" else 0.0
                
                self.add_result(
                    "Evidence Alignment - PARP Evidence Tier",
                    passed, score,
                    "supported or consider",
                    evidence_tier,
                    None if passed else f"PARP should have strong evidence (HRD+), got: {evidence_tier}"
                )
            
        except Exception as e:
            self.add_result(
                "Evidence Alignment - Exception",
                False, 0.0,
                "No exception",
                str(e),
                f"Exception: {e}"
            )
    
    # =========================================================================
    # RUN ALL TESTS
    # =========================================================================
    
    async def run_all_tests(self):
        """Run all benchmark tests"""
        print("\n" + "="*80)
        print("AYESHA MBD4+TP53 ACCURACY BENCHMARK")
        print("="*80)
        print(f"\nAPI Base URL: {self.api_base_url}")
        print(f"Ground Truth: {len(GROUND_TRUTH)} test categories")
        print(f"Timestamp: {datetime.now().isoformat()}")
        
        await self.test_pathway_accuracy()
        await self.test_drug_accuracy()
        await self.test_mechanism_vector_accuracy()
        await self.test_synthetic_lethality_accuracy()
        await self.test_evidence_alignment()
        
        return self.print_summary()


async def main():
    """Main execution"""
    api_base = os.getenv("API_BASE_URL", "http://localhost:8000")
    
    async with AccuracyBenchmark(api_base_url=api_base) as benchmark:
        summary = await benchmark.run_all_tests()
        
        # Save results
        output_dir = os.path.join(os.path.dirname(__file__), "..", "results", "benchmarks")
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = os.path.join(output_dir, f"ayesha_accuracy_benchmark_{timestamp}.json")
        
        results_data = {
            "timestamp": datetime.now().isoformat(),
            "ground_truth": GROUND_TRUTH,
            "summary": summary,
            "results": [
                {
                    "test_name": r.test_name,
                    "passed": r.passed,
                    "score": r.score,
                    "expected": str(r.expected),
                    "actual": str(r.actual),
                    "error": r.error
                }
                for r in benchmark.results
            ]
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_data, f, indent=2)
        
        print(f"\n💾 Results saved to: {output_file}")
        print("\n" + "="*80)
        
        return summary


if __name__ == "__main__":
    summary = asyncio.run(main())
    sys.exit(0 if summary["pass_rate"] >= 0.8 else 1)

