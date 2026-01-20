"""
Drug Mapping: Drug-to-pathway mapping utilities.
"""
from typing import Dict
from .panel_config import DEFAULT_MM_PANEL, DEFAULT_OVARIAN_PANEL, DEFAULT_MELANOMA_PANEL, get_panel_for_disease


def get_pathway_weights_for_drug(drug_name: str, disease: str = None) -> Dict[str, float]:
        """Get pathway weights for a specific drug.
        
        Args:
                drug_name: Name of the drug
                disease: Optional disease context to search disease-specific panels
                
        Returns:
                Dictionary of pathway weights for the drug
        """
        # Try disease-specific panel first if provided
        if disease:
                panel = get_panel_for_disease(disease)
                for drug in panel:
                        if drug["name"] == drug_name:
                                return drug.get("pathway_weights", {})
        
        # Fallback to MM panel
        for drug in DEFAULT_MM_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("pathway_weights", {})
        
        # Try ovarian panel
        for drug in DEFAULT_OVARIAN_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("pathway_weights", {})
        
        # Try melanoma panel
        for drug in DEFAULT_MELANOMA_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("pathway_weights", {})
        
        return {}


def get_pathway_weights_for_gene(gene_symbol: str) -> Dict[str, float]:
        """Get pathway weights for a gene (used to aggregate sequence impact by pathway).

        Pathway mappings:
        - MAPK drivers (BRAF/KRAS/NRAS) → ras_mapk
        - DDR genes (BRCA1/BRCA2/ATR) → ddr
        - TP53 and related → tp53
        - PI3K pathway → pi3k
        - VEGF pathway → vegf
        """
        if not gene_symbol:
                return {}
        g = gene_symbol.strip().upper()
        
        # MAPK/RAS pathway
        if g in {"BRAF", "KRAS", "NRAS", "EGFR", "MAP2K1", "MAPK1", "MEK1", "MEK2"}:
                return {"ras_mapk": 1.0}
        
        # DDR (DNA Damage Response) pathway - separate from TP53
        # Includes BER (Base Excision Repair) genes like MBD4
        if g in {"BRCA1", "BRCA2", "ATM", "ATR", "CDK12", "ARID1A", "CHEK1", "RAD50", "PALB2", "RAD51", "RAD51C", "RAD51D", "BARD1", "NBN", "MBD4"}:
                return {"ddr": 1.0}
        
        # TP53 pathway (tumor suppressor, separate from DDR)
        if g in {"TP53", "MDM2", "CHEK2"}:
                return {"tp53": 1.0}
        
        # PI3K pathway
        if g in {"PTEN", "PIK3CA", "PIK3CB", "PIK3CD", "AKT1", "AKT2", "AKT3", "MTOR"}:
                return {"pi3k": 1.0}
        
        # VEGF pathway
        if g in {"VEGFA", "VEGFR1", "VEGFR2", "KDR", "FLT1"}:
                return {"vegf": 1.0}
        

        # ═══════════════════════════════════════════════════════════════════════════════
        # PHARMACOGENE PATHWAYS (PGx - Drug Metabolism/Toxicity)
        # These route to drug-specific toxicity assessments
        # ═══════════════════════════════════════════════════════════════════════════════
        
        # DPYD - Fluoropyrimidine metabolism (5-FU, Capecitabine)
        if g in {"DPYD", "DPD"}:
                return {"fluoropyrimidine_metabolism": 1.0, "pgx_toxicity": 1.0}
        
        # TPMT - Thiopurine Methyltransferase (6-MP, Azathioprine)
        if g in {"TPMT"}:
                return {"thiopurine_metabolism": 1.0, "pgx_toxicity": 1.0}
        
        # UGT1A1 - UDP Glucuronosyltransferase (Irinotecan)
        if g in {"UGT1A1"}:
                return {"irinotecan_metabolism": 1.0, "pgx_toxicity": 1.0}
        
        # CYP2D6 - Cytochrome P450 2D6 (Codeine, Tamoxifen, many others)
        if g in {"CYP2D6"}:
                return {"cyp2d6_metabolism": 1.0, "pgx_toxicity": 1.0}
        
        # CYP2C19 - Cytochrome P450 2C19 (Clopidogrel, PPIs)
        if g in {"CYP2C19"}:
                return {"cyp2c19_metabolism": 1.0, "pgx_toxicity": 1.0}
        
        # NUDT15 - Thiopurine metabolism (especially East Asian populations)
        if g in {"NUDT15"}:
                return {"thiopurine_metabolism": 1.0, "pgx_toxicity": 1.0}
        return {}


def get_drug_moa(drug_name: str, disease: str = None) -> str:
        """Get mechanism of action for a specific drug.
        
        Args:
                drug_name: Name of the drug
                disease: Optional disease context to search disease-specific panels
                
        Returns:
                Mechanism of action string
        """
        # Try disease-specific panel first if provided
        if disease:
                panel = get_panel_for_disease(disease)
                for drug in panel:
                        if drug["name"] == drug_name:
                                return drug.get("moa", "")
        
        # Fallback to MM panel
        for drug in DEFAULT_MM_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("moa", "")
        
        # Try ovarian panel
        for drug in DEFAULT_OVARIAN_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("moa", "")
        
        # Try melanoma panel
        for drug in DEFAULT_MELANOMA_PANEL:
                if drug["name"] == drug_name:
                        return drug.get("moa", "")
        
        return ""


