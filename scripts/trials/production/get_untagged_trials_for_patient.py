#!/usr/bin/env python3
"""
Get Untagged Trials for Patient

Generic script that uses disease module configs to find untagged trials.
No hard-coding - everything driven by YAML configs.

Usage:
    python get_untagged_trials_for_patient.py --disease ovarian_cancer --patient-profile ayesha --max-results 30
"""

import sys
import argparse
import json
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

from api.services.disease_based_trial_ranker import get_disease_trial_ranker


def load_patient_profile(profile_name: str, profile_file: str = None) -> dict:
    """Load patient profile by name or from file"""
    if profile_file:
        with open(profile_file, 'r') as f:
            return json.load(f)
    
    if profile_name.lower() == "ayesha":
        # Ayesha's profile (minimal for trial ranking)
        return {
            "patientId": "ayesha",
            "disease": {
                "type": "ovarian cancer",
                "histology": "high grade serous ovarian"
            },
            "tumor_context": {
                "somatic_mutations": [
                    {"gene": "TP53", "variant": "mutant", "hgvs_p": "p.R273H"}
                ]
            },
            "germline_variants": [
                {"gene": "MBD4", "variant": "pathogenic", "hgvs_p": "c.1234G>A"}
            ],
            "biomarkers": {
                "PD-L1": {
                    "cps": 10,
                    "positive": True
                },
                "FOLR1": {
                    "positive": False
                },
                "HER2": {
                    "positive": False
                }
            }
        }
    else:
        raise ValueError(f"Unknown patient profile: {profile_name}. Use --profile-file to load from JSON")


def main():
    parser = argparse.ArgumentParser(
        description="Get untagged trials for a patient using disease module configs"
    )
    parser.add_argument(
        "--disease",
        type=str,
        required=True,
        help="Disease name (e.g., ovarian_cancer, colon, breast)"
    )
    parser.add_argument(
        "--patient-profile",
        type=str,
        default="ayesha",
        help="Patient profile name (default: ayesha)"
    )
    parser.add_argument(
        "--profile-file",
        type=str,
        help="Path to patient profile JSON file (overrides --patient-profile)"
    )
    parser.add_argument(
        "--max-results",
        type=int,
        default=30,
        help="Maximum number of untagged trials to return (default: 30)"
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=0.5,
        help="Minimum score threshold (default: 0.5)"
    )
    parser.add_argument(
        "--recruiting-only",
        action="store_true",
        help="Only show RECRUITING trials (default: show all active trials, prioritizing RECRUITING)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output file path (JSON). If not provided, prints to stdout"
    )
    
    args = parser.parse_args()
    
    # Load patient profile
    try:
        patient_profile = load_patient_profile(args.patient_profile, args.profile_file)
    except Exception as e:
        print(f"❌ Failed to load patient profile: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Get ranker
    try:
        ranker = get_disease_trial_ranker(args.disease)
    except Exception as e:
        print(f"❌ Failed to initialize ranker: {e}", file=sys.stderr)
        sys.exit(1)
    
    # Get untagged trials
    status_filter = "RECRUITING only" if args.recruiting_only else "all active (prioritizing RECRUITING)"
    print(f"🎯 Finding untagged trials for {args.patient_profile} ({args.disease}) - {status_filter}")
    print("=" * 100)
    
    untagged_trials = ranker.get_untagged_trials(
        patient_profile=patient_profile,
        max_results=args.max_results,
        recruiting_only=args.recruiting_only
    )
    
    if not untagged_trials:
        print("✅ No untagged trials found")
        return
    
    # Print results
    print(f"\n📊 Found {len(untagged_trials)} untagged trials")
    print("=" * 100)
    
    for i, trial in enumerate(untagged_trials, 1):
        print(f"\n{i:2d}. {trial.nct_id} [score: {trial.score:.2f}] [{trial.status:22s}]")
        print(f"    {trial.title[:70]}...")
        print(f"    Matches: {', '.join(trial.keyword_matches.keys())}")
        if trial.combo_matches:
            print(f"    Combos: {', '.join(trial.combo_matches)}")
        if trial.dominant_axis:
            print(f"    Dominant axis: {trial.dominant_axis}")
        if trial.evidence_gates_triggered:
            print(f"    Evidence gates: {', '.join(trial.evidence_gates_triggered)}")
    
    # Output NCT IDs
    nct_ids = [trial.nct_id for trial in untagged_trials]
    print(f"\n✅ NCT IDs to tag ({len(nct_ids)}):")
    print(" ".join(nct_ids))
    
    # Output JSON if requested
    if args.output:
        output_data = {
            "disease": args.disease,
            "patient_profile": args.patient_profile,
            "untagged_trials": [
                {
                    "nct_id": trial.nct_id,
                    "title": trial.title,
                    "status": trial.status,
                    "phases": trial.phases,
                    "score": trial.score,
                    "mechanism_vector": trial.mechanism_vector,
                    "dominant_axis": trial.dominant_axis,
                    "evidence_gates_triggered": trial.evidence_gates_triggered,
                    "keyword_matches": trial.keyword_matches,
                    "combo_matches": trial.combo_matches,
                    "explainability": trial.explainability
                }
                for trial in untagged_trials
            ],
            "nct_ids": nct_ids
        }
        
        with open(args.output, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✅ Results saved to {args.output}")


if __name__ == "__main__":
    main()
