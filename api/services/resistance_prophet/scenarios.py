"""
Resistance Prophet Preview Scenarios (L2/L3)
Defines curated demo scenarios that flip resistance decision gates.

Scenarios:
- L2: Genomic Only (NGS + HRD/TMB).
- L3: Phenotypic Corroboration (Expression + CA-125).
"""

import copy
from typing import Dict, List, Any, Optional

# Constants for Expression Mapping
# Maps genes to canonical pathway indices (0-6)
# Indexes based on PATHWAY_NAMES in constants.py:
# ["Homologous Recombination", "Mismatch Repair", "BER", "NHEJ", "Replication Stress", "Checkpoint", "Apoptosis"]
# (This is approximate mapping for the demo logic)
PATHWAY_GENE_MAP = {
    "Homologous Recombination": ["BRCA1", "BRCA2", "RAD51C", "PALB2"],
    "Mismatch Repair": ["MLH1", "MSH2", "MSH6", "PMS2"],
    "BER": ["MBD4", "PARP1"],
    "NHEJ": ["XRCC4", "LIG4"],
    "Replication Stress": ["ATM", "ATR", "CHEK1", "WEE1"],
    "Checkpoint": ["TP53", "CCNE1", "CDKN1A"],
    "Apoptosis": ["BCL2", "BAX", "CASP3"]
}

PATHWAY_ORDER = [
    "Homologous Recombination", 
    "Mismatch Repair", 
    "BER", 
    "NHEJ", 
    "Replication Stress", 
    "Checkpoint", 
    "Apoptosis"
]

def _expression_to_mechanism_vector(expression_dict: Dict[str, float]) -> List[float]:
    """
    Map 0-10 Expression Scores to 0.0-1.0 Mechanism Vector.
    Logic:
    - Average expression of mapped genes per pathway.
    - Normalize (divide by 10).
    - Result is 'Pathway Burden' (High = 1.0, Low = 0.0).
    """
    vector = []
    for pathway in PATHWAY_ORDER:
        genes = PATHWAY_GENE_MAP.get(pathway, [])
        valid_scores = [expression_dict[g] for g in genes if g in expression_dict]
        
        if not valid_scores:
            # Default to "Active" (0.5 or 1.0?) if data missing?
            # Or 0.0? For 'Escape', we look for drops.
            # If baseline is unknown, we assume high.
            # Here, we output calculated score.
            vector.append(0.5) 
        else:
            avg = sum(valid_scores) / len(valid_scores)
            vector.append(min(1.0, avg / 10.0))
            
    return vector

L2_SCENARIOS = {
  # L2-A: HRD-high, TMB-high  -> favors PARP/platinum; may also surface IO
  "L2A_HRDhi_TMBhi": {
    "somaticmutations": [
      {"gene":"TP53","hgvsp":"p.Arg175His","hgvsc":"c.524G>A","chrom":"17","pos":7577120,"ref":"G","alt":"A",
       "consequence":"missense_variant","source":"NGS","note":"Hotspot R175H example"}
    ],
    "tumorcontextadditions": {"hrdscore":52.0,"hrdstatus":"HIGH","tmb":25.0,"tmbstatus":"HIGH"},
    "completenessscore":0.75
  },

  # L2-B: HRD-low, TMB-low -> suppresses PARP rationale; shifts toward non-HRD strategies
  "L2B_HRDlo_TMBlo": {
    "somaticmutations": [
      {"gene":"TP53","hgvsp":"p.Arg175His","hgvsc":"c.524G>A","chrom":"17","pos":7577120,"ref":"G","alt":"A",
       "consequence":"missense_variant","source":"NGS"}
    ],
    "tumorcontextadditions": {"hrdscore":18.0,"hrdstatus":"LOW","tmb":4.0,"tmbstatus":"LOW"},
    "completenessscore":0.75
  },

  # L2-C: HRD-high, TMB-low -> isolates “pure HRD” effect
  "L2C_HRDhi_TMBlo": {
    "somaticmutations": [
      {"gene":"TP53","hgvsp":"p.Arg175His","hgvsc":"c.524G>A","chrom":"17","pos":7577120,"ref":"G","alt":"A",
       "consequence":"missense_variant","source":"NGS"}
    ],
    "tumorcontextadditions": {"hrdscore":55.0,"hrdstatus":"HIGH","tmb":6.0,"tmbstatus":"LOW"},
    "completenessscore":0.75
  }
}

L3_SCENARIOS = {
  # L3-A: "HRD-like + responding marker" -> reinforces PARP/platinum
  "L3A_DDRlow_CA125down": {
    "tumorcontextadditions": {
      "expression": {
        "BRCA1":2.0,"BRCA2":2.5,"RAD51C":2.0,"PALB2":2.2,"ATM":3.0,"ATR":3.5,"CHEK1":3.2,
        "ABCB1":2.0,"ABCC1":2.0,"ABCG2":2.0,
        "CD8A":4.5,"GZMB":4.0,"IFNG":3.8,"PDCD1":4.0,"CD274":5.0
      },
      "ca125history": [
        {"date":"2025-10-01","value":4200,"units":"U/mL"},
        {"date":"2025-10-22","value":3100,"units":"U/mL"},
        {"date":"2025-11-17","value":2842,"units":"U/mL"},
        {"date":"2025-12-08","value":1600,"units":"U/mL"}
      ]
    },
    "ca125_value": 1600.0,
    "completenessscore":0.92
  },

  # L3-B: "DDR restored + efflux high + marker rising" -> shifts away from PARP/platinum
  "L3B_DDRhigh_Effluxhi_CA125up": {
    "tumorcontextadditions": {
      "expression": {
        "BRCA1":8.5,"BRCA2":8.0,"RAD51C":7.5,"PALB2":7.0,"ATM":7.5,"ATR":8.0,"CHEK1":7.8,
        "ABCB1":8.5,"ABCC1":7.8,"ABCG2":8.0,
        "CD8A":2.0,"GZMB":1.8,"IFNG":1.5,"PDCD1":2.0,"CD274":4.0
      },
      "ca125history": [
        {"date":"2025-10-01","value":2600,"units":"U/mL"},
        {"date":"2025-10-22","value":2800,"units":"U/mL"},
        {"date":"2025-11-17","value":2842,"units":"U/mL"},
        {"date":"2025-12-08","value":3600,"units":"U/mL"}
      ]
    },
    "ca125_value": 3600.0,
    "completenessscore":0.92
  },

  # L3-C: "Immune inflamed" -> elevates IO
  "L3C_IOhot_CA125flat": {
    "tumorcontextadditions": {
      "expression": {
        "BRCA1":4.0,"BRCA2":4.2,"RAD51C":4.0,"PALB2":4.0,"ATM":4.5,"ATR":4.8,"CHEK1":4.6,
        "ABCB1":3.0,"ABCC1":3.2,"ABCG2":3.0,
        "CD8A":8.0,"GZMB":8.5,"IFNG":8.2,"PDCD1":7.5,"CD274":7.0
      },
      "ca125history": [
        {"date":"2025-10-01","value":2900,"units":"U/mL"},
        {"date":"2025-10-22","value":2750,"units":"U/mL"},
        {"date":"2025-11-17","value":2842,"units":"U/mL"},
        {"date":"2025-12-08","value":2900,"units":"U/mL"}
      ]
    },
    "ca125_value": 2900.0,
    "completenessscore":0.92
  }
}

def get_scenario(scenario_id: str) -> Optional[Dict]:
    """Retrieve scenario definition by ID."""
    if not scenario_id: return None
    
    if scenario_id in L2_SCENARIOS:
        return copy.deepcopy(L2_SCENARIOS[scenario_id])
    if scenario_id in L3_SCENARIOS:
        return copy.deepcopy(L3_SCENARIOS[scenario_id])
    return None

def apply_scenario_to_context(
    tumor_context: Dict, 
    scenario_id: str
) -> Dict:
    """
    Apply a scenario to the V2 tumor_context payload.
    Merges biomarkers, mutations, and derived vectors.
    """
    scenario = get_scenario(scenario_id)
    if not scenario:
        return tumor_context
        
    ctx = copy.deepcopy(tumor_context)
    
    # 1. Update Somatic Mutations
    if "somaticmutations" in scenario:
        existing = ctx.get("somatic_mutations", [])
        # Append or Replace? Demo usually implies replacement of somatic profile relevant to demo
        # But Ayesha has MBD4 germline. We keep germline (separate field usually)
        # and replace somatic.
        ctx["somatic_mutations"] = scenario["somaticmutations"]
        
    # 2. Update Biomarkers / Context Additions
    additions = scenario.get("tumorcontextadditions", {})
    biomarkers = ctx.get("biomarkers", {})
    
    # Simple Fields
    if "hrdscore" in additions:
        biomarkers["hrd_score"] = additions["hrdscore"]
    if "hrdstatus" in additions:
        biomarkers["hrd_status"] = additions["hrdstatus"]
    if "tmb" in additions:
        biomarkers["tmb"] = additions["tmb"]
    if "tmbstatus" in additions:
        biomarkers["tmb_status"] = additions["tmbstatus"]
        
    # Complex Fields (Expression -> Vector)
    if "expression" in additions:
        # Calculate Vector
        vec = _expression_to_mechanism_vector(additions["expression"])
        ctx["mechanism_vector"] = vec
        # Also store expression for potential future use or display
        ctx["expression_profile"] = additions["expression"]
        
    # CA-125 History
    if "ca125history" in additions:
        ctx["ca125_history"] = additions["ca125history"]
        
    ctx["biomarkers"] = biomarkers
    
    # CA-125 Scalar (Completeness Trigger)
    # Note: ca125_value sits at root of request, but here we only modify tumor_context.
    # The Router handles mapping this scalar. 
    # BUT wait, the orchestrator (get_complete_care_plan) takes CompleteCareV2Request.
    # The router constructs Request object from payload + scenario.
    # We need a way to pass scalar up.
    # Updated strategy: Store it in tumor_context temporarily or return a tuple?
    # Let's modify apply_scenario_to_context to return just the context, 
    # but we need to patch the Router to look for the scalar in the Scenario definition if needed.
    # Or, cleaner: put scalar in context["latest_ca125"] and have router extract it?
    # No, Router already built the V2 request BEFORE calling orchestrator?
    # Router logic:
    #   tumor_context = { ... }
    #   tumor_context = apply_scenario(tumor_context)
    #   v2_request_data = { ... tumor_context=tumor_context ... }
    # So if we want to set v2_request.ca125_value, we need to do it in Router.
    
    # We will let the Router extract it from the scenario dict directly.
    
    # completeness
    if "completenessscore" in scenario:
        ctx["completeness_score"] = scenario["completenessscore"]
        
    return ctx
