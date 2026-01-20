"""
Agent Scheduler Service - Background polling to trigger scheduled agent runs

Modular service for scheduling agent executions.
Uses simple polling loop (Option A) for Phase 1.
"""

import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Any

from .agent_manager import get_agent_manager
from .agent_executor import get_agent_executor

logger = logging.getLogger(__name__)


class AgentScheduler:
    """
    Schedules and triggers agent executions.
    
    Modular design: Simple polling loop that checks for agents ready to run.
    """
    
    def __init__(self, poll_interval: int = 60):
        """
        Initialize scheduler.
        
        Args:
            poll_interval: How often to check for scheduled agents (seconds)
        """
        self.poll_interval = poll_interval
        self.agent_manager = get_agent_manager()
        self.agent_executor = get_agent_executor()
        self._running = False
        self._task = None
    
    async def start(self):
        """Start the scheduler background task."""
        if self._running:
            logger.warning("⚠️ Scheduler already running")
            return
        
        self._running = True
        self._task = asyncio.create_task(self._scheduler_loop())
        logger.info(f"✅ Agent scheduler started (poll interval: {self.poll_interval}s)")
    
    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 Agent scheduler stopped")
    
    async def _scheduler_loop(self):
        """Main scheduler loop - polls for agents ready to run."""
        while self._running:
            try:
                # Get agents ready to run
                agents = await self.agent_manager.get_next_scheduled_agents(limit=10)
                
                if agents:
                    logger.info(f"📋 Found {len(agents)} agents ready to run")
                    
                    # Execute agents in parallel (with limit)
                    tasks = []
                    for agent in agents[:5]:  # Limit concurrent executions
                        task = asyncio.create_task(self._execute_agent_safe(agent))
                        tasks.append(task)
                    
                    # Wait for all to complete (or fail)
                    await asyncio.gather(*tasks, return_exceptions=True)
                
                # Wait before next poll
                await asyncio.sleep(self.poll_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ Scheduler loop error: {e}")
                await asyncio.sleep(self.poll_interval)
    
    async def _execute_agent_safe(self, agent: Dict[str, Any]):
        """
        Execute an agent with error handling.
        
        Args:
            agent: Agent record
        """
        agent_id = agent['id']
        try:
            logger.info(f"🚀 Executing agent {agent_id} ({agent['name']})")
            result = await self.agent_executor.execute_agent(agent_id)
            logger.info(f"✅ Agent {agent_id} completed: {result['results_count']} results, {result['new_results_count']} new")
        except Exception as e:
            logger.error(f"❌ Agent {agent_id} execution failed: {e}")
            # Update agent status to error
            try:
                await self.agent_manager.update_agent(
                    agent_id,
                    agent['user_id'],
                    {'status': 'error'}
                )
            except Exception as update_error:
                logger.error(f"❌ Failed to update agent status: {update_error}")


# Global scheduler instance
_scheduler = None

def get_scheduler() -> AgentScheduler:
    """Get singleton scheduler instance."""
    global _scheduler
    if _scheduler is None:
        _scheduler = AgentScheduler()
    return _scheduler


