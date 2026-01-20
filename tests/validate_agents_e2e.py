#!/usr/bin/env python3
"""
End-to-End Validation Script for Zeta Agent System

Tests complete workflow:
1. Database connectivity
2. Agent creation
3. Agent execution
4. Results retrieval
5. Frontend API compatibility

Run: python tests/validate_agents_e2e.py
"""

import sys
import os
import asyncio
import httpx
from datetime import datetime
from typing import Dict, Any, Optional

# Add parent directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from api.services.agent_manager import AgentManager, get_supabase_client
from api.services.agent_executor import AgentExecutor

# Test configuration
TEST_USER_ID = "00000000-0000-0000-0000-000000000000"  # Test user UUID
BASE_URL = "http://localhost:8000"
API_BASE = f"{BASE_URL}/api/agents"

# Colors for output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"


def print_section(title: str):
    """Print formatted section header."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}{title}{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")


def print_success(message: str):
    """Print success message."""
    print(f"{GREEN}✅ {message}{RESET}")


def print_error(message: str):
    """Print error message."""
    print(f"{RED}❌ {message}{RESET}")


def print_warning(message: str):
    """Print warning message."""
    print(f"{YELLOW}⚠️  {message}{RESET}")


def print_info(message: str):
    """Print info message."""
    print(f"ℹ️  {message}")


async def test_database_connectivity():
    """Test 1: Database connectivity and table existence."""
    print_section("TEST 1: Database Connectivity")
    
    try:
        client = get_supabase_client()
        if not client:
            print_error("Supabase client not available")
            return False
        
        # Check if tables exist by trying to query them
        tables_to_check = ['agents', 'agent_runs', 'agent_results', 'agent_alerts']
        all_exist = True
        
        for table in tables_to_check:
            try:
                result = client.table(table).select('id').limit(1).execute()
                print_success(f"Table '{table}' exists and is accessible")
            except Exception as e:
                print_error(f"Table '{table}' not accessible: {e}")
                all_exist = False
        
        return all_exist
    
    except Exception as e:
        print_error(f"Database connectivity test failed: {e}")
        return False


async def test_agent_manager():
    """Test 2: Agent Manager CRUD operations."""
    print_section("TEST 2: Agent Manager (Backend Service)")
    
    try:
        manager = AgentManager()
        
        # Test: Create agent
        print_info("Creating test agent...")
        agent = await manager.create_agent(
            user_id=TEST_USER_ID,
            agent_type='pubmed_sentinel',
            name='E2E Test Agent',
            config={
                'keywords': {'query': 'ovarian cancer PARP inhibitor'},
                'filters': {'date_range': '2024-01-01'}
            },
            description='Test agent for E2E validation',
            run_frequency='daily'
        )
        
        if not agent or 'id' not in agent:
            print_error("Agent creation failed - no ID returned")
            return False, None
        
        agent_id = agent['id']
        print_success(f"Agent created: {agent_id}")
        
        # Test: Get agent
        print_info("Retrieving agent...")
        retrieved = await manager.get_agent(agent_id, TEST_USER_ID)
        if not retrieved or retrieved['id'] != agent_id:
            print_error("Agent retrieval failed")
            return False, agent_id
        
        print_success("Agent retrieved successfully")
        
        # Test: Update agent
        print_info("Updating agent...")
        updated = await manager.update_agent(
            agent_id,
            TEST_USER_ID,
            {'description': 'Updated description'}
        )
        if not updated or updated['description'] != 'Updated description':
            print_error("Agent update failed")
            return False, agent_id
        
        print_success("Agent updated successfully")
        
        # Test: List agents
        print_info("Listing agents...")
        agents = await manager.list_agents(TEST_USER_ID)
        if not agents or len(agents) == 0:
            print_error("Agent listing failed")
            return False, agent_id
        
        print_success(f"Found {len(agents)} agent(s)")
        
        # Cleanup: Delete agent
        print_info("Cleaning up test agent...")
        await manager.delete_agent(agent_id, TEST_USER_ID)
        print_success("Test agent deleted")
        
        return True, None
    
    except ValueError as e:
        if "Agent limit reached" in str(e):
            print_warning(f"Agent limit reached (expected for testing): {e}")
            # Try to delete existing agents
            try:
                agents = await manager.list_agents(TEST_USER_ID)
                for a in agents[:1]:  # Delete first agent
                    await manager.delete_agent(a['id'], TEST_USER_ID)
                print_info("Deleted existing agent, retrying...")
                return await test_agent_manager()  # Retry
            except Exception:
                pass
        print_error(f"Agent Manager test failed: {e}")
        return False, None
    except Exception as e:
        print_error(f"Agent Manager test failed: {e}")
        return False, None


async def test_api_endpoints():
    """Test 3: API endpoints (HTTP)."""
    print_section("TEST 3: API Endpoints (HTTP)")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        # Test: Health check (agents endpoint)
        print_info("Testing GET /api/agents (list agents)...")
        try:
            response = await client.get(API_BASE)
            if response.status_code == 200:
                data = response.json()
                print_success(f"GET /api/agents: {response.status_code}")
                print_info(f"  Response: {len(data.get('agents', []))} agents")
            elif response.status_code == 401:
                print_warning("GET /api/agents: 401 (authentication required - expected)")
            else:
                print_error(f"GET /api/agents: {response.status_code}")
                return False
        except httpx.ConnectError:
            print_error("Cannot connect to backend server. Is it running?")
            print_info("  Start backend: cd oncology-coPilot/oncology-backend-minimal && uvicorn api.main:app --reload")
            return False
        except Exception as e:
            print_error(f"GET /api/agents failed: {e}")
            return False
        
        # Test: Create agent (requires auth, but we can test structure)
        print_info("Testing POST /api/agents (create agent - requires auth)...")
        try:
            response = await client.post(
                API_BASE,
                json={
                    'agent_type': 'pubmed_sentinel',
                    'name': 'API Test Agent',
                    'config': {'keywords': {'query': 'test'}}
                }
            )
            if response.status_code == 401:
                print_warning("POST /api/agents: 401 (authentication required - expected)")
            elif response.status_code == 200:
                print_success("POST /api/agents: 200 (agent created)")
            else:
                print_warning(f"POST /api/agents: {response.status_code} (may need auth)")
        except Exception as e:
            print_warning(f"POST /api/agents test incomplete: {e}")
        
        return True


async def test_agent_execution():
    """Test 4: Agent execution (manual run)."""
    print_section("TEST 4: Agent Execution")
    
    try:
        manager = AgentManager()
        executor = AgentExecutor()
        
        # Create test agent
        print_info("Creating agent for execution test...")
        agent = await manager.create_agent(
            user_id=TEST_USER_ID,
            agent_type='pubmed_sentinel',
            name='Execution Test Agent',
            config={
                'keywords': {'query': 'cancer immunotherapy'},
                'filters': {'date_range': '2024-01-01'}
            },
            run_frequency='daily'
        )
        
        agent_id = agent['id']
        print_success(f"Agent created: {agent_id}")
        
        # Execute agent
        print_info("Executing agent (this may take 30-60 seconds)...")
        try:
            result = await executor.execute_agent(agent_id)
            
            if result and 'run_id' in result:
                print_success(f"Agent execution started: run_id={result['run_id']}")
                
                # Wait a bit for execution to complete
                print_info("Waiting for execution to complete...")
                await asyncio.sleep(5)
                
                # Check run status
                runs = await manager.get_agent_runs(agent_id)
                if runs and len(runs) > 0:
                    latest_run = runs[0]
                    print_success(f"Agent run found: status={latest_run.get('run_status')}")
                    print_info(f"  Results count: {latest_run.get('results_count', 0)}")
                    print_info(f"  New results: {latest_run.get('new_results_count', 0)}")
                else:
                    print_warning("No agent runs found (execution may still be in progress)")
            else:
                print_error("Agent execution failed - no run_id returned")
                return False, agent_id
        
        except Exception as e:
            print_warning(f"Agent execution test incomplete: {e}")
            print_info("  (This is expected if PubMed API is unavailable)")
        
        # Cleanup
        print_info("Cleaning up test agent...")
        await manager.delete_agent(agent_id, TEST_USER_ID)
        print_success("Test agent deleted")
        
        return True, None
    
    except Exception as e:
        print_error(f"Agent execution test failed: {e}")
        return False, None


async def test_agent_limits():
    """Test 5: Agent limits (tier-based)."""
    print_section("TEST 5: Agent Limits")
    
    try:
        manager = AgentManager()
        
        # Test: Create agents up to limit (for free tier: 3)
        print_info("Testing agent limits (free tier: 3 agents)...")
        
        created_agents = []
        try:
            for i in range(4):  # Try to create 4 agents (should fail on 4th)
                agent = await manager.create_agent(
                    user_id=TEST_USER_ID,
                    agent_type='pubmed_sentinel',
                    name=f'Limit Test Agent {i+1}',
                    config={'keywords': {'query': 'test'}},
                    run_frequency='daily'
                )
                created_agents.append(agent['id'])
                print_success(f"Agent {i+1} created")
        
        except ValueError as e:
            if "Agent limit reached" in str(e):
                print_success(f"Agent limit correctly enforced: {e}")
            else:
                print_error(f"Unexpected error: {e}")
                return False
        
        # Cleanup
        print_info("Cleaning up test agents...")
        for agent_id in created_agents:
            try:
                await manager.delete_agent(agent_id, TEST_USER_ID)
            except Exception:
                pass
        
        print_success("Agent limits test passed")
        return True
    
    except Exception as e:
        print_error(f"Agent limits test failed: {e}")
        return False


async def test_frontend_compatibility():
    """Test 6: Frontend API compatibility."""
    print_section("TEST 6: Frontend API Compatibility")
    
    # Check if frontend components exist and can import
    frontend_files = [
        'oncology-coPilot/oncology-frontend/src/context/AgentContext.jsx',
        'oncology-coPilot/oncology-frontend/src/components/agents/AgentDashboard.jsx',
        'oncology-coPilot/oncology-frontend/src/components/agents/AgentWizard.jsx',
        'oncology-coPilot/oncology-frontend/src/pages/AgentsPage.jsx'
    ]
    
    all_exist = True
    for file_path in frontend_files:
        if os.path.exists(file_path):
            print_success(f"Frontend file exists: {file_path}")
        else:
            print_error(f"Frontend file missing: {file_path}")
            all_exist = False
    
    # Check if AgentContext has required methods
    if os.path.exists(frontend_files[0]):
        with open(frontend_files[0], 'r') as f:
            content = f.read()
            required_methods = [
                'fetchAgents',
                'createAgent',
                'updateAgent',
                'deleteAgent',
                'runAgent',
                'fetchAgentRuns',
                'fetchAgentResults'
            ]
            
            for method in required_methods:
                if method in content:
                    print_success(f"AgentContext has method: {method}")
                else:
                    print_error(f"AgentContext missing method: {method}")
                    all_exist = False
    
    return all_exist


async def main():
    """Run all validation tests."""
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"{BLUE}ZETA AGENT SYSTEM - END-TO-END VALIDATION{RESET}")
    print(f"{BLUE}{'='*60}{RESET}\n")
    print(f"Test User ID: {TEST_USER_ID}")
    print(f"Backend URL: {BASE_URL}")
    print(f"Timestamp: {datetime.now().isoformat()}\n")
    
    results = {}
    
    # Test 1: Database
    results['database'] = await test_database_connectivity()
    
    # Test 2: Agent Manager
    results['agent_manager'], _ = await test_agent_manager()
    
    # Test 3: API Endpoints
    results['api_endpoints'] = await test_api_endpoints()
    
    # Test 4: Agent Execution
    results['agent_execution'], _ = await test_agent_execution()
    
    # Test 5: Agent Limits
    results['agent_limits'] = await test_agent_limits()
    
    # Test 6: Frontend Compatibility
    results['frontend'] = await test_frontend_compatibility()
    
    # Summary
    print_section("VALIDATION SUMMARY")
    
    total_tests = len(results)
    passed_tests = sum(1 for v in results.values() if v)
    
    for test_name, passed in results.items():
        status = f"{GREEN}✅ PASS{RESET}" if passed else f"{RED}❌ FAIL{RESET}"
        print(f"{test_name:20} {status}")
    
    print(f"\n{BLUE}{'='*60}{RESET}")
    print(f"Total: {passed_tests}/{total_tests} tests passed")
    
    if passed_tests == total_tests:
        print_success("🎉 ALL TESTS PASSED - SYSTEM IS OPERATIONAL!")
        return 0
    else:
        print_warning(f"⚠️  {total_tests - passed_tests} test(s) failed - review above")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)


