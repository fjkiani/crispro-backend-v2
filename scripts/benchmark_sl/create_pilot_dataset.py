#!/usr/bin/env python3
"""Create 10-case pilot dataset for synthetic lethality benchmark."""
import json
from pathlib import Path
from typing import List, Dict, Any

def create_pilot_dataset() -> List[Dict[str, Any]]:
    """Create 10 test cases for pilot benchmark."""
    
    test_cases = [
        # Case 1: BRCA1 C61G (known SL with PARP)
        {
            "case_id": "SL_001",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IVB",
            "mutations": [
                {
                    "gene": "BRCA1",
                    "hgvs_p": "p.C61G",
                    "chrom": "17",
                    "pos": 43070943,
                    "ref": "A",
                    "alt": "T",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["BRCA1+PARP"],
                "effective_drugs": ["Olaparib", "Niraparib", "Rucaparib"],
                "broken_pathways": ["HR"],
                "essential_pathways": ["PARP"],
                "depmap_essentiality": {
                    "BRCA1": 0.92
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "olaparib_indication": "BRCA-mutated ovarian cancer",
                    "response_rate": 0.65
                }
            }
        },
        
        # Case 2: BRCA2 truncating (known SL with PARP)
        {
            "case_id": "SL_002",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IIIB",
            "mutations": [
                {
                    "gene": "BRCA2",
                    "hgvs_p": "p.K3326*",
                    "chrom": "13",
                    "pos": 32936750,
                    "ref": "A",
                    "alt": "T",
                    "consequence": "stop_gained"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["BRCA2+PARP"],
                "effective_drugs": ["Olaparib", "Niraparib"],
                "broken_pathways": ["HR"],
                "essential_pathways": ["PARP"],
                "depmap_essentiality": {
                    "BRCA2": 0.88
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "response_rate": 0.60
                }
            }
        },
        
        # Case 3: MBD4 frameshift + TP53 (Ayesha's case)
        {
            "case_id": "SL_003",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IVB",
            "mutations": [
                {
                    "gene": "MBD4",
                    "hgvs_p": "p.R346fs",
                    "chrom": "3",
                    "pos": 129430488,
                    "ref": "A",
                    "alt": "AT",
                    "consequence": "frameshift_variant"
                },
                {
                    "gene": "TP53",
                    "hgvs_p": "p.R175H",
                    "chrom": "17",
                    "pos": 7577120,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["MBD4+PARP", "TP53+ATR"],
                "effective_drugs": ["Olaparib", "Ceralasertib"],
                "broken_pathways": ["BER", "G1/S Checkpoint"],
                "essential_pathways": ["HR", "ATR/CHK1"],
                "depmap_essentiality": {
                    "MBD4": 0.80,
                    "TP53": 0.75
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "ceralasertib_status": "clinical_trials"
                }
            }
        },
        
        # Case 4: TP53 hotspot alone (moderate SL)
        {
            "case_id": "SL_004",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IIIC",
            "mutations": [
                {
                    "gene": "TP53",
                    "hgvs_p": "p.R273H",
                    "chrom": "17",
                    "pos": 7577539,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["TP53+ATR"],
                "effective_drugs": ["Ceralasertib", "Adavosertib"],
                "broken_pathways": ["G1/S Checkpoint"],
                "essential_pathways": ["ATR/CHK1"],
                "depmap_essentiality": {
                    "TP53": 0.70
                },
                "clinical_evidence": {
                    "ceralasertib_status": "clinical_trials"
                }
            }
        },
        
        # Case 5: BRCA1 + TP53 (double-hit)
        {
            "case_id": "SL_005",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IVB",
            "mutations": [
                {
                    "gene": "BRCA1",
                    "hgvs_p": "p.Q563*",
                    "chrom": "17",
                    "pos": 43094450,
                    "ref": "C",
                    "alt": "T",
                    "consequence": "stop_gained"
                },
                {
                    "gene": "TP53",
                    "hgvs_p": "p.R175H",
                    "chrom": "17",
                    "pos": 7577120,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["BRCA1+PARP", "TP53+ATR"],
                "effective_drugs": ["Olaparib", "Ceralasertib"],
                "broken_pathways": ["HR", "G1/S Checkpoint"],
                "essential_pathways": ["PARP", "ATR/CHK1"],
                "depmap_essentiality": {
                    "BRCA1": 0.95,
                    "TP53": 0.75
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "response_rate": 0.70
                }
            }
        },
        
        # Case 6: Negative control - Benign variant
        {
            "case_id": "SL_006",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IIIC",
            "mutations": [
                {
                    "gene": "OR4F5",
                    "hgvs_p": "p.V123M",
                    "chrom": "1",
                    "pos": 920000,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": False,
                "known_sl_pairs": [],
                "effective_drugs": [],
                "broken_pathways": [],
                "essential_pathways": [],
                "depmap_essentiality": {
                    "OR4F5": 0.10
                },
                "clinical_evidence": {
                    "note": "Benign variant, no known SL"
                }
            }
        },
        
        # Case 7: Negative control - Non-essential gene
        {
            "case_id": "SL_007",
            "disease": "ovarian_cancer",
            "subtype": "endometrioid",
            "stage": "II",
            "mutations": [
                {
                    "gene": "HLA-A",
                    "hgvs_p": "p.A74T",
                    "chrom": "6",
                    "pos": 29910284,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": False,
                "known_sl_pairs": [],
                "effective_drugs": [],
                "broken_pathways": [],
                "essential_pathways": [],
                "depmap_essentiality": {
                    "HLA-A": 0.15
                },
                "clinical_evidence": {
                    "note": "Non-essential gene, no SL expected"
                }
            }
        },
        
        # Case 8: Negative control - Low essentiality
        {
            "case_id": "SL_008",
            "disease": "ovarian_cancer",
            "subtype": "mucinous",
            "stage": "IIIB",
            "mutations": [
                {
                    "gene": "KRAS",
                    "hgvs_p": "p.G12D",
                    "chrom": "12",
                    "pos": 25398284,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": False,
                "known_sl_pairs": [],
                "effective_drugs": ["Trametinib"],  # MEK inhibitor, not SL-based
                "broken_pathways": ["MAPK"],
                "essential_pathways": [],
                "depmap_essentiality": {
                    "KRAS": 0.25
                },
                "clinical_evidence": {
                    "note": "KRAS mutation, but no SL relationship"
                }
            }
        },
        
        # Case 9: Edge case - Multiple mutations, one SL
        {
            "case_id": "SL_009",
            "disease": "breast_cancer",
            "subtype": "triple_negative",
            "stage": "IIB",
            "mutations": [
                {
                    "gene": "BRCA1",
                    "hgvs_p": "p.E23*",
                    "chrom": "17",
                    "pos": 43045694,
                    "ref": "G",
                    "alt": "T",
                    "consequence": "stop_gained"
                },
                {
                    "gene": "PIK3CA",
                    "hgvs_p": "p.E545K",
                    "chrom": "3",
                    "pos": 178952085,
                    "ref": "G",
                    "alt": "A",
                    "consequence": "missense"
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["BRCA1+PARP"],
                "effective_drugs": ["Olaparib", "Niraparib"],
                "broken_pathways": ["HR"],
                "essential_pathways": ["PARP"],
                "depmap_essentiality": {
                    "BRCA1": 0.90,
                    "PIK3CA": 0.30
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "note": "BRCA1 SL dominates, PIK3CA secondary"
                }
            }
        },
        
        # Case 10: Edge case - Germline + Somatic
        {
            "case_id": "SL_010",
            "disease": "ovarian_cancer",
            "subtype": "high_grade_serous",
            "stage": "IVB",
            "mutations": [
                {
                    "gene": "BRCA2",
                    "hgvs_p": "p.N372H",
                    "chrom": "13",
                    "pos": 32911507,
                    "ref": "A",
                    "alt": "C",
                    "consequence": "missense",
                    "germline": True
                },
                {
                    "gene": "TP53",
                    "hgvs_p": "p.R248W",
                    "chrom": "17",
                    "pos": 7577539,
                    "ref": "C",
                    "alt": "T",
                    "consequence": "missense",
                    "germline": False
                }
            ],
            "ground_truth": {
                "synthetic_lethality_detected": True,
                "known_sl_pairs": ["BRCA2+PARP", "TP53+ATR"],
                "effective_drugs": ["Olaparib", "Ceralasertib"],
                "broken_pathways": ["HR", "G1/S Checkpoint"],
                "essential_pathways": ["PARP", "ATR/CHK1"],
                "depmap_essentiality": {
                    "BRCA2": 0.85,
                    "TP53": 0.72
                },
                "clinical_evidence": {
                    "olaparib_fda_approved": True,
                    "note": "Germline BRCA2 + somatic TP53"
                }
            }
        }
    ]
    
    return test_cases

def main():
    """Create and save pilot dataset."""
    print("Creating 10-case pilot dataset...")
    
    test_cases = create_pilot_dataset()
    
    output_file = Path("test_cases_pilot.json")
    with open(output_file, 'w') as f:
        json.dump(test_cases, f, indent=2)
    
    print(f"\n✅ Created {len(test_cases)} test cases")
    print(f"   - {sum(1 for c in test_cases if c['ground_truth']['synthetic_lethality_detected'])} positive cases (SL detected)")
    print(f"   - {sum(1 for c in test_cases if not c['ground_truth']['synthetic_lethality_detected'])} negative controls")
    print(f"   - Saved to {output_file}")
    
    return test_cases

if __name__ == "__main__":
    main()



