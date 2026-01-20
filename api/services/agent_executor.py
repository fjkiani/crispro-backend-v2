"""
Agent Executor Service - Execute agent runs and process results

Modular service for executing agent runs, fetching data, filtering results,
and generating alerts. Delegates to agent-specific executors.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging
import asyncio
import os

# Try to import supabase, but handle gracefully if not installed
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

from .agent_manager import get_agent_manager
from ..config import SUPABASE_URL, SUPABASE_KEY

logger = logging.getLogger(__name__)

# Initialize Supabase client
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY") or SUPABASE_KEY
_supabase_client: Optional[Client] = None

def get_supabase_client() -> Optional[Client]:
    """Get Supabase client (singleton)."""
    global _supabase_client
    
    if not SUPABASE_AVAILABLE:
        logger.warning("⚠️ supabase package not installed. Run: pip install supabase")
        return None
    
    if _supabase_client is None:
        if not SUPABASE_URL or not SUPABASE_ANON_KEY:
            logger.warning("⚠️ Supabase not configured (SUPABASE_URL or SUPABASE_ANON_KEY missing)")
            return None
        
        try:
            _supabase_client = create_client(SUPABASE_URL, SUPABASE_ANON_KEY)
            logger.info("✅ Supabase client initialized")
        except Exception as e:
            logger.error(f"❌ Failed to initialize Supabase client: {e}")
            return None
    
    return _supabase_client


class AgentExecutor:
    """
    Executes agent runs and processes results.
    
    Modular design: Orchestrates agent execution, delegates to agent-specific services.
    """
    
    def __init__(self):
        self.client = get_supabase_client()
        if not self.client:
            raise ValueError("Supabase client not available")
        self.agent_manager = get_agent_manager()
    
    async def execute_agent(self, agent_id: str) -> Dict[str, Any]:
        """
        Execute a single agent run.
        
        Args:
            agent_id: Agent ID to execute
        
        Returns:
            Agent run record with results
        """
        # Get agent config
        agent = await self.agent_manager.get_agent(agent_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        if agent['status'] != 'active':
            raise ValueError(f"Agent {agent_id} is not active (status: {agent['status']})")
        
        # Create agent run record
        run_id = await self._create_agent_run(agent_id)
        
        try:
            # Execute agent-specific logic
            agent_type = agent['agent_type']
            config = agent['config']
            
            if agent_type == 'pubmed_sentinel':
                results = await self._execute_pubmed_sentinel(agent_id, config, run_id)
            elif agent_type == 'trial_scout':
                results = await self._execute_trial_scout(agent_id, config, run_id)
            elif agent_type == 'genomic_forager':
                results = await self._execute_genomic_forager(agent_id, config, run_id)
            elif agent_type == 'patient_knowledge_base':
                results = await self._execute_patient_kb(agent_id, config, run_id)
            else:
                raise ValueError(f"Unknown agent type: {agent_type}")
            
            # Process and store results
            processed = await self._process_results(agent_id, agent['user_id'], run_id, results)
            
            # Generate alerts for high-priority results
            alerts = await self._generate_alerts(agent_id, agent['user_id'], processed['high_priority'])
            
            # Update agent run
            await self._complete_agent_run(
                run_id,
                processed['total'],
                processed['new_count'],
                execution_log={
                    'results_count': processed['total'],
                    'new_results_count': processed['new_count'],
                    'alerts_generated': len(alerts)
                }
            )
            
            # Update agent last_run_at and next_run_at
            frequency = agent.get('run_frequency', 'daily')
            delta = {
                'hourly': timedelta(hours=1),
                'daily': timedelta(days=1),
                'weekly': timedelta(weeks=1),
                'monthly': timedelta(days=30)
            }.get(frequency, timedelta(days=1))
            
            next_run_at = (datetime.utcnow() + delta).isoformat()
            await self.agent_manager.update_agent(agent_id, agent['user_id'], {
                'last_run_at': datetime.utcnow().isoformat(),
                'next_run_at': next_run_at
            })
            
            logger.info(f"✅ Agent {agent_id} run {run_id} completed: {processed['total']} results, {processed['new_count']} new")
            
            return {
                'run_id': run_id,
                'results_count': processed['total'],
                'new_results_count': processed['new_count'],
                'alerts_count': len(alerts)
            }
            
        except Exception as e:
            logger.error(f"❌ Agent {agent_id} run {run_id} failed: {e}")
            await self._fail_agent_run(run_id, str(e))
            raise
    
    async def _create_agent_run(self, agent_id: str) -> str:
        """Create agent run record."""
        run_data = {
            'agent_id': agent_id,
            'run_status': 'running',
            'started_at': datetime.utcnow().isoformat(),
            'results_count': 0,
            'new_results_count': 0
        }
        
        result = self.client.table('agent_runs').insert(run_data).execute()
        if result.data and len(result.data) > 0:
            return result.data[0]['id']
        raise Exception("Failed to create agent run record")
    
    async def _complete_agent_run(
        self,
        run_id: str,
        results_count: int,
        new_results_count: int,
        execution_log: Optional[Dict] = None
    ):
        """Mark agent run as completed."""
        self.client.table('agent_runs').update({
            'run_status': 'completed',
            'completed_at': datetime.utcnow().isoformat(),
            'results_count': results_count,
            'new_results_count': new_results_count,
            'execution_log': execution_log or {}
        }).eq('id', run_id).execute()
    
    async def _fail_agent_run(self, run_id: str, error_message: str):
        """Mark agent run as failed."""
        self.client.table('agent_runs').update({
            'run_status': 'error',
            'completed_at': datetime.utcnow().isoformat(),
            'error_message': error_message
        }).eq('id', run_id).execute()
    
    async def _execute_pubmed_sentinel(
        self,
        agent_id: str,
        config: Dict[str, Any],
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Execute PubMed Sentinel agent.
        
        Delegates to enhanced_evidence_service for PubMed queries.
        """
        from .enhanced_evidence_service import EnhancedEvidenceService
        
        keywords = config.get('keywords', {})
        filters = config.get('filters', {})
        
        # Build search query
        search_terms = []
        if keywords.get('genes'):
            search_terms.extend(keywords['genes'])
        if keywords.get('diseases'):
            search_terms.extend(keywords['diseases'])
        if keywords.get('mechanisms'):
            search_terms.extend(keywords['mechanisms'])
        
        query = ' AND '.join(search_terms) if search_terms else ''
        
        # Get last run date for delta query
        agent = await self.agent_manager.get_agent(agent_id)
        last_run = agent.get('last_run_at')
        since_date = filters.get('min_date') or (last_run[:10] if last_run else None)
        
        # Query PubMed
        evidence_service = EnhancedEvidenceService()
        # TODO: Add delta query support to evidence_service
        # For now, use basic search
        papers = await evidence_service.search_pubmed(query, max_results=config.get('execution', {}).get('max_results_per_run', 100))
        
        # Format results
        results = []
        for paper in papers[:config.get('execution', {}).get('max_results_per_run', 100)]:
            results.append({
                'result_type': 'pubmed_article',
                'result_data': {
                    'pmid': paper.get('pmid'),
                    'title': paper.get('title'),
                    'authors': paper.get('authors'),
                    'abstract': paper.get('abstract'),
                    'publication_date': paper.get('publication_date'),
                    'journal': paper.get('journal'),
                    'url': f"https://pubmed.ncbi.nlm.nih.gov/{paper.get('pmid')}"
                },
                'relevance_score': 0.7,  # TODO: Calculate relevance
                'is_high_priority': paper.get('article_type') in ['Clinical Trial', 'Meta-Analysis']
            })
        
        return results
    
    async def _execute_trial_scout(
        self,
        agent_id: str,
        config: Dict[str, Any],
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Execute Trial Scout agent.
        
        Delegates to hybrid_trial_search for trial queries.
        """
        from .hybrid_trial_search import HybridTrialSearch
        
        patient_profile = config.get('patient_profile', {})
        filters = config.get('filters', {})
        
        # Build search query
        search_params = {
            'disease': patient_profile.get('disease'),
            'biomarkers': patient_profile.get('biomarkers', {}),
            'stage': patient_profile.get('stage'),
            'treatment_line': patient_profile.get('treatment_line'),
            'phase': filters.get('phase', []),
            'status': filters.get('status', ['Recruiting']),
            'location': filters.get('location', {})
        }
        
        # Query trials
        trial_search = HybridTrialSearch()
        trials = await trial_search.search_optimized(search_params)
        
        # Format results
        results = []
        for trial in trials[:config.get('execution', {}).get('max_results_per_run', 20)]:
            results.append({
                'result_type': 'clinical_trial',
                'result_data': {
                    'nct_id': trial.get('nct_id'),
                    'title': trial.get('title'),
                    'phase': trial.get('phase'),
                    'status': trial.get('status'),
                    'sites': trial.get('sites', []),
                    'eligibility_score': trial.get('eligibility_score'),
                    'url': f"https://clinicaltrials.gov/study/{trial.get('nct_id')}"
                },
                'relevance_score': trial.get('eligibility_score', 0.5),
                'is_high_priority': (
                    trial.get('phase') == 'Phase III' or
                    patient_profile.get('treatment_line') == 'first-line' and 'frontline' in trial.get('title', '').lower()
                )
            })
        
        return results
    
    async def _execute_genomic_forager(
        self,
        agent_id: str,
        config: Dict[str, Any],
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Execute Genomic Forager agent.
        
        Queries cBioPortal, TCGA, GEO for new datasets.
        """
        # TODO: Implement genomic dataset search
        # For now, return empty results
        logger.warning(f"⚠️ Genomic Forager not yet implemented for agent {agent_id}")
        return []
    
    async def _execute_patient_kb(
        self,
        agent_id: str,
        config: Dict[str, Any],
        run_id: str
    ) -> List[Dict[str, Any]]:
        """
        Execute Patient Knowledge Base agent.
        
        Builds/updates knowledge base for a patient.
        """
        from api.services.patient_knowledge_base_agent import PatientKnowledgeBaseAgent
        
        patient_id = config.get('patient_id')
        patient_profile = config.get('patient_profile')
        
        if not patient_id or not patient_profile:
            raise ValueError("patient_id and patient_profile required in config")
        
        # Initialize agent
        agent = PatientKnowledgeBaseAgent(patient_id, patient_profile)
        
        # Build/update KB
        execution_config = config.get('execution', {})
        max_queries = execution_config.get('max_queries_per_run', 10)
        
        result = await agent.build_knowledge_base(max_queries=max_queries)
        
        # Format results for agent executor
        results = []
        
        # Add papers as results
        if result.get('papers_added', 0) > 0:
            results.append({
                'result_type': 'kb_papers',
                'result_data': {
                    'papers_added': result['papers_added'],
                    'patient_id': patient_id
                },
                'relevance_score': 0.8,
                'is_high_priority': False
            })
        
        # Add edge cases as high-priority results
        if result.get('edge_cases_detected', 0) > 0:
            results.append({
                'result_type': 'edge_cases',
                'result_data': {
                    'edge_cases_detected': result['edge_cases_detected'],
                    'patient_id': patient_id
                },
                'relevance_score': 0.9,
                'is_high_priority': True
            })
        
        # Add entities as results
        if result.get('entities_created', 0) > 0:
            results.append({
                'result_type': 'kb_entities',
                'result_data': {
                    'entities_created': result['entities_created'],
                    'patient_id': patient_id
                },
                'relevance_score': 0.7,
                'is_high_priority': False
            })
        
        return results
    
    async def _process_results(
        self,
        agent_id: str,
        user_id: str,
        run_id: str,
        results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Process and store agent results.
        
        Deduplicates results and stores in database.
        """
        # Check for duplicates (by result_data hash or unique identifier)
        existing_results = self.client.table('agent_results').select('result_data').eq('agent_id', agent_id).execute()
        existing_hashes = set()
        
        for existing in (existing_results.data if existing_results.data else []):
            # Create hash from result_data
            result_data = existing.get('result_data', {})
            if result_data.get('pmid'):
                existing_hashes.add(f"pmid:{result_data['pmid']}")
            elif result_data.get('nct_id'):
                existing_hashes.add(f"nct:{result_data['nct_id']}")
        
        # Filter new results
        new_results = []
        high_priority = []
        
        for result in results:
            result_data = result.get('result_data', {})
            hash_key = None
            
            if result_data.get('pmid'):
                hash_key = f"pmid:{result_data['pmid']}"
            elif result_data.get('nct_id'):
                hash_key = f"nct:{result_data['nct_id']}"
            
            if hash_key and hash_key in existing_hashes:
                continue  # Skip duplicate
            
            # Store result
            result_record = {
                'agent_run_id': run_id,
                'agent_id': agent_id,
                'user_id': user_id,
                'result_type': result.get('result_type'),
                'result_data': result.get('result_data'),
                'relevance_score': result.get('relevance_score'),
                'is_high_priority': result.get('is_high_priority', False),
                'is_read': False
            }
            
            insert_result = self.client.table('agent_results').insert(result_record).execute()
            if insert_result.data:
                new_results.append(insert_result.data[0])
                if result.get('is_high_priority'):
                    high_priority.append(insert_result.data[0])
        
        return {
            'total': len(results),
            'new_count': len(new_results),
            'new_results': new_results,
            'high_priority': high_priority
        }
    
    async def _generate_alerts(
        self,
        agent_id: str,
        user_id: str,
        high_priority_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Generate alerts for high-priority results.
        """
        alerts = []
        
        for result in high_priority_results:
            result_type = result.get('result_type')
            result_data = result.get('result_data', {})
            
            # Determine alert type and content
            if result_type == 'pubmed_article':
                alert_type = 'new_publication'
                title = result_data.get('title', 'New Publication')
                message = f"New high-priority paper: {title}"
                priority = 'high' if 'RCT' in result_data.get('article_type', '') else 'medium'
            elif result_type == 'clinical_trial':
                alert_type = 'matching_trial'
                title = result_data.get('title', 'New Trial')
                message = f"New matching trial: {title}"
                priority = 'high' if result_data.get('phase') == 'Phase III' else 'medium'
            else:
                continue
            
            alert_record = {
                'agent_id': agent_id,
                'user_id': user_id,
                'agent_result_id': result.get('id'),
                'alert_type': alert_type,
                'title': title[:500],
                'message': message,
                'priority': priority,
                'is_read': False
            }
            
            insert_result = self.client.table('agent_alerts').insert(alert_record).execute()
            if insert_result.data:
                alerts.append(insert_result.data[0])
        
        return alerts


# Singleton instance
_agent_executor = None

def get_agent_executor() -> AgentExecutor:
    """Get singleton AgentExecutor instance."""
    global _agent_executor
    if _agent_executor is None:
        _agent_executor = AgentExecutor()
    return _agent_executor

