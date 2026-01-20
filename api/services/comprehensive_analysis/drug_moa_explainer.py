"""
Drug MoA Explainer - Explains how drugs work and why toxicity happens.

Provides step-by-step mechanism explanations and connects to patient genomics.
"""

from typing import Dict, Any, List, Optional
import logging

from api.services.toxicity_pathway_mappings import (
    get_drug_moa,
    compute_pathway_overlap,
    get_moa_toxicity_weights,
    get_mitigating_foods,
)

logger = logging.getLogger(__name__)


class DrugMoAExplainer:
    """Explain drug mechanisms of action and toxicity risks."""
    
    # Drug mechanism explanations (step-by-step HOW)
    DRUG_MECHANISMS = {
        "platinum_agent": {
            "how": (
                "1. Carboplatin enters cells and releases platinum ions\n"
                "2. Platinum ions form DNA crosslinks - they 'glue' two strands of DNA together\n"
                "3. When the cell tries to divide, it can't separate the DNA strands → cell death\n"
                "4. Why cancer cells die more: They divide faster → hit the crosslink more often → die first"
            ),
            "toxicity_why": (
                "Normal cells (kidney, bone marrow) also get crosslinks → toxicity. "
                "Platinum creates reactive oxygen species (ROS) → damages cell membranes. "
                "Kidney damage: Platinum concentrates in kidney → damages tubules → nephrotoxicity."
            )
        },
        "taxane": {
            "how": (
                "1. Paclitaxel binds to microtubules (protein structures that help cells divide)\n"
                "2. Microtubules become 'frozen' - can't disassemble during cell division\n"
                "3. Cell gets stuck in mitosis (cell division phase) → cell death\n"
                "4. Why cancer cells die: They divide constantly → hit this block more often"
            ),
            "toxicity_why": (
                "Neuropathy: Peripheral nerves also need microtubules → paclitaxel disrupts them → "
                "numbness/tingling. Myelosuppression: Bone marrow cells divide rapidly → get hit by paclitaxel. "
                "Hypersensitivity: Paclitaxel is dissolved in cremophor (oil-based) → can trigger allergic reactions."
            )
        },
        "anthracycline": {
            "how": (
                "1. Doxorubicin intercalates into DNA (inserts between base pairs)\n"
                "2. Blocks topoisomerase II (enzyme that untangles DNA during replication)\n"
                "3. Creates DNA breaks that can't be repaired → cell death\n"
                "4. Also generates reactive oxygen species → damages cell membranes"
            ),
            "toxicity_why": (
                "Cardiotoxicity: Doxorubicin generates ROS in heart muscle → cumulative damage → heart failure. "
                "Myelosuppression: Kills rapidly dividing bone marrow cells."
            )
        },
        "PARP_inhibitor": {
            "how": (
                "1. PARP1 enzyme repairs single-strand DNA breaks\n"
                "2. PARP inhibitor blocks PARP1 → single-strand breaks become double-strand breaks\n"
                "3. HRD+ cells can't fix double-strand breaks → cell death\n"
                "4. Normal cells survive because they have functional HR pathway"
            ),
            "toxicity_why": (
                "Myelosuppression: Bone marrow cells are rapidly dividing → more sensitive. "
                "Fatigue: PARP inhibition affects cellular energy metabolism."
            )
        },
        "checkpoint_inhibitor": {
            "how": (
                "1. T-cells have PD-1 receptor (checkpoint that prevents autoimmunity)\n"
                "2. Tumor cells express PD-L1 (ligand) → binds PD-1 → tells T-cells to 'stand down'\n"
                "3. Checkpoint inhibitor blocks PD-1/PD-L1 interaction\n"
                "4. T-cells are unleashed → attack tumor cells"
            ),
            "toxicity_why": (
                "Immune-related adverse events (iRAEs): Unleashed immune system attacks normal tissues. "
                "Common: Colitis, pneumonitis, hepatitis, thyroid dysfunction."
            )
        }
    }
    
    def __init__(self):
        pass
    
    def explain_drug_mechanism(
        self,
        drug_name: str,
        patient_genomics: Dict[str, Any],
        germline_genes: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Explain HOW drug works and WHY toxicity happens for THIS patient.
        
        Args:
            drug_name: Name of the drug (e.g., "carboplatin")
            patient_genomics: Patient genomic context (critical findings, etc.)
            germline_genes: List of germline gene names
        
        Returns:
            {
                'mechanism': str,  # Step-by-step HOW
                'toxicity_risks': List[Dict],  # Risk assessment
                'patient_specific_impact': str,  # How genomics affect risk
                'mitigation_strategies': List[Dict]  # What to do
            }
        """
        # Get drug MoA
        moa = get_drug_moa(drug_name)
        
        if moa == "unknown":
            return {
                "mechanism": f"Mechanism of action for {drug_name} not yet mapped in MOAT system.",
                "toxicity_risks": [],
                "patient_specific_impact": "Unable to assess patient-specific impact without MoA mapping.",
                "mitigation_strategies": []
            }
        
        # Get mechanism explanation
        mechanism_info = self.DRUG_MECHANISMS.get(moa, {})
        mechanism = mechanism_info.get("how", f"{drug_name} works via {moa} mechanism.")
        toxicity_why = mechanism_info.get("toxicity_why", "Standard toxicity risks apply.")
        
        # Compute pathway overlap for patient-specific risk
        germline_genes = germline_genes or []
        if patient_genomics.get("critical_findings"):
            # Extract genes from critical findings
            for finding in patient_genomics["critical_findings"]:
                gene = finding.get("gene", "")
                if gene and gene not in germline_genes:
                    germline_genes.append(gene)
        
        pathway_overlap = {}
        if germline_genes:
            pathway_overlap = compute_pathway_overlap(germline_genes, moa)
        
        # Get toxicity weights
        moa_weights = get_moa_toxicity_weights(moa)
        
        # Assess toxicity risks
        toxicity_risks = self._assess_toxicity_risks(
            drug_name, moa, moa_weights, pathway_overlap, patient_genomics
        )
        
        # Patient-specific impact
        patient_impact = self._explain_patient_impact(
            drug_name, moa, pathway_overlap, patient_genomics, germline_genes
        )
        
        # Mitigation strategies
        mitigating_foods = []
        if pathway_overlap:
            mitigating_foods = get_mitigating_foods(pathway_overlap)
        
        mitigation_strategies = self._generate_mitigation_strategies(
            drug_name, moa, toxicity_risks, mitigating_foods
        )
        
        return {
            "drug_name": drug_name,
            "moa": moa,
            "mechanism": mechanism,
            "toxicity_why": toxicity_why,
            "toxicity_risks": toxicity_risks,
            "patient_specific_impact": patient_impact,
            "mitigation_strategies": mitigation_strategies,
            "pathway_overlap": pathway_overlap
        }
    
    def _assess_toxicity_risks(
        self,
        drug_name: str,
        moa: str,
        moa_weights: Dict[str, float],
        pathway_overlap: Dict[str, float],
        patient_genomics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Assess specific toxicity risks."""
        risks = []
        
        # DNA repair pathway → nephrotoxicity, myelosuppression
        if moa_weights.get("dna_repair", 0) > 0.5:
            risk_level = "HIGH" if pathway_overlap.get("dna_repair", 0) > 0.5 else "MODERATE"
            risks.append({
                "toxicity": "Nephrotoxicity",
                "risk_level": risk_level,
                "mechanism": "DNA repair pathway stress → kidney cells can't repair damage",
                "patient_impact": (
                    f"Your pathway overlap: {pathway_overlap.get('dna_repair', 0):.2f}. "
                    "Higher overlap = more vulnerable kidneys."
                ) if pathway_overlap else "Standard risk applies."
            })
            
            risks.append({
                "toxicity": "Myelosuppression",
                "risk_level": "HIGH",
                "mechanism": "Kills rapidly dividing cells (bone marrow)",
                "patient_impact": "Monitor CBC at day 7-10 (nadir period)."
            })
        
        # Cardiometabolic pathway → cardiotoxicity
        if moa_weights.get("cardiometabolic", 0) > 0.5:
            risks.append({
                "toxicity": "Cardiotoxicity",
                "risk_level": "HIGH" if moa_weights.get("cardiometabolic", 0) > 0.7 else "MODERATE",
                "mechanism": "Cardiometabolic pathway stress → heart muscle damage",
                "patient_impact": "Cumulative risk - monitor cardiac function."
            })
        
        # Inflammation pathway → immune-related adverse events
        if moa_weights.get("inflammation", 0) > 0.5:
            risks.append({
                "toxicity": "Immune-related adverse events",
                "risk_level": "MODERATE",
                "mechanism": "Inflammation pathway activation",
                "patient_impact": "Monitor for autoimmune-like symptoms."
            })
        
        # Taxane-specific: Neuropathy
        if moa == "taxane":
            risks.append({
                "toxicity": "Peripheral neuropathy",
                "risk_level": "HIGH",
                "mechanism": "Microtubule disruption in peripheral nerves",
                "patient_impact": "Cumulative - each cycle adds more damage. Prevention is key."
            })
        
        return risks
    
    def _explain_patient_impact(
        self,
        drug_name: str,
        moa: str,
        pathway_overlap: Dict[str, float],
        patient_genomics: Dict[str, Any],
        germline_genes: List[str]
    ) -> str:
        """Explain how patient's genomics affect toxicity risk."""
        
        if not pathway_overlap or not germline_genes:
            return "Standard toxicity risks apply. No specific genomic risk factors identified."
        
        # Find critical genomic finding that affects this drug
        critical_findings = patient_genomics.get("critical_findings", [])
        
        impact_parts = []
        
        for finding in critical_findings:
            gene = finding.get("gene", "")
            pathway = finding.get("pathway", "")
            
            if gene in germline_genes:
                overlap_score = pathway_overlap.get("dna_repair", 0)
                
                if gene == "MBD4" and pathway == "Base Excision Repair (BER)":
                    impact_parts.append(
                        f"Your MBD4 homozygous loss weakens BER pathway → can't repair {drug_name}-induced "
                        "oxidative damage in kidney cells. Your kidneys are more vulnerable → need NAC support."
                    )
                
                elif gene in ["BRCA1", "BRCA2"] and overlap_score > 0.5:
                    impact_parts.append(
                        f"Your {gene} loss affects DNA repair → enhanced {drug_name} sensitivity (good for tumor, "
                        "but normal cells also struggle)."
                    )
        
        if not impact_parts:
            # Generic explanation based on pathway overlap
            if pathway_overlap.get("dna_repair", 0) > 0.3:
                impact_parts.append(
                    f"Your genomic profile shows DNA repair pathway involvement (overlap: "
                    f"{pathway_overlap.get('dna_repair', 0):.2f}). This may affect how you respond to {drug_name}."
                )
        
        return " | ".join(impact_parts) if impact_parts else "Standard toxicity risks apply."
    
    def _generate_mitigation_strategies(
        self,
        drug_name: str,
        moa: str,
        toxicity_risks: List[Dict[str, Any]],
        mitigating_foods: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Generate mitigation strategies."""
        strategies = []
        
        # Add food-based mitigations
        for food in mitigating_foods:
            strategies.append({
                "type": "nutrition",
                "compound": food.get("compound", ""),
                "dose": food.get("dose", ""),
                "timing": food.get("timing", ""),
                "mechanism": food.get("mechanism", ""),
                "target_toxicity": food.get("pathway", "general")
            })
        
        # Add drug-specific mitigations
        if moa == "taxane":
            strategies.append({
                "type": "supplement",
                "compound": "Alpha-lipoic acid",
                "dose": "600mg daily",
                "timing": "Start now, continue throughout treatment",
                "mechanism": "Protects nerve cells from oxidative damage",
                "target_toxicity": "peripheral_neuropathy"
            })
        
        if moa == "platinum_agent":
            strategies.append({
                "type": "monitoring",
                "action": "Monitor kidney function (creatinine, eGFR)",
                "frequency": "Before each cycle",
                "target_toxicity": "nephrotoxicity"
            })
        
        return strategies













