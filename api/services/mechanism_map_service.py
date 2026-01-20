"""
Mechanism Map Service - Pathway Burden Visualization

CLINICAL PURPOSE: Visual pathway burden map for mechanism-matched therapy selection
Based on Manager's policy (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md - C9)

Key Policies:
- 6 mechanism chips: DDR | MAPK | PI3K | VEGF | IO | Efflux
- Color thresholds: Green ≥0.70, Yellow 0.40-0.69, Gray <0.40
- IO special case: MSI-H=Green, Unknown=Gray, MSI-S=Red (binary, not gradient)
- Pre-NGS: All gray chips with "Awaiting NGS" overlay
- Post-NGS: Color-coded from SAE pathway_burden + tumor context

Clinical Meaning (Manager's Policy C9):
- Green (≥0.70): High burden → Targetable with mechanism-matched therapies
- Yellow (0.40-0.69): Moderate burden → Consider combination strategies
- Gray (<0.40): Low burden → Lower priority for monotherapy
- "Awaiting NGS": No tumor data yet → Cannot assess mechanism burden

Author: Zo
Date: January 13, 2025
Manager: SR
For: AK - Stage IVB HGSOC
"""

from dataclasses import dataclass, asdict
from typing import Dict, List, Optional, Any


# Simple logger (standalone test compatibility)
class SimpleLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

logger = SimpleLogger()


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class MechanismChip:
    """
    A single mechanism chip in the map.
    
    Attributes:
        pathway: "DDR", "MAPK", "PI3K", "VEGF", "IO", "Efflux"
        burden: 0-1 (pathway burden score, 0.0 if unknown)
        color: "success" (green), "warning" (yellow), "default" (gray), "error" (red)
        label: Display text (e.g., "82%", "Awaiting NGS", "MSI-H")
        tooltip: Detailed explanation for hover
        status: "computed" or "awaiting_ngs"
    """
    pathway: str
    burden: float
    color: str
    label: str
    tooltip: str
    status: str = "computed"


# ============================================================================
# MECHANISM MAP SERVICE
# ============================================================================

class MechanismMapService:
    """
    Generate mechanism map chips per Manager's policy.
    
    Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (C9)
    
    Color Thresholds:
    - Green ≥0.70 (high burden, targetable)
    - Yellow 0.40-0.69 (moderate burden, consider combos)
    - Gray <0.40 (low burden, lower priority)
    
    Special Cases:
    - IO: Binary (MSI-H=Green, MSI-S=Red, Unknown=Gray)
    - Pre-NGS: All gray "Awaiting NGS"
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_map(
        self,
        tumor_context: Optional[Dict],
        sae_features: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Generate mechanism map chips.
        
        Args:
            tumor_context: Tumor NGS data (None = pre-NGS)
            sae_features: SAE pathway_burden dict (from sae_service.py)
        
        Returns:
            Dict with chips list, status, message
        
        Manager's Policy (C9):
        - Pre-NGS: All gray "Awaiting NGS"
        - Post-NGS: Color-coded from pathway_burden
        """
        # ===================================================================
        # PRE-NGS: ALL GRAY (Manager's policy C9)
        # ===================================================================
        if not tumor_context or not sae_features:
            self.logger.info("MechanismMap: Pre-NGS mode - all chips gray")
            
            return {
                "chips": [
                    asdict(MechanismChip(
                        pathway="DDR",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="DNA damage repair pathway burden - requires tumor NGS to assess. High burden (≥70%) indicates PARP/ATR/CHK1 eligibility.",
                        status="awaiting_ngs"
                    )),
                    asdict(MechanismChip(
                        pathway="MAPK",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="RAS/RAF/MEK pathway burden - requires tumor NGS. High burden (≥70%) indicates MEK/RAF inhibitor eligibility.",
                        status="awaiting_ngs"
                    )),
                    asdict(MechanismChip(
                        pathway="PI3K",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="PI3K/AKT/mTOR pathway burden - requires tumor NGS. High burden (≥70%) indicates PI3K/mTOR inhibitor eligibility.",
                        status="awaiting_ngs"
                    )),
                    asdict(MechanismChip(
                        pathway="VEGF",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="Angiogenesis pathway burden - requires tumor NGS. High burden (≥70%) supports bevacizumab addition.",
                        status="awaiting_ngs"
                    )),
                    asdict(MechanismChip(
                        pathway="IO",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="Immune checkpoint pathway - requires MSI/TMB testing. MSI-High OR TMB ≥20 → Immunotherapy eligible.",
                        status="awaiting_ngs"
                    )),
                    asdict(MechanismChip(
                        pathway="Efflux",
                        burden=0.0,
                        color="default",
                        label="Awaiting NGS",
                        tooltip="Drug efflux resistance (ABCB1) - requires tumor NGS. High expression → Cross-resistance to taxanes/anthracyclines.",
                        status="awaiting_ngs"
                    ))
                ],
                "status": "awaiting_ngs",
                "message": "Mechanism map will be available once tumor NGS results are uploaded (7-10 days). Order HRD + ctDNA to unlock.",
                "provenance": {
                    "mode": "pre_ngs",
                    "policy": "All chips gray per Manager C9"
                }
            }
        
        # ===================================================================
        # POST-NGS: COLOR-CODED (Manager's policy C9)
        # ===================================================================
        self.logger.info("MechanismMap: Post-NGS mode - computing from SAE features")
        
        pathway_burden = sae_features.get("pathway_burden", {})
        chips = []
        
        # DDR Chip
        ddr_burden = pathway_burden.get("ddr", 0.0)
        chips.append(MechanismChip(
            pathway="DDR",
            burden=ddr_burden,
            color=self._get_color(ddr_burden),
            label=f"{int(ddr_burden * 100)}%",
            tooltip=self._get_tooltip("DDR", ddr_burden),
            status="computed"
        ))
        
        # MAPK Chip
        mapk_burden = pathway_burden.get("mapk", 0.0)
        chips.append(MechanismChip(
            pathway="MAPK",
            burden=mapk_burden,
            color=self._get_color(mapk_burden),
            label=f"{int(mapk_burden * 100)}%",
            tooltip=self._get_tooltip("MAPK", mapk_burden),
            status="computed"
        ))
        
        # PI3K Chip
        pi3k_burden = pathway_burden.get("pi3k", 0.0)
        chips.append(MechanismChip(
            pathway="PI3K",
            burden=pi3k_burden,
            color=self._get_color(pi3k_burden),
            label=f"{int(pi3k_burden * 100)}%",
            tooltip=self._get_tooltip("PI3K", pi3k_burden),
            status="computed"
        ))
        
        # VEGF Chip
        vegf_burden = pathway_burden.get("vegf", 0.0)
        chips.append(MechanismChip(
            pathway="VEGF",
            burden=vegf_burden,
            color=self._get_color(vegf_burden),
            label=f"{int(vegf_burden * 100)}%",
            tooltip=self._get_tooltip("VEGF", vegf_burden),
            status="computed"
        ))
        
        # ===================================================================
        # IO Chip (SPECIAL CASE - Manager's policy C9)
        # Binary from MSI status: MSI-H=Green, MSI-S=Red, Unknown=Gray
        # ===================================================================
        msi_status = tumor_context.get("msi_status", "unknown")
        
        if msi_status == "MSI-High":
            io_chip = MechanismChip(
                pathway="IO",
                burden=1.0,
                color="success",  # Green
                label="MSI-H",
                tooltip="MSI-High detected → Immunotherapy eligible (pembrolizumab + chemo). IO mechanism chip GREEN.",
                status="computed"
            )
        elif msi_status == "MSI-Stable":
            io_chip = MechanismChip(
                pathway="IO",
                burden=0.0,
                color="error",  # Red
                label="MSI-S",
                tooltip="MSI-Stable → Immunotherapy lower priority (40% confidence). IO mechanism chip RED.",
                status="computed"
            )
        else:
            io_chip = MechanismChip(
                pathway="IO",
                burden=0.0,
                color="default",  # Gray
                label="Unknown",
                tooltip="MSI status unknown - order ctDNA to assess immunotherapy eligibility. IO mechanism chip GRAY.",
                status="awaiting_ngs"
            )
        chips.append(io_chip)
        
        # ===================================================================
        # Efflux Chip (from ABCB1 status)
        # ===================================================================
        abcb1_status = tumor_context.get("abcb1_status", "unknown")
        
        if abcb1_status == "high":
            efflux_chip = MechanismChip(
                pathway="Efflux",
                burden=1.0,
                color="error",  # Red (BAD - indicates resistance)
                label="High Risk",
                tooltip="ABCB1 high → Cross-resistance to taxanes/anthracyclines. Consider non-substrates: platinum, PARP, ATR/CHK1.",
                status="computed"
            )
        elif abcb1_status == "normal":
            efflux_chip = MechanismChip(
                pathway="Efflux",
                burden=0.0,
                color="success",  # Green (GOOD - no resistance)
                label="Low Risk",
                tooltip="ABCB1 normal → No efflux-mediated resistance detected. Re-challenge with taxanes may be appropriate.",
                status="computed"
            )
        else:
            efflux_chip = MechanismChip(
                pathway="Efflux",
                burden=0.0,
                color="default",  # Gray
                label="Unknown",
                tooltip="ABCB1 status unknown - may be included in comprehensive NGS panel or order IHC.",
                status="awaiting_ngs"
            )
        chips.append(efflux_chip)
        
        return {
            "chips": [asdict(c) for c in chips],
            "status": "computed",
            "message": "Mechanism burden computed from tumor NGS + SAE features",
            "provenance": {
                "sae_version": sae_features.get("version", "unknown"),
                "pathway_burden_source": "sae_service.pathway_burden",
                "policy_source": "MANAGER_ANSWERS (C9)"
            }
        }
    
    def _get_color(self, burden: float) -> str:
        """
        Get chip color per Manager's thresholds (C9).
        
        Manager's Policy:
        - Green ≥0.70 (high burden, targetable)
        - Yellow 0.40-0.69 (moderate burden, combos)
        - Gray <0.40 (low burden, lower priority)
        """
        if burden >= 0.70:
            return "success"  # Green
        elif burden >= 0.40:
            return "warning"  # Yellow
        else:
            return "default"  # Gray
    
    def _get_tooltip(self, pathway: str, burden: float) -> str:
        """
        Generate tooltip explaining burden level.
        
        Args:
            pathway: Pathway name (e.g., "DDR")
            burden: 0-1 burden score
        
        Returns:
            Tooltip text with clinical interpretation
        """
        pathway_descriptions = {
            "DDR": "DNA damage repair (BRCA1/2, RAD51, PALB2, ATM, etc.)",
            "MAPK": "RAS/RAF/MEK pathway (KRAS, BRAF, NRAS, etc.)",
            "PI3K": "PI3K/AKT/mTOR pathway",
            "VEGF": "Angiogenesis pathway"
        }
        
        pathway_desc = pathway_descriptions.get(pathway, pathway)
        burden_pct = int(burden * 100)
        
        if burden >= 0.70:
            return (
                f"{pathway_desc}: High burden ({burden_pct}%) detected. "
                f"Targetable with {pathway}-specific therapies. "
                f"Consider mechanism-matched trials or approved agents."
            )
        elif burden >= 0.40:
            return (
                f"{pathway_desc}: Moderate burden ({burden_pct}%). "
                f"Consider combination strategies targeting {pathway} + other pathways."
            )
        else:
            return (
                f"{pathway_desc}: Low burden ({burden_pct}%). "
                f"Lower priority for {pathway}-targeted monotherapy. "
                f"Consider alternative mechanisms or broad-spectrum approaches."
            )


# ============================================================================
# FACTORY FUNCTION (for orchestrator)
# ============================================================================

def get_mechanism_map(
    tumor_context: Optional[Dict] = None,
    sae_features: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Factory function for orchestrator integration.
    
    Args:
        tumor_context: Tumor NGS data (None = pre-NGS)
        sae_features: SAE pathway_burden from sae_service.py
    
    Returns:
        Dict with chips, status, message, provenance
    
    Example (Pre-NGS):
        >>> result = get_mechanism_map(tumor_context=None, sae_features=None)
        >>> result["status"]
        "awaiting_ngs"
        >>> len(result["chips"])
        6  # All gray
    
    Example (Post-NGS):
        >>> result = get_mechanism_map(
        ...     tumor_context={"hrd_score": 55, "msi_status": "MSI-High"},
        ...     sae_features={"pathway_burden": {"ddr": 0.82, "mapk": 0.15, ...}}
        ... )
        >>> result["status"]
        "computed"
        >>> result["chips"][0]  # DDR chip
        {"pathway": "DDR", "burden": 0.82, "color": "success", "label": "82%", ...}
    """
    service = MechanismMapService()
    return service.generate_map(tumor_context, sae_features)


# ============================================================================
# QUICK TEST (for validation)
# ============================================================================

if __name__ == "__main__":
    # Test Case 1: Pre-NGS (Ayesha's current state)
    print("\n⚔️ TEST CASE 1: PRE-NGS (Ayesha - awaiting tumor data)")
    
    result = get_mechanism_map(
        tumor_context=None,
        sae_features=None
    )
    
    print(f"\n✅ Status: {result['status']}")
    print(f"✅ Message: {result['message']}")
    print(f"✅ Total chips: {len(result['chips'])}")
    print(f"\n📋 ALL CHIPS (should be gray):")
    for chip in result['chips']:
        print(f"  {chip['pathway']}: {chip['label']} ({chip['color']})")
    
    # Expected: All 6 chips gray, status="awaiting_ngs"
    assert result['status'] == "awaiting_ngs", "FAILED: Should be awaiting_ngs"
    assert all(c['color'] == 'default' for c in result['chips']), "FAILED: All chips should be gray"
    print("\n✅ Pre-NGS policy VERIFIED!")
    
    print("\n" + "="*80)
    
    # Test Case 2: Post-NGS with high DDR burden (HRD-high patient)
    print("\n⚔️ TEST CASE 2: POST-NGS (High DDR burden, MSI-High)")
    
    mock_sae = {
        "pathway_burden": {
            "ddr": 0.82,   # High (green)
            "mapk": 0.15,  # Low (gray)
            "pi3k": 0.30,  # Low (gray)
            "vegf": 0.55   # Moderate (yellow)
        },
        "version": "v1.0"
    }
    
    mock_tumor = {
        "hrd_score": 62,
        "msi_status": "MSI-High",  # IO chip should be GREEN
        "tmb": 25,
        "abcb1_status": "normal"   # Efflux chip should be GREEN (good)
    }
    
    result2 = get_mechanism_map(
        tumor_context=mock_tumor,
        sae_features=mock_sae
    )
    
    print(f"\n✅ Status: {result2['status']}")
    print(f"✅ Total chips: {len(result2['chips'])}")
    print(f"\n📋 ALL CHIPS (color-coded):")
    for chip in result2['chips']:
        print(f"  {chip['pathway']}: {chip['label']} ({chip['color']}) - {chip['tooltip'][:60]}...")
    
    # Expected:
    # DDR: 82% (green) - high burden
    # MAPK: 15% (gray) - low burden
    # PI3K: 30% (gray) - low burden
    # VEGF: 55% (yellow) - moderate burden
    # IO: MSI-H (green) - binary high
    # Efflux: Low Risk (green) - ABCB1 normal
    
    assert result2['status'] == "computed", "FAILED: Should be computed"
    assert result2['chips'][0]['color'] == 'success', "FAILED: DDR should be green (0.82)"
    assert result2['chips'][4]['color'] == 'success', "FAILED: IO should be green (MSI-High)"
    print("\n✅ Post-NGS color coding VERIFIED!")
    
    print("\n" + "="*80)
    
    # Test Case 3: Edge case - all moderate burdens
    print("\n⚔️ TEST CASE 3: EDGE CASE (All moderate burdens, MSI-Stable)")
    
    mock_sae3 = {
        "pathway_burden": {
            "ddr": 0.55,   # Moderate (yellow)
            "mapk": 0.45,  # Moderate (yellow)
            "pi3k": 0.50,  # Moderate (yellow)
            "vegf": 0.60   # Moderate (yellow)
        }
    }
    
    mock_tumor3 = {
        "hrd_score": 38,  # Below threshold but not zero
        "msi_status": "MSI-Stable",  # IO chip should be RED
        "abcb1_status": "unknown"    # Efflux chip should be GRAY
    }
    
    result3 = get_mechanism_map(
        tumor_context=mock_tumor3,
        sae_features=mock_sae3
    )
    
    print(f"\n📋 ALL CHIPS:")
    for chip in result3['chips']:
        print(f"  {chip['pathway']}: {chip['label']} ({chip['color']})")
    
    # Expected: All yellow (moderate) except IO (red) and Efflux (gray)
    yellow_count = sum(1 for c in result3['chips'] if c['color'] == 'warning')
    print(f"\n✅ Yellow (moderate) chips: {yellow_count} (expected 4)")
    print(f"✅ IO chip: {result3['chips'][4]['label']} ({result3['chips'][4]['color']}) - Expected RED for MSI-S")
    print(f"✅ Efflux chip: {result3['chips'][5]['label']} ({result3['chips'][5]['color']}) - Expected GRAY for unknown")


