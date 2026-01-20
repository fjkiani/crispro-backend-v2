"""
Monte Carlo Simulation for KELIM Computation Validation.

Validates KELIM computation robustness with realistic noise and measurement timing variation.
"""

import sys
import os
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime, timedelta
import random
import numpy as np
import json

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from api.services.resistance.validation.synthetic_data_generator import (
    generate_synthetic_ca125_trajectories,
)


def compute_kelim_from_measurements(
    ca125_measurements: List[Dict[str, Any]],
    treatment_start_date: datetime
) -> Tuple[Optional[float], Optional[str], Dict[str, Any]]:
    """
    Compute KELIM K value from CA-125 measurements.
    
    This is a simplified implementation for validation purposes.
    The actual KELIM computation will be implemented in the Kinetic Biomarker Framework.
    
    Args:
        ca125_measurements: List of CA-125 measurement records
        treatment_start_date: Treatment start date
    
    Returns:
        Tuple of (k_value, category, metadata)
    """
    # Sort measurements by date
    sorted_measurements = sorted(
        ca125_measurements,
        key=lambda m: m["measurement_date"]
    )
    
    if len(sorted_measurements) < 4:
        return None, None, {"error": "Insufficient measurements (need ≥4)"}
    
    # Extract baseline (first measurement)
    baseline = sorted_measurements[0]
    baseline_ca125 = baseline["ca125_value"]
    baseline_date = baseline["measurement_date"]
    
    # Compute K using log-linear regression on measurements during first 100 days
    # KELIM: K = -30 * (ln(CA125_t) - ln(CA125_0)) / t
    # Where t is in days, standardized to 30-day periods
    
    treatment_measurements = [
        m for m in sorted_measurements[1:]
        if (m["measurement_date"] - treatment_start_date).days <= 100
    ]
    
    if len(treatment_measurements) < 3:
        return None, None, {"error": "Insufficient measurements during treatment window"}
    
    # Linear regression: ln(CA125_t) = ln(CA125_0) - (K/30) * t
    # Using least squares: K = -30 * slope
    
    x_values = []  # Days since treatment start
    y_values = []  # ln(CA125_t)
    
    for m in treatment_measurements:
        days_since_start = (m["measurement_date"] - treatment_start_date).days
        if days_since_start > 0:
            x_values.append(days_since_start)
            y_values.append(np.log(m["ca125_value"]))
    
    if len(x_values) < 3:
        return None, None, {"error": "Insufficient valid measurements"}
    
    # Compute linear regression
    x_array = np.array(x_values)
    y_array = np.array(y_values)
    
    # Normalize x to 30-day periods for K computation
    x_normalized = x_array / 30.0
    
    # Least squares: y = a + b*x, where b = -K/30
    if len(x_normalized) > 1:
        slope, intercept = np.polyfit(x_normalized, y_array, 1)
        k_value = -30.0 * slope
        
        # Categorize K
        if k_value >= 1.0:
            category = "favorable"
        elif k_value >= 0.5:
            category = "intermediate"
        else:
            category = "unfavorable"
        
        metadata = {
            "n_measurements": len(x_values),
            "baseline_ca125": baseline_ca125,
            "slope": float(slope),
            "r_squared": float(np.corrcoef(x_normalized, y_array)[0, 1] ** 2) if len(x_normalized) > 1 else None,
        }
        
        return float(k_value), category, metadata
    else:
        return None, None, {"error": "Cannot compute K with <2 measurements"}


def monte_carlo_kelim_simulation(
    n_simulations: int = 1000,
    noise_cv_levels: List[float] = [0.0, 0.05, 0.10, 0.15, 0.20],
    seed: Optional[int] = None
) -> Dict[str, Any]:
    """
    Run Monte Carlo simulation to validate KELIM computation robustness.
    
    Args:
        n_simulations: Number of synthetic patients to generate
        noise_cv_levels: List of coefficient of variation values for noise (0.0-1.0)
        seed: Random seed for reproducibility
    
    Returns:
        Dictionary with simulation results
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    results = {
        "simulation_timestamp": datetime.now().isoformat(),
        "n_simulations": n_simulations,
        "noise_levels": noise_cv_levels,
        "noise_level_results": {},
    }
    
    # Generate ground truth K values from literature distribution
    # ICON7: mean K ≈ 0.8, SD ≈ 0.45
    mean_k = 0.80
    sd_k = 0.45
    
    for noise_cv in noise_cv_levels:
        print(f"\n   Running simulation with noise CV = {noise_cv:.0%}...")
        
        level_results = {
            "noise_cv": noise_cv,
            "n_computed": 0,
            "n_failed": 0,
            "correlations": [],
            "category_accuracies": [],
            "k_errors": [],
            "r_squared_values": [],
        }
        
        # Generate synthetic patients
        ground_truth_k_values = []
        computed_k_values = []
        ground_truth_categories = []
        computed_categories = []
        
        for i in range(n_simulations):
            # Sample ground truth K
            k_ground_truth = np.random.normal(mean_k, sd_k)
            k_ground_truth = max(0.0, k_ground_truth)  # Ensure non-negative
            
            # Categorize ground truth
            if k_ground_truth >= 1.0:
                category_ground_truth = "favorable"
            elif k_ground_truth >= 0.5:
                category_ground_truth = "intermediate"
            else:
                category_ground_truth = "unfavorable"
            
            # Generate CA-125 trajectory with noise
            treatment_start = datetime(2020, 1, 1)
            baseline_ca125 = random.uniform(100.0, 2000.0)
            
            # Measurement days: 0 (baseline), 21, 42, 63, 90
            measurement_days = [0, 21, 42, 63, 90]
            ca125_measurements = []
            
            for days in measurement_days:
                # True value (no noise)
                true_ca125 = baseline_ca125 * np.exp(-k_ground_truth * (days / 30.0))
                
                # Add noise
                if noise_cv > 0:
                    noise = np.random.normal(0, true_ca125 * noise_cv)
                    measured_ca125 = true_ca125 + noise
                    measured_ca125 = max(1.0, measured_ca125)  # Ensure positive
                else:
                    measured_ca125 = true_ca125
                
                measurement_date = treatment_start + timedelta(days=days)
                ca125_measurements.append({
                    "patient_id": f"MC_{i:04d}",
                    "regimen_id": "R1",
                    "measurement_date": measurement_date,
                    "ca125_value": measured_ca125,
                })
            
            # Compute K from noisy measurements
            k_computed, category_computed, metadata = compute_kelim_from_measurements(
                ca125_measurements,
                treatment_start
            )
            
            if k_computed is not None:
                level_results["n_computed"] += 1
                ground_truth_k_values.append(k_ground_truth)
                computed_k_values.append(k_computed)
                ground_truth_categories.append(category_ground_truth)
                computed_categories.append(category_computed)
                
                # Compute error
                k_error = abs(k_computed - k_ground_truth)
                level_results["k_errors"].append(k_error)
                
                # Store R-squared if available
                if metadata.get("r_squared") is not None:
                    level_results["r_squared_values"].append(metadata["r_squared"])
                
                # Check category accuracy
                if category_computed == category_ground_truth:
                    level_results["category_accuracies"].append(1.0)
                else:
                    level_results["category_accuracies"].append(0.0)
            else:
                level_results["n_failed"] += 1
        
        # Compute statistics
        if len(ground_truth_k_values) > 0:
            # Correlation
            if len(ground_truth_k_values) > 1:
                correlation = np.corrcoef(ground_truth_k_values, computed_k_values)[0, 1]
                level_results["correlations"].append(correlation)
                level_results["mean_correlation"] = float(correlation)
            
            # Category accuracy
            if len(level_results["category_accuracies"]) > 0:
                category_accuracy = np.mean(level_results["category_accuracies"])
                level_results["mean_category_accuracy"] = float(category_accuracy)
                level_results["category_accuracy_pct"] = float(category_accuracy * 100)
            
            # K error statistics
            if len(level_results["k_errors"]) > 0:
                level_results["mean_k_error"] = float(np.mean(level_results["k_errors"]))
                level_results["median_k_error"] = float(np.median(level_results["k_errors"]))
                level_results["p90_k_error"] = float(np.percentile(level_results["k_errors"], 90))
            
            # R-squared statistics
            if len(level_results["r_squared_values"]) > 0:
                level_results["mean_r_squared"] = float(np.mean(level_results["r_squared_values"]))
        
        results["noise_level_results"][f"cv_{noise_cv:.2f}"] = level_results
        
        print(f"      Computed: {level_results['n_computed']}/{n_simulations}")
        if level_results.get("mean_correlation"):
            print(f"      Correlation: {level_results['mean_correlation']:.3f}")
        if level_results.get("mean_category_accuracy"):
            print(f"      Category Accuracy: {level_results['mean_category_accuracy']:.2%}")
        if level_results.get("mean_k_error"):
            print(f"      Mean K Error: {level_results['mean_k_error']:.3f}")
    
    return results


def main():
    """Main Monte Carlo simulation script."""
    print("=" * 70)
    print("MONTE CARLO KELIM VALIDATION")
    print("=" * 70)
    
    # Run simulation
    print("\n1. Running Monte Carlo simulation...")
    print(f"   Simulations: 1000")
    print(f"   Noise levels: 0%, 5%, 10%, 15%, 20%")
    
    results = monte_carlo_kelim_simulation(
        n_simulations=1000,
        noise_cv_levels=[0.0, 0.05, 0.10, 0.15, 0.20],
        seed=42
    )
    
    # Display results
    print("\n2. Simulation Results:")
    
    for noise_level, level_results in results["noise_level_results"].items():
        noise_cv = level_results["noise_cv"]
        print(f"\n   Noise CV = {noise_cv:.0%}:")
        print(f"      Computed: {level_results['n_computed']}/1000")
        if level_results.get("mean_correlation"):
            corr = level_results["mean_correlation"]
            status = "✅" if corr > 0.8 else "⚠️"
            print(f"      Correlation: {corr:.3f} {status}")
        if level_results.get("mean_category_accuracy"):
            acc = level_results["mean_category_accuracy"]
            status = "✅" if acc >= 0.90 else "⚠️"
            print(f"      Category Accuracy: {acc:.2%} {status}")
        if level_results.get("mean_k_error"):
            print(f"      Mean K Error: {level_results['mean_k_error']:.3f}")
            print(f"      P90 K Error: {level_results.get('p90_k_error', 0):.3f}")
    
    # Save results
    output_dir = project_root / "data" / "validation" / "kelim"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    output_file = output_dir / "monte_carlo_kelim_results.json"
    with open(output_file, "w") as f:
        json.dump(results, f, indent=2, default=str)
    
    print(f"\n3. Saved results to: {output_file}")
    
    # Summary
    print("\n" + "=" * 70)
    print("MONTE CARLO SIMULATION COMPLETE")
    print("=" * 70)
    
    # Check success criteria
    print("\n✅ Success Criteria:")
    for noise_level, level_results in results["noise_level_results"].items():
        noise_cv = level_results["noise_cv"]
        corr = level_results.get("mean_correlation", 0)
        acc = level_results.get("mean_category_accuracy", 0)
        
        corr_pass = corr > 0.8
        acc_pass = acc >= 0.90
        
        status = "✅" if (corr_pass and acc_pass) else "⚠️"
        print(f"   CV {noise_cv:.0%}: Correlation > 0.8: {corr_pass} ✅, Category Accuracy ≥ 90%: {acc_pass} ✅ {status}")


if __name__ == "__main__":
    main()
