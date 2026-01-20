"""
Agent Manager Service - CRUD operations for agent configurations

Modular service for managing user-configured autonomous agents.
Handles agent lifecycle: create, update, delete, pause, activate.
"""

from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import uuid
import logging
import os

# Try to import supabase, but handle gracefully if not installed
try:
    from supabase import create_client, Client
    SUPABASE_AVAILABLE = True
except ImportError:
    SUPABASE_AVAILABLE = False
    Client = None

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

# Agent type definitions
AGENT_TYPES = {
    'pubmed_sentinel': {
        'name': 'PubMed Sentinel',
        'description': 'Monitor biomedical literature for new publications',
        'config_schema': {
            'keywords': {'type': 'object', 'required': True},
            'filters': {'type': 'object', 'required': False},
            'relevance': {'type': 'object', 'required': False},
            'execution': {'type': 'object', 'required': False},
            'alerts': {'type': 'object', 'required': False}
        }
    },
    'trial_scout': {
        'name': 'Trial Scout',
        'description': 'Monitor clinical trial landscape for matching opportunities',
        'config_schema': {
            'patient_profile': {'type': 'object', 'required': True},
            'filters': {'type': 'object', 'required': False},
            'matching': {'type': 'object', 'required': False},
            'execution': {'type': 'object', 'required': False},
            'alerts': {'type': 'object', 'required': False}
        }
    },
    'genomic_forager': {
        'name': 'Genomic Forager',
        'description': 'Hunt for new genomic datasets across public repositories',
        'config_schema': {
            'search_criteria': {'type': 'object', 'required': True},
            'repositories': {'type': 'array', 'required': False},
            'execution': {'type': 'object', 'required': False},
            'alerts': {'type': 'object', 'required': False}
        }
    },
    'patient_knowledge_base': {
        'name': 'Patient Knowledge Base Agent',
        'description': 'Continuously builds knowledge base for patients based on their profiles',
        'config_schema': {
            'patient_id': {'type': 'string', 'required': True},
            'patient_profile': {'type': 'object', 'required': True},
            'execution': {
                'type': 'object',
                'required': False,
                'properties': {
                    'frequency': {'type': 'string', 'enum': ['hourly', 'daily', 'weekly', 'monthly']},
                    'max_queries_per_run': {'type': 'integer', 'default': 10}
                }
            },
            'alerts': {
                'type': 'object',
                'required': False,
                'properties': {
                    'new_opportunities': {'type': 'boolean', 'default': True},
                    'edge_cases': {'type': 'boolean', 'default': True}
                }
            }
        }
    }
}

# Frequency to timedelta mapping
FREQUENCY_DELTA = {
    'hourly': timedelta(hours=1),
    'daily': timedelta(days=1),
    'weekly': timedelta(weeks=1),
    'monthly': timedelta(days=30)
}


class AgentManager:
    """
    Manages agent configurations and lifecycle.
    
    Modular design: Single responsibility for agent CRUD operations.
    """
    
    def __init__(self):
        self.client = get_supabase_client()
        if not self.client:
            raise ValueError("Supabase client not available")
    
    async def create_agent(
        self,
        user_id: str,
        agent_type: str,
        name: str,
        config: Dict[str, Any],
        description: Optional[str] = None,
        run_frequency: str = 'daily'
    ) -> Dict[str, Any]:
        """
        Create a new agent configuration.
        
        Enforces tier-based agent limits:
        - Free: 3 agents
        - Pro: 10 agents
        - Enterprise: Unlimited
        
        Args:
            user_id: User who owns the agent
            agent_type: Type of agent (pubmed_sentinel, trial_scout, etc.)
            name: User-friendly name
            config: Agent-specific configuration
            description: Optional description
            run_frequency: How often to run (hourly, daily, weekly, monthly)
        
        Returns:
            Created agent record
        
        Raises:
            ValueError: If agent limit reached or invalid agent_type
        """
        # Check agent count limit
        user_tier = await self._get_user_tier(user_id)
        current_count = await self._count_user_agents(user_id)
        limit = self._get_agent_limit(user_tier)
        
        if limit is not None and current_count >= limit:
            raise ValueError(f"Agent limit reached ({limit} agents for {user_tier} tier)")
        
        # Validate agent type
        if agent_type not in AGENT_TYPES:
            raise ValueError(f"Invalid agent_type: {agent_type}. Must be one of {list(AGENT_TYPES.keys())}")
        
        # Validate config schema (basic validation)
        schema = AGENT_TYPES[agent_type]['config_schema']
        for key, spec in schema.items():
            if spec.get('required') and key not in config:
                raise ValueError(f"Missing required config key: {key}")
        
        # Calculate next_run_at (1 hour from now for immediate first run)
        next_run_at = (datetime.utcnow() + timedelta(hours=1)).isoformat()
        
        # Insert agent
        agent_data = {
            'user_id': user_id,
            'agent_type': agent_type,
            'name': name,
            'description': description or '',
            'config': config,
            'status': 'active',
            'run_frequency': run_frequency,
            'next_run_at': next_run_at,
            'created_at': datetime.utcnow().isoformat(),
            'updated_at': datetime.utcnow().isoformat()
        }
        
        try:
            result = self.client.table('agents').insert(agent_data).execute()
            if result.data:
                logger.info(f"✅ Created agent {result.data[0]['id']} for user {user_id}")
                return result.data[0]
            else:
                raise Exception("No data returned from insert")
        except Exception as e:
            logger.error(f"❌ Failed to create agent: {e}")
            raise
    
    async def get_user_agents(
        self,
        user_id: str,
        status: Optional[str] = None,
        agent_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get all agents for a user.
        
        Args:
            user_id: User ID
            status: Optional filter by status (active, paused, etc.)
            agent_type: Optional filter by agent type
        
        Returns:
            List of agent records
        """
        query = self.client.table('agents').select('*').eq('user_id', user_id)
        
        if status:
            query = query.eq('status', status)
        if agent_type:
            query = query.eq('agent_type', agent_type)
        
        query = query.order('created_at', desc=True)
        
        try:
            result = query.execute()
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Failed to get user agents: {e}")
            return []
    
    async def get_agent(self, agent_id: str, user_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Get a single agent by ID.
        
        Args:
            agent_id: Agent ID
            user_id: Optional user ID for ownership verification
        
        Returns:
            Agent record or None
        """
        query = self.client.table('agents').select('*').eq('id', agent_id)
        
        if user_id:
            query = query.eq('user_id', user_id)
        
        try:
            result = query.execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error(f"❌ Failed to get agent {agent_id}: {e}")
            return None
    
    async def update_agent(
        self,
        agent_id: str,
        user_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Update an agent configuration.
        
        Args:
            agent_id: Agent ID
            user_id: User ID (for ownership verification)
            updates: Fields to update (config, name, description, run_frequency, etc.)
        
        Returns:
            Updated agent record
        """
        # Verify ownership
        agent = await self.get_agent(agent_id, user_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found or not owned by user {user_id}")
        
        # Update next_run_at if frequency changed
        if 'run_frequency' in updates and updates['run_frequency'] != agent['run_frequency']:
            delta = FREQUENCY_DELTA.get(updates['run_frequency'], timedelta(days=1))
            updates['next_run_at'] = (datetime.utcnow() + delta).isoformat()
        
        updates['updated_at'] = datetime.utcnow().isoformat()
        
        try:
            result = self.client.table('agents').update(updates).eq('id', agent_id).eq('user_id', user_id).execute()
            if result.data:
                logger.info(f"✅ Updated agent {agent_id}")
                return result.data[0]
            else:
                raise Exception("No data returned from update")
        except Exception as e:
            logger.error(f"❌ Failed to update agent {agent_id}: {e}")
            raise
    
    async def delete_agent(self, agent_id: str, user_id: str) -> bool:
        """
        Delete an agent (cascade deletes runs, results, alerts).
        
        Args:
            agent_id: Agent ID
            user_id: User ID (for ownership verification)
        
        Returns:
            True if deleted, False otherwise
        """
        # Verify ownership
        agent = await self.get_agent(agent_id, user_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found or not owned by user {user_id}")
        
        try:
            result = self.client.table('agents').delete().eq('id', agent_id).eq('user_id', user_id).execute()
            logger.info(f"✅ Deleted agent {agent_id}")
            return True
        except Exception as e:
            logger.error(f"❌ Failed to delete agent {agent_id}: {e}")
            return False
    
    async def pause_agent(self, agent_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Pause an agent (stops scheduled runs).
        
        Args:
            agent_id: Agent ID
            user_id: User ID
        
        Returns:
            Updated agent record
        """
        return await self.update_agent(agent_id, user_id, {'status': 'paused'})
    
    async def activate_agent(self, agent_id: str, user_id: str) -> Optional[Dict[str, Any]]:
        """
        Activate a paused agent (resumes scheduled runs).
        
        Args:
            agent_id: Agent ID
            user_id: User ID
        
        Returns:
            Updated agent record
        """
        # Calculate next_run_at when reactivating
        agent = await self.get_agent(agent_id, user_id)
        if not agent:
            raise ValueError(f"Agent {agent_id} not found")
        
        frequency = agent.get('run_frequency', 'daily')
        delta = FREQUENCY_DELTA.get(frequency, timedelta(days=1))
        next_run_at = (datetime.utcnow() + delta).isoformat()
        
        return await self.update_agent(agent_id, user_id, {
            'status': 'active',
            'next_run_at': next_run_at
        })
    
    async def get_next_scheduled_agents(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get agents that should run next (for scheduler).
        
        Args:
            limit: Maximum number of agents to return
        
        Returns:
            List of agents ready to run
        """
        now = datetime.utcnow().isoformat()
        
        try:
            result = (
                self.client.table('agents')
                .select('*')
                .eq('status', 'active')
                .lte('next_run_at', now)
                .order('next_run_at', desc=False)
                .limit(limit)
                .execute()
            )
            return result.data if result.data else []
        except Exception as e:
            logger.error(f"❌ Failed to get scheduled agents: {e}")
            return []
    
    async def _get_user_tier(self, user_id: str) -> str:
        """
        Get user tier from user_profiles table.
        
        Args:
            user_id: User ID
        
        Returns:
            User tier ('free', 'pro', 'enterprise') - defaults to 'free'
        """
        try:
            result = (
                self.client.table('user_profiles')
                .select('tier')
                .eq('id', user_id)
                .execute()
            )
            if result.data and len(result.data) > 0:
                tier = result.data[0].get('tier', 'free')
                return tier.lower() if tier else 'free'
            return 'free'  # Default to free tier if no profile found
        except Exception as e:
            logger.warning(f"⚠️ Failed to get user tier for {user_id}: {e}, defaulting to 'free'")
            return 'free'
    
    async def _count_user_agents(self, user_id: str) -> int:
        """
        Count active agents for a user.
        
        Args:
            user_id: User ID
        
        Returns:
            Count of active agents
        """
        try:
            result = (
                self.client.table('agents')
                .select('id', count='exact')
                .eq('user_id', user_id)
                .eq('status', 'active')
                .execute()
            )
            # Supabase returns count in result.count if count='exact'
            if hasattr(result, 'count') and result.count is not None:
                return result.count
            # Fallback: count data array
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error(f"❌ Failed to count user agents: {e}")
            return 0
    
    def _get_agent_limit(self, tier: str) -> Optional[int]:
        """
        Get agent limit for tier.
        
        Args:
            tier: User tier ('free', 'pro', 'enterprise')
        
        Returns:
            Agent limit (None for unlimited)
        """
        limits = {
            'free': 3,
            'pro': 10,
            'enterprise': None  # Unlimited
        }
        return limits.get(tier.lower(), 3)  # Default to free tier limit


# Singleton instance
_agent_manager = None

def get_agent_manager() -> AgentManager:
    """Get singleton AgentManager instance."""
    global _agent_manager
    if _agent_manager is None:
        _agent_manager = AgentManager()
    return _agent_manager

