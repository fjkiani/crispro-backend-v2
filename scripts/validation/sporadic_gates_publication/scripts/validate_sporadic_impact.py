
import json
import sys
import os
from pathlib import Path
from typing import Dict, List, Any

# FALLBACK TO MAIN DIRECTORY FOR CODE AND DATA
MAIN_DIR = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal")
sys.path.insert(0, str(MAIN_DIR))

from api.services.efficacy_orchestrator.sporadic_gates import apply_sporadic_gates
from api.services.input_completeness import compute_input_completeness

def run_real_world_impact():
    print("# Sporadic Gates: Real-World Impact Analysis (TCGA-OV)")
    
    data_path = MAIN_DIR / "biomarker_enriched_cohorts" / "data" / "tcga_ov_enriched_v2.json"
    
    if not data_path.exists():
        print(f"❌ Missing TCGA-OV data at: {data_path}")
        return

    print(f"Loading data from: {data_path}")
    with open(data_path) as f:
        data = json.load(f)
    
    # Fix: patients are inside cohort object
    patients = data.get("cohort", {}).get("patients", [])
    if not patients:
        # Fallback if structure is different than expected
        patients = data.get("patients", [])
        
    print(f"Loaded {len(patients)} patients from TCGA-OV.")

    # Define drugs to test
    drugs = [
        {"name": "Olaparib", "class": "PARP inhibitor", "moa": "PARP inhibition"},
        {"name": "Pembrolizumab", "class": "checkpoint_inhibitor", "moa": "PD-1 blockade"},
        {"name": "Generic Chemotherapy", "class": "cytotoxic", "moa": "DNA damaging"}
    ]

    stats = {
        "total_patients": len(patients),
        "gate_triggers": {
            "PARP_PENALTY": 0,
            "PARP_RESCUE": 0,
            "IO_BOOST": 0,
            "CONFIDENCE_CAP": 0
        },
        "level_distribution": {"L0": 0, "L1": 0, "L2": 0},
        "efficacy_deltas": [],
        "confidence_deltas": []
    }

    results = []

    for patient in patients:
        p_id = patient.get("patient_id")
        
        # Prepare TumorContext
        hrd_map = {"HRD-High": 50, "HRD-Intermediate": 30, "HRD-Low": 10}
        hrd_score = hrd_map.get(patient.get("hrd_proxy"), 0)
        
        # Map germline status
        germline = patient.get("germline_brca_status", "unknown")
        if germline == "pathogenic":
            germline_status = "positive"
        elif germline == "wildtype":
            germline_status = "negative"
        else:
            germline_status = "unknown"

        tumor_context = {
            "tmb": patient.get("tmb"),
            "msi_status": patient.get("msi_status"),
            "hrd_score": hrd_score,
            "somatic_mutations": [patient.get("brca_somatic")] if patient.get("brca_somatic") else []
        }

        # Compute completeness level
        completeness = compute_input_completeness(tumor_context=tumor_context)
        stats["level_distribution"][completeness.level] += 1
        
        level_to_score = {"L0": 0.1, "L1": 0.5, "L2": 0.9}
        tumor_context["completeness_score"] = level_to_score[completeness.level]

        patient_results = {"patient_id": p_id, "drugs": []}

        for drug in drugs:
            base_eff = 0.7
            base_conf = 0.8
            
            adj_eff, adj_conf, rationale = apply_sporadic_gates(
                drug_name=drug["name"],
                drug_class=drug["class"],
                moa=drug["moa"],
                efficacy_score=base_eff,
                confidence=base_conf,
                germline_status=germline_status,
                tumor_context=tumor_context
            )

            eff_delta = adj_eff - base_eff
            conf_delta = adj_conf - base_conf
            
            if abs(eff_delta) > 0.001 or abs(conf_delta) > 0.001:
                stats["efficacy_deltas"].append(eff_delta)
                stats["confidence_deltas"].append(conf_delta)
                
                gates = [r["gate"] for r in rationale if "gate" in r]
                for g in gates:
                    if "PARP_HRD_LOW" in g or "PARP_UNKNOWN" in g or "PARP_UNKNOWN_GERMLINE" in g:
                        stats["gate_triggers"]["PARP_PENALTY"] += 1
                    if "PARP_HRD_RESCUE" in g:
                        stats["gate_triggers"]["PARP_RESCUE"] += 1
                    if "IO" in g:
                        stats["gate_triggers"]["IO_BOOST"] += 1
                    if "CONFIDENCE_CAP" in g:
                        stats["gate_triggers"]["CONFIDENCE_CAP"] += 1

            patient_results["drugs"].append({
                "name": drug["name"],
                "base_eff": base_eff,
                "adj_eff": adj_eff,
                "base_conf": base_conf,
                "adj_conf": adj_conf,
                "gates": [r["gate"] for r in rationale if "gate" in r]
            })
        
        results.append(patient_results)

    # Summarize
    print("\n## Impact Summary")
    print(f"- Total Patients: {stats['total_patients']}")
    print(f"- Completeness Levels: {stats['level_distribution']}")
    print(f"- Gate Trigger Counts (per drug-patient pair):")
    for gate, count in stats["gate_triggers"].items():
        print(f"  - {gate}: {count}")
    
    if stats["efficacy_deltas"]:
        avg_eff_delta = sum(stats["efficacy_deltas"]) / len(stats["efficacy_deltas"])
        print(f"- Avg Efficacy Delta (when triggered): {avg_eff_delta:.3f}")
    
    if stats["confidence_deltas"]:
        avg_conf_delta = sum(stats["confidence_deltas"]) / len(stats["confidence_deltas"])
        print(f"- Avg Confidence Delta (when triggered): {avg_conf_delta:.3f}")

    # Write receipt
    receipt_dir = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/publications/sporadic_cancer/receipts")
    receipt_dir.mkdir(parents=True, exist_ok=True)
    output_path = receipt_dir / "sporadic_gates_real_world_impact.json"
    with open(output_path, "w") as f:
        json.dump({"stats": stats, "results_sample": results[:10]}, f, indent=2)
    print(f"\n✅ Receipt saved to: {output_path}")

if __name__ == "__main__":
    run_real_world_impact()
