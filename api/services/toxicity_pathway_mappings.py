"""
Toxicity pathway mappings for MoA to toxic pathway overlap detection.

Based on answers from toxicity_risk_plan.mdc:
- DNA repair pathways
- Inflammation pathways  
- Cardiometabolic pathways
- Pharmacogene list

Conservative approach: Better to flag potential toxicity than miss it (RUO).

Enhanced (Jan 2025): Drug-specific IO profiles for irAE risk stratification.
- Different checkpoint inhibitors have different irAE profiles
- CTLA-4 (ipilimumab) has 2-3x higher irAE rate than PD-1 mono
- Combination therapy (PD-1 + CTLA-4) has highest irAE risk
"""

from typing import Dict, List, Set, Any, Tuple, Optional


# ============================================================================
# TOXIC PATHWAY GENE SETS
# ============================================================================

DNA_REPAIR_GENES: Set[str] = {
    # Homologous Recombination (HR)
    "BRCA1", "BRCA2", "ATM", "ATR", "CHEK2", "PALB2", 
    "RAD51", "RAD51C", "RAD51D", 
    "FANCA", "FANCC", "FANCD2",
    "MRE11", "NBN", "TP53", "PARP1", "PARP2",
    # Mismatch Repair (MMR)
    "MLH1", "MSH2", "MSH6", "PMS2",
    # Base Excision Repair (BER) - Critical for MBD4-deficient patients
    "MBD4", "OGG1", "MUTYH", "NTHL1", "NEIL1", "NEIL2", "NEIL3",
    "APEX1", "APEX2", "POLB", "XRCC1", "LIG3",
}

INFLAMMATION_GENES: Set[str] = {
    "TNF", "TNFA", "TNFRSF1A", "TNFRSF1B",
    "IL6", "IL1B", "IL8", "IL10",
    "NFKB1", "NFKB2", "RELA", "RELB",
    "STAT3", "STAT1", "JAK1", "JAK2",
    "NLRP3", "CASP1", "PYCARD",
}

CARDIOMETABOLIC_GENES: Set[str] = {
    "APOB", "LDLR", "PCSK9", "APOE",
    "MTOR", "TSC1", "TSC2", 
    "HNF1A", "HNF4A", "GCK",
    "KCNQ1", "KCNH2", "SCN5A",  # Cardiac ion channels
    "RYR2", "CACNA1C",
}

# Pharmacogenes (PGx) - variants in these genes can affect drug metabolism/toxicity
# From PharmGKB VIP genes + common clinical examples
PHARMACOGENES: Set[str] = {
    # Phase I metabolism (CYP enzymes)
    "CYP2D6", "CYP2C19", "CYP2C9", "CYP3A4", "CYP3A5",
    "CYP1A2", "CYP2B6", "CYP2E1",
    
    # Phase II metabolism
    "UGT1A1", "UGT2B7", "UGT2B15",
    "TPMT", "DPYD", "NUDT15",
    
    # Transporters
    "ABCB1", "SLCO1B1", "SLC22A1",
    
    # Drug targets
    "VKORC1", "CFTR", "G6PD",
    
    # Adverse reactions
    "HLA-B", "HLA-A", "RYR1",
    "CACNA1S", "NAT2", "GSTM1", "GSTT1",
}


# ============================================================================
# MoA to TOXICITY PATHWAY MAPPINGS
# ============================================================================

# Map drug mechanism of action to potentially affected toxic pathways
# Conservative: Include if there's ANY mechanistic overlap
MOA_TO_TOXIC_PATHWAYS: Dict[str, Dict[str, float]] = {
    # MAPK pathway inhibitors
    "BRAF_inhibitor": {
        "dna_repair": 0.3,  # BRAF inhibition can stress DNA repair
        "inflammation": 0.2,  # Paradoxical MAPK activation
        "cardiometabolic": 0.1,  # QT prolongation risk
    },
    "MEK_inhibitor": {
        "dna_repair": 0.2,
        "inflammation": 0.3,
        "cardiometabolic": 0.2,  # Cardiac toxicity
    },
    
    # Chemotherapy
    "alkylating_agent": {
        "dna_repair": 0.8,  # Direct DNA damage
        "inflammation": 0.4,  # Immune suppression
        "cardiometabolic": 0.2,
    },
    "platinum_agent": {
        "dna_repair": 0.9,  # DNA crosslinks
        "inflammation": 0.3,
        "cardiometabolic": 0.2,  # Nephrotoxicity
    },
    "anthracycline": {
        "dna_repair": 0.7,
        "inflammation": 0.3,
        "cardiometabolic": 0.9,  # HIGH cardiotoxicity risk
    },
    
    # Targeted therapy
    "proteasome_inhibitor": {
        "dna_repair": 0.3,
        "inflammation": 0.5,  # ER stress
        "cardiometabolic": 0.3,
    },
    "PARP_inhibitor": {
        "dna_repair": 0.9,  # Synthetic lethality with HRD
        "inflammation": 0.2,
        "cardiometabolic": 0.1,
    },
    "immunomodulatory": {  # IMiDs
        "dna_repair": 0.2,
        "inflammation": 0.7,  # Immune modulation
        "cardiometabolic": 0.3,  # Thrombosis risk
    },
    
    # Immunotherapy - Class level (use IO_DRUG_PROFILES for drug-specific)
    "checkpoint_inhibitor": {
        "dna_repair": 0.1,
        "inflammation": 0.9,  # Immune-related adverse events
        "cardiometabolic": 0.4,  # Myocarditis risk
    },
    # PD-1 specific (lower irAE than CTLA-4)
    "pd1_inhibitor": {
        "dna_repair": 0.1,
        "inflammation": 0.7,  # Lower than CTLA-4
        "cardiometabolic": 0.3,
    },
    # PD-L1 specific (may have even lower irAE profile)
    "pdl1_inhibitor": {
        "dna_repair": 0.1,
        "inflammation": 0.65,  # Slightly lower than PD-1
        "cardiometabolic": 0.25,
    },
    # CTLA-4 specific (HIGHEST irAE risk)
    "ctla4_inhibitor": {
        "dna_repair": 0.1,
        "inflammation": 0.95,  # VERY HIGH irAE risk
        "cardiometabolic": 0.5,  # Higher myocarditis risk
    },
    "CAR_T": {
        "dna_repair": 0.2,
        "inflammation": 0.9,  # Cytokine release syndrome
        "cardiometabolic": 0.3,
    },
    
    # Microtubule agents
    "taxane": {
        "dna_repair": 0.2,  # Indirect DNA stress via mitotic arrest
        "inflammation": 0.4,  # Hypersensitivity reactions
        "cardiometabolic": 0.2,  # Cardiac arrhythmias possible
        # Note: Main toxicity is NEUROTOXICITY (peripheral neuropathy)
    },
    "vinca_alkaloid": {
        "dna_repair": 0.2,
        "inflammation": 0.3,
        "cardiometabolic": 0.2,
        # Note: Main toxicity is NEUROTOXICITY
    },
    
    # Antimetabolites
    "antimetabolite": {
        "dna_repair": 0.6,  # Interfere with DNA synthesis
        "inflammation": 0.5,  # Mucositis, GI toxicity
        "cardiometabolic": 0.3,  # 5-FU cardiotoxicity
    },
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def get_toxic_pathway_genes(pathway: str) -> Set[str]:
    """Get gene set for a toxic pathway."""
    pathway_lower = pathway.lower()
    if "dna" in pathway_lower or "repair" in pathway_lower:
        return DNA_REPAIR_GENES
    elif "inflam" in pathway_lower:
        return INFLAMMATION_GENES
    elif "cardio" in pathway_lower or "metabolic" in pathway_lower:
        return CARDIOMETABOLIC_GENES
    return set()


def get_moa_toxicity_weights(moa: str) -> Dict[str, float]:
    """
    Get toxicity pathway weights for a drug MoA.
    
    Returns:
        Dict mapping pathway name to risk weight (0-1).
        Empty dict if MoA not recognized (conservative: assume no specific toxicity).
    """
    moa_normalized = moa.lower().replace(" ", "_").replace("-", "_")
    
    # Try exact match first
    if moa_normalized in MOA_TO_TOXIC_PATHWAYS:
        return MOA_TO_TOXIC_PATHWAYS[moa_normalized]
    
    # Try partial matches (e.g., "BRAF" matches "BRAF_inhibitor")
    for known_moa, weights in MOA_TO_TOXIC_PATHWAYS.items():
        if moa_normalized in known_moa or known_moa in moa_normalized:
            return weights
    
    # Conservative: Unknown MoAs get modest baseline risk
    return {
        "dna_repair": 0.1,
        "inflammation": 0.1,
        "cardiometabolic": 0.1,
    }


def is_pharmacogene(gene: str) -> bool:
    """Check if gene is a known pharmacogene."""
    return gene.upper() in PHARMACOGENES


def get_pharmacogene_risk_weight(gene: str) -> float:
    """
    Get toxicity risk weight for a pharmacogene variant.
    
    High-impact genes (DPYD, TPMT, UGT1A1) get higher weights.
    """
    gene_upper = gene.upper()
    
    # High-impact PGx genes (severe ADRs well-documented)
    high_impact = {"DPYD", "TPMT", "UGT1A1", "G6PD", "NUDT15", "HLA-B"}
    if gene_upper in high_impact:
        return 0.4
    
    # CYP enzymes (moderate impact, drug-dependent)
    if gene_upper.startswith("CYP"):
        return 0.3
    
    # Other PGx genes (modest impact)
    if gene_upper in PHARMACOGENES:
        return 0.2
    
    return 0.0


def compute_pathway_overlap(patient_genes: List[str], moa: str) -> Dict[str, float]:
    """
    Compute overlap between patient germline variants and drug MoA toxic pathways.
    
    Args:
        patient_genes: List of genes with germline variants
        moa: Drug mechanism of action
    
    Returns:
        Dict with pathway overlap scores (0-1)
    """
    patient_gene_set = {g.upper() for g in patient_genes if g}
    moa_weights = get_moa_toxicity_weights(moa)
    
    overlap_scores = {}
    
    for pathway, base_weight in moa_weights.items():
        pathway_genes = get_toxic_pathway_genes(pathway)
        overlap_count = len(patient_gene_set & pathway_genes)
        
        if overlap_count > 0:
            # Score = base weight * (1 + log(overlap_count)) to handle multiple hits
            import math
            overlap_scores[pathway] = min(1.0, base_weight * (1 + math.log(overlap_count + 1) / 3))
        else:
            overlap_scores[pathway] = 0.0
    
    return overlap_scores


# ============================================================================
# MITIGATING FOODS (THE MOAT)
# ============================================================================

def get_mitigating_foods(pathway_overlap: Dict[str, float]) -> List[Dict[str, Any]]:
    """
    Map toxicity pathway overlap to mitigating foods.
    
    THE MOAT - connecting toxicity assessment to food recommendations.
    
    This implements Section 4 + Section 7 from ADVANCED_CARE_PLAN_EXPLAINED.md:
    - Section 4: Toxicity & Pharmacogenomics - detects drug toxicity risks
    - Section 7: Nutraceutical Synergy/Antagonism - recommends timing and foods
    
    Args:
        pathway_overlap: Dict from compute_pathway_overlap() 
                        e.g., {"dna_repair": 1.0, "inflammation": 0.0, "cardiometabolic": 0.0}
    
    Returns:
        List of mitigating food recommendations with timing guidance
    """
    recommendations = []
    
    # DNA REPAIR pathway - mitigating foods
    # From ADVANCED_CARE_PLAN Section 7: "Vitamin D for HRD context repletion (DNA repair support)"
    if pathway_overlap.get("dna_repair", 0) > 0.3:
        recommendations.extend([
            {
                "compound": "NAC (N-Acetyl Cysteine)",
                "dose": "600mg twice daily",
                "timing": "post-chemo (not during infusion)",
                "mechanism": "Glutathione precursor, supports DNA repair enzymes",
                "evidence_tier": "MODERATE",
                "pathway": "dna_repair",
                "care_plan_ref": "Section 7: Antioxidants - After chemo: Use - helps recovery"
            },
            {
                "compound": "Vitamin D3",
                "dose": "5000 IU daily",
                "timing": "continuous, with fatty meal",
                "mechanism": "Modulates DNA repair gene expression (VDR-mediated)",
                "evidence_tier": "MODERATE",
                "pathway": "dna_repair",
                "care_plan_ref": "Section 7: Vitamin D - HRD context repletion (DNA repair support)"
            },
            {
                "compound": "Folate (5-MTHF)",
                "dose": "400-800mcg daily",
                "timing": "continuous",
                "mechanism": "DNA synthesis and repair cofactor",
                "evidence_tier": "MODERATE",
                "pathway": "dna_repair",
                "care_plan_ref": "DNA repair support - continuous supplementation"
            }
        ])
    
    # INFLAMMATION pathway - mitigating foods
    # From ADVANCED_CARE_PLAN Section 7: "Omega-3 - Post-chemo inflammation control"
    if pathway_overlap.get("inflammation", 0) > 0.3:
        recommendations.extend([
            {
                "compound": "Omega-3 (EPA+DHA)",
                "dose": "2-3g combined EPA+DHA daily",
                "timing": "post-infusion (anti-inflammatory)",
                "mechanism": "Resolvin precursor, inhibits NF-κB, reduces IL-6",
                "evidence_tier": "SUPPORTED",
                "pathway": "inflammation",
                "care_plan_ref": "Section 7: Omega-3 - Post-chemo inflammation control"
            },
            {
                "compound": "Curcumin (Turmeric Extract)",
                "dose": "500-1000mg daily (with piperine)",
                "timing": "between meals, post-chemo",
                "mechanism": "NF-κB inhibitor, COX-2 inhibitor, reduces cytokine storm",
                "evidence_tier": "MODERATE",
                "pathway": "inflammation",
                "care_plan_ref": "Anti-inflammatory - for checkpoint inhibitor iRAEs"
            },
            {
                "compound": "EGCG (Green Tea Extract)",
                "dose": "400-800mg daily",
                "timing": "between meals (not with iron supplements)",
                "mechanism": "Anti-inflammatory, STAT3 inhibitor",
                "evidence_tier": "MODERATE",
                "pathway": "inflammation",
                "care_plan_ref": "STAT3 pathway modulation"
            }
        ])
    
    # CARDIOMETABOLIC pathway - mitigating foods  
    # From ADVANCED_CARE_PLAN Section 4: Anthracycline cardiotoxicity prevention
    if pathway_overlap.get("cardiometabolic", 0) > 0.3:
        recommendations.extend([
            {
                "compound": "CoQ10 (Ubiquinol)",
                "dose": "200-400mg daily",
                "timing": "with fatty meal, continuous during anthracycline",
                "mechanism": "Mitochondrial support, cardioprotective against doxorubicin",
                "evidence_tier": "SUPPORTED",
                "pathway": "cardiometabolic",
                "care_plan_ref": "Section 4: Anthracycline cardiotoxicity - CoQ10 for protection"
            },
            {
                "compound": "L-Carnitine",
                "dose": "1000-2000mg daily",
                "timing": "morning, with breakfast",
                "mechanism": "Fatty acid transport, cardiac energy metabolism",
                "evidence_tier": "MODERATE",
                "pathway": "cardiometabolic",
                "care_plan_ref": "Cardiac metabolism support"
            },
            {
                "compound": "Magnesium Glycinate",
                "dose": "400mg daily",
                "timing": "evening (aids sleep, cardiac rhythm)",
                "mechanism": "Cardiac rhythm support, ATP synthesis, QT stabilization",
                "evidence_tier": "MODERATE",
                "pathway": "cardiometabolic",
                "care_plan_ref": "QT prolongation risk mitigation"
            }
        ])
    
    return recommendations


# ============================================================================
# DRUG TO MOA MAPPING
# ============================================================================

DRUG_TO_MOA: Dict[str, str] = {
    # Platinum agents
    "carboplatin": "platinum_agent",
    "cisplatin": "platinum_agent",
    "oxaliplatin": "platinum_agent",
    
    # Anthracyclines (HIGH cardiotoxicity - Section 4)
    "doxorubicin": "anthracycline",
    "adriamycin": "anthracycline",
    "epirubicin": "anthracycline",
    "daunorubicin": "anthracycline",
    
    # PARP inhibitors
    "olaparib": "PARP_inhibitor",
    "niraparib": "PARP_inhibitor",
    "rucaparib": "PARP_inhibitor",
    "talazoparib": "PARP_inhibitor",
    
    # Checkpoint inhibitors (inflammation - iRAEs)
    "pembrolizumab": "checkpoint_inhibitor",
    "nivolumab": "checkpoint_inhibitor",
    "atezolizumab": "checkpoint_inhibitor",
    "ipilimumab": "checkpoint_inhibitor",
    "durvalumab": "checkpoint_inhibitor",
    "avelumab": "checkpoint_inhibitor",
    
    # Alkylating agents
    "cyclophosphamide": "alkylating_agent",
    "temozolomide": "alkylating_agent",
    "ifosfamide": "alkylating_agent",
    "bendamustine": "alkylating_agent",
    
    # BRAF/MEK inhibitors
    "vemurafenib": "BRAF_inhibitor",
    "dabrafenib": "BRAF_inhibitor",
    "encorafenib": "BRAF_inhibitor",
    "trametinib": "MEK_inhibitor",
    "cobimetinib": "MEK_inhibitor",
    "binimetinib": "MEK_inhibitor",
    
    # Proteasome inhibitors
    "bortezomib": "proteasome_inhibitor",
    "carfilzomib": "proteasome_inhibitor",
    "ixazomib": "proteasome_inhibitor",
    
    # IMiDs
    "lenalidomide": "immunomodulatory",
    "pomalidomide": "immunomodulatory",
    "thalidomide": "immunomodulatory",
    
    # Taxanes (neurotoxicity, myelosuppression)
    "paclitaxel": "taxane",
    "docetaxel": "taxane",
    "cabazitaxel": "taxane",
    "nab-paclitaxel": "taxane",
    "abraxane": "taxane",
    
    # Vinca alkaloids (neurotoxicity)
    "vincristine": "vinca_alkaloid",
    "vinblastine": "vinca_alkaloid",
    "vinorelbine": "vinca_alkaloid",
    
    # Antimetabolites
    "5-fluorouracil": "antimetabolite",
    "5-fu": "antimetabolite",
    "capecitabine": "antimetabolite",
    "gemcitabine": "antimetabolite",
    "methotrexate": "antimetabolite",
    "pemetrexed": "antimetabolite",
}


def get_drug_moa(drug_name: str) -> str:
    """
    Get mechanism of action for a drug.
    
    Args:
        drug_name: Drug name (case-insensitive)
    
    Returns:
        MoA string or "unknown" if not found
    """
    return DRUG_TO_MOA.get(drug_name.lower().strip(), "unknown")


# ============================================================================
# IO DRUG-SPECIFIC PROFILES (irAE Risk Stratification)
# ============================================================================
# Different checkpoint inhibitors have different irAE profiles
# Based on meta-analyses and phase III trial data
#
# Sources:
# - Wang et al. 2018: Meta-analysis of irAE rates
# - Martins et al. 2019: irAE comparison across IO drugs
# - Postow et al. 2018: Combination therapy irAE rates

IO_DRUG_PROFILES: Dict[str, Dict[str, Any]] = {
    # PD-1 inhibitors (moderate irAE risk)
    "pembrolizumab": {
        "brand_name": "Keytruda",
        "target": "PD-1",
        "moa_specific": "pd1_inhibitor",
        "irae_grade3plus_rate": 0.17,  # 17% Grade 3+ irAEs
        "organ_specific_risks": {
            "pneumonitis": 0.04,      # 4% - MONITOR closely
            "colitis": 0.02,          # 2%
            "hepatitis": 0.02,        # 2%
            "thyroiditis": 0.10,      # 10% - most common
            "hypophysitis": 0.01,     # 1%
            "myocarditis": 0.01,      # <1% but FATAL if missed
            "nephritis": 0.01,        # 1%
        },
        "monitoring_priority": ["pneumonitis", "myocarditis", "thyroid"],
        "notes": "FDA approved for TMB-H (≥10 mut/Mb) solid tumors"
    },
    "nivolumab": {
        "brand_name": "Opdivo",
        "target": "PD-1",
        "moa_specific": "pd1_inhibitor",
        "irae_grade3plus_rate": 0.16,  # 16% Grade 3+
        "organ_specific_risks": {
            "pneumonitis": 0.03,
            "colitis": 0.02,
            "hepatitis": 0.03,
            "thyroiditis": 0.08,
            "hypophysitis": 0.01,
            "myocarditis": 0.01,
            "nephritis": 0.02,
        },
        "monitoring_priority": ["pneumonitis", "hepatitis", "myocarditis"],
        "notes": "Similar to pembrolizumab, slightly different trial populations"
    },
    
    # CTLA-4 inhibitors (HIGH irAE risk)
    "ipilimumab": {
        "brand_name": "Yervoy",
        "target": "CTLA-4",
        "moa_specific": "ctla4_inhibitor",
        "irae_grade3plus_rate": 0.35,  # 35% Grade 3+ - MUCH HIGHER!
        "organ_specific_risks": {
            "colitis": 0.15,          # 15% - VERY HIGH
            "hepatitis": 0.05,        # 5%
            "hypophysitis": 0.05,     # 5% - higher than PD-1
            "dermatitis": 0.10,       # 10%
            "thyroiditis": 0.05,
            "myocarditis": 0.02,      # Higher than PD-1
        },
        "monitoring_priority": ["colitis", "hypophysitis", "myocarditis"],
        "notes": "HIGHER irAE risk than PD-1. Reserve for specific indications or combinations."
    },
    
    # PD-L1 inhibitors (may have slightly lower irAE)
    "atezolizumab": {
        "brand_name": "Tecentriq",
        "target": "PD-L1",
        "moa_specific": "pdl1_inhibitor",
        "irae_grade3plus_rate": 0.14,  # 14% - slightly lower
        "organ_specific_risks": {
            "pneumonitis": 0.02,
            "hepatitis": 0.02,
            "colitis": 0.01,
            "thyroiditis": 0.06,
            "dermatitis": 0.03,
        },
        "monitoring_priority": ["pneumonitis", "hepatitis"],
        "notes": "PD-L1 may have modestly lower irAE profile"
    },
    "durvalumab": {
        "brand_name": "Imfinzi",
        "target": "PD-L1",
        "moa_specific": "pdl1_inhibitor",
        "irae_grade3plus_rate": 0.15,
        "organ_specific_risks": {
            "pneumonitis": 0.03,
            "hepatitis": 0.02,
            "thyroiditis": 0.07,
            "dermatitis": 0.02,
        },
        "monitoring_priority": ["pneumonitis"],
        "notes": "Approved for lung cancer maintenance after chemoradiation"
    },
    "avelumab": {
        "brand_name": "Bavencio",
        "target": "PD-L1",
        "moa_specific": "pdl1_inhibitor",
        "irae_grade3plus_rate": 0.13,
        "organ_specific_risks": {
            "pneumonitis": 0.02,
            "hepatitis": 0.02,
            "colitis": 0.01,
            "thyroiditis": 0.05,
        },
        "monitoring_priority": ["infusion_reaction", "pneumonitis"],
        "notes": "Higher infusion reaction rate than other PD-L1s"
    },
    
    # COMBINATION THERAPY (HIGHEST irAE risk)
    "nivolumab_ipilimumab": {
        "brand_name": "Nivo + Ipi",
        "target": "PD-1 + CTLA-4",
        "moa_specific": "combination_io",
        "irae_grade3plus_rate": 0.55,  # 55% - VERY HIGH!
        "organ_specific_risks": {
            "colitis": 0.20,          # 20% - VERY HIGH
            "hepatitis": 0.15,        # 15%
            "thyroiditis": 0.15,      # 15%
            "pneumonitis": 0.08,      # 8%
            "hypophysitis": 0.08,     # 8%
            "myocarditis": 0.03,      # 3% - higher than mono
            "nephritis": 0.05,
        },
        "monitoring_priority": ["colitis", "hepatitis", "myocarditis", "hypophysitis"],
        "notes": "HIGHEST irAE risk. Reserve for melanoma or when mono fails."
    },
}


def get_io_drug_profile(drug_name: str) -> Optional[Dict[str, Any]]:
    """
    Get detailed IO drug profile including irAE risks.
    
    Args:
        drug_name: Drug name (case-insensitive)
    
    Returns:
        Drug profile dict or None if not an IO drug
    """
    drug_lower = drug_name.lower().strip()
    
    # Handle combination therapy
    if "ipi" in drug_lower and "nivo" in drug_lower:
        return IO_DRUG_PROFILES.get("nivolumab_ipilimumab")
    
    return IO_DRUG_PROFILES.get(drug_lower)


def compare_io_drugs(drug_list: List[str]) -> List[Dict[str, Any]]:
    """
    Compare irAE profiles across multiple IO drugs.
    
    Args:
        drug_list: List of IO drug names
    
    Returns:
        Sorted list of drug profiles (lowest irAE first)
    """
    profiles = []
    for drug in drug_list:
        profile = get_io_drug_profile(drug)
        if profile:
            profiles.append({
                "drug": drug,
                **profile
            })
    
    # Sort by irAE risk (lowest first)
    return sorted(profiles, key=lambda x: x.get("irae_grade3plus_rate", 1.0))


def select_safest_io(
    eligible_drugs: List[str],
    patient_age: Optional[int] = None,
    autoimmune_history: Optional[List[str]] = None,
    organ_risk_flags: Optional[List[str]] = None
) -> Dict[str, Any]:
    """
    Select the safest IO drug for a patient.
    
    Args:
        eligible_drugs: List of IO drugs the patient is eligible for
        patient_age: Patient age (older = higher irAE risk)
        autoimmune_history: List of autoimmune conditions (increases irAE risk)
    
    Returns:
        Recommendation dict with selected drug and rationale
    """
    # Get profiles and sort by safety
    profiles = compare_io_drugs(eligible_drugs)
    
    if not profiles:
        return {
            "selected": None,
            "reason": "No IO drug profiles found for the provided drugs",
            "alternatives": []
        }
    
    # Normalize optional lists
    if organ_risk_flags is not None and not isinstance(organ_risk_flags, list):
        organ_risk_flags = [str(organ_risk_flags)]

    organ_risk_flags_norm = {str(x).strip().lower() for x in (organ_risk_flags or []) if x}

    # Adjust risk for patient factors
    adjusted_profiles = []
    for p in profiles:
        base_risk = p["irae_grade3plus_rate"]
        risk_factors = []
        
        # Age adjustment
        if patient_age and patient_age > 65:
            base_risk *= 1.3
            risk_factors.append(f"Age {patient_age} > 65 → +30% irAE risk")
        
        # Autoimmune history
        if autoimmune_history:
            base_risk *= 2.0
            risk_factors.append(f"Autoimmune history → +100% irAE risk")
        
        # Organ risk flags (conservative)
        # NOTE: these do not exclude drugs; they increase risk and annotate rationa.
        # Example: prior pneumonitis should down-rank drugs with higher pneumonitis rates.
        organ_specific = p.get("organ_specific_risks") or {}
        if "prior_pneumonitis" in organ_risk_flags_norm or "pneumonitis" in organ_risk_flags_norm:
            pneu = organ_specific.get("pneumonitis")
            try:
                pneu_f = float(pneu) if pneu is not None else 0.0
            except Exception:
                pneu_f = 0.0
            if pneu_f >= 0.03:
                base_risk *= 1.5
                risk_factors.append(f"Prior pneumonitis → +50% (drug pneumonitis risk {pneu_f:.0%})")
        
        adjusted_profiles.append({
            **p,
            "adjusted_risk": min(base_risk, 1.0),
            "risk_factors": risk_factors
        })
    
    # Sort by adjusted risk
    adjusted_profiles.sort(key=lambda x: x["adjusted_risk"])
    
    selected = adjusted_profiles[0]
    
    return {
        "selected": selected["drug"],
        "brand_name": selected.get("brand_name"),
        "target": selected.get("target"),
        "irae_risk_raw": selected["irae_grade3plus_rate"],
        "irae_risk_adjusted": selected["adjusted_risk"],
        "risk_factors": selected.get("risk_factors", []),
        "monitoring_priority": selected.get("monitoring_priority", []),
        "reason": f"Lowest irAE risk ({selected['adjusted_risk']:.0%}) among options",
        "alternatives": adjusted_profiles[1:] if len(adjusted_profiles) > 1 else [],
        "avoid": [p for p in adjusted_profiles if p.get("target") == "CTLA-4" or p.get("target") == "PD-1 + CTLA-4"]
    }
