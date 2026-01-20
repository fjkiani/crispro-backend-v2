"""
Hint Tiles Service - Clinician Action Guidance

CLINICAL PURPOSE: Generate concise, actionable hint tiles for clinical decision support
Based on Manager's policy (MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md - P5, C8)

Key Policies:
- Max 4 tiles total
- Priority order: Next test → Trials lever → Monitoring → Avoid
- Pre-NGS: test + monitoring + trials lever only (NO "avoid" for treatment-naive)
- Suggestive tone ("Consider..."), NOT directive ("Order now")
- Short reasons (2-3 bullets max)
- RUO-appropriate language

Tile Categories:
1. "next_test" - Recommended diagnostic test
2. "trials_lever" - Clinical trial opportunities
3. "monitoring" - CA-125 or biomarker monitoring strategy
4. "avoid" - Cross-resistance avoidance (ONLY if treatment history + risk detected)

Author: Zo
Date: January 13, 2025
Manager: SR
For: AK - Stage IVB HGSOC
"""

from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any


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
class HintTile:
    """
    A clinician hint tile.
    
    Attributes:
        category: "next_test", "trials_lever", "monitoring", "avoid"
        title: Tile header (e.g., "📋 Recommended Next Test")
        message: Main actionable message (e.g., "Consider ordering HRD test")
        reasons: List of 2-3 supporting reasons
        priority: 1-4 (1 = highest, per Manager's policy)
        icon: Emoji or icon name for UI
        action_link: Optional deep link to action (e.g., "/ngs-fast-track")
        provenance: Data source for this hint
    """
    category: str
    title: str
    message: str
    reasons: List[str]
    priority: int
    icon: str
    action_link: Optional[str] = None
    provenance: Optional[str] = None


# ============================================================================
# HINT TILES SERVICE
# ============================================================================

class HintTilesService:
    """
    Generate clinician hint tiles per Manager's policy.
    
    Policy Source: MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P5, C8)
    
    Rules:
    - Max 4 tiles
    - Priority: Test (1) → Trials (2) → Monitor (3) → Avoid (4)
    - Tone: Suggestive ("Consider..."), not directive
    - Pre-NGS: Only Test + Trials + Monitor (NO Avoid for treatment-naive)
    """
    
    def __init__(self):
        self.logger = logger
    
    def generate_hints(
        self,
        germline_status: str,
        tumor_context: Optional[Dict],
        ca125_intelligence: Optional[Dict],
        next_test_recommendations: List[Dict],
        treatment_history: Optional[List[str]] = None,
        trials_matched: int = 0,
        sae_features: Optional[Dict] = None  # ⚔️ NEW: SAE hotspot detection (P1.1)
    ) -> List[HintTile]:
        """
        Generate max 4 hint tiles.
        
        Args:
            germline_status: "positive", "negative", "unknown"
            tumor_context: Tumor NGS data (may be None)
            ca125_intelligence: CA-125 analysis results
            next_test_recommendations: From next_test_recommender service
            treatment_history: Prior therapies
            trials_matched: Number of trials matched
        
        Returns:
            List of HintTile objects (max 4), sorted by priority
        
        Manager's Priority Order (P5):
        1. Next test
        2. Trials lever
        3. Monitoring
        4. Avoid (only if applicable)
        """
        hints = []
        treatment_history = treatment_history or []
        
        # ===================================================================
        # TILE 1: NEXT TEST (Priority 1)
        # Show if missing biomarkers
        # ===================================================================
        if next_test_recommendations and len(next_test_recommendations) > 0:
            top_test = next_test_recommendations[0]
            
            # Extract test name (shorten if too long)
            test_name_short = top_test.get("test_name", "").split("(")[0].strip()
            
            hints.append(HintTile(
                category="next_test",
                title="📋 Recommended Next Test",
                message=f"Consider ordering {test_name_short}",
                reasons=[
                    top_test.get("rationale", "")[:120] + "...",
                    f"Turnaround: {top_test.get('turnaround_days')} days",
                    f"Unlocks: {top_test.get('impact_if_positive', '')[:100]}..."
                ],
                priority=1,
                icon="🧪",
                action_link="/ngs-fast-track",
                provenance="next_test_recommender.priority_1"
            ))
        
        # ===================================================================
        # TILE 2: TRIALS LEVER (Priority 2)
        # Show for frontline patients or when trials matched
        # ===================================================================
        if germline_status == "negative" and not tumor_context:
            # Pre-NGS scenario (like Ayesha)
            hints.append(HintTile(
                category="trials_lever",
                title="🔬 Clinical Trial Opportunities",
                message=f"Consider frontline trial enrollment ({trials_matched} trials matched)",
                reasons=[
                    "Stage IVB frontline - prime trial candidate",
                    f"NYC metro - multiple sites within 50 miles",
                    "Once NGS available → mechanism-matched trial prioritization"
                ],
                priority=2,
                icon="🎯",
                action_link="/ayesha-trials",
                provenance="ayesha_trials.frontline_filter"
            ))
        
        elif tumor_context and trials_matched > 0:
            # Post-NGS scenario (mechanism fit available)
            hints.append(HintTile(
                category="trials_lever",
                title="🎯 Mechanism-Matched Trials",
                message=f"Consider mechanism-aligned trials ({trials_matched} matched)",
                reasons=[
                    "Mechanism fit calculated from tumor genomics",
                    f"{trials_matched} trials align with detected pathway burden",
                    "Ranked by eligibility (70%) + mechanism fit (30%)"
                ],
                priority=2,
                icon="🎯",
                action_link="/ayesha-trials",
                provenance="mechanism_fit_ranker.post_ngs"
            ))
        
        # ===================================================================
        # TILE 2.5: HOTSPOT MUTATION DETECTED (Priority 2, added after trials)
        # ⚔️ P1.1: Manager's Order - Show MEK/RAF trial hint when hotspot detected
        # Manager Policy (C2): MAPK hotspot → MEK/RAF trial candidates
        # ===================================================================
        if sae_features and sae_features.get("hotspot_mutation"):
            hotspot_details = sae_features.get("hotspot_details", {})
            gene = hotspot_details.get("gene", "KRAS")
            mutation = hotspot_details.get("mutation", "unknown")
            pathway = hotspot_details.get("pathway", "MAPK")
            
            hints.append(HintTile(
                category="trials_lever",
                title=f"🧬 {pathway} Hotspot Detected",
                message=f"Consider MEK/RAF inhibitor trials - {gene} {mutation} detected",
                reasons=[
                    f"{gene} {mutation} is a known COSMIC hotspot",
                    f"{pathway} pathway activation likely",
                    "MEK/RAF inhibitor trials may show enhanced efficacy",
                    "RUO: Investigational only - not standard of care"
                ],
                priority=2,  # Same priority as trials (will appear in trials section)
                icon="🧬",
                action_link="/ayesha-trials?filter=MAPK",
                provenance="sae_hotspot_detector.cosmic_match"
            ))
            self.logger.info(f"⚔️ P1.1: Added hotspot hint tile for {gene} {mutation}")
        
        # ===================================================================
        # TILE 3: MONITORING (Priority 3)
        # Show CA-125 monitoring strategy if burden EXTENSIVE
        # ===================================================================
        if ca125_intelligence:
            burden_class = ca125_intelligence.get("burden_classification", "UNKNOWN")
            current_ca125 = ca125_intelligence.get("current_value", 0)
            
            if burden_class == "EXTENSIVE":
                hints.append(HintTile(
                    category="monitoring",
                    title="📊 CA-125 Monitoring Strategy",
                    message="Consider monitoring CA-125 every 3 weeks during chemotherapy",
                    reasons=[
                        f"Current CA-125: {current_ca125:,.0f} U/mL (EXTENSIVE burden)",
                        "Alert if: <50% drop by cycle 3 OR on-therapy rise",
                        "Target: ≥70% drop by cycle 3, ≥90% by cycle 6"
                    ],
                    priority=3,
                    icon="⏱️",
                    action_link="/ca125-tracker",
                    provenance="ca125_intelligence.extensive_burden"
                ))
            
            elif burden_class in ["SIGNIFICANT", "MODERATE"]:
                hints.append(HintTile(
                    category="monitoring",
                    title="📊 CA-125 Monitoring",
                    message=f"Consider CA-125 monitoring ({burden_class.lower()} burden)",
                    reasons=[
                        f"Current CA-125: {current_ca125:,.0f} U/mL",
                        "Track response during treatment",
                        "Early resistance detection (3-6 weeks earlier than imaging)"
                    ],
                    priority=3,
                    icon="📈",
                    provenance=f"ca125_intelligence.{burden_class.lower()}_burden"
                ))
        
        # ===================================================================
        # TILE 4: AVOID (Priority 4 - ONLY if treatment history + resistance)
        # Manager's Policy (P5): "No 'avoid' tile for treatment-naive"
        # ===================================================================
        prior_taxane = any(
            "taxane" in t.lower() or 
            "paclitaxel" in t.lower()
            for t in treatment_history
        )
        
        # ONLY show if:
        # 1. Prior taxane exposure AND
        # 2. ABCB1 detected high (efflux risk)
        if prior_taxane and tumor_context and tumor_context.get("abcb1_status") == "high":
            hints.append(HintTile(
                category="avoid",
                title="⚠️ Cross-Resistance Consideration",
                message="Consider avoiding re-taxane (cross-resistance risk detected)",
                reasons=[
                    "Prior taxane exposure with progression",
                    "ABCB1 high → efflux-mediated resistance",
                    "Suggest non-substrates: platinum, PARP, ATR/CHK1"
                ],
                priority=4,
                icon="🚫",
                provenance="cross_resistance_risk.abcb1_high"
            ))
        
        # ===================================================================
        # MANAGER'S RULE: MAX 4 TILES, SORTED BY PRIORITY
        # ===================================================================
        hints.sort(key=lambda x: x.priority)
        final_hints = hints[:4]
        
        self.logger.info(f"HintTiles generated {len(final_hints)} tiles: {[h.category for h in final_hints]}")
        
        return final_hints
    
    def format_as_summary(self, hints: List[HintTile]) -> str:
        """
        Format hints as plain text summary.
        
        Args:
            hints: List of hint tiles
        
        Returns:
            Plain text summary string
        """
        if not hints:
            return "No additional actions recommended at this time."
        
        lines = ["## 🎯 Recommended Actions\n"]
        
        for hint in hints:
            lines.append(f"### {hint.icon} {hint.title}")
            lines.append(f"**{hint.message}**\n")
            lines.append("**Why:**")
            for reason in hint.reasons:
                lines.append(f"- {reason}")
            lines.append("")
        
        return "\n".join(lines)


# ============================================================================
# FACTORY FUNCTION (for orchestrator)
# ============================================================================

def get_hint_tiles(
    germline_status: str,
    tumor_context: Optional[Dict] = None,
    ca125_intelligence: Optional[Dict] = None,
    next_test_recommendations: Optional[List[Dict]] = None,
    treatment_history: Optional[List[str]] = None,
    trials_matched: int = 0,
    sae_features: Optional[Dict] = None  # ⚔️ NEW: SAE hotspot detection (P1.1)
) -> Dict[str, Any]:
    """
    Factory function for orchestrator integration.
    
    Args:
        germline_status: Germline mutation status
        tumor_context: Tumor NGS data
        ca125_intelligence: CA-125 analysis results
        next_test_recommendations: From next_test_recommender service
        treatment_history: Prior therapies
        trials_matched: Number of trials matched
    
    Returns:
        Dict with hint_tiles list + summary + provenance
    
    Example:
        >>> result = get_hint_tiles(
        ...     germline_status="negative",
        ...     tumor_context=None,
        ...     ca125_intelligence={"burden_classification": "EXTENSIVE", "current_value": 2842},
        ...     next_test_recommendations=[{"test_name": "HRD...", "priority": 1, ...}],
        ...     trials_matched=10
        ... )
        >>> len(result["hint_tiles"])
        3  # Next test + Trials + Monitoring (no Avoid for treatment-naive)
    """
    service = HintTilesService()
    
    next_test_recommendations = next_test_recommendations or []
    ca125_intelligence = ca125_intelligence or {}
    
    hints = service.generate_hints(
        germline_status=germline_status,
        tumor_context=tumor_context,
        ca125_intelligence=ca125_intelligence,
        next_test_recommendations=next_test_recommendations,
        treatment_history=treatment_history,
        trials_matched=trials_matched,
        sae_features=sae_features  # ⚔️ P1.1: Pass SAE features for hotspot detection
    )
    
    # Convert to dict for JSON
    hints_dict = [asdict(h) for h in hints]
    
    # Categorize for UI
    by_category = {}
    for hint in hints:
        by_category[hint.category] = asdict(hint)
    
    return {
        "hint_tiles": hints_dict,
        "total_tiles": len(hints_dict),
        "categories": list(by_category.keys()),
        "by_category": by_category,
        "summary_text": service.format_as_summary(hints),
        "provenance": {
            "version": "v1.0",
            "policy_source": "MANAGER_ANSWERS_TO_ZO_SAE_QUESTIONS.md (P5, C8)",
            "manager": "SR",
            "date": "2025-01-13",
            "max_tiles": 4,
            "tone": "suggestive",
            "note": "Priority: Test → Trials → Monitor → Avoid. Pre-NGS excludes 'avoid' tile."
        }
    }


# ============================================================================
# QUICK TEST (for validation)
# ============================================================================

if __name__ == "__main__":
    # Test Case 1: Ayesha (treatment-naive, no NGS, EXTENSIVE CA-125)
    print("\n⚔️ TEST CASE 1: AYESHA (treatment-naive, EXTENSIVE CA-125, 10 trials matched)")
    
    # Mock next-test recommendations
    mock_next_tests = [
        {
            "test_name": "HRD Score (MyChoice CDx)",
            "priority": 1,
            "turnaround_days": 10,
            "rationale": "HRD determines PARP eligibility",
            "impact_if_positive": "HRD ≥42 → PARP eligible, 90% confidence"
        }
    ]
    
    # Mock CA-125 intelligence
    mock_ca125 = {
        "current_value": 2842,
        "burden_classification": "EXTENSIVE"
    }
    
    result = get_hint_tiles(
        germline_status="negative",
        tumor_context=None,  # No NGS yet
        ca125_intelligence=mock_ca125,
        next_test_recommendations=mock_next_tests,
        treatment_history=[],  # Treatment-naive
        trials_matched=10
    )
    
    print(f"\n✅ Total tiles: {result['total_tiles']}")
    print(f"✅ Categories: {result['categories']}")
    print(f"\n📋 TILES GENERATED:")
    for tile in result['hint_tiles']:
        print(f"  {tile['priority']}. [{tile['category']}] {tile['title']}")
        print(f"     Message: {tile['message']}")
        print(f"     Reasons: {len(tile['reasons'])} reasons")
    
    # Expected: 3 tiles (Next test, Trials, Monitoring)
    # NOT: Avoid (because treatment-naive per Manager's policy P5)
    
    print("\n" + "="*80)
    
    # Test Case 2: Post-taxane patient with ABCB1 high (should trigger "Avoid" tile)
    print("\n⚔️ TEST CASE 2: POST-TAXANE PATIENT (ABCB1 high, should show 'Avoid' tile)")
    
    result2 = get_hint_tiles(
        germline_status="negative",
        tumor_context={"hrd_score": 55, "abcb1_status": "high"},  # ABCB1 high!
        ca125_intelligence=mock_ca125,
        next_test_recommendations=[],  # All tests complete
        treatment_history=["carboplatin", "paclitaxel"],  # Prior taxane!
        trials_matched=8
    )
    
    print(f"\n✅ Total tiles: {result2['total_tiles']}")
    print(f"✅ Categories: {result2['categories']}")
    print(f"\n📋 TILES GENERATED:")
    for tile in result2['hint_tiles']:
        print(f"  {tile['priority']}. [{tile['category']}] {tile['title']}")
        print(f"     Message: {tile['message']}")
    
    # Expected: 3 tiles (Trials, Monitoring, Avoid)
    # YES: Avoid (because prior taxane + ABCB1 high)
    
    print("\n" + "="*80)
    
    # Test Case 3: Max 4 tile enforcement
    print("\n⚔️ TEST CASE 3: MAX 4 TILES ENFORCEMENT (all criteria present)")
    
    result3 = get_hint_tiles(
        germline_status="negative",
        tumor_context={"hrd_score": 45, "abcb1_status": "high"},
        ca125_intelligence=mock_ca125,
        next_test_recommendations=mock_next_tests,  # Has next test
        treatment_history=["paclitaxel"],  # Prior taxane
        trials_matched=12
    )
    
    print(f"\n✅ Total tiles: {result3['total_tiles']} (should be ≤4 per Manager's policy)")
    print(f"✅ Categories: {result3['categories']}")
    
    # Expected: Exactly 4 tiles (Test, Trials, Monitor, Avoid)
    # Verify max 4 enforcement
    assert result3['total_tiles'] <= 4, f"FAILED: Generated {result3['total_tiles']} tiles (max is 4)"
    print("\n✅ Max 4 tiles policy ENFORCED!")


