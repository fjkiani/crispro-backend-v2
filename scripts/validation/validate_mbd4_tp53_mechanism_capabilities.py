#!/usr/bin/env python3
"""
MBD4+TP53 End-to-End Mechanism Capabilities Validation
Day 3 - Task 3.3

Tests both trial matching AND resistance prediction together.

Run: python scripts/validation/validate_mbd4_tp53_mechanism_capabilities.py
"""

import sys
import os
import json
import asyncio
from typing import Dict, List, Any
from datetime import datetime
from dataclasses import dataclass, asdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from api.services.mechanism_fit_ranker import rank_trials_by_mechanism
    from api.services.resistance_prophet_service import ResistanceProphetService
    from api.services.pathway_to_mechanism_vector import convert_moa_dict_to_vector
    IMPORTS_OK = True
except ImportError as e:
    print(f"Warning: Import failed - {e}")
    IMPORTS_OK = False


@dataclass
class IntegrationResult:
    test_name: str
    passed: bool
    details: str
    metrics: Dict[str, Any]


@dataclass
class IntegrationReport:
    timestamp: str
    patient_profile: Dict[str, Any]
    overall_passed: bool
    trial_matching: IntegrationResult
    resistance_prediction: IntegrationResult
    integration_success: bool


class MBD4TP53IntegrationValidator:
    """End-to-end integration test for MBD4+TP53 patient"""
    
    def __init__(self):
        self.resistance_service = ResistanceProphetService() if IMPORTS_OK else None
        self.trial_moa_vectors = self._load_moa_vectors()
        
        # MBD4+TP53 patient mechanism vector (DDR-high)
        self.patient_mechanism_vector = [0.88, 0.12, 0.05, 0.02, 0.0, 0.0, 0.0]
        
        self.patient_profile = {
            "mutations": [
                {"gene": "MBD4", "hgvs_p": "p.R361*", "type": "germline"},
                {"gene": "TP53", "hgvs_p": "p.R175H", "type": "somatic"}
            ],
            "disease": "ovarian_cancer_hgsoc",
            "stage": "IVB"
        }
    
    def _load_moa_vectors(self) -> Dict[str, Any]:
        """Load trial MoA vectors"""
        path = os.path.join(
            os.path.dirname(__file__),
            "../../api/resources/trial_moa_vectors.json"
        )
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {}
    
    def run_integration_test(self) -> IntegrationReport:
        """Run complete integration test"""
        print("=" * 60)
        print("MBD4+TP53 END-TO-END INTEGRATION TEST")
        print("=" * 60)
        print()
        print(f"Patient: MBD4 R361* (germline) + TP53 R175H (somatic)")
        print(f"Disease: High-Grade Serous Ovarian Cancer")
        print(f"Mechanism Vector (DDR-high): {self.patient_mechanism_vector}")
        print()
        
        # Test 1: Trial Matching
        print("Test 1: Mechanism-Based Trial Matching...")
        trial_result = self._test_trial_matching()
        
        # Test 2: Resistance Prediction
        print("\nTest 2: Mechanism-Based Resistance Prediction...")
        resistance_result = asyncio.run(self._test_resistance_prediction())
        
        # Integration Success
        integration_success = trial_result.passed and resistance_result.passed
        overall_passed = integration_success
        
        return IntegrationReport(
            timestamp=datetime.utcnow().isoformat(),
            patient_profile=self.patient_profile,
            overall_passed=overall_passed,
            trial_matching=trial_result,
            resistance_prediction=resistance_result,
            integration_success=integration_success
        )
    
    def _test_trial_matching(self) -> IntegrationResult:
        """Test trial matching with MBD4+TP53 mechanism vector"""
        if not IMPORTS_OK:
            return IntegrationResult(
                test_name="Trial Matching",
                passed=False, details="Imports failed",
                metrics={}
            )
        
        # Get DDR-focused trials
        ddr_trials = []
        for nct_id, data in list(self.trial_moa_vectors.items())[:30]:
            moa = data.get("moa_vector", {})
            if moa.get("ddr", 0) > 0.5:
                ddr_trials.append({
                    "nct_id": nct_id,
                    "title": data.get("title", f"Trial {nct_id}"),
                    "eligibility_score": 0.75,
                    "moa_vector": convert_moa_dict_to_vector(moa, use_7d=True)
                })
        
        if len(ddr_trials) < 3:
            return IntegrationResult(
                test_name="Trial Matching",
                passed=False, details=f"Insufficient DDR trials ({len(ddr_trials)})",
                metrics={"ddr_trials_found": len(ddr_trials)}
            )
        
        # Rank trials
        ranked = rank_trials_by_mechanism(
            trials=ddr_trials,
            sae_mechanism_vector=self.patient_mechanism_vector,
            min_eligibility=0.0,
            min_mechanism_fit=0.0
        )
        
        top_5 = ranked[:5]
        avg_mechanism_fit = sum(t.get("mechanism_fit_score", 0) for t in top_5) / len(top_5) if top_5 else 0
        
        passed = len(ranked) > 0 and avg_mechanism_fit > 0.70
        details = f"Ranked {len(ranked)} trials, avg mechanism fit: {avg_mechanism_fit:.2f}"
        
        print(f"  {'✅' if passed else '❌'} {details}")
        if top_5:
            print(f"  Top trial: {top_5[0]['nct_id']} (score: {top_5[0].get('mechanism_fit_score', 0):.2f})")
        
        return IntegrationResult(
            test_name="Trial Matching",
            passed=passed, details=details,
            metrics={
                "trials_ranked": len(ranked),
                "avg_mechanism_fit": avg_mechanism_fit,
                "top_trial": top_5[0]["nct_id"] if top_5 else None
            }
        )
    
    async def _test_resistance_prediction(self) -> IntegrationResult:
        """Test resistance prediction for MBD4+TP53"""
        if not self.resistance_service:
            return IntegrationResult(
                test_name="Resistance Prediction",
                passed=False, details="Service not available",
                metrics={}
            )
        
        # Baseline (pre-treatment)
        baseline_sae = {
            "dna_repair_capacity": 0.85,
            "mechanism_vector": self.patient_mechanism_vector
        }
        
        # Current (on-treatment, showing resistance)
        current_sae = {
            "dna_repair_capacity": 0.60,  # Dropped
            "mechanism_vector": [0.65, 0.15, 0.10, 0.05, 0.0, 0.0, 0.05]  # DDR dropped
        }
        
        prediction = await self.resistance_service.predict_resistance(
            current_sae_features=current_sae,
            baseline_sae_features=baseline_sae,
            current_drug_class="parp_inhibitor"
        )
        
        # Check for signals
        dna_detected = any(s.detected and s.signal_type.value == "DNA_REPAIR_RESTORATION" 
                          for s in prediction.signals_detected)
        pathway_detected = any(s.detected and s.signal_type.value == "PATHWAY_ESCAPE" 
                               for s in prediction.signals_detected)
        
        passed = prediction.signal_count >= 1
        details = (
            f"Risk: {prediction.risk_level.value}, Probability: {prediction.probability:.2f}, "
            f"Signals: {prediction.signal_count}"
        )
        
        print(f"  {'✅' if passed else '❌'} {details}")
        print(f"  DNA repair: {'detected' if dna_detected else 'not detected'}")
        print(f"  Pathway escape: {'detected' if pathway_detected else 'not detected'}")
        
        return IntegrationResult(
            test_name="Resistance Prediction",
            passed=passed, details=details,
            metrics={
                "risk_level": prediction.risk_level.value,
                "probability": prediction.probability,
                "signal_count": prediction.signal_count,
                "dna_repair_detected": dna_detected,
                "pathway_escape_detected": pathway_detected
            }
        )


def main():
    validator = MBD4TP53IntegrationValidator()
    report = validator.run_integration_test()
    
    print()
    print("=" * 60)
    print("INTEGRATION TEST SUMMARY")
    print("=" * 60)
    print(f"Overall: {'✅ PASSED' if report.overall_passed else '❌ FAILED'}")
    print(f"Integration Success: {'✅' if report.integration_success else '❌'}")
    print()
    print("Trial Matching:")
    print(f"  Trials ranked: {report.trial_matching.metrics.get('trials_ranked', 0)}")
    print(f"  Avg mechanism fit: {report.trial_matching.metrics.get('avg_mechanism_fit', 0):.2f}")
    print()
    print("Resistance Prediction:")
    print(f"  Risk level: {report.resistance_prediction.metrics.get('risk_level', 'N/A')}")
    print(f"  Probability: {report.resistance_prediction.metrics.get('probability', 0):.2f}")
    
    report_path = os.path.join(
        os.path.dirname(__file__),
        f"mbd4_tp53_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    )
    with open(report_path, "w") as f:
        json.dump({
            "timestamp": report.timestamp,
            "patient_profile": report.patient_profile,
            "overall_passed": report.overall_passed,
            "integration_success": report.integration_success,
            "trial_matching": asdict(report.trial_matching),
            "resistance_prediction": asdict(report.resistance_prediction)
        }, f, indent=2)
    print(f"\nReport saved: {report_path}")
    
    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    sys.exit(main())
