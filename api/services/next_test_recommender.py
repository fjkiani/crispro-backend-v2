"""
Next-Test Recommender Service

CLINICAL PURPOSE: Prioritized biomarker testing recommendations for ovarian cancer
Based on Manager's policy (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md - P1, C6)

Priority Logic (Manager-Approved):
1. HRD (MyChoice CDx) - PARP gate, 10d turnaround
2. ctDNA (Guardant360/FoundationOne) - MSI/TMB + somatic HRR, 7d turnaround
3. SLFN11 IHC - PARP sensitivity, 5d turnaround
4. ABCB1 proxy - Efflux resistance (only if prior taxane), 5d turnaround

Key Policies:
- Use "differential branches" format (If positive → X; If negative → Y)
- Include turnaround + cost estimates
- Trigger on completeness L0/L1 or missing HRD/MSI/TMB
- Max 4 recommendations

Author: Zo
Date: January 13, 2025
Manager: SR
For: AK - Stage IVB HGSOC (germline-negative, awaiting NGS)
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any


# Simple logger (avoid logging import conflicts in standalone test)
class SimpleLogger:
    def info(self, msg): print(f"[INFO] {msg}")
    def warning(self, msg): print(f"[WARN] {msg}")
    def error(self, msg): print(f"[ERROR] {msg}")

logger = SimpleLogger()


# ============================================================================
# DATA STRUCTURES
# ============================================================================

@dataclass
class NextTestRecommendation:
    """
    A prioritized biomarker test recommendation.
    
    Attributes:
        test_name: Full test name (e.g., "HRD Score (MyChoice CDx)")
        priority: 1-4 (1 = highest priority per Manager's policy)
        turnaround_days: Expected turnaround in days
        cost_estimate: Cost range (e.g., "$4,000-$6,000")
        impact_if_positive: What unlocks if test is positive
        impact_if_negative: What unlocks if test is negative
        rationale: Why this test is recommended
        urgency: "high", "medium", "low"
        test_type: "tissue", "blood", "ihc" for logistics
        ordering_info: How to order (optional)
    """
    test_name: str
    priority: int
    turnaround_days: int
    cost_estimate: str
    impact_if_positive: str
    impact_if_negative: str
    rationale: str
    urgency: str
    test_type: str = "tissue"
    ordering_info: Optional[str] = None


# ============================================================================
# NEXT-TEST RECOMMENDER SERVICE
# ============================================================================

class NextTestRecommenderService:
    """
    Generate prioritized next-test recommendations per Manager's policy.
    
    Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P1, C6)
    
    Priority Order:
    1. HRD (PARP gate)
    2. ctDNA MSI/TMB + somatic HRR (IO + DDR combo considerations)
    3. SLFN11 IHC (PARP sensitivity)
    4. ABCB1 proxy (only if prior taxane exposure)
    """
    
    def __init__(self):
        self.logger = logger
    
    def recommend_tests(
        self,
        germline_status: str,
        tumor_context: Optional[Dict] = None,
        treatment_history: Optional[List[str]] = None,
        disease: str = "ovarian_cancer_hgs",
        sae_features: Optional[Dict] = None  # ⚔️ P1.3: SAE-based dynamic prioritization
    ) -> List[NextTestRecommendation]:
        """
        Generate prioritized test recommendations.
        
        Args:
            germline_status: "positive", "negative", "unknown"
            tumor_context: Existing tumor NGS data (may be None or incomplete)
            treatment_history: List of prior therapies (e.g., ["carboplatin", "paclitaxel"])
            disease: Disease type (default: ovarian HGSOC)
        
        Returns:
            List of NextTestRecommendation objects, sorted by priority
        
        Manager's Policy:
        - Trigger on missing HRD/MSI/TMB or completeness L0/L1
        - Priority: 1) HRD → 2) ctDNA → 3) SLFN11 → 4) ABCB1
        - Differential branches format (If + → X; If - → Y)
        """
        recommendations = []
        treatment_history = treatment_history or []
        tumor_context = tumor_context or {}
        
        # Parse existing biomarkers
        has_hrd = tumor_context.get("hrd_score") is not None
        has_msi = tumor_context.get("msi_status") is not None
        has_tmb = tumor_context.get("tmb") is not None
        has_slfn11 = tumor_context.get("slfn11_status") is not None
        has_abcb1 = tumor_context.get("abcb1_status") is not None
        
        self.logger.info(f"NextTest recommender: germline={germline_status}, has_hrd={has_hrd}, has_msi={has_msi}, has_tmb={has_tmb}")
        
        # ===================================================================
        # TEST 1: HRD (Priority 1 - PARP gate)
        # Manager's Policy (P1, C6): "HRD (PARP gate)"
        # ===================================================================
        if not has_hrd:
            recommendations.append(NextTestRecommendation(
                test_name="HRD Score (MyChoice CDx or tissue-based NGS)",
                priority=1,
                turnaround_days=10,
                cost_estimate="$4,000-$6,000 (typically covered by insurance for Stage III/IV ovarian)",
                impact_if_positive=(
                    "HRD ≥42 → PARP maintenance eligible (NCCN Category 1), "
                    "confidence 90% for olaparib/niraparib/rucaparib. "
                    "Unlock mechanism map DDR chip (green if ≥0.70)."
                ),
                impact_if_negative=(
                    "HRD <42 → PARP reduced benefit (confidence 60%), "
                    "consider ATR/CHK1 combo trials (NCT03462342, NCT02264678) or "
                    "platinum-based standard without PARP maintenance."
                ),
                rationale=(
                    "HRD score determines PARP inhibitor eligibility and confidence level. "
                    "Critical for first-line maintenance decision after platinum response. "
                    "Germline-negative patients can still have somatic HRD."
                ),
                urgency="high",
                test_type="tissue",
                ordering_info=(
                    "Order via Myriad Genetics (MyChoice CDx) or include in comprehensive tumor NGS panel. "
                    "Requires FFPE tissue block or fresh tumor biopsy."
                )
            ))
        
        # ===================================================================
        # TEST 2: ctDNA Panel (Priority 2 - IO + DDR combo considerations)
        # Manager's Policy (P1, C6): "ctDNA MSI/TMB + somatic HRR"
        # ===================================================================
        if not (has_msi and has_tmb):
            recommendations.append(NextTestRecommendation(
                test_name="ctDNA Comprehensive Panel (Guardant360 CDx or FoundationOne Liquid CDx)",
                priority=2,
                turnaround_days=7,
                cost_estimate="$5,000-$7,000 (typically covered by insurance)",
                impact_if_positive=(
                    "MSI-High OR TMB ≥20 → Immunotherapy eligible (pembrolizumab + chemo), confidence 85%. "
                    "IO mechanism chip → green. "
                    "Somatic BRCA1/BRCA2 or HRR mutations → PARP confidence 90% (even with germline-negative). "
                    "DDR mechanism chip → green if somatic HRR detected."
                ),
                impact_if_negative=(
                    "MSI-Stable AND TMB <20 → Immunotherapy lower priority (confidence 40%). "
                    "IO mechanism chip → red. "
                    "No somatic HRR → standard platinum backbone (no PARP unless tissue HRD ≥42)."
                ),
                rationale=(
                    "MSI/TMB unlock immunotherapy eligibility (critical in platinum-resistant setting). "
                    "Somatic HRR mutations enable PARP strategies even when germline negative (15-20% of HGSOC). "
                    "ctDNA faster than tissue (7d vs 10-14d) and tracks clonal evolution."
                ),
                urgency="high",
                test_type="blood",
                ordering_info=(
                    "Order via Guardant Health (Guardant360 CDx) or Foundation Medicine (FoundationOne Liquid CDx). "
                    "Requires 2-3 tubes of blood (10mL EDTA). No tissue needed."
                )
            ))
        
        # ===================================================================
        # TEST 3: SLFN11 IHC (Priority 3 - PARP sensitivity)
        # Manager's Policy (P1, C6): "SLFN11 IHC (PARP sensitivity)"
        # ===================================================================
        if not has_slfn11 and germline_status != "positive":
            recommendations.append(NextTestRecommendation(
                test_name="SLFN11 IHC (Immunohistochemistry)",
                priority=3,
                turnaround_days=5,
                cost_estimate="$300-$500",
                impact_if_positive=(
                    "SLFN11+ → Normal PARP sensitivity maintained, confidence 85%. "
                    "Proceed with PARP maintenance if HRD ≥42. "
                    "No adjustment to DDR mechanism burden."
                ),
                impact_if_negative=(
                    "SLFN11- → Reduced PARP sensitivity (confidence drops to 50%), "
                    "consider ATR/CHK1 or platinum-based alternatives. "
                    "Flag in hint tiles: 'SLFN11 loss → favor ATR over PARP'."
                ),
                rationale=(
                    "SLFN11 (Schlafen 11) expression correlates with PARP inhibitor response. "
                    "Low/absent SLFN11 indicates intrinsic PARP resistance risk. "
                    "Important for germline-negative patients where PARP benefit less certain."
                ),
                urgency="medium",
                test_type="ihc",
                ordering_info=(
                    "Order via pathology lab IHC panel. "
                    "Requires FFPE tissue block (same block used for HRD/tumor NGS). "
                    "Not always covered by insurance (check prior authorization)."
                )
            ))
        
        # ===================================================================
        # TEST 4: ABCB1 Proxy (Priority 4 - only if prior taxane exposure)
        # Manager's Policy (C4): "ABCB1 proxy if post-taxane scenario emerges"
        # ===================================================================
        prior_taxane = any(
            "taxane" in t.lower() or 
            "paclitaxel" in t.lower() or 
            "docetaxel" in t.lower() or
            "nab-paclitaxel" in t.lower()
            for t in treatment_history
        )
        
        if prior_taxane and not has_abcb1:
            recommendations.append(NextTestRecommendation(
                test_name="ABCB1 Expression Proxy (via CNV from NGS or IHC)",
                priority=4,
                turnaround_days=5,
                cost_estimate="$200-$400 (if not included in NGS panel)",
                impact_if_positive=(
                    "ABCB1 CNV >4 or expression high → Cross-resistance to taxanes/anthracyclines likely (70% risk). "
                    "Efflux mechanism chip → red. "
                    "Consider non-substrate regimens: platinum, PARP, ATR/CHK1 (not taxane substrates)."
                ),
                impact_if_negative=(
                    "ABCB1 normal → No efflux-mediated resistance detected. "
                    "Efflux mechanism chip → gray/green. "
                    "Re-challenge with taxanes may be appropriate if other factors favorable."
                ),
                rationale=(
                    "Prior taxane exposure + ABCB1 (P-glycoprotein) overexpression indicates efflux-mediated resistance. "
                    "ABCB1 pumps out taxanes, anthracyclines, vinca alkaloids → reduced drug efficacy. "
                    "Relevant only if prior taxane exposure (not applicable to treatment-naive patients like Ayesha)."
                ),
                urgency="medium",
                test_type="tissue",
                ordering_info=(
                    "Check if ABCB1 copy number included in comprehensive NGS panel. "
                    "If not, order IHC for P-glycoprotein (MDR1 antibody). "
                    "Requires FFPE tissue."
                )
            ))
        
        # ===================================================================
        # ⚔️ P1.3: SAE-BASED DYNAMIC PRIORITIZATION
        # Manager Policy (C6): Adjust priorities based on SAE features
        # ===================================================================
        if sae_features:
            dna_repair_capacity = sae_features.get("dna_repair_capacity", 0.5)
            hotspot_mutation = sae_features.get("hotspot_mutation", False)
            
            # Rule 1: High DNA repair capacity (≥0.70) → Prioritize SLFN11 IHC
            # Rationale: High DNA repair suggests HRD; SLFN11 validates PARP sensitivity
            if dna_repair_capacity >= 0.70:
                for rec in recommendations:
                    if "SLFN11" in rec.test_name and rec.priority > 2:
                        self.logger.info(f"⚔️ P1.3: Elevating SLFN11 priority (DNA repair capacity={dna_repair_capacity:.2f})")
                        rec.priority = 2  # Elevate to priority 2 (after HRD)
                        rec.rationale = (
                            f"[SAE-Enhanced Priority] High DNA repair capacity ({dna_repair_capacity:.2f}) detected. "
                            "SLFN11 IHC recommended to validate PARP sensitivity in HRD-likely tumors. " +
                            rec.rationale
                        )
            
            # Rule 2: Hotspot mutation detected → Prioritize ctDNA panel
            # Rationale: Hotspot detected; full somatic profiling needed for pathway analysis
            if hotspot_mutation:
                hotspot_details = sae_features.get("hotspot_details", {})
                mutation = hotspot_details.get("mutation", "unknown")
                for rec in recommendations:
                    if "ctDNA" in rec.test_name and rec.priority > 2:
                        self.logger.info(f"⚔️ P1.3: Elevating ctDNA priority (hotspot {mutation} detected)")
                        rec.priority = 2  # Elevate to priority 2 (after HRD)
                        rec.rationale = (
                            f"[SAE-Enhanced Priority] MAPK hotspot ({mutation}) detected. "
                            "Comprehensive ctDNA profiling recommended for full somatic landscape. " +
                            rec.rationale
                        )
        
        # ===================================================================
        # SORT BY PRIORITY AND RETURN
        # ===================================================================
        recommendations.sort(key=lambda x: x.priority)
        
        self.logger.info(f"NextTest recommender generated {len(recommendations)} tests: {[r.test_name for r in recommendations]}")
        
        return recommendations
    
    def get_top_priority_test(
        self,
        germline_status: str,
        tumor_context: Optional[Dict] = None,
        treatment_history: Optional[List[str]] = None
    ) -> Optional[NextTestRecommendation]:
        """
        Get single highest-priority test.
        
        Args:
            germline_status: Germline mutation status
            tumor_context: Existing tumor NGS data
            treatment_history: Prior therapies
        
        Returns:
            Top priority test or None if all tests complete
        """
        recommendations = self.recommend_tests(
            germline_status, tumor_context, treatment_history
        )
        
        return recommendations[0] if recommendations else None
    
    def format_as_checklist(
        self,
        recommendations: List[NextTestRecommendation]
    ) -> str:
        """
        Format recommendations as Markdown checklist.
        
        Args:
            recommendations: List of test recommendations
        
        Returns:
            Markdown-formatted checklist string
        
        Example:
            ## 📋 NGS Fast-Track Checklist
            
            ### Priority 1: HRD Score
            - **Test**: MyChoice CDx (tissue-based)
            - **Turnaround**: 10 days
            - **Cost**: $4,000-$6,000
            ...
        """
        if not recommendations:
            return "✅ All recommended biomarker tests complete!"
        
        lines = ["## 📋 NGS Fast-Track Checklist\n"]
        
        for rec in recommendations:
            lines.append(f"### Priority {rec.priority}: {rec.test_name.split('(')[0].strip()}")
            lines.append(f"- **Test**: {rec.test_name}")
            lines.append(f"- **Turnaround**: {rec.turnaround_days} days")
            lines.append(f"- **Cost**: {rec.cost_estimate}")
            lines.append(f"- **Urgency**: {rec.urgency.upper()}")
            lines.append(f"\n**What This Unlocks**:")
            lines.append(f"- ✅ If Positive: {rec.impact_if_positive[:150]}...")
            lines.append(f"- ⚠️ If Negative: {rec.impact_if_negative[:150]}...")
            lines.append(f"\n**Why**: {rec.rationale[:200]}...")
            lines.append(f"\n**Ordering**: {rec.ordering_info or 'Consult pathology/oncology team'}")
            lines.append("\n---\n")
        
        return "\n".join(lines)


# ============================================================================
# FACTORY FUNCTION (for orchestrator)
# ============================================================================

def get_next_test_recommendations(
    germline_status: str,
    tumor_context: Optional[Dict] = None,
    treatment_history: Optional[List[str]] = None,
    disease: str = "ovarian_cancer_hgs",
    sae_features: Optional[Dict] = None  # ⚔️ P1.3: SAE-based dynamic prioritization
) -> Dict[str, Any]:
    """
    Factory function for orchestrator integration.
    
    Args:
        germline_status: Germline mutation status
        tumor_context: Existing tumor NGS data
        treatment_history: Prior therapies
        disease: Disease type
    
    Returns:
        Dict with recommendations, top_priority, summary, provenance
    
    Example:
        >>> result = get_next_test_recommendations(
        ...     germline_status="negative",
        ...     tumor_context=None,
        ...     treatment_history=[]
        ... )
        >>> result["recommendations"]
        [
            {"test_name": "HRD Score...", "priority": 1, ...},
            {"test_name": "ctDNA Panel...", "priority": 2, ...},
            {"test_name": "SLFN11 IHC...", "priority": 3, ...}
        ]
    """
    service = NextTestRecommenderService()
    recommendations = service.recommend_tests(
        germline_status, tumor_context, treatment_history, disease, sae_features  # ⚔️ P1.3
    )
    
    # Convert to dict for JSON serialization
    recs_dict = [asdict(r) for r in recommendations]
    
    # Summary
    high_priority_count = sum(1 for r in recommendations if r.urgency == "high")
    total_turnaround = max([r.turnaround_days for r in recommendations], default=0)
    
    return {
        "recommendations": recs_dict,
        "top_priority": recs_dict[0] if recs_dict else None,
        "total_tests": len(recs_dict),
        "high_priority_count": high_priority_count,
        "estimated_turnaround": f"{total_turnaround} days (if tests run in parallel)",
        "urgency_summary": f"{high_priority_count} high-priority test{'s' if high_priority_count != 1 else ''} recommended",
        "checklist_markdown": service.format_as_checklist(recommendations),
        "provenance": {
            "version": "v1.0",
            "policy_source": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P1, C6)",
            "manager": "SR",
            "date": "2025-01-13",
            "note": "Priority order: 1) HRD (PARP gate), 2) ctDNA (IO+DDR), 3) SLFN11 (PARP sensitivity), 4) ABCB1 (if prior taxane)"
        }
    }


# ============================================================================
# QUICK TEST (for validation)
# ============================================================================

if __name__ == "__main__":
    # Test Case 1: Ayesha's profile (germline-negative, no NGS, treatment-naive)
    print("\n⚔️ TEST CASE 1: AYESHA (germline-negative, no NGS, treatment-naive)")
    result = get_next_test_recommendations(
        germline_status="negative",
        tumor_context=None,
        treatment_history=[]
    )
    
    print(f"\n✅ Total tests: {result['total_tests']}")
    print(f"✅ Urgency: {result['urgency_summary']}")
    print(f"✅ Top priority: {result['top_priority']['test_name']}")
    print(f"\n📋 ALL TESTS:")
    for rec in result['recommendations']:
        print(f"  {rec['priority']}. {rec['test_name']} ({rec['urgency']} urgency, {rec['turnaround_days']}d)")
    
    # Expected: 3 tests (HRD, ctDNA, SLFN11)
    # NOT: ABCB1 (because treatment-naive)
    
    print("\n" + "="*80)
    
    # Test Case 2: Post-taxane patient (simulate resistance scenario)
    print("\n⚔️ TEST CASE 2: POST-TAXANE PATIENT (prior paclitaxel, no ABCB1 data)")
    result2 = get_next_test_recommendations(
        germline_status="negative",
        tumor_context={"hrd_score": 55, "msi_status": "MSI-Stable"},  # Has HRD + MSI
        treatment_history=["carboplatin", "paclitaxel"]
    )
    
    print(f"\n✅ Total tests: {result2['total_tests']}")
    print(f"✅ Top priority: {result2['top_priority']['test_name'] if result2['top_priority'] else 'None'}")
    print(f"\n📋 ALL TESTS:")
    for rec in result2['recommendations']:
        print(f"  {rec['priority']}. {rec['test_name']} ({rec['urgency']} urgency)")
    
    # Expected: 2 tests (SLFN11, ABCB1)
    # NOT: HRD (already has it), ctDNA (already has MSI)

