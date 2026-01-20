-- ============================================================================
-- AGENT SYSTEM TABLES MIGRATION
-- ============================================================================
-- Migration: 001_create_agent_tables.sql
-- Date: 2025-01-13
-- Purpose: Create agent system tables (agents, agent_runs, agent_results, agent_alerts)

-- Agent Definitions (user-configured agents)
CREATE TABLE IF NOT EXISTS public.agents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    agent_type VARCHAR(50) CHECK (agent_type IN (
        'pubmed_sentinel', 
        'trial_scout', 
        'vus_vigil',
        'genomic_forager',
        'patient_watchtower',
        'resistance_prophet'
    )) NOT NULL,
    name VARCHAR(255) NOT NULL,  -- User-friendly name
    description TEXT,
    config JSONB NOT NULL,  -- Agent-specific configuration
    status VARCHAR(20) CHECK (status IN ('active', 'paused', 'completed', 'error')) DEFAULT 'active',
    last_run_at TIMESTAMPTZ,
    next_run_at TIMESTAMPTZ,
    run_frequency VARCHAR(20) CHECK (run_frequency IN ('hourly', 'daily', 'weekly', 'monthly')) DEFAULT 'daily',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agents_user_id ON public.agents(user_id);
CREATE INDEX idx_agents_type ON public.agents(agent_type);
CREATE INDEX idx_agents_status ON public.agents(status);
CREATE INDEX idx_agents_next_run ON public.agents(next_run_at);

-- Agent Execution History
CREATE TABLE IF NOT EXISTS public.agent_runs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES public.agents(id) ON DELETE CASCADE NOT NULL,
    run_status VARCHAR(20) CHECK (run_status IN ('running', 'completed', 'error')) DEFAULT 'running',
    started_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ,
    results_count INT DEFAULT 0,
    new_results_count INT DEFAULT 0,  -- How many new findings vs. duplicates
    error_message TEXT,
    execution_log JSONB,  -- Detailed execution log
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_runs_agent_id ON public.agent_runs(agent_id);
CREATE INDEX idx_agent_runs_status ON public.agent_runs(run_status);
CREATE INDEX idx_agent_runs_started_at ON public.agent_runs(started_at);

-- Agent Results (what the agents found)
CREATE TABLE IF NOT EXISTS public.agent_results (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_run_id UUID REFERENCES public.agent_runs(id) ON DELETE CASCADE NOT NULL,
    agent_id UUID REFERENCES public.agents(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    result_type VARCHAR(50) CHECK (result_type IN (
        'pubmed_article', 
        'clinical_trial', 
        'vus_reclassification',
        'genomic_dataset',
        'patient_alert'
    )) NOT NULL,
    result_data JSONB NOT NULL,  -- Full result data (paper metadata, trial details, etc.)
    relevance_score FLOAT,  -- How relevant is this result? (0-1)
    is_high_priority BOOLEAN DEFAULT false,  -- Should this trigger an alert?
    is_read BOOLEAN DEFAULT false,  -- Has user acknowledged this result?
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_results_agent_run_id ON public.agent_results(agent_run_id);
CREATE INDEX idx_agent_results_agent_id ON public.agent_results(agent_id);
CREATE INDEX idx_agent_results_user_id ON public.agent_results(user_id);
CREATE INDEX idx_agent_results_type ON public.agent_results(result_type);
CREATE INDEX idx_agent_results_priority ON public.agent_results(is_high_priority);
CREATE INDEX idx_agent_results_unread ON public.agent_results(is_read) WHERE is_read = false;
CREATE INDEX idx_agent_results_created_at ON public.agent_results(created_at DESC);

-- Agent Alerts (high-priority notifications)
CREATE TABLE IF NOT EXISTS public.agent_alerts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    agent_id UUID REFERENCES public.agents(id) ON DELETE CASCADE NOT NULL,
    user_id UUID REFERENCES auth.users(id) ON DELETE CASCADE NOT NULL,
    agent_result_id UUID REFERENCES public.agent_results(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) CHECK (alert_type IN (
        'new_publication',
        'matching_trial',
        'vus_resolved',
        'new_dataset',
        'patient_alert'
    )) NOT NULL,
    title VARCHAR(500) NOT NULL,
    message TEXT NOT NULL,
    priority VARCHAR(20) CHECK (priority IN ('low', 'medium', 'high', 'critical')) DEFAULT 'medium',
    is_read BOOLEAN DEFAULT false,
    read_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX idx_agent_alerts_user_id ON public.agent_alerts(user_id);
CREATE INDEX idx_agent_alerts_agent_id ON public.agent_alerts(agent_id);
CREATE INDEX idx_agent_alerts_priority ON public.agent_alerts(priority);
CREATE INDEX idx_agent_alerts_unread ON public.agent_alerts(is_read) WHERE is_read = false;
CREATE INDEX idx_agent_alerts_created_at ON public.agent_alerts(created_at DESC);

