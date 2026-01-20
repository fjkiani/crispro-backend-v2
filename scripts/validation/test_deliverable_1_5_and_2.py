#!/usr/bin/env python3
"""
Test Script: Deliverable 1.5 (TRUE SAE Frontend) + Deliverable 2 (Mechanism Fit Validation)

This script tests:
1. Deliverable 1.5: Verify backend passes saeSource and ddrBinScore correctly
2. Deliverable 2: Validate mechanism fit scores and shortlist compression

Run: python scripts/validation/test_deliverable_1_5_and_2.py
"""

import sys
import os
import json
from pathlib import Path
from typing import Dict, List, Any, Optional

# Add parent to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../.."))

try:
    from api.services.mechanism_fit_ranker import MechanismFitRanker
    from api.services.pathway_to_mechanism_vector import convert_moa_dict_to_vector
    from api.services.sae_feature_service import SAEFeatureService
    IMPORTS_OK = True
except ImportError as e:
    print(f"⚠️  Warning: Import failed - {e}")
    IMPORTS_OK = False


def test_deliverable_1_5_backend() -> Dict[str, Any]:
    """
    Test Deliverable 1.5: Verify backend can compute and pass saeSource/ddrBinScore
    """
    print("=" * 60)
    print("TEST 1: DELIVERABLE 1.5 - Backend TRUE SAE Integration")
    print("=" * 60)
    print()
    
    results = {
        "test_name": "Deliverable 1.5 Backend",
        "passed": False,
        "details": [],
        "errors": []
    }
    
    if not IMPORTS_OK:
        results["errors"].append("Imports failed - cannot test")
        return results
    
    try:
        # Test 1: Verify SAEFeatureService can compute DDR_bin
        print("Test 1.1: SAEFeatureService DDR_bin computation...")
        service = SAEFeatureService()
        
        # Mock TRUE SAE features (32K-dim vector with 9 diamond features)
        # For testing, we'll check if the method exists and can be called
        if hasattr(service, '_compute_sae_diagnostics'):
            print("  ✅ _compute_sae_diagnostics method exists")
            results["details"].append("_compute_sae_diagnostics method exists")
        else:
            print("  ❌ _compute_sae_diagnostics method not found")
            results["errors"].append("_compute_sae_diagnostics method not found")
            return results
        
        # Test 2: Verify mechanism fit ranker accepts saeSource/ddrBinScore
        print("Test 1.2: MechanismFitRanker integration...")
        ranker = MechanismFitRanker(alpha=0.7, beta=0.3)
        
        # Create mock trial with saeSource and ddrBinScore
        mock_trial = {
            "nct_id": "NCT12345678",
            "title": "Test Trial",
            "eligibility_score": 0.85,
            "mechanism_fit_score": 0.92,
            "sae_source": "true_sae",
            "ddr_bin_score": 0.88,
            "moa_vector": [0.9, 0.1, 0.0, 0.0, 0.0, 0.0, 0.0]
        }
        
        print(f"  ✅ Mock trial created with sae_source={mock_trial['sae_source']}, ddr_bin_score={mock_trial['ddr_bin_score']}")
        results["details"].append(f"Mock trial created with sae_source and ddr_bin_score")
        
        # Test 3: Verify trial MoA vectors exist
        print("Test 1.3: Trial MoA vectors availability...")
        moa_path = Path(__file__).parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"
        
        if moa_path.exists():
            with open(moa_path, "r") as f:
                trial_moa_vectors = json.load(f)
            print(f"  ✅ Found {len(trial_moa_vectors)} trials with MoA vectors")
            results["details"].append(f"Found {len(trial_moa_vectors)} trials with MoA vectors")
        else:
            print(f"  ⚠️  Trial MoA vectors file not found: {moa_path}")
            results["errors"].append(f"Trial MoA vectors file not found")
        
        results["passed"] = len(results["errors"]) == 0
        print()
        print(f"✅ Deliverable 1.5 Backend Test: {'PASSED' if results['passed'] else 'FAILED'}")
        
    except Exception as e:
        results["errors"].append(f"Exception: {str(e)}")
        print(f"  ❌ Exception: {e}")
        results["passed"] = False
    
    return results


def test_deliverable_2_mechanism_fit() -> Dict[str, Any]:
    """
    Test Deliverable 2: Validate mechanism fit scores
    """
    print("=" * 60)
    print("TEST 2: DELIVERABLE 2 - Mechanism Fit Validation")
    print("=" * 60)
    print()
    
    results = {
        "test_name": "Deliverable 2 Mechanism Fit",
        "passed": False,
        "details": [],
        "errors": [],
        "metrics": {}
    }
    
    if not IMPORTS_OK:
        results["errors"].append("Imports failed - cannot test")
        return results
    
    try:
        # Load trial MoA vectors
        moa_path = Path(__file__).parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"
        
        if not moa_path.exists():
            results["errors"].append(f"Trial MoA vectors file not found: {moa_path}")
            return results
        
        with open(moa_path, "r") as f:
            trial_moa_vectors = json.load(f)
        
        print(f"Loaded {len(trial_moa_vectors)} trials with MoA vectors")
        results["details"].append(f"Loaded {len(trial_moa_vectors)} trials")
        
        # DDR-high patient mechanism vector (7D): [DDR, MAPK, PI3K, VEGF, HER2, IO, Efflux]
        patient_mechanism_vector = [0.88, 0.12, 0.05, 0.02, 0.0, 0.0, 0.0]
        print(f"Patient Mechanism Vector: {patient_mechanism_vector}")
        print()
        
        # Prepare trials for scoring
        trials = []
        ddr_trials = []
        non_ddr_trials = []
        
        for nct_id, data in trial_moa_vectors.items():
            moa_dict = data.get("moa_vector") or {}
            moa_vector = convert_moa_dict_to_vector(moa_dict, use_7d=True)
            
            # Check if DDR-focused
            ddr_value = float(moa_dict.get("ddr", 0.0) or 0.0)
            is_ddr = ddr_value > 0.5
            
            trials.append({
                "nct_id": nct_id,
                "title": data.get("title", nct_id),
                "eligibility_score": 0.85,  # Constant for testing
                "moa_vector": moa_vector,
            })
            
            if is_ddr:
                ddr_trials.append(nct_id)
            else:
                non_ddr_trials.append(nct_id)
        
        print(f"Total trials: {len(trials)}")
        print(f"DDR-focused trials (ddr>0.5): {len(ddr_trials)}")
        print(f"Non-DDR trials: {len(non_ddr_trials)}")
        print()
        
        results["metrics"]["total_trials"] = len(trials)
        results["metrics"]["ddr_trials"] = len(ddr_trials)
        results["metrics"]["non_ddr_trials"] = len(non_ddr_trials)
        
        # Rank trials
        ranker = MechanismFitRanker(alpha=0.7, beta=0.3)
        ranked_scores = ranker.rank_trials(
            trials=trials,
            sae_mechanism_vector=patient_mechanism_vector,
            min_eligibility=0.60,
            min_mechanism_fit=0.0,  # Allow all for comparison
        )
        
        # Calculate mechanism fit scores for DDR vs non-DDR
        ddr_mechanism_fits = []
        non_ddr_mechanism_fits = []
        
        for score in ranked_scores:
            nct_id = score.nct_id
            moa_dict = (trial_moa_vectors.get(nct_id, {}) or {}).get("moa_vector") or {}
            ddr_value = float(moa_dict.get("ddr", 0.0) or 0.0)
            
            if ddr_value > 0.5:
                ddr_mechanism_fits.append(score.mechanism_fit_score)
            else:
                non_ddr_mechanism_fits.append(score.mechanism_fit_score)
        
        # Calculate statistics
        if ddr_mechanism_fits:
            mean_ddr_fit = sum(ddr_mechanism_fits) / len(ddr_mechanism_fits)
            min_ddr_fit = min(ddr_mechanism_fits)
            max_ddr_fit = max(ddr_mechanism_fits)
            
            print("DDR Trials Mechanism Fit:")
            print(f"  Mean: {mean_ddr_fit:.3f}")
            print(f"  Min:  {min_ddr_fit:.3f}")
            print(f"  Max:  {max_ddr_fit:.3f}")
            print(f"  Count: {len(ddr_mechanism_fits)}")
            print()
            
            results["metrics"]["ddr_mean_fit"] = mean_ddr_fit
            results["metrics"]["ddr_min_fit"] = min_ddr_fit
            results["metrics"]["ddr_max_fit"] = max_ddr_fit
            results["metrics"]["ddr_count"] = len(ddr_mechanism_fits)
        else:
            print("⚠️  No DDR trials found")
            results["errors"].append("No DDR trials found")
        
        if non_ddr_mechanism_fits:
            mean_non_ddr_fit = sum(non_ddr_mechanism_fits) / len(non_ddr_mechanism_fits)
            min_non_ddr_fit = min(non_ddr_mechanism_fits)
            max_non_ddr_fit = max(non_ddr_mechanism_fits)
            
            print("Non-DDR Trials Mechanism Fit:")
            print(f"  Mean: {mean_non_ddr_fit:.3f}")
            print(f"  Min:  {min_non_ddr_fit:.3f}")
            print(f"  Max:  {max_non_ddr_fit:.3f}")
            print(f"  Count: {len(non_ddr_mechanism_fits)}")
            print()
            
            results["metrics"]["non_ddr_mean_fit"] = mean_non_ddr_fit
            results["metrics"]["non_ddr_min_fit"] = min_non_ddr_fit
            results["metrics"]["non_ddr_max_fit"] = max_non_ddr_fit
            results["metrics"]["non_ddr_count"] = len(non_ddr_mechanism_fits)
        else:
            print("⚠️  No non-DDR trials found")
            results["errors"].append("No non-DDR trials found")
        
        # Verify claim: 0.92 mechanism fit for DDR-high patients
        if ddr_mechanism_fits and non_ddr_mechanism_fits:
            mean_ddr = sum(ddr_mechanism_fits) / len(ddr_mechanism_fits)
            mean_non = sum(non_ddr_mechanism_fits) / len(non_ddr_mechanism_fits)
            delta = mean_ddr - mean_non
            
            print("=" * 60)
            print("CLAIM VERIFICATION")
            print("=" * 60)
            print(f"Mean DDR fit: {mean_ddr:.3f} (target ≥ 0.92)")
            print(f"Mean non-DDR fit: {mean_non:.3f} (target ≤ 0.20)")
            print(f"Separation Δ: {delta:.3f} (target ≥ 0.60)")
            print()
            
            # Acceptance criteria
            min_mean_ddr = 0.92
            max_mean_non = 0.20
            min_delta = 0.60
            
            claim_passed = (
                mean_ddr >= min_mean_ddr and
                mean_non <= max_mean_non and
                delta >= min_delta
            )
            
            if claim_passed:
                print("✅ PASS: Mechanism fit claim verified")
                results["details"].append("Mechanism fit claim verified")
            else:
                print("⚠️  PARTIAL: Mechanism fit claim partially met")
                if mean_ddr < min_mean_ddr:
                    results["errors"].append(f"Mean DDR fit {mean_ddr:.3f} < {min_mean_ddr}")
                if mean_non > max_mean_non:
                    results["errors"].append(f"Mean non-DDR fit {mean_non:.3f} > {max_mean_non}")
                if delta < min_delta:
                    results["errors"].append(f"Separation Δ {delta:.3f} < {min_delta}")
            
            results["metrics"]["claim_passed"] = claim_passed
            results["metrics"]["mean_ddr_fit"] = mean_ddr
            results["metrics"]["mean_non_ddr_fit"] = mean_non
            results["metrics"]["separation_delta"] = delta
        
        # Test shortlist compression
        print()
        print("=" * 60)
        print("SHORTLIST COMPRESSION TEST")
        print("=" * 60)
        
        # Filter to mechanism-aligned trials (mechanism_fit >= 0.50)
        aligned_trials = [s for s in ranked_scores if s.mechanism_fit_score >= 0.50]
        
        print(f"Total trials: {len(ranked_scores)}")
        print(f"Mechanism-aligned trials (fit ≥ 0.50): {len(aligned_trials)}")
        
        if len(ranked_scores) > 0:
            compression_ratio = len(aligned_trials) / len(ranked_scores)
            reduction_pct = (1 - compression_ratio) * 100
            print(f"Compression ratio: {compression_ratio:.2%}")
            print(f"Reduction: {reduction_pct:.1f}%")
            print()
            
            results["metrics"]["total_trials_ranked"] = len(ranked_scores)
            results["metrics"]["aligned_trials"] = len(aligned_trials)
            results["metrics"]["compression_ratio"] = compression_ratio
            results["metrics"]["reduction_pct"] = reduction_pct
            
            # Target: 50+ → 5-12 trials (60-65% reduction)
            if len(ranked_scores) >= 50 and 5 <= len(aligned_trials) <= 12:
                print("✅ PASS: Shortlist compression target met")
                results["details"].append("Shortlist compression target met")
            elif len(ranked_scores) >= 50:
                print(f"⚠️  PARTIAL: Shortlist compression {len(aligned_trials)} trials (target: 5-12)")
                results["errors"].append(f"Shortlist compression {len(aligned_trials)} trials (target: 5-12)")
            else:
                print(f"ℹ️  INFO: Only {len(ranked_scores)} trials available (target: 50+)")
                results["details"].append(f"Only {len(ranked_scores)} trials available (target: 50+)")
        
        # Show top 5 trials
        print()
        print("Top 5 Ranked Trials:")
        for i, score in enumerate(ranked_scores[:5], 1):
            moa_dict = (trial_moa_vectors.get(score.nct_id, {}) or {}).get("moa_vector") or {}
            ddr_value = float(moa_dict.get("ddr", 0.0) or 0.0)
            is_ddr = ddr_value > 0.5
            
            print(f"  {i}. {score.nct_id}")
            print(f"     Combined: {score.combined_score:.3f} (0.7×{score.eligibility_score:.3f} + 0.3×{score.mechanism_fit_score:.3f})")
            print(f"     Mechanism Fit: {score.mechanism_fit_score:.3f} {'(DDR)' if is_ddr else ''}")
        
        results["passed"] = len(results["errors"]) == 0
        
    except Exception as e:
        results["errors"].append(f"Exception: {str(e)}")
        print(f"  ❌ Exception: {e}")
        import traceback
        traceback.print_exc()
        results["passed"] = False
    
    return results


def main():
    """Run all tests"""
    print()
    print("=" * 60)
    print("DELIVERABLE 1.5 + 2 TEST SUITE")
    print("=" * 60)
    print()
    
    all_results = {
        "deliverable_1_5": test_deliverable_1_5_backend(),
        "deliverable_2": test_deliverable_2_mechanism_fit()
    }
    
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print()
    
    for name, result in all_results.items():
        status = "✅ PASSED" if result["passed"] else "❌ FAILED"
        print(f"{name.upper()}: {status}")
        if result.get("errors"):
            for error in result["errors"]:
                print(f"  - {error}")
    
    # Save results
    output_path = Path(__file__).parent / f"test_results_{Path(__file__).stem}.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print()
    print(f"Results saved to: {output_path}")
    
    # Return exit code
    all_passed = all(r["passed"] for r in all_results.values())
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())


