"""
Intelligence Extractor Service

Extracts deep intelligence about PIs and their trials:
1. Trial Intelligence (ClinicalTrials.gov API)
2. Research Intelligence (PubMed API)
3. Biomarker Intelligence (KELIM fit, CA-125, platinum detection)
4. Goal Understanding (what they're trying to achieve)
5. Value Proposition Generation (how we can help)
"""
import logging
import asyncio
from typing import Dict, List, Any, Optional
import httpx

from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query
from api.services.trial_data_enricher import extract_pi_information
from api.services.research_intelligence.portals.pubmed_enhanced import EnhancedPubMedPortal

logger = logging.getLogger(__name__)

CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


class IntelligenceExtractor:
    """
    Extracts comprehensive intelligence about PIs and their trials.
    
    Combines:
    - Trial data (ClinicalTrials.gov API)
    - Research intelligence (PubMed)
    - Biomarker analysis (KELIM fit, CA-125, platinum)
    - Goal inference
    - Value proposition generation
    """
    
    def __init__(self, pubmed_email: Optional[str] = None, pubmed_api_key: Optional[str] = None):
        """
        Initialize intelligence extractor.
        
        Args:
            pubmed_email: NCBI email for PubMed API
            pubmed_api_key: NCBI API key for PubMed API
        """
        self.pubmed_portal = None
        if pubmed_email:
            try:
                self.pubmed_portal = EnhancedPubMedPortal(email=pubmed_email, api_key=pubmed_api_key)
            except Exception as e:
                logger.warning(f"PubMed portal initialization failed: {e}")
    
    async def extract_trial_intelligence(self, nct_id: str) -> Dict[str, Any]:
        """
        Fetch and analyze trial details from ClinicalTrials.gov API.
        
        Args:
            nct_id: ClinicalTrials.gov identifier (e.g., "NCT01234567")
        
        Returns:
            {
                "nct_id": str,
                "title": str,
                "status": str,
                "phase": List[str],
                "conditions": List[str],
                "interventions": List[str],
                "outcomes": List[str],
                "eligibility": Dict[str, Any],
                "enrollment": int,
                "locations": List[Dict],
                "dates": Dict[str, str],
                "pi_info": Dict[str, Any],
                "full_trial_data": Dict[str, Any]
            }
        """
        try:
            # Fetch trial from ClinicalTrials.gov API
            async with httpx.AsyncClient(timeout=30.0) as client:
                url = f"{CLINICAL_TRIALS_BASE_URL}/{nct_id}"
                response = await client.get(url)
                response.raise_for_status()
                trial_data = response.json()
            
            protocol_section = trial_data.get("protocolSection", {})
            identification = protocol_section.get("identificationModule", {})
            status_module = protocol_section.get("statusModule", {})
            design_module = protocol_section.get("designModule", {})
            eligibility_module = protocol_section.get("eligibilityModule", {})
            contacts_locations = protocol_section.get("contactsLocationsModule", {})
            interventions_module = protocol_section.get("interventionsModule", {})
            outcomes_module = protocol_section.get("outcomesModule", {})
            
            # Extract interventions
            interventions = []
            for intervention in interventions_module.get("interventions", []):
                interventions.append(intervention.get("name", ""))
            
            # Extract conditions
            conditions = []
            for condition in protocol_section.get("conditionsModule", {}).get("conditions", []):
                conditions.append(condition)
            
            # Extract outcomes
            outcomes = []
            for outcome in outcomes_module.get("primaryOutcomeMeasures", []):
                outcomes.append(outcome.get("measure", ""))
            for outcome in outcomes_module.get("secondaryOutcomeMeasures", []):
                outcomes.append(outcome.get("measure", ""))
            
            # Extract PI information
            pi_info = extract_pi_information(trial_data)
            
            # Extract locations
            locations = []
            for location in contacts_locations.get("locations", []):
                locations.append({
                    "facility": location.get("facility", ""),
                    "city": location.get("city", ""),
                    "state": location.get("state", ""),
                    "country": location.get("country", "")
                })
            
            return {
                "nct_id": nct_id,
                "title": identification.get("briefTitle", ""),
                "status": status_module.get("overallStatus", ""),
                "phase": [p for p in design_module.get("phases", [])],
                "conditions": conditions,
                "interventions": interventions,
                "outcomes": outcomes,
                "eligibility": {
                    "inclusion": eligibility_module.get("eligibilityCriteria", ""),
                    "gender": eligibility_module.get("gender", ""),
                    "minimum_age": eligibility_module.get("minimumAge", ""),
                    "maximum_age": eligibility_module.get("maximumAge", "")
                },
                "enrollment": status_module.get("enrollmentInfo", {}).get("count", 0),
                "locations": locations,
                "dates": {
                    "start_date": status_module.get("startDateStruct", {}).get("date", ""),
                    "completion_date": status_module.get("completionDateStruct", {}).get("date", ""),
                    "first_posted": status_module.get("startDateStruct", {}).get("date", "")
                },
                "pi_info": pi_info or {},
                "full_trial_data": trial_data
            }
        except Exception as e:
            logger.error(f"Failed to extract trial intelligence for {nct_id}: {e}")
            return {
                "nct_id": nct_id,
                "error": str(e)
            }
    
    async def extract_research_intelligence(self, pi_name: str, institution: str) -> Dict[str, Any]:
        """
        Search PubMed and analyze PI's research focus.
        
        Args:
            pi_name: Principal Investigator name
            institution: Institution name
        
        Returns:
            {
                "publications": List[Dict],
                "research_focus": List[str],
                "expertise_areas": List[str],
                "publication_count": int,
                "recent_publications": List[Dict],
                "keyword_analysis": Dict[str, Any]
            }
        """
        if not self.pubmed_portal:
            logger.warning("PubMed portal not available - skipping research intelligence")
            return {
                "publications": [],
                "research_focus": [],
                "expertise_areas": [],
                "publication_count": 0,
                "recent_publications": [],
                "keyword_analysis": {}
            }
        
        try:
            # Build PubMed query
            query = f'("{pi_name}"[Author]) AND ("{institution}"[Affiliation])'
            
            # Search with analysis
            result = await self.pubmed_portal.search_with_analysis(
                query=query,
                max_results=100,
                analyze_keywords=True,
                include_trends=True
            )
            
            articles = result.get("articles", [])
            keyword_analysis = result.get("keyword_analysis", {})
            
            # Extract research focus from top keywords
            top_keywords = self.pubmed_portal.get_top_keywords(result, top_n=10)
            
            # Get recent publications (last 5 years)
            recent_publications = [
                article for article in articles
                if article.get("pub_date", "").startswith("202") or article.get("pub_date", "").startswith("2019")
            ][:10]
            
            return {
                "publications": articles,
                "research_focus": top_keywords,
                "expertise_areas": top_keywords[:5],  # Top 5 as expertise areas
                "publication_count": len(articles),
                "recent_publications": recent_publications,
                "keyword_analysis": keyword_analysis
            }
        except Exception as e:
            logger.error(f"Failed to extract research intelligence for {pi_name}: {e}")
            return {
                "publications": [],
                "research_focus": [],
                "expertise_areas": [],
                "publication_count": 0,
                "recent_publications": [],
                "keyword_analysis": {}
            }
    
    async def analyze_biomarker_intelligence(self, trial_data: Dict) -> Dict[str, Any]:
        """
        Analyze trial for biomarker relevance (KELIM, CA-125, platinum).
        
        Args:
            trial_data: Trial intelligence from extract_trial_intelligence()
        
        Returns:
            {
                "kelim_fit_score": float,  # 0-5
                "fit_reasons": List[str],
                "platinum_detected": bool,
                "ca125_monitoring_detected": bool,
                "resistance_focus_detected": bool,
                "relevance_indicators": Dict[str, bool]
            }
        """
        fit_reasons = []
        kelim_fit_score = 0.0
        platinum_detected = False
        ca125_monitoring_detected = False
        resistance_focus_detected = False
        
        # Check interventions for platinum
        interventions = trial_data.get("interventions", [])
        intervention_text = " ".join(interventions).lower()
        
        if any(term in intervention_text for term in ["platinum", "carboplatin", "cisplatin", "oxaliplatin"]):
            platinum_detected = True
            fit_reasons.append("Trial uses platinum-based therapy")
            kelim_fit_score += 1.0
        
        # Check outcomes for CA-125
        outcomes = trial_data.get("outcomes", [])
        outcomes_text = " ".join(outcomes).lower()
        
        if "ca-125" in outcomes_text or "ca125" in outcomes_text or "cancer antigen 125" in outcomes_text:
            ca125_monitoring_detected = True
            fit_reasons.append("Trial monitors CA-125 as outcome")
            kelim_fit_score += 1.0
        
        # Check eligibility for CA-125
        eligibility = trial_data.get("eligibility", {})
        eligibility_text = eligibility.get("inclusion", "").lower()
        
        if "ca-125" in eligibility_text or "ca125" in eligibility_text:
            ca125_monitoring_detected = True
            fit_reasons.append("CA-125 mentioned in eligibility criteria")
            kelim_fit_score += 0.5
        
        # Check for resistance focus
        title = trial_data.get("title", "").lower()
        conditions = " ".join(trial_data.get("conditions", [])).lower()
        full_text = f"{title} {conditions} {intervention_text} {outcomes_text}".lower()
        
        if any(term in full_text for term in ["resistance", "resistant", "refractory", "progression"]):
            resistance_focus_detected = True
            fit_reasons.append("Trial focuses on resistance/refractory disease")
            kelim_fit_score += 1.0
        
        # Check for ovarian cancer
        if "ovarian" in conditions or "ovarian" in title.lower():
            fit_reasons.append("Ovarian cancer trial (KELIM validation target)")
            kelim_fit_score += 1.0
        
        # Check for platinum-free interval or progression-free survival
        if "pfi" in full_text or "platinum-free interval" in full_text:
            fit_reasons.append("Trial measures platinum-free interval (KELIM-relevant)")
            kelim_fit_score += 0.5
        
        if "pfs" in full_text or "progression-free survival" in full_text:
            fit_reasons.append("Trial measures progression-free survival")
            kelim_fit_score += 0.5
        
        # Cap score at 5.0
        kelim_fit_score = min(kelim_fit_score, 5.0)
        
        return {
            "kelim_fit_score": kelim_fit_score,
            "fit_reasons": fit_reasons,
            "platinum_detected": platinum_detected,
            "ca125_monitoring_detected": ca125_monitoring_detected,
            "resistance_focus_detected": resistance_focus_detected,
            "relevance_indicators": {
                "platinum": platinum_detected,
                "ca125": ca125_monitoring_detected,
                "resistance": resistance_focus_detected,
                "ovarian_cancer": "ovarian" in conditions or "ovarian" in title.lower()
            }
        }
    
    async def understand_goals(self, trial_data: Dict, research_data: Dict) -> List[str]:
        """
        Infer what the PI is trying to achieve.
        
        Args:
            trial_data: Trial intelligence
            research_data: Research intelligence
        
        Returns:
            List of inferred goals
        """
        goals = []
        
        # Analyze trial design
        title = trial_data.get("title", "").lower()
        interventions = " ".join(trial_data.get("interventions", [])).lower()
        outcomes = " ".join(trial_data.get("outcomes", [])).lower()
        
        # Infer goals from trial characteristics
        if "resistance" in title or "refractory" in title:
            goals.append("Understanding mechanisms of treatment resistance")
        
        if "biomarker" in title or "biomarker" in outcomes:
            goals.append("Identifying predictive biomarkers")
        
        if "combination" in interventions or "combination" in title:
            goals.append("Evaluating combination therapy strategies")
        
        if "maintenance" in title or "maintenance" in interventions:
            goals.append("Optimizing maintenance therapy approaches")
        
        # Infer from research focus
        research_focus = research_data.get("research_focus", [])
        if any("resistance" in kw.lower() for kw in research_focus):
            goals.append("Advancing understanding of resistance mechanisms")
        
        if any("biomarker" in kw.lower() for kw in research_focus):
            goals.append("Developing biomarker-driven treatment strategies")
        
        # Default goals if none inferred
        if not goals:
            goals.append("Improving treatment outcomes for patients")
            goals.append("Advancing clinical research in oncology")
        
        return goals
    
    async def generate_value_proposition(self, goals: List[str], fit_reasons: List[str]) -> List[str]:
        """
        Determine how we can help them specifically.
        
        Args:
            goals: Inferred goals from understand_goals()
            fit_reasons: KELIM fit reasons from analyze_biomarker_intelligence()
        
        Returns:
            List of specific help points
        """
        value_props = []
        
        # Map goals to our capabilities
        for goal in goals:
            if "resistance" in goal.lower():
                value_props.append("Early resistance prediction using CA-125 kinetics (3-6 months before imaging)")
            
            if "biomarker" in goal.lower():
                value_props.append("KELIM biomarker validation and integration into trial endpoints")
            
            if "combination" in goal.lower() or "therapy" in goal.lower():
                value_props.append("AI-powered drug efficacy prediction for combination therapy design")
        
        # Add KELIM-specific value if relevant
        if any("platinum" in reason.lower() or "ca-125" in reason.lower() for reason in fit_reasons):
            value_props.append("KELIM biomarker (CA-125 elimination rate) for platinum response prediction")
            value_props.append("Serial CA-125 data analysis and early resistance detection")
        
        # Default value props
        if not value_props:
            value_props.append("AI-powered precision medicine platform for clinical decision support")
            value_props.append("Biomarker discovery and validation capabilities")
        
        return value_props
    
    async def extract_complete_intelligence(
        self,
        nct_id: str,
        pi_name: Optional[str] = None,
        institution: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Orchestrates all extraction steps.
        
        Args:
            nct_id: ClinicalTrials.gov identifier
            pi_name: PI name (optional, extracted from trial if not provided)
            institution: Institution name (optional, extracted from trial if not provided)
        
        Returns:
            Complete intelligence profile
        """
        # Step 1: Extract trial intelligence
        trial_intelligence = await self.extract_trial_intelligence(nct_id)
        
        if "error" in trial_intelligence:
            return {
                "nct_id": nct_id,
                "error": trial_intelligence["error"],
                "status": "failed"
            }
        
        # Extract PI info if not provided
        if not pi_name:
            pi_info = trial_intelligence.get("pi_info", {})
            pi_name = pi_info.get("name", "")
            institution = institution or pi_info.get("institution", "")
        
        # Step 2: Extract research intelligence (if PI name available)
        research_intelligence = {}
        if pi_name and self.pubmed_portal:
            research_intelligence = await self.extract_research_intelligence(pi_name, institution or "")
        
        # Step 3: Analyze biomarker intelligence
        biomarker_intelligence = await self.analyze_biomarker_intelligence(trial_intelligence)
        
        # Step 4: Understand goals
        goals = await self.understand_goals(trial_intelligence, research_intelligence)
        
        # Step 5: Generate value proposition
        value_proposition = await self.generate_value_proposition(goals, biomarker_intelligence.get("fit_reasons", []))
        
        return {
            "nct_id": nct_id,
            "trial_intelligence": trial_intelligence,
            "research_intelligence": research_intelligence,
            "biomarker_intelligence": biomarker_intelligence,
            "goals": goals,
            "value_proposition": value_proposition,
            "status": "success",
            "personalization_quality": self._calculate_personalization_quality(
                trial_intelligence,
                research_intelligence,
                biomarker_intelligence
            )
        }
    
    def _calculate_personalization_quality(
        self,
        trial_intelligence: Dict,
        research_intelligence: Dict,
        biomarker_intelligence: Dict
    ) -> float:
        """
        Calculate personalization quality score (0-1).
        
        Higher score = more personalized (more data extracted).
        """
        score = 0.0
        
        # Trial data completeness (40%)
        if trial_intelligence.get("title"):
            score += 0.1
        if trial_intelligence.get("interventions"):
            score += 0.1
        if trial_intelligence.get("outcomes"):
            score += 0.1
        if trial_intelligence.get("pi_info", {}).get("name"):
            score += 0.1
        
        # Research data completeness (30%)
        if research_intelligence.get("publication_count", 0) > 0:
            score += 0.15
        if research_intelligence.get("research_focus"):
            score += 0.15
        
        # Biomarker analysis completeness (30%)
        if biomarker_intelligence.get("kelim_fit_score", 0) > 0:
            score += 0.15
        if biomarker_intelligence.get("fit_reasons"):
            score += 0.15
        
        return min(score, 1.0)
