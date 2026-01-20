"""
ClinicalTrials.gov API v2 Query Builder

Builds precise queries with multiple filters for complex clinical trial searches.
Supports conditions, interventions, status, phases, study types, geo, and keywords.
"""
import logging
from typing import Dict, List, Any, Optional
import asyncio
import httpx

logger = logging.getLogger(__name__)

CLINICAL_TRIALS_BASE_URL = "https://clinicaltrials.gov/api/v2/studies"


class CTGovQueryBuilder:
    """Builder for ClinicalTrials.gov API v2 queries with multiple filters."""
    
    def __init__(self):
        self.params: Dict[str, Any] = {}
        self.condition_terms: List[str] = []
        self.intervention_terms: List[str] = []
        self.keyword_terms: List[str] = []
    
    def add_condition(self, condition: str, operator: str = "AND") -> "CTGovQueryBuilder":
        """
        Add a condition filter.
        
        Args:
            condition: Condition query (e.g., "ovarian cancer")
            operator: "AND" or "OR" (default: "AND")
        """
        if condition:
            self.condition_terms.append(condition)
        return self
    
    def add_intervention(self, intervention: str, operator: str = "OR") -> "CTGovQueryBuilder":
        """
        Add an intervention filter.
        
        Args:
            intervention: Intervention query (e.g., "PARP inhibitor")
            operator: "AND" or "OR" (default: "OR")
        """
        if intervention:
            self.intervention_terms.append(intervention)
        return self
    
    def add_status(self, status: List[str]) -> "CTGovQueryBuilder":
        """
        Add status filters.
        
        Args:
            status: List of statuses (e.g., ["RECRUITING", "NOT_YET_RECRUITING"])
        """
        if status:
            # API v2 expects comma-separated values, not pipe-separated
            self.params["filter.overallStatus"] = ",".join(status)
        return self
    
    def add_phase(self, phases: List[str]) -> "CTGovQueryBuilder":
        """
        Add phase filters.
        
        Args:
            phases: List of phases (e.g., ["PHASE1", "PHASE2", "PHASE3"])
        """
        if phases:
            # API v2 expects comma-separated values, not pipe-separated
            self.params["filter.phase"] = ",".join(phases)
        return self
    
    def add_study_type(self, study_type: str) -> "CTGovQueryBuilder":
        """
        Add study type filter.
        
        Args:
            study_type: Study type (e.g., "INTERVENTIONAL")
        """
        if study_type:
            self.params["filter.studyType"] = study_type
        return self
    
    def add_geo(self, country: str = "United States") -> "CTGovQueryBuilder":
        """
        Add geographic filter.
        
        Args:
            country: Country name (default: "United States")
        """
        if country:
            self.params["filter.countries"] = country
        return self
    
    def add_keyword(self, keyword: str) -> "CTGovQueryBuilder":
        """
        Add keyword filter.
        
        Args:
            keyword: Additional keyword (e.g., "basket", "rare disease", "precision medicine")
        """
        if keyword:
            self.keyword_terms.append(keyword)
        return self
    
    def build(self) -> Dict[str, Any]:
        """
        Build the final query parameters.
        
        Returns:
            Dictionary of query parameters ready for API call
        """
        params = self.params.copy()
        
        # Build condition query
        if self.condition_terms:
            condition_query = " AND ".join(self.condition_terms)
            params["query.cond"] = condition_query
        
        # Build intervention query
        if self.intervention_terms:
            intervention_query = " OR ".join(self.intervention_terms)
            params["query.intr"] = intervention_query
        
        # Build keyword query (combine with condition if present)
        if self.keyword_terms:
            keyword_query = " ".join(self.keyword_terms)
            if "query.cond" in params:
                params["query.cond"] = f"{params['query.cond']} {keyword_query}"
            else:
                params["query.term"] = keyword_query
        
        # Add format
        params["format"] = "json"
        params["pageSize"] = 100  # Max per request
        
        return params
    
    def build_dna_repair_query(
        self, 
        conditions: List[str], 
        mutations: List[str], 
        interventions: List[str]
    ) -> Dict[str, Any]:
        """
        Build specialized query for DNA repair deficiency trials.
        
        Args:
            conditions: List of conditions (e.g., ["ovarian cancer"])
            mutations: List of mutations (e.g., ["MBD4", "TP53"])
            interventions: List of interventions (e.g., ["PARP inhibitor"])
        """
        self.condition_terms = []
        self.intervention_terms = []
        self.keyword_terms = []
        
        # Add conditions
        for condition in conditions:
            self.add_condition(condition)
        
        # Add DNA repair keyword
        self.add_keyword("DNA repair deficiency")
        
        # Add mutations as keywords
        for mutation in mutations:
            self.add_keyword(mutation)
        
        # Add interventions
        for intervention in interventions:
            self.add_intervention(intervention)
        
        return self.build()
    
    def build_basket_trial_query(
        self, 
        conditions: List[str], 
        mutations: List[str]
    ) -> Dict[str, Any]:
        """
        Build specialized query for basket trials.
        
        Args:
            conditions: List of conditions
            mutations: List of mutations
        """
        self.condition_terms = []
        self.intervention_terms = []
        self.keyword_terms = []
        
        # Add conditions
        for condition in conditions:
            self.add_condition(condition)
        
        # Add basket trial keywords
        self.add_keyword("basket trial")
        self.add_keyword("tumor agnostic")
        
        # Add mutations
        for mutation in mutations:
            self.add_keyword(mutation)
        
        return self.build()
    
    def build_rare_mutation_query(
        self, 
        gene: str, 
        condition: str
    ) -> Dict[str, Any]:
        """
        Build specialized query for rare mutation registries.
        
        Args:
            gene: Gene name (e.g., "MBD4")
            condition: Condition (e.g., "ovarian cancer")
        """
        self.condition_terms = []
        self.intervention_terms = []
        self.keyword_terms = []
        
        self.add_condition(condition)
        self.add_keyword(f"{gene} mutation")
        self.add_keyword("rare disease registry")
        
        return self.build()
    
    def build_immunotherapy_query(
        self, 
        condition: str, 
        dna_repair_allowed: bool = True
    ) -> Dict[str, Any]:
        """
        Build specialized query for immunotherapy trials.
        
        Args:
            condition: Condition (e.g., "ovarian cancer")
            dna_repair_allowed: Whether to include DNA repair mutations in query
        """
        self.condition_terms = []
        self.intervention_terms = []
        self.keyword_terms = []
        
        self.add_condition(condition)
        self.add_intervention("PD-1")
        self.add_intervention("PD-L1")
        self.add_intervention("checkpoint inhibitor")
        
        if dna_repair_allowed:
            self.add_keyword("DNA repair mutation")
            self.add_keyword("hypermutator")
        
        return self.build()


async def execute_query(
    builder: CTGovQueryBuilder, 
    max_results: int = 1000
) -> List[Dict[str, Any]]:
    """
    Execute a query built by CTGovQueryBuilder.
    
    Handles pagination, rate limiting, and deduplication.
    
    Args:
        builder: CTGovQueryBuilder instance with built query
        max_results: Maximum number of trials to fetch
        
    Returns:
        List of trial study objects from API
    """
    params = builder.build()
    trials: List[Dict[str, Any]] = []
    page_token: Optional[str] = None
    
    logger.info(f"Starting query execution for up to {max_results} trials...")
    
    while len(trials) < max_results:
        if page_token:
            params["pageToken"] = page_token
        
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(CLINICAL_TRIALS_BASE_URL, params=params)
                response.raise_for_status()
                data = response.json()
            
            studies = data.get("studies", [])
            
            if not studies:
                logger.info("No more studies in this page")
                break
            
            # Deduplicate by NCT ID
            nct_ids_seen = {
                s.get("protocolSection", {}).get("identificationModule", {}).get("nctId")
                for s in trials
            }
            new_studies = [
                s for s in studies
                if s.get("protocolSection", {}).get("identificationModule", {}).get("nctId") not in nct_ids_seen
            ]
            
            trials.extend(new_studies)
            
            # Progress logging
            logger.info(
                f"Fetched {len(trials)}/{max_results} trials "
                f"(deduped: {len(new_studies)} new, page total: {len(studies)})"
            )
            
            # Check for next page
            next_page_token = data.get("nextPageToken")
            if not next_page_token:
                logger.info("No more pages available")
                break
            page_token = next_page_token
            
            # Rate limiting: 2 req/sec
            await asyncio.sleep(0.5)
            
        except httpx.HTTPError as e:
            logger.error(f"API request failed: {e}")
            break
        except Exception as e:
            logger.error(f"Unexpected error during query execution: {e}", exc_info=True)
            break
    
    logger.info(f"✅ Total fetched: {len(trials)} trials")
    return trials[:max_results]


