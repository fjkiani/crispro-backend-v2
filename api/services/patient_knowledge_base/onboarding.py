"""
Patient KB Onboarding - MVP Implementation

Automatically creates and configures Patient KB Agent for new patients.

Research Use Only - Not for Clinical Decision Making
"""

from typing import Dict, Any
import logging
import asyncio

from api.services.agent_manager import get_agent_manager

logger = logging.getLogger(__name__)


async def onboard_patient_kb_agent(
    user_id: str,
    patient_id: str,
    patient_profile: Dict[str, Any],
    frequency: str = "daily"
) -> Dict[str, Any]:
    """
    Create Patient KB Agent for new patient.
    
    Args:
        user_id: User ID (for agent ownership)
        patient_id: Patient identifier
        patient_profile: Complete patient profile
        frequency: Execution frequency (daily/weekly)
    
    Returns:
        Agent configuration
    """
    try:
        agent_manager = get_agent_manager()
        
        # Create agent configuration
        agent_config = {
            "type": "patient_knowledge_base",
            "name": f"{patient_id} Knowledge Base Agent",
            "user_id": user_id,
            "config": {
                "patient_id": patient_id,
                "patient_profile": patient_profile,
                "execution": {
                    "frequency": frequency,
                    "max_queries_per_run": 10
                },
                "alerts": {
                    "new_opportunities": True,
                    "edge_cases": True
                }
            },
            "is_active": True
        }
        
        # Create agent via Agent Manager
        agent = await agent_manager.create_agent(
            user_id=user_id,
            agent_type="patient_knowledge_base",
            name=agent_config["name"],
            config=agent_config["config"],
            run_frequency=frequency
        )
        
        # Trigger initial KB build (don't wait - run in background)
        try:
            from api.services.agent_executor import AgentExecutor
            executor = AgentExecutor()
            # Schedule initial build (non-blocking)
            asyncio.create_task(executor.execute_agent(agent["id"]))
            logger.info(f"✅ Initial KB build triggered for {patient_id}")
        except Exception as e:
            logger.warning(f"⚠️ Failed to trigger initial KB build: {e}")
            # Don't fail onboarding if initial build fails
        
        return {
            "agent_id": agent["id"],
            "patient_id": patient_id,
            "status": "created",
            "initial_build_triggered": True
        }
    except Exception as e:
        logger.error(f"❌ Failed to create Patient KB Agent for {patient_id}: {e}", exc_info=True)
        raise
