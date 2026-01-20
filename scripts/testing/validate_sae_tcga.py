import json
import numpy as np
from sklearn.metrics import roc_auc_score, roc_curve, classification_report
import matplotlib.pyplot as plt
import sys
import os

# Add the parent directory of api to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from api.services.sae_feature_service import compute_sae_features

# Placeholder for infer_variant_type
def infer_variant_type(patient_input):
    hgvs_p = patient_input.get("hgvs_p", "")
    if not hgvs_p:
        return "UNKNOWN"

    # Check for frameshift deletions/insertions (common in BRCA)
    if "fs" in hgvs_p:
        return "FRAMESHIFT"
    # Check for direct deletions/insertions
    if "del" in hgvs_p or "ins" in hgvs_p:
        return "INDEL"
    # Check for stop-gain mutations
    if "*" in hgvs_p:
        return "STOP_GAIN"
    # Check for splice site variants (simplified, can be more complex)
    if "_splice" in hgvs_p or "spl" in hgvs_p:
        return "SPLICE_SITE"
    # Check for missense mutations (e.g., A123B)
    if len(hgvs_p) > 1 and hgvs_p[0].isalpha() and hgvs_p[-1].isalpha() and hgvs_p[1:-1].isdigit():
        return "MISSENSE"
    # Default to SNV if none of the above more specific types match
    return "SNV"


def main():
    # Load TCGA data
    tcga_file_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', 'tools', 'benchmarks', 'hrd_tcga_ov_labeled_sample_use_evo.json')
    if not os.path.exists(tcga_file_path):
        print(f"Error: TCGA data file not found at {tcga_file_path}")
        sys.exit(1)

    with open(tcga_file_path) as f:
        tcga_data = json.load(f)

    # Compute SAE for each patient
    results = []
    for patient in tcga_data['results']:
        # Extract tumor context
        tumor_context = {
            "somatic_mutations": [{
                "gene": patient["input"]["gene"],
                "hgvs_p": patient["input"]["hgvs_p"],
                "variant_type": infer_variant_type(patient["input"])
            }],
            # For now, HRD score is not directly from SAE, keeping it as placeholder or removing if not used
            # "hrd_score": infer_hrd_from_mutations(patient["input"]) / 100.0, # Pass HRD as 0-1 for dna_repair_capacity
            "hrd_score": 0.0, # Placeholder until real HRD from SAE
            "tmb_score": patient["input"].get("tmb_score", 5.0),  # Use actual TMB if available, else default
            "msi_status": patient["input"].get("msi_status", "MSS") # Use actual MSI if available, else default
        }

        # *** REVERTING TO ACTUAL SAE FEATURE COMPUTATION WITH PLACEHOLDER INPUTS ***
        # The artificial signal generation proved the AUROC pipeline works. Now, we revert
        # to calling the actual compute_sae_features with placeholder insights and pathway scores.
        # The next step will be to provide REAL, Evo2-derived insights and pathway scores.
        
        # Placeholder for insights_bundle and pathway_scores
        insights_bundle = {"essentiality": 0.5, "regulatory": 0.5} # Mock data
        pathway_scores = {"ddr": 0.5, "mapk": 0.5, "pi3k": 0.5, "vegf": 0.5, "her2": 0.5} # Mock data

        sae_features = compute_sae_features(
            insights_bundle=insights_bundle,
            pathway_scores=pathway_scores,
            tumor_context=tumor_context
        )
        dna_repair_capacity_score = sae_features.get("dna_repair_capacity", 0.0)

        results.append({
            "patient_id": patient["input"].get("sample_id"),
            "gene": patient["input"]["gene"],
            "dna_repair_capacity": dna_repair_capacity_score,
            "pathway_burden_ddr": patient["input"].get("ddr_pathway_burden", dna_repair_capacity_score), # Use inferred HRD as DDR burden proxy
            "platinum_response": int(patient["input"]["outcome_platinum"])
        })

    # --- Diagnostic prints, Alpha! ---
    dna_repair_capacities = [r["dna_repair_capacity"] for r in results]
    platinum_responses = [r["platinum_response"] for r in results]

    print(f"\nDiagnostic: Min DNA Repair Capacity: {min(dna_repair_capacities):.3f}")
    print(f"Diagnostic: Max DNA Repair Capacity: {max(dna_repair_capacities):.3f}")
    print(f"Diagnostic: Mean DNA Repair Capacity: {np.mean(dna_repair_capacities):.3f}")
    print(f"Diagnostic: Std Dev DNA Repair Capacity: {np.std(dna_repair_capacities):.3f}")
    print(f"Diagnostic: Platinum Response Counts (0/1): {np.unique(platinum_responses, return_counts=True)}")

    # --- New Diagnostic: Gene Distribution per Platinum Response, Alpha! ---
    brca1_2_platinum_1 = 0
    brca1_2_platinum_0 = 0
    other_gene_platinum_1 = 0
    other_gene_platinum_0 = 0

    for patient in tcga_data['results']:
        gene = patient["input"]["gene"].upper()
        platinum_outcome = int(patient["input"]["outcome_platinum"])

        if gene in ["BRCA1", "BRCA2"]:
            if platinum_outcome == 1:
                brca1_2_platinum_1 += 1
            else:
                brca1_2_platinum_0 += 1
        else:
            if platinum_outcome == 1:
                other_gene_platinum_1 += 1
            else:
                other_gene_platinum_0 += 1

    print(f"\nDiagnostic: BRCA1/2 mutations in Platinum Response 1: {brca1_2_platinum_1}")
    print(f"Diagnostic: BRCA1/2 mutations in Platinum Response 0: {brca1_2_platinum_0}")
    print(f"Diagnostic: Other genes in Platinum Response 1: {other_gene_platinum_1}")
    print(f"Diagnostic: Other genes in Platinum Response 0: {other_gene_platinum_0}")

    # Extract ground truth and predictions
    y_true = [r["platinum_response"] for r in results]
    y_scores = [r["dna_repair_capacity"] for r in results]

    # AUROC
    auroc = roc_auc_score(y_true, y_scores)
    print(f"\nDNA Repair Capacity AUROC: {auroc:.3f}")

    # ROC curve
    fpr, tpr, thresholds = roc_curve(y_true, y_scores)
    plt.figure(figsize=(8, 6))
    plt.plot(fpr, tpr, label=f'ROC Curve (AUROC={auroc:.3f})')
    plt.plot([0, 1], [0, 1], 'k--', label='Random Classifier')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title('DNA Repair Capacity vs. Platinum Response (TCGA Validation)')
    plt.legend()
    plt.savefig('sae_validation_roc_curve.png')
    print("ROC curve saved to sae_validation_roc_curve.png")

    # Classification report at optimal threshold
    optimal_idx = np.argmax(tpr - fpr)
    optimal_threshold = thresholds[optimal_idx]
    y_pred = [1 if score > optimal_threshold else 0 for score in y_scores]
    print(f"\nOptimal Threshold: {optimal_threshold:.3f}")
    print("Classification Report at Optimal Threshold:")
    print(classification_report(y_true, y_pred))

    # Compare to published HRD scores (benchmark) - as per SAE_VALIDATION_STRATEGY.mdc
    print("\n--- Benchmark Comparison (from SAE_VALIDATION_STRATEGY.mdc) ---")
    print("Published HRD scores (MyChoice CDx) AUROC for platinum response: 0.60-0.75")
    print("Target AUROC for DNA Repair Capacity: >0.70 (reasonable for first version)")

if __name__ == "__main__":
    main()
