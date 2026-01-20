"""
Research Intelligence Dossier Generator

Generates beautiful markdown dossiers from Research Intelligence results.
Supports persona-specific formatting (patient, doctor, r&d).
"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class ResearchIntelligenceDossierGenerator:
    """Generates markdown dossiers from Research Intelligence results."""
    
    async def generate_dossier(
        self,
        query_result: Dict[str, Any],
        persona: str = "patient",
        query_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate markdown dossier.
        
        Args:
            query_result: Full Research Intelligence API response
            persona: Target persona (patient, doctor, r&d)
            query_id: Optional query ID for linking
        
        Returns:
        {
            "markdown": "...",
            "persona": "patient",
            "query_id": "...",
            "sections": {...}
        }
        """
        research_plan = query_result.get("research_plan", {})
        synthesized = query_result.get("synthesized_findings", {})
        moat = query_result.get("moat_analysis", {})
        portal_results = query_result.get("portal_results", {})
        
        markdown_parts = []
        
        # Title
        question = research_plan.get("primary_question", "Research Query")
        markdown_parts.append(f"# Research Intelligence Report\n\n")
        markdown_parts.append(f"**Question**: {question}\n\n")
        markdown_parts.append(f"**Generated**: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}\n\n")
        markdown_parts.append("---\n\n")
        
        # Executive Summary (persona-specific)
        if persona == "patient":
            markdown_parts.append(self._generate_patient_summary(synthesized, moat))
        elif persona == "doctor":
            markdown_parts.append(self._generate_doctor_summary(synthesized, moat))
        else:  # r&d
            markdown_parts.append(self._generate_rnd_summary(synthesized, moat))
        
        # Mechanisms Section
        markdown_parts.append(self._generate_mechanisms_section(synthesized, persona))
        
        # Evidence Section
        markdown_parts.append(self._generate_evidence_section(synthesized, persona))
        
        # Clinical Implications (if MOAT analysis)
        if moat:
            markdown_parts.append(self._generate_clinical_implications(moat, persona))
        
        # Citations
        markdown_parts.append(self._generate_citations_section(query_result))
        
        markdown = "\n".join(markdown_parts)
        
        return {
            "markdown": markdown,
            "persona": persona,
            "query_id": query_id,
            "sections": {
                "executive_summary": True,
                "mechanisms": True,
                "evidence": True,
                "clinical_implications": bool(moat),
                "citations": True
            }
        }
    
    def _generate_patient_summary(self, synthesized: Dict[str, Any], moat: Dict[str, Any]) -> str:
        """Generate patient-friendly executive summary."""
        mechanisms = synthesized.get("mechanisms", [])
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        confidence = synthesized.get("overall_confidence", 0.5)
        
        summary = "## Executive Summary\n\n"
        summary += f"Based on analysis of **{len(mechanisms)} key mechanisms**, "
        summary += f"the evidence strength is **{evidence_tier}** "
        summary += f"(confidence: {confidence:.0%}).\n\n"
        
        # Safety (if available)
        if moat.get("toxicity_mitigation"):
            toxicity = moat["toxicity_mitigation"]
            risk_level = toxicity.get("risk_level", "UNKNOWN")
            summary += f"**Safety**: {risk_level} risk level.\n\n"
        
        # Evidence summary
        evidence_summary = synthesized.get("evidence_summary", "")
        if evidence_summary:
            summary += f"**Summary**: {evidence_summary[:300]}...\n\n"
        
        return summary
    
    def _generate_doctor_summary(self, synthesized: Dict[str, Any], moat: Dict[str, Any]) -> str:
        """Generate doctor-friendly executive summary."""
        mechanisms = synthesized.get("mechanisms", [])
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        confidence = synthesized.get("overall_confidence", 0.5)
        badges = synthesized.get("badges", [])
        
        summary = "## Executive Summary\n\n"
        summary += f"**Mechanisms Identified**: {len(mechanisms)}\n"
        summary += f"**Evidence Tier**: {evidence_tier}\n"
        summary += f"**Confidence**: {confidence:.0%}\n"
        if badges:
            summary += f"**Badges**: {', '.join(badges)}\n"
        summary += "\n"
        
        # Clinical context
        if moat.get("treatment_line_analysis"):
            treatment_line = moat["treatment_line_analysis"]
            summary += f"**Treatment Line Analysis**: {treatment_line.get('analysis', 'N/A')}\n\n"
        
        # Evidence summary
        evidence_summary = synthesized.get("evidence_summary", "")
        if evidence_summary:
            summary += f"**Evidence Summary**: {evidence_summary}\n\n"
        
        return summary
    
    def _generate_rnd_summary(self, synthesized: Dict[str, Any], moat: Dict[str, Any]) -> str:
        """Generate R&D-friendly executive summary."""
        mechanisms = synthesized.get("mechanisms", [])
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        confidence = synthesized.get("overall_confidence", 0.5)
        badges = synthesized.get("badges", [])
        
        summary = "## Executive Summary\n\n"
        summary += f"**Research Question**: Comprehensive analysis completed\n\n"
        summary += f"**Key Findings**:\n"
        summary += f"- Mechanisms identified: {len(mechanisms)}\n"
        summary += f"- Evidence tier: {evidence_tier}\n"
        summary += f"- Overall confidence: {confidence:.0%}\n"
        if badges:
            summary += f"- Evidence badges: {', '.join(badges)}\n"
        summary += "\n"
        
        # Research gaps
        knowledge_gaps = synthesized.get("knowledge_gaps", [])
        if knowledge_gaps:
            summary += "**Knowledge Gaps**:\n"
            for gap in knowledge_gaps[:5]:
                summary += f"- {gap}\n"
            summary += "\n"
        
        return summary
    
    def _generate_mechanisms_section(self, synthesized: Dict[str, Any], persona: str) -> str:
        """Generate mechanisms section."""
        mechanisms = synthesized.get("mechanisms", [])
        if not mechanisms:
            return ""
        
        section = "## How It Works\n\n"
        
        for i, mech in enumerate(mechanisms[:10], 1):
            if isinstance(mech, dict):
                mech_name = mech.get("mechanism", "")
                confidence = mech.get("confidence", 0.5)
                description = mech.get("description", "")
                
                if persona == "patient":
                    section += f"{i}. **{mech_name}**\n"
                    if description:
                        section += f"   {description}\n"
                else:
                    section += f"{i}. **{mech_name}** (confidence: {confidence:.0%})\n"
                    if description:
                        section += f"   {description}\n"
            else:
                section += f"{i}. {mech}\n"
        section += "\n"
        
        return section
    
    def _generate_evidence_section(self, synthesized: Dict[str, Any], persona: str) -> str:
        """Generate evidence section."""
        evidence_tier = synthesized.get("evidence_tier", "Unknown")
        badges = synthesized.get("badges", [])
        overall_confidence = synthesized.get("overall_confidence", 0.5)
        
        section = "## Evidence Strength\n\n"
        section += f"**Evidence Tier**: {evidence_tier}\n"
        section += f"**Confidence**: {overall_confidence:.0%}\n"
        
        if badges:
            section += f"**Badges**: {', '.join(badges)}\n"
        section += "\n"
        
        # Evidence summary
        evidence_summary = synthesized.get("evidence_summary", "")
        if evidence_summary and persona != "patient":
            section += f"**Summary**: {evidence_summary}\n\n"
        
        return section
    
    def _generate_clinical_implications(self, moat: Dict[str, Any], persona: str) -> str:
        """Generate clinical implications section."""
        section = "## Clinical Implications\n\n"
        
        # Treatment line analysis
        if moat.get("treatment_line_analysis"):
            treatment_line = moat["treatment_line_analysis"]
            section += f"**Treatment Line**: {treatment_line.get('analysis', 'N/A')}\n\n"
        
        # Biomarker analysis
        if moat.get("biomarker_analysis"):
            biomarker = moat["biomarker_analysis"]
            section += f"**Biomarker Alignment**: {biomarker.get('analysis', 'N/A')}\n\n"
        
        # Toxicity mitigation
        if moat.get("toxicity_mitigation"):
            toxicity = moat["toxicity_mitigation"]
            risk_level = toxicity.get("risk_level", "UNKNOWN")
            section += f"**Safety Risk**: {risk_level}\n"
            
            if persona == "patient":
                mitigating_foods = toxicity.get("mitigating_foods", [])
                if mitigating_foods:
                    section += f"**Foods that may help**: {', '.join(mitigating_foods[:5])}\n"
            section += "\n"
        
        # Cross-resistance
        if moat.get("cross_resistance") and persona != "patient":
            cross_resistance = moat["cross_resistance"]
            if isinstance(cross_resistance, list) and cross_resistance:
                section += "**Cross-Resistance Analysis**:\n"
                for item in cross_resistance[:5]:
                    if isinstance(item, dict):
                        section += f"- {item.get('analysis', 'N/A')}\n"
                    else:
                        section += f"- {item}\n"
                section += "\n"
        
        return section
    
    def _generate_citations_section(self, query_result: Dict[str, Any]) -> str:
        """Generate citations section."""
        portal_results = query_result.get("portal_results", {})
        pubmed = portal_results.get("pubmed", {})
        articles = pubmed.get("articles", [])
        
        if not articles:
            return ""
        
        section = "## Citations\n\n"
        section += f"**Total Articles Analyzed**: {len(articles)}\n\n"
        section += "**Key References**:\n\n"
        
        for i, article in enumerate(articles[:20], 1):
            pmid = article.get("pmid", "")
            title = article.get("title", "")
            journal = article.get("journal", "")
            year = article.get("publication_date", "")
            
            if title:
                section += f"{i}. {title}"
                if journal:
                    section += f" ({journal})"
                if year:
                    section += f" {year}"
                if pmid:
                    section += f" [PMID: {pmid}](https://pubmed.ncbi.nlm.nih.gov/{pmid})"
                section += "\n"
        
        section += "\n"
        return section

