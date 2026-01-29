import requests
import json
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "http://127.0.0.1:8000/api/ayesha/complete_care_plan"

# Base Payload (Minimal Ayesha context)
BASE_PAYLOAD = {
    "patient_context": {
        "stage": "IVB",
        "treatment_line": "recurrent",
        "treatment_history": [
            {"regimen": "Carboplatin-Paclitaxel", "response": "PR", "outcome": "progression"}
        ],
        "biomarkers": {
            "hrd_status": "HRD-", # Will be overridden by scenario
            "tmb": 5.0
        }
    },
    "mutations": [
        # MBD4 germline is standard baseline, but scenario overrides somatic
        {"gene": "MBD4", "hgvs_p": "p.R153*", "classification": "germline_homozygous"} 
    ]
}

SCENARIOS_TO_TEST = [
    ("L2A_HRDhi_TMBhi", "MEDIUM", ["GENE_LEVEL_RESISTANCE"]), # High HRD score normally lowers risk (sensitive), but TP53 might flag resistance? Wait. HRD High = Sensitive. High Risk = Resistance. 
    # Logic check:
    # L2A: HRD High (Sensitive). TP53 (maybe sensitive or resistant).
    # Expected: Risk should be LOW/MEDIUM (Sensitive profile).
    
    # L2B: HRD Low (Resistant/Proficient). 
    # Expected: Risk should be HIGHER than L2A.
    
    # L3B: DDR High (Proficient) + Efflux High + CA125 Up.
    # Expected: HIGH Risk (Restoration confirmed + Escape + Kinetics).
]

def run_test():
    for scenario_id, expected_risk_floor, expected_signals in SCENARIOS_TO_TEST:
        logger.info(f"--- Testing Scenario: {scenario_id} ---")
        
        payload = BASE_PAYLOAD.copy()
        payload["scenario_id"] = scenario_id
        
        try:
            resp = requests.post(API_URL, json=payload)
            resp.raise_for_status()
            data = resp.json()
            
            prediction = data.get("resistance_prediction", {})
            risk = prediction.get("risk_level", "UNKNOWN")
            prob = prediction.get("probability", 0.0)
            signals = [s["signal_type"] for s in prediction.get("signals_detected", []) if s["detected"]]
            
            logger.info(f"Result for {scenario_id}:")
            logger.info(f"  Risk Level: {risk}")
            logger.info(f"  Probability: {prob}")
            logger.info(f"  Signals: {signals}")
            logger.info(f"  Rationale: {prediction.get('rationale', [])[:1]}")
            
            # Basic validation
            if scenario_id == "L3B_DDRhigh_Effluxhi_CA125up":
                # Expecting HIGH risk or at least signals detected
                if risk not in ["HIGH", "MEDIUM"]:
                    logger.warning(f"⚠️ {scenario_id} Risk mismatch. Expected HIGH/MEDIUM, got {risk}")
                if "CA125_KINETICS" in signals or "DNA_REPAIR_RESTORATION" in signals:
                    logger.info("✅ Resistance signals detected as expected.")
                else:
                    logger.warning(f"⚠️ {scenario_id} missing expected resistance signals.")
                    
        except Exception as e:
            logger.error(f"Failed to run {scenario_id}: {e}")

if __name__ == "__main__":
    run_test()
