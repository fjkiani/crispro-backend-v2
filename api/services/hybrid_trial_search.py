"""
Hybrid Trial Search Service - Component 4
Combines AstraDB semantic search with Neo4j graph optimization.

Flow:
1. AstraDB: Semantic search finds 50 candidate trials
2. Neo4j: Graph algorithms optimize ranking (PI proximity, site location, org connections)
3. Returns top K optimized results with graph-based scoring
"""
import logging
from typing import Dict, List, Any, Optional
from api.services.clinical_trial_search_service import ClinicalTrialSearchService
from api.services.neo4j_connection import get_neo4j_driver

logger = logging.getLogger(__name__)


class HybridTrialSearchService:
    """Hybrid search: AstraDB semantic + Neo4j graph optimization."""
    
    def __init__(self):
        self.astradb_service = ClinicalTrialSearchService()
        self.neo4j_driver = get_neo4j_driver()
        if not self.neo4j_driver:
            logger.warning("Neo4j not available - falling back to AstraDB only")
    
    async def search_optimized(
        self,
        query: str,
        patient_context: Optional[Dict[str, Any]] = None,
        germline_status: Optional[str] = None,
        tumor_context: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Graph-optimized trial search with sporadic cancer filtering.
        
        Args:
            query: Semantic search query
            patient_context: {condition, biomarkers, location_state, disease_category}
            germline_status: "positive", "negative", "unknown" (for sporadic filtering)
            tumor_context: {tmb, hrd_score, msi_status, somatic_mutations} (for biomarker boost)
            top_k: Final number of results
            
        Returns:
            Optimized trial results with graph scores + biomarker matches
        """
        patient_context = patient_context or {}
        tumor_context = tumor_context or {}
        condition = patient_context.get('condition') or patient_context.get('disease_category')
        location_state = patient_context.get('location_state')
        
        # Step 1: AstraDB semantic search (get 50 candidates)
        try:
            # ⚔️ FIX: Don't filter by disease_category if it's None or doesn't match
            # Trials may have disease_category=None, so filtering breaks search
            disease_category_filter = patient_context.get('disease_category')
            # Only filter if we have a valid category AND trials have this field populated
            # For now, skip the filter to allow semantic search to work
            disease_category_filter = None  # Disable category filter - use semantic search instead
            
            astradb_response = await self.astradb_service.search_trials(
                query=query,
                disease_category=disease_category_filter,  # None = no filter, semantic search only
                top_k=50  # Get more candidates for graph optimization
            )
            
            # Extract found_trials from response dict
            if not astradb_response.get("success", False):
                logger.warning(f"AstraDB search failed: {astradb_response.get('error', 'Unknown error')}")
                return []
            
            astradb_results = astradb_response.get("data", {}).get("found_trials", [])
            candidate_nct_ids = [t.get('nct_id') or t.get('nctId') for t in astradb_results if t.get('nct_id') or t.get('nctId')]
            
            if not candidate_nct_ids:
                logger.warning("No candidates from AstraDB")
                return []
            
            logger.info(f"✅ AstraDB found {len(candidate_nct_ids)} candidate trials")
        except Exception as e:
            logger.error(f"AstraDB search failed: {e}", exc_info=True)
            return []
        
        # Step 2: Neo4j graph optimization
        if not self.neo4j_driver or len(candidate_nct_ids) == 0:
            # Fallback to AstraDB results
            logger.info(f"Using AstraDB-only results (Neo4j unavailable or no candidates)")
            return astradb_results[:top_k]
        
        try:
            optimized = self._optimize_with_graph(
                candidate_nct_ids=candidate_nct_ids,
                condition=condition,
                location_state=location_state,
                top_k=top_k * 2  # Get 2x for filtering
            )
            
            # Merge with AstraDB metadata
            result_map = {t.get('nct_id') or t.get('nctId'): t for t in astradb_results}
            
            final_results = []
            for opt_trial in optimized:
                nct_id = opt_trial['nct_id']
                astradb_data = result_map.get(nct_id, {})
                
                final_results.append({
                    **astradb_data,  # All AstraDB fields
                    **opt_trial,     # Graph optimization data (overwrites common fields)
                    "optimization_score": opt_trial.get('optimization_score', 0.0),
                    "optimization_method": "hybrid_graph"
                })
            
            # Step 3: Apply sporadic cancer filtering (if germline_status provided)
            excluded_count = 0
            if germline_status == "negative":
                filtered_results = []
                for trial in final_results:
                    if not self._requires_germline(trial):
                        filtered_results.append(trial)
                    else:
                        excluded_count += 1
                
                logger.info(f"🔒 Sporadic filter: Excluded {excluded_count} germline-required trials (kept {len(filtered_results)})")
                final_results = filtered_results
            
            # Step 4: Apply biomarker boost (if tumor_context provided)
            if tumor_context and any(tumor_context.values()):
                final_results = self._apply_biomarker_boost(final_results, tumor_context)
                logger.info(f"🎯 Biomarker boost applied based on tumor context")
            
            # Add metadata about filtering
            for trial in final_results:
                trial["sporadic_filtering_applied"] = (germline_status == "negative")
                trial["excluded_count"] = excluded_count if germline_status == "negative" else 0
            
            return final_results[:top_k]
            
        except Exception as e:
            logger.error(f"Graph optimization failed: {e}", exc_info=True)
            # Fallback to AstraDB results
            logger.info(f"Falling back to AstraDB-only results")
            return astradb_results[:top_k]
    
    def _optimize_with_graph(
        self,
        candidate_nct_ids: List[str],
        condition: Optional[str] = None,
        location_state: Optional[str] = None,
        top_k: int = 10
    ) -> List[Dict[str, Any]]:
        """Use Neo4j graph algorithms to optimize trial ranking."""
        
        with self.neo4j_driver.session(database="neo4j") as session:
            # Build Cypher query for graph-optimized ranking
            cypher = """
            MATCH (t:Trial)
            WHERE t.nct_id IN $candidate_ids
            
            // Optional: Match condition if provided
            OPTIONAL MATCH (t)-[:TARGETS]->(c:Condition)
            WHERE ($condition_pattern IS NULL OR c.name =~ $condition_pattern)
            
            // Get PI information (boost for trials with known PIs)
            OPTIONAL MATCH (pi:PI)-[:LEADS]->(t)
            
            // Get organization information
            OPTIONAL MATCH (org:Organization)-[:LEAD_SPONSOR|COLLABORATOR]->(t)
            WHERE org.type = 'ACADEMIC'
            
            // Get site information (location proximity boost)
            OPTIONAL MATCH (t)-[:CONDUCTED_AT]->(s:Site)
            WHERE ($patient_state IS NULL OR s.state = $patient_state)
            
            // Calculate proximity boost (graph-based scoring)
            WITH t, 
                 collect(DISTINCT pi.name) as pi_names,
                 collect(DISTINCT org.name) as sponsor_names,
                 collect(DISTINCT s) as sites,
                 count(DISTINCT pi) as pi_count,
                 count(DISTINCT org) as org_count,
                 sum(CASE WHEN s.state = $patient_state THEN 1 ELSE 0 END) as proximity_sites
            
            // Graph proximity score: PI count + Academic org count + Location match
            WITH t, 
                 pi_names[0] as pi_name,
                 pi_names,
                 sponsor_names[0] as sponsor_name,
                 sites,
                 (pi_count * 0.3 + org_count * 0.3 + proximity_sites * 0.4) as proximity_boost
            
            RETURN t.nct_id as nct_id,
                   t.title as title,
                   t.status as status,
                   t.phase as phase,
                   pi_name,
                   pi_names,
                   sponsor_name,
                   [s in sites | s.facility + ', ' + s.city + ', ' + s.state][0] as site_name,
                   sites[0].city as site_city,
                   sites[0].state as site_state,
                   proximity_boost
            
            ORDER BY proximity_boost DESC, t.status DESC
            LIMIT $top_k
            """
            
            result = session.run(cypher, {
                "candidate_ids": candidate_nct_ids,
                "condition_pattern": f"(?i).*{condition}.*" if condition else None,
                "patient_state": location_state,
                "top_k": top_k
            })
            
            optimized = []
            for record in result:
                optimized.append({
                    "nct_id": record["nct_id"],
                    "title": record["title"],
                    "status": record["status"],
                    "phase": record["phase"],
                    "pi_name": record["pi_name"],
                    "pi_names": record["pi_names"],
                    "sponsor": record["sponsor_name"],
                    "site_name": record["site_name"],
                    "site_location": f"{record['site_city']}, {record['site_state']}" if record["site_city"] else None,
                    "optimization_score": round(record["proximity_boost"], 3),
                    "optimization_method": "graph_proximity"
                })
            
            return optimized
    
    def _requires_germline(self, trial: Dict[str, Any]) -> bool:
        """
        Check if trial requires germline mutation (hereditary cancer).
        
        Returns True if trial explicitly requires germline BRCA, Lynch syndrome, etc.
        """
        title = (trial.get("title") or "").lower()
        desc = (trial.get("description") or "").lower()
        criteria = (trial.get("inclusion_criteria") or "").lower()
        
        # Germline requirement keywords
        germline_keywords = [
            "germline brca", "hereditary brca", "brca mutation carrier",
            "lynch syndrome", "hereditary cancer syndrome",
            "family history required", "inherited mutation",
            "germline mutation positive", "hereditary ovarian",
            "hereditary breast", "brca1/2 carrier"
        ]
        
        # Check all text fields
        all_text = f"{title} {desc} {criteria}"
        for keyword in germline_keywords:
            if keyword in all_text:
                logger.debug(f"Trial {trial.get('nct_id')} requires germline: '{keyword}' found")
                return True
        
        return False
    
    def _apply_biomarker_boost(
        self,
        trials: List[Dict[str, Any]],
        tumor_context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Boost trials matching tumor biomarkers (TMB, MSI, HRD).
        
        Updates optimization_score and adds biomarker_matches field.
        """
        tmb = tumor_context.get("tmb")
        msi_status = tumor_context.get("msi_status", "").lower()
        hrd_score = tumor_context.get("hrd_score")
        
        for trial in trials:
            title_desc = f"{trial.get('title', '')} {trial.get('description', '')}".lower()
            boost = 1.0
            biomarker_matches = []
            
            # TMB-high boost (TMB >= 10)
            if tmb and tmb >= 10:
                if "tmb" in title_desc or "tumor mutational burden" in title_desc:
                    if tmb >= 20:
                        boost *= 1.35
                        biomarker_matches.append({"name": "TMB-High", "value": f"{tmb:.1f} mut/Mb", "tier": "high"})
                    else:
                        boost *= 1.25
                        biomarker_matches.append({"name": "TMB-Intermediate", "value": f"{tmb:.1f} mut/Mb", "tier": "intermediate"})
            
            # MSI-high boost
            if msi_status and ("msi-h" in msi_status or "msi-high" in msi_status):
                if "msi" in title_desc or "microsatellite" in title_desc:
                    boost *= 1.30
                    biomarker_matches.append({"name": "MSI-High", "value": msi_status.upper(), "tier": "high"})
            
            # HRD boost (HRD >= 42)
            if hrd_score and hrd_score >= 42:
                if "hrd" in title_desc or "homologous recombination" in title_desc or "brca" in title_desc:
                    boost *= 1.20
                    biomarker_matches.append({"name": "HRD-High", "value": f"Score: {hrd_score:.1f}", "tier": "high"})
            
            # Apply boost to optimization score
            if boost > 1.0:
                original_score = trial.get("optimization_score", 1.0)
                trial["optimization_score"] = original_score * boost
                trial["biomarker_matches"] = biomarker_matches
                trial["biomarker_boost_factor"] = round(boost, 2)
                logger.debug(f"Trial {trial.get('nct_id')} boosted {boost:.2f}x (biomarkers: {[m['name'] for m in biomarker_matches]})")
        
        # Re-sort by optimization score (biomarker-matched trials bubble up)
        trials.sort(key=lambda t: t.get("optimization_score", 0), reverse=True)
        return trials






