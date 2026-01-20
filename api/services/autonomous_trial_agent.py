"""
Autonomous Clinical Trial Agent - Component 5
Automatically searches for relevant trials based on patient context.

Agent capabilities:
- Extracts patient context from genomic/demographic data
- Generates search queries automatically
- Runs graph-optimized searches
- Monitors for new trials matching patient profile
- Sends notifications when matches found
"""
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from api.services.hybrid_trial_search import HybridTrialSearchService

logger = logging.getLogger(__name__)


class AutonomousTrialAgent:
    """Agent that autonomously searches for clinical trials."""
    
    # Query templates for advanced query generation
    QUERY_TEMPLATES = {
        'basket_trial': "{condition} basket trial tumor agnostic",
        'rare_mutation': "{gene} mutation rare disease registry",
        'dna_repair': "{condition} DNA repair deficiency syndrome",
        'parp_inhibitor': "{condition} PARP inhibitor",
        'checkpoint_inhibitor': "{condition} PD-1 PD-L1 checkpoint inhibitor",
        'precision_medicine': "{condition} precision medicine protocol",
        'synthetic_lethal': "{gene} synthetic lethal targeted agent",
        'atr_atm_inhibitor': "{condition} ATR ATM DNA-PK inhibitor",
        'immunotherapy': "{condition} immunotherapy DNA repair mutation",
        'rare_disease': "{condition} rare disease registry precision medicine"
    }
    
    # DNA repair pathway mutations
    DNA_REPAIR_GENES = {'MBD4', 'BRCA1', 'BRCA2', 'TP53', 'ATM', 'ATR', 'CHEK2', 'PALB2', 'RAD51', 'BRIP1'}
    
    def __init__(self):
        self.search_service = HybridTrialSearchService()
    
    def extract_patient_context(self, patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract search context from patient data.
        
        Enhanced to detect DNA repair mutations, intervention preferences, 
        efficacy predictions, and sporadic cancer context.
        
        Args:
            patient_data: {mutations, disease, demographics, biomarkers, location, 
                          efficacy_predictions, pathway_scores, germline_status, tumor_context}
            
        Returns:
            Patient context for graph search with enhanced metadata
        """
        # Extract disease category
        disease = patient_data.get('disease', '')
        disease_category = self._map_disease_to_category(disease)
        
        # Extract condition keywords
        condition = disease or disease_category
        
        # Extract biomarkers from mutations
        biomarkers = []
        dna_repair_mutations = []
        mutations = patient_data.get('mutations', [])
        for mut in mutations:
            gene = mut.get('gene', '')
            hgvs = mut.get('hgvs_p', '')
            if gene:
                biomarkers.append(gene)
                # Check if DNA repair pathway mutation
                if gene.upper() in self.DNA_REPAIR_GENES:
                    dna_repair_mutations.append(gene.upper())
            if hgvs:
                biomarkers.append(hgvs)
        
        # Extract location
        location_state = patient_data.get('location', {}).get('state') or patient_data.get('state')
        
        # NEW: Detect DNA repair pathway mutations
        has_dna_repair = len(dna_repair_mutations) > 0
        
        # NEW: Extract intervention preferences from efficacy predictions
        intervention_preferences = []
        efficacy_predictions = patient_data.get('efficacy_predictions')
        pathway_scores = patient_data.get('pathway_scores')
        
        if efficacy_predictions:
            # Extract top-ranked drugs
            drugs = efficacy_predictions.get('drugs', [])
            if drugs:
                # Sort by efficacy score
                sorted_drugs = sorted(drugs, key=lambda x: x.get('efficacy', 0), reverse=True)
                top_drugs = sorted_drugs[:5]  # Top 5 drugs
                
                # Look up MoA from DRUG_MECHANISM_DB
                from api.services.client_dossier.dossier_generator import get_drug_mechanism
                for drug in top_drugs:
                    drug_name = drug.get('name', '')
                    if drug_name:
                        mechanism_info = get_drug_mechanism(drug_name)
                        mechanism = mechanism_info.get('mechanism', '').lower()
                        
                        # Map MoA to intervention keywords
                        if 'parp' in mechanism:
                            intervention_preferences.append('PARP inhibitor')
                        elif 'checkpoint' in mechanism or 'pd-1' in mechanism or 'pd-l1' in mechanism:
                            intervention_preferences.append('checkpoint inhibitor')
                        elif 'atr' in mechanism or 'atm' in mechanism:
                            intervention_preferences.append('ATR/ATM inhibitor')
                        elif 'vegf' in mechanism or 'angiogenesis' in mechanism:
                            intervention_preferences.append('anti-angiogenic')
        
        # NEW: Extract pathway scores for mechanism vector conversion
        mechanism_vector_data = None
        if pathway_scores:
            mechanism_vector_data = pathway_scores
        elif efficacy_predictions:
            # Extract from provenance
            provenance = efficacy_predictions.get('provenance', {})
            confidence_breakdown = provenance.get('confidence_breakdown', {})
            pathway_disruption = confidence_breakdown.get('pathway_disruption', {})
            if pathway_disruption:
                mechanism_vector_data = pathway_disruption
        
        # NEW: Identify rare mutation status
        rare_mutations = [gene for gene in biomarkers if gene.upper() in {'MBD4', 'CHEK2', 'PALB2', 'BRIP1'}]
        has_rare_mutation = len(rare_mutations) > 0
        
        # NEW: Extract platinum sensitivity status (if available)
        platinum_sensitivity = patient_data.get('platinum_sensitivity')  # 'sensitive', 'resistant', 'unknown'
        
        # NEW: Sporadic cancer support (already exists but enhance context)
        germline_status = patient_data.get('germline_status', 'unknown')
        tumor_context = patient_data.get('tumor_context', {})
        
        return {
            "condition": condition,
            "disease_category": disease_category,
            "biomarkers": biomarkers,
            "location_state": location_state,
            # NEW: Enhanced metadata
            "dna_repair_mutations": dna_repair_mutations,
            "has_dna_repair": has_dna_repair,
            "intervention_preferences": list(set(intervention_preferences)),  # Deduplicate
            "pathway_scores": mechanism_vector_data,
            "rare_mutations": rare_mutations,
            "has_rare_mutation": has_rare_mutation,
            "platinum_sensitivity": platinum_sensitivity,
            "germline_status": germline_status,
            "tumor_context": tumor_context
        }
    
    def generate_search_queries(self, patient_context: Dict[str, Any]) -> List[str]:
        """
        Generate multiple search queries from patient context.
        
        Enhanced to generate 5-10 queries including basket trials, rare disease registries,
        intervention-specific queries, and DNA repair pathway queries.
        
        Returns:
            List of query strings to try (5-10 queries)
        """
        queries = []
        
        condition = patient_context.get('condition')
        disease_category = patient_context.get('disease_category')
        biomarkers = patient_context.get('biomarkers', [])
        dna_repair_mutations = patient_context.get('dna_repair_mutations', [])
        has_dna_repair = patient_context.get('has_dna_repair', False)
        intervention_preferences = patient_context.get('intervention_preferences', [])
        rare_mutations = patient_context.get('rare_mutations', [])
        has_rare_mutation = patient_context.get('has_rare_mutation', False)
        
        # Query 1: Disease + biomarker (original)
        if biomarkers:
            queries.append(f"{condition} {biomarkers[0]} biomarker trial")
        
        # Query 2: Disease category (original)
        if disease_category:
            queries.append(f"{disease_category} clinical trial")
        
        # Query 3: Disease + treatment (original)
        if condition:
            queries.append(f"{condition} treatment trial")
        
        # Query 4: Biomarker-specific (original)
        if len(biomarkers) > 0:
            queries.append(f"{biomarkers[0]} mutation clinical trial")
        
        # NEW: Query 5: DNA repair pathway query
        if has_dna_repair and condition:
            queries.append(self.QUERY_TEMPLATES['dna_repair'].format(condition=condition))
        
        # NEW: Query 6: Basket trial query
        if condition:
            queries.append(self.QUERY_TEMPLATES['basket_trial'].format(condition=condition))
        
        # NEW: Query 7: Rare mutation registry query
        if has_rare_mutation and rare_mutations:
            for gene in rare_mutations[:2]:  # Limit to first 2 rare mutations
                queries.append(self.QUERY_TEMPLATES['rare_mutation'].format(gene=gene))
        
        # NEW: Query 8: Intervention-specific queries (PARP, checkpoint, ATR/ATM)
        if intervention_preferences:
            for intervention in intervention_preferences[:3]:  # Limit to first 3
                if 'PARP' in intervention and condition:
                    queries.append(self.QUERY_TEMPLATES['parp_inhibitor'].format(condition=condition))
                elif 'checkpoint' in intervention.lower() and condition:
                    queries.append(self.QUERY_TEMPLATES['checkpoint_inhibitor'].format(condition=condition))
                elif 'ATR' in intervention or 'ATM' in intervention:
                    if condition:
                        queries.append(self.QUERY_TEMPLATES['atr_atm_inhibitor'].format(condition=condition))
        
        # NEW: Query 9: Precision medicine protocol
        if condition:
            queries.append(self.QUERY_TEMPLATES['precision_medicine'].format(condition=condition))
        
        # NEW: Query 10: Synthetic lethal (for DNA repair mutations)
        if has_dna_repair and dna_repair_mutations:
            for gene in dna_repair_mutations[:2]:  # Limit to first 2
                queries.append(self.QUERY_TEMPLATES['synthetic_lethal'].format(gene=gene))
        
        # NEW: Query 11: Immunotherapy with DNA repair (if applicable)
        if has_dna_repair and condition:
            queries.append(self.QUERY_TEMPLATES['immunotherapy'].format(condition=condition))
        
        # NEW: Query 12: Rare disease registry (if rare mutations)
        if has_rare_mutation and condition:
            queries.append(self.QUERY_TEMPLATES['rare_disease'].format(condition=condition))
        
        # Deduplicate queries
        unique_queries = []
        seen = set()
        for query in queries:
            if query and query not in seen:
                seen.add(query)
                unique_queries.append(query)
        
        # Return 5-10 queries (limit to 10)
        return unique_queries[:10]
    
    async def search_for_patient(
        self,
        patient_data: Dict[str, Any],
        germline_status: Optional[str] = None,
        tumor_context: Optional[Dict[str, Any]] = None,
        top_k: int = 10
    ) -> Dict[str, Any]:
        """
        Autonomous search for patient's matching trials with sporadic cancer support.
        
        Args:
            patient_data: Patient genomic/demographic data
            germline_status: "positive", "negative", "unknown" (for sporadic filtering)
            tumor_context: {tmb, hrd_score, msi_status} (for biomarker boost)
            top_k: Number of results per query
            
        Returns:
            {
                "matched_trials": [...],
                "queries_used": [...],
                "patient_context": {...},
                "germline_status": "...",
                "tumor_context": {...},
                "excluded_count": int,
                "timestamp": "..."
            }
        """
        # Extract context
        patient_context = self.extract_patient_context(patient_data)
        
        # Extract sporadic context from patient_data if not provided
        if germline_status is None:
            germline_status = patient_data.get("germline_status", "unknown")
        
        if tumor_context is None:
            tumor_context = patient_data.get("tumor_context", {})
        
        # Generate queries
        queries = self.generate_search_queries(patient_context)
        
        all_results = []
        queries_used = []
        total_excluded = 0
        
        # Search with each query
        for query in queries:
            try:
                results = await self.search_service.search_optimized(
                    query=query,
                    patient_context=patient_context,
                    germline_status=germline_status,
                    tumor_context=tumor_context,
                    top_k=top_k
                )
                
                if results:
                    # Track excluded count from first result
                    if len(all_results) == 0 and len(results) > 0:
                        total_excluded = results[0].get("excluded_count", 0)
                    all_results.extend(results)
                    queries_used.append(query)
            except Exception as e:
                logger.error(f"Query '{query}' failed: {e}")
        
        # Deduplicate by nct_id
        seen_ids = set()
        unique_results = []
        for trial in all_results:
            nct_id = trial.get('nct_id') or trial.get('nctId')
            if nct_id and nct_id not in seen_ids:
                seen_ids.add(nct_id)
                unique_results.append(trial)
        
        # Sort by optimization_score
        unique_results.sort(key=lambda x: x.get('optimization_score', 0), reverse=True)
        
        return {
            "matched_trials": unique_results[:top_k * 2],  # Return more for selection
            "queries_used": queries_used,
            "patient_context": patient_context,
            "germline_status": germline_status,
            "tumor_context": tumor_context,
            "excluded_count": total_excluded,
            "timestamp": datetime.utcnow().isoformat(),
            "total_found": len(unique_results)
        }
    
    def _map_disease_to_category(self, disease: str) -> str:
        """Map disease name to category."""
        # ⚔️ FIX: Null safety check
        if not disease:
            return "cancer"
        disease_lower = disease.lower()
        
        category_map = {
            'ovarian': 'ovarian_cancer',
            'breast': 'breast_cancer',
            'lung': 'lung_cancer',
            'colorectal': 'colorectal_cancer',
            'pancreatic': 'pancreatic_cancer',
            'melanoma': 'melanoma',
            'leukemia': 'leukemia',
            'lymphoma': 'lymphoma'
        }
        
        for key, category in category_map.items():
            if key in disease_lower:
                return category
        
        return disease_lower.replace(' ', '_') if disease else ''
    
    async def generate_dossiers_for_patient(
        self,
        patient_profile: Dict[str, Any],
        nct_ids: Optional[List[str]] = None,
        use_llm: bool = True,
        max_dossiers: int = 10
    ) -> Dict[str, Any]:
        """
        Generate dossiers for a patient using universal pipeline.
        
        Args:
            patient_profile: Full patient profile (or simple profile - will be adapted)
            nct_ids: Optional list of NCT IDs to generate dossiers for. If None, searches first.
            use_llm: Enable LLM analysis
            max_dossiers: Maximum number of dossiers to generate
            
        Returns:
            {
                'dossiers_generated': [...],
                'total_trials_found': int,
                'patient_id': str
            }
        """
        from api.services.trial_intelligence_universal.pipeline import TrialIntelligencePipeline
        from api.services.trial_intelligence_universal.profile_adapter import adapt_simple_to_full_profile, is_simple_profile
        from api.services.trial_intelligence_universal.config import create_config_from_patient_profile
        from api.services.trial_intelligence_universal.stage6_dossier.assembler import assemble
        from pathlib import Path
        from datetime import datetime
        import json
        
        # Adapt profile if needed
        if is_simple_profile(patient_profile):
            full_profile = adapt_simple_to_full_profile(patient_profile)
        else:
            full_profile = patient_profile
        
        patient_id = full_profile['demographics']['patient_id']
        
        # If no NCT IDs provided, search for trials first
        if not nct_ids:
            search_results = await self.search_for_patient(patient_profile, top_k=50)
            nct_ids = [trial.get('nct_id') or trial.get('nctId') for trial in search_results['matched_trials']]
            nct_ids = [nid for nid in nct_ids if nid]  # Filter None
        
        if not nct_ids:
            return {
                'dossiers_generated': [],
                'total_trials_found': 0,
                'patient_id': patient_id,
                'error': 'No trials found'
            }
        
        # Get trial details
        from api.services.clinical_trial_search_service import ClinicalTrialSearchService
        search_service = ClinicalTrialSearchService()
        
        trials = []
        for nct_id in nct_ids[:max_dossiers]:
            trial = await search_service.get_trial_details(nct_id)
            if trial:
                trials.append(trial)
        
        if not trials:
            return {
                'dossiers_generated': [],
                'total_trials_found': 0,
                'patient_id': patient_id,
                'error': 'No trial details found'
            }
        
        # Run pipeline
        config = create_config_from_patient_profile(full_profile)
        pipeline = TrialIntelligencePipeline(
            patient_profile=full_profile,
            config=config,
            use_llm=use_llm,
            verbose=False
        )
        
        results = await pipeline.execute(trials)
        
        # Generate dossiers
        all_survivors = results['top_tier'] + results['good_tier']
        dossier_dir = Path(__file__).resolve().parent.parent.parent / ".cursor" / "patients" / patient_id / "dossiers"
        dossier_dir.mkdir(parents=True, exist_ok=True)
        
        generated_dossiers = []
        for trial in all_survivors[:max_dossiers]:
            try:
                markdown = assemble(trial, full_profile)
                
                nct_id = trial.get('nct_id', 'UNKNOWN')
                timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
                
                dossier_file = dossier_dir / f"{nct_id}_{timestamp}.md"
                dossier_file.write_text(markdown)
                
                metadata = {
                    'dossier_id': f"{patient_id}_{nct_id}_{timestamp}",
                    'nct_id': nct_id,
                    'patient_id': patient_id,
                    'tier': 'TOP_TIER' if trial.get('_composite_score', 0) >= 0.8 else 'GOOD_TIER',
                    'match_score': trial.get('_composite_score', 0),
                    'file_path': str(dossier_file),
                    'created_at': datetime.now().isoformat(),
                }
                
                metadata_file = dossier_dir / f"{nct_id}_{timestamp}.json"
                metadata_file.write_text(json.dumps(metadata, indent=2))
                
                generated_dossiers.append(metadata)
            except Exception as e:
                logger.error(f"❌ Failed to generate dossier for {trial.get('nct_id')}: {e}")
                continue
        
        return {
            'dossiers_generated': generated_dossiers,
            'total_trials_found': len(trials),
            'patient_id': patient_id,
            'top_tier_count': len(results['top_tier']),
            'good_tier_count': len(results['good_tier'])
        }



