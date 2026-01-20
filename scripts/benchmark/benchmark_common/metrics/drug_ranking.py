"""
Drug Ranking Accuracy Module

Compute accuracy of drug rankings (did we rank received drugs in top 3?).
"""

from typing import List, Dict, Any


def compute_drug_ranking_accuracy(
    predictions: List[Dict[str, Any]],
    patients: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute drug ranking accuracy (did we rank received drugs in top 3?).
    
    Args:
        predictions: List of prediction results (may include errors)
        patients: List of patient dicts with treatments
    
    Returns:
        Dict with top_1_accuracy, top_3_accuracy, top_5_accuracy
    """
    print(f"\n📊 Computing drug ranking accuracy...")
    
    # Create patient lookup
    patient_lookup = {p.get("patient_id"): p for p in patients}
    
    # Extract received treatments
    patients_with_treatments = []
    
    for pred in predictions:
        if "error" in pred:
            continue
        
        patient_id = pred.get("patient_id")
        patient = patient_lookup.get(patient_id)
        
        if not patient:
            continue
        
        # Handle both list and dict formats for treatments
        treatments = patient.get("treatments", [])
        if isinstance(treatments, dict):
            # If treatments is a dict, try to extract list
            treatments = treatments.get("drugs", []) or treatments.get("treatments", [])
        
        if not treatments:
            continue
        
        # Get treatment names
        received_drugs = set()
        for treatment in treatments:
            if isinstance(treatment, dict):
                drug_name = treatment.get("treatment") or treatment.get("drug") or treatment.get("name", "")
            else:
                drug_name = str(treatment)
            
            if drug_name:
                # Normalize drug names (lowercase, remove common variations)
                drug_name_normalized = drug_name.lower().strip()
                received_drugs.add(drug_name_normalized)
        
        if received_drugs:
            # Get our drug rankings (handle both formats)
            drug_rankings = pred.get("drug_rankings", [])
            if not drug_rankings:
                # Fallback to all_drugs format
                all_drugs = pred.get("all_drugs", [])
                drug_rankings = [{"name": d} for d in all_drugs]
            
            our_drugs = [d.get("name", "").lower().strip() if isinstance(d, dict) else str(d).lower().strip() for d in drug_rankings]
            
            patients_with_treatments.append({
                "patient_id": patient_id,
                "received_drugs": received_drugs,
                "our_drugs": our_drugs,
            })
    
    if len(patients_with_treatments) < 10:
        error_msg = {"error": f"Insufficient data (n={len(patients_with_treatments)})"}
        print(f"   ⚠️  Drug Ranking: {error_msg['error']}")
        return error_msg
    
    # Compute accuracy metrics
    top_1_matches = 0
    top_3_matches = 0
    top_5_matches = 0
    
    for patient_data in patients_with_treatments:
        received = patient_data["received_drugs"]
        our_drugs = patient_data["our_drugs"]
        
        # Check if any received drug is in our top N
        if our_drugs and any(drug in received for drug in our_drugs[:1]):
            top_1_matches += 1
        if our_drugs and any(drug in received for drug in our_drugs[:3]):
            top_3_matches += 1
        if our_drugs and any(drug in received for drug in our_drugs[:5]):
            top_5_matches += 1
    
    n = len(patients_with_treatments)
    
    metrics = {
        "top_1_accuracy": top_1_matches / n if n > 0 else 0.0,
        "top_3_accuracy": top_3_matches / n if n > 0 else 0.0,
        "top_5_accuracy": top_5_matches / n if n > 0 else 0.0,
        "n_patients": n
    }
    
    print(f"   ✅ Drug Ranking: Top-1={metrics['top_1_accuracy']:.3f}, Top-3={metrics['top_3_accuracy']:.3f}, Top-5={metrics['top_5_accuracy']:.3f} (n={n})")
    
    return metrics


