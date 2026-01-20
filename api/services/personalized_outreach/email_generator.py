"""
Email Generator Service

Generates highly personalized outreach emails based on intelligence profiles.
"""
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class EmailGenerator:
    """
    Generates personalized outreach emails.
    
    Key Features:
    - References specific research
    - Mentions trial by name
    - Explains fit reasons
    - Shows understanding of goals
    - Offers targeted value
    """
    
    def generate_personalized_email(
        self,
        intelligence_profile: Dict[str, Any],
        outreach_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Generate highly personalized email.
        
        Args:
            intelligence_profile: Complete intelligence from IntelligenceExtractor
            outreach_config: Optional outreach configuration
        
        Returns:
            {
                "subject": str,
                "body": str,
                "personalization_quality": float,  # 0-1 score
                "key_points": List[str]
            }
        """
        outreach_config = outreach_config or {}
        
        trial_intelligence = intelligence_profile.get("trial_intelligence", {})
        research_intelligence = intelligence_profile.get("research_intelligence", {})
        biomarker_intelligence = intelligence_profile.get("biomarker_intelligence", {})
        goals = intelligence_profile.get("goals", [])
        value_proposition = intelligence_profile.get("value_proposition", [])
        
        # Extract key information
        nct_id = trial_intelligence.get("nct_id", "")
        trial_title = trial_intelligence.get("title", "")
        pi_info = trial_intelligence.get("pi_info", {})
        pi_name = pi_info.get("name", "Dr. [Name]")
        institution = pi_info.get("institution", "")
        
        # Extract first name for greeting
        first_name = pi_name.split()[0] if pi_name and " " in pi_name else "Dr."
        
        # Build subject line
        subject = self._generate_subject(trial_title, biomarker_intelligence, outreach_config)
        
        # Build email body
        body = self._generate_body(
            first_name=first_name,
            pi_name=pi_name,
            institution=institution,
            trial_title=trial_title,
            nct_id=nct_id,
            research_intelligence=research_intelligence,
            biomarker_intelligence=biomarker_intelligence,
            goals=goals,
            value_proposition=value_proposition,
            outreach_config=outreach_config
        )
        
        # Calculate personalization quality
        personalization_quality = intelligence_profile.get("personalization_quality", 0.0)
        
        # Extract key points
        key_points = self._extract_key_points(
            biomarker_intelligence,
            value_proposition,
            research_intelligence
        )
        
        return {
            "subject": subject,
            "body": body,
            "personalization_quality": personalization_quality,
            "key_points": key_points,
            "pi_name": pi_name,
            "pi_email": pi_info.get("email", ""),
            "institution": institution
        }
    
    def _generate_subject(
        self,
        trial_title: str,
        biomarker_intelligence: Dict[str, Any],
        outreach_config: Dict[str, Any]
    ) -> str:
        """Generate personalized subject line."""
        # Use custom subject if provided
        if outreach_config.get("subject"):
            return outreach_config["subject"]
        
        # Generate based on KELIM fit
        kelim_score = biomarker_intelligence.get("kelim_fit_score", 0.0)
        
        if kelim_score >= 3.0:
            return f"KELIM Biomarker Validation Opportunity: {trial_title[:50]}"
        elif kelim_score >= 1.0:
            return f"CA-125 Biomarker Collaboration: {trial_title[:50]}"
        else:
            return f"Precision Medicine Collaboration: {trial_title[:50]}"
    
    def _generate_body(
        self,
        first_name: str,
        pi_name: str,
        institution: str,
        trial_title: str,
        nct_id: str,
        research_intelligence: Dict[str, Any],
        biomarker_intelligence: Dict[str, Any],
        goals: List[str],
        value_proposition: List[str],
        outreach_config: Dict[str, Any]
    ) -> str:
        """Generate personalized email body."""

        parts: List[str] = []
        parts.append(f"Dear {first_name},")
        parts.append("")

        # Research acknowledgement (if available)
        intro = ""
        if research_intelligence.get("publication_count", 0) > 0:
            recent_pubs = research_intelligence.get("recent_publications", []) or []
            if recent_pubs:
                pub_title = (recent_pubs[0] or {}).get("title", "") or ""
                if pub_title:
                    intro += (
                        f"I came across your recent work on {pub_title[:100]}... "
                        "and was particularly interested in your research focus on "
                    )
                    research_focus = research_intelligence.get("research_focus", []) or []
                    if research_focus:
                        intro += f"{research_focus[0]}. "
                    else:
                        intro += "oncology. "
            if not intro:
                intro += f"Your research at {institution} in oncology has caught our attention. "
        else:
            intro += f"Your work on {trial_title} at {institution} has caught our attention. "

        # Trial-specific mention
        intro += f"Specifically, I noticed your trial {nct_id} ({trial_title}) "

        # KELIM fit reasons
        fit_reasons = biomarker_intelligence.get("fit_reasons", []) or []
        if fit_reasons:
            intro += "which aligns well with our biomarker validation work. "
            if len(fit_reasons) > 0:
                intro += f"Your trial {str(fit_reasons[0]).lower()}, "
            if len(fit_reasons) > 1:
                intro += f"and {str(fit_reasons[1]).lower()}, "
            intro += "making it an excellent fit for KELIM biomarker validation. "
        else:
            intro += "and believe there may be opportunities for collaboration. "

        parts.append(intro.strip())

        # Goals understanding
        if goals:
            parts.append(
                f"Based on your research focus, it appears you're working to {str(goals[0]).lower()}."
            )

        # Value proposition
        parts.append(
            "We at CrisPRO.ai have developed an AI-powered precision medicine platform that could support your work."
        )
        if value_proposition:
            parts.append("Specifically, we can help with:")
            for i, value_prop in enumerate(value_proposition[:3], 1):
                parts.append(f"{i}. {value_prop}")

        # What we're asking for
        what_we_need = outreach_config.get("what_we_need", "serial CA-125 data for biomarker validation")
        parts.append(f"We're reaching out to request your collaboration on {what_we_need}.")

        # Mutual benefit
        parts.append("This collaboration would provide:")
        parts.append("- Validation data for our KELIM biomarker (CA-125 elimination rate)")
        parts.append("- Early resistance prediction capabilities for your trial")
        parts.append("- Potential publication opportunities")
        parts.append("- Enhanced patient stratification tools")

        parts.append("")
        parts.append("Would you be open to a brief conversation to explore how we might work together?")
        parts.append("")
        parts.append("Best regards,")
        parts.append("[Your Name]")
        parts.append("CrisPRO.ai")
        parts.append("[Contact Information]")

        return "\n".join(parts)

    def _extract_key_points(
        self,
        biomarker_intelligence: Dict[str, Any],
        value_proposition: List[str],
        research_intelligence: Dict[str, Any]
    ) -> List[str]:
        """Extract key points for email summary."""
        key_points = []
        
        # KELIM fit
        kelim_score = biomarker_intelligence.get("kelim_fit_score", 0.0)
        if kelim_score >= 2.0:
            key_points.append(f"High KELIM fit score: {kelim_score:.1f}/5.0")
        
        # Fit reasons
        fit_reasons = biomarker_intelligence.get("fit_reasons", [])
        if fit_reasons:
            key_points.append(f"Fit reasons: {len(fit_reasons)} identified")
        
        # Value props
        if value_proposition:
            key_points.append(f"Value propositions: {len(value_proposition)} identified")
        
        # Research data
        pub_count = research_intelligence.get("publication_count", 0)
        if pub_count > 0:
            key_points.append(f"PI publications: {pub_count} found")
        
        return key_points
