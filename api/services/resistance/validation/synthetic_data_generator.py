"""
Synthetic Data Generator for Timing & Chemosensitivity Engine Validation.

Generates synthetic patient journeys with known ground truth PFI/PTPI/TFI/PFS/OS
and CA-125 trajectories with known K values for proxy validation.
"""

from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timedelta
import random
import numpy as np
import json

from api.services.resistance.config.timing_config import get_timing_config


def generate_synthetic_timing_test_cases(
    n_patients: int = 100,
    disease_site: str = "ovary",
    seed: Optional[int] = None
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Generate synthetic patient journeys with known ground truth timing metrics.
    
    Args:
        n_patients: Number of synthetic patients to generate
        disease_site: Disease site (ovary, breast, etc.)
        seed: Random seed for reproducibility
    
    Returns:
        Dictionary with:
        - regimen_table: List of regimen records with known timing
        - survival_table: List of survival records
        - clinical_table: List of clinical records
        - ground_truth: Dictionary of known timing metrics per patient/regimen
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    base_date = datetime(2020, 1, 1)
    config = get_timing_config(disease_site)
    
    regimen_table = []
    survival_table = []
    clinical_table = []
    ground_truth = {}  # {(patient_id, regimen_id): {PFI_days: X, PTPI_days: Y, ...}}
    
    for i in range(n_patients):
        patient_id = f"SYNTH_{disease_site.upper()}_{i:03d}"
        
        # Patient clinical data
        clinical_table.append({
            "patient_id": patient_id,
            "disease_site": disease_site,
            "tumor_subtype": "HGSOC" if disease_site == "ovary" else None
        })
        
        # Generate patient journey (1-4 regimens)
        n_regimens = random.randint(1, 4)
        regimens = []
        
        current_date = base_date + timedelta(days=random.randint(0, 365))
        prior_platinum_end = None
        prior_regimen_end = None
        
        for j in range(n_regimens):
            regimen_id = f"R{j+1}"
            
            # Regimen type
            if j == 0:
                # First regimen is usually platinum
                regimen_type = "platinum" if random.random() < 0.8 else "non_platinum_chemo"
            else:
                # Subsequent regimens vary
                weights = {"platinum": 0.3, "PARPi": 0.2, "non_platinum_chemo": 0.4, "ATR_inhibitor": 0.1}
                regimen_type = random.choices(list(weights.keys()), weights=list(weights.values()))[0]
            
            # Regimen dates
            regimen_start_date = current_date
            regimen_duration_days = random.randint(90, 270)  # 3-9 months
            regimen_end_date = regimen_start_date + timedelta(days=regimen_duration_days)
            
            # Treatment line
            line_of_therapy = j + 1
            setting = "frontline" if j == 0 else ("first_recurrence" if j == 1 else "later_recurrence")
            
            # Platinum-specific fields
            last_platinum_dose_date = None
            if regimen_type == "platinum":
                last_platinum_dose_date = regimen_end_date - timedelta(days=random.randint(7, 21))
                prior_platinum_end = last_platinum_dose_date
            
            # Progression date (may occur during or after regimen)
            progression_date = None
            if j < n_regimens - 1:  # Not the last regimen
                if random.random() < 0.8:  # 80% progress
                    # Progression occurs after regimen end (for PFI calculation)
                    progression_days_after_end = random.randint(30, 365)
                    progression_date = regimen_end_date + timedelta(days=progression_days_after_end)
            
            # Best response
            best_response = random.choice(["CR", "PR", "SD", "PD"])
            if best_response in ["CR", "PR"]:
                best_response_date = regimen_start_date + timedelta(days=random.randint(42, 126))
            else:
                best_response_date = None
            
            regimen = {
                "patient_id": patient_id,
                "regimen_id": regimen_id,
                "regimen_start_date": regimen_start_date,
                "regimen_end_date": regimen_end_date,
                "regimen_type": regimen_type,
                "line_of_therapy": line_of_therapy,
                "setting": setting,
                "last_platinum_dose_date": last_platinum_dose_date,
                "progression_date": progression_date,
                "best_response": best_response,
                "best_response_date": best_response_date,
            }
            
            regimens.append(regimen)
            
            # Compute ground truth timing metrics
            truth = {}
            
            # TFI (Treatment-Free Interval)
            if j > 0 and prior_regimen_end:
                tfi_days = (regimen_start_date - prior_regimen_end).days
                truth["TFI_days"] = max(0, tfi_days)  # Ensure non-negative
            else:
                truth["TFI_days"] = None
            
            # PFI (Platinum-Free Interval) - for platinum regimens
            if regimen_type == "platinum" and prior_platinum_end:
                # Find next platinum or progression
                next_platinum_start = None
                if j < len(regimens) - 1:
                    # Check if next regimen is platinum
                    for future_regimen in regimens:
                        if future_regimen["regimen_type"] == "platinum" and future_regimen["regimen_start_date"] > regimen_start_date:
                            next_platinum_start = future_regimen["regimen_start_date"]
                            break
                
                # PFI event: next platinum OR progression (whichever comes first)
                event_dates = []
                if next_platinum_start:
                    event_dates.append(next_platinum_start)
                if progression_date:
                    event_dates.append(progression_date)
                
                if event_dates:
                    pfi_event_date = min(event_dates)
                    pfi_days = (pfi_event_date - prior_platinum_end).days
                    truth["PFI_days"] = max(0, pfi_days)
                    
                    # Categorize PFI
                    pfi_cutpoints = config.get("pfi_cutpoints_days", [180, 365])
                    if pfi_days < pfi_cutpoints[0]:
                        truth["PFI_category"] = "<6m"
                    elif pfi_days < pfi_cutpoints[1]:
                        truth["PFI_category"] = "6-12m"
                    else:
                        truth["PFI_category"] = ">12m"
                else:
                    truth["PFI_days"] = None
                    truth["PFI_category"] = None
            else:
                truth["PFI_days"] = None
                truth["PFI_category"] = None
            
            # PTPI (Platinum-to-PARPi Interval) - for DDR-targeted regimens
            if regimen_type in ["PARPi", "ATR_inhibitor", "WEE1_inhibitor"] and prior_platinum_end:
                ptpi_days = (regimen_start_date - prior_platinum_end).days
                truth["PTPI_days"] = max(0, ptpi_days)
            else:
                truth["PTPI_days"] = None
            
            # Store ground truth
            ground_truth[(patient_id, regimen_id)] = truth
            
            # Update for next regimen
            prior_regimen_end = regimen_end_date
            current_date = regimen_end_date + timedelta(days=random.randint(30, 180))  # 1-6 months between regimens
        
        regimen_table.extend(regimens)
        
        # Survival data
        last_regimen_end = regimens[-1]["regimen_end_date"] if regimens else base_date
        followup_duration = random.randint(180, 1080)  # 6-36 months
        last_followup_date = last_regimen_end + timedelta(days=followup_duration)
        
        # Vital status (80% alive, 20% dead)
        vital_status = "Dead" if random.random() < 0.2 else "Alive"
        death_date = None
        if vital_status == "Dead":
            death_date = last_regimen_end + timedelta(days=random.randint(60, followup_duration))
        
        survival_table.append({
            "patient_id": patient_id,
            "vital_status": vital_status,
            "death_date": death_date,
            "last_followup_date": last_followup_date,
        })
    
    return {
        "regimen_table": regimen_table,
        "survival_table": survival_table,
        "clinical_table": clinical_table,
        "ground_truth": ground_truth,
    }


def generate_synthetic_ca125_trajectories(
    n_patients: int = 50,
    disease_site: str = "ovary",
    seed: Optional[int] = None,
    noise_cv: float = 0.1  # Coefficient of variation for measurement noise
) -> Dict[str, Any]:
    """
    Generate synthetic CA-125 trajectories with known K values for KELIM validation.
    
    Args:
        n_patients: Number of synthetic patients to generate
        disease_site: Disease site (must be "ovary" for CA-125)
        seed: Random seed for reproducibility
        noise_cv: Coefficient of variation for measurement noise (0.0-1.0)
    
    Returns:
        Dictionary with:
        - ca125_measurements: List of CA-125 measurement records
        - treatment_start_dates: Dictionary of {patient_id: {regimen_id: start_date}}
        - ground_truth_k: Dictionary of {(patient_id, regimen_id): k_value}
        - ground_truth_category: Dictionary of {(patient_id, regimen_id): category}
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
    
    if disease_site != "ovary":
        # CA-125 is only used for ovarian cancer
        return {
            "ca125_measurements": [],
            "treatment_start_dates": {},
            "ground_truth_k": {},
            "ground_truth_category": {},
        }
    
    base_date = datetime(2020, 1, 1)
    
    ca125_measurements = []
    treatment_start_dates = {}
    ground_truth_k = {}
    ground_truth_category = {}
    
    # KELIM distribution from literature (ICON7: ~40% favorable, mean K ≈ 0.8)
    # Favorable: K ≥ 1.0, Intermediate: 0.5-1.0, Unfavorable: <0.5
    k_distribution_mean = 0.8
    k_distribution_std = 0.4
    
    for i in range(n_patients):
        patient_id = f"SYNTH_OVARY_CA125_{i:03d}"
        regimen_id = "R1"  # Focus on first regimen for now
        
        # Sample K value from distribution
        k_ground_truth = np.random.normal(k_distribution_mean, k_distribution_std)
        k_ground_truth = max(0.0, k_ground_truth)  # Ensure non-negative
        
        # Categorize K
        if k_ground_truth >= 1.0:
            category = "favorable"
        elif k_ground_truth >= 0.5:
            category = "intermediate"
        else:
            category = "unfavorable"
        
        ground_truth_k[(patient_id, regimen_id)] = round(k_ground_truth, 2)
        ground_truth_category[(patient_id, regimen_id)] = category
        
        # Treatment start date
        treatment_start = base_date + timedelta(days=random.randint(0, 365))
        treatment_start_dates[(patient_id, regimen_id)] = treatment_start
        
        # Baseline CA-125 (typically 100-2000 U/mL)
        baseline_ca125 = random.uniform(100.0, 2000.0)
        
        # Generate measurements: baseline + ≥3 during treatment (first 100 days)
        measurement_days = [0]  # Baseline at day 0 (treatment start)
        
        # Add measurements during treatment (days 21, 42, 63, 90 are common)
        available_days = [21, 42, 63, 90]
        n_measurements_during_treatment = random.randint(3, 4)  # 3-4 measurements during treatment
        selected_days = random.sample(available_days, n_measurements_during_treatment)
        measurement_days.extend(selected_days)
        measurement_days.sort()
        
        # Generate CA-125 values using exponential decay model: CA-125(t) = CA-125(0) * exp(-K * t/30)
        # t is in days, K is per 30-day period (standardized)
        for days in measurement_days:
            # Compute true value without noise
            true_ca125 = baseline_ca125 * np.exp(-k_ground_truth * (days / 30.0))
            
            # Add measurement noise
            if noise_cv > 0:
                noise = np.random.normal(0, true_ca125 * noise_cv)
                measured_ca125 = true_ca125 + noise
                measured_ca125 = max(1.0, measured_ca125)  # Ensure positive
            else:
                measured_ca125 = true_ca125
            
            measurement_date = treatment_start + timedelta(days=days)
            
            ca125_measurements.append({
                "patient_id": patient_id,
                "regimen_id": regimen_id,
                "measurement_date": measurement_date,
                "ca125_value": round(measured_ca125, 1),
            })
    
    return {
        "ca125_measurements": ca125_measurements,
        "treatment_start_dates": treatment_start_dates,
        "ground_truth_k": ground_truth_k,
        "ground_truth_category": ground_truth_category,
    }


def save_synthetic_data(
    timing_data: Dict[str, Any],
    ca125_data: Dict[str, Any],
    output_dir: str = "data/validation/synthetic"
) -> Dict[str, str]:
    """
    Save synthetic data to JSON files.
    
    Args:
        timing_data: Output from generate_synthetic_timing_test_cases()
        ca125_data: Output from generate_synthetic_ca125_trajectories()
        output_dir: Directory to save files
    
    Returns:
        Dictionary of file paths saved
    """
    import os
    
    os.makedirs(output_dir, exist_ok=True)
    
    saved_files = {}
    
    # Save timing data
    timing_output = {
        "regimen_table": [
            {**r, "regimen_start_date": r["regimen_start_date"].isoformat(), 
             "regimen_end_date": r["regimen_end_date"].isoformat(),
             "last_platinum_dose_date": r["last_platinum_dose_date"].isoformat() if r["last_platinum_dose_date"] else None,
             "progression_date": r["progression_date"].isoformat() if r["progression_date"] else None,
             "best_response_date": r["best_response_date"].isoformat() if r["best_response_date"] else None}
            for r in timing_data["regimen_table"]
        ],
        "survival_table": [
            {**s, "death_date": s["death_date"].isoformat() if s["death_date"] else None,
             "last_followup_date": s["last_followup_date"].isoformat()}
            for s in timing_data["survival_table"]
        ],
        "clinical_table": timing_data["clinical_table"],
        "ground_truth": {
            f"{patient_id}_{regimen_id}": truth
            for (patient_id, regimen_id), truth in timing_data["ground_truth"].items()
        }
    }
    
    timing_file = os.path.join(output_dir, "synthetic_timing_test_cases.json")
    with open(timing_file, "w") as f:
        json.dump(timing_output, f, indent=2)
    saved_files["timing_data"] = timing_file
    
    # Save CA-125 data
    ca125_output = {
        "ca125_measurements": [
            {**m, "measurement_date": m["measurement_date"].isoformat()}
            for m in ca125_data["ca125_measurements"]
        ],
        "treatment_start_dates": {
            f"{patient_id}_{regimen_id}": date.isoformat()
            for (patient_id, regimen_id), date in ca125_data["treatment_start_dates"].items()
        },
        "ground_truth_k": {
            f"{patient_id}_{regimen_id}": k
            for (patient_id, regimen_id), k in ca125_data["ground_truth_k"].items()
        },
        "ground_truth_category": ca125_data["ground_truth_category"]
    }
    
    ca125_file = os.path.join(output_dir, "synthetic_ca125_trajectories.json")
    with open(ca125_file, "w") as f:
        json.dump(ca125_output, f, indent=2)
    saved_files["ca125_data"] = ca125_file
    
    return saved_files


if __name__ == "__main__":
    # Generate and save synthetic data
    print("=" * 70)
    print("GENERATING SYNTHETIC VALIDATION DATA")
    print("=" * 70)
    
    # Timing test cases
    print("\n1. Generating synthetic timing test cases...")
    timing_data = generate_synthetic_timing_test_cases(n_patients=100, disease_site="ovary", seed=42)
    print(f"   Generated {len(timing_data['regimen_table'])} regimens across {len(timing_data['clinical_table'])} patients")
    
    # CA-125 trajectories
    print("\n2. Generating synthetic CA-125 trajectories...")
    ca125_data = generate_synthetic_ca125_trajectories(n_patients=50, disease_site="ovary", seed=42, noise_cv=0.1)
    print(f"   Generated {len(ca125_data['ca125_measurements'])} CA-125 measurements for {len(ca125_data['ground_truth_k'])} patients")
    
    # Save to files
    print("\n3. Saving synthetic data...")
    saved_files = save_synthetic_data(timing_data, ca125_data)
    print(f"   Saved timing data to: {saved_files['timing_data']}")
    print(f"   Saved CA-125 data to: {saved_files['ca125_data']}")
    
    print("\n" + "=" * 70)
    print("SYNTHETIC DATA GENERATION COMPLETE")
    print("=" * 70)
