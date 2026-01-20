"""
Configuration module for the oncology backend.
"""
import os
from dotenv import load_dotenv
from httpx import Timeout
from loguru import logger

# Load environment variables from .env file
load_dotenv()

# HIPAA and Security Configuration
HIPAA_MODE = os.getenv("HIPAA_MODE", "false").lower() == "true"
AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "false").lower() == "true"
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://localhost:5173").split(",")

# Database configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

# API keys
DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# S/P/E Weight Configuration (clinical-grade defaults)
WEIGHT_SEQUENCE = float(os.getenv("WEIGHT_SEQUENCE", "0.35"))
WEIGHT_PATHWAY = float(os.getenv("WEIGHT_PATHWAY", "0.35"))
WEIGHT_EVIDENCE = float(os.getenv("WEIGHT_EVIDENCE", "0.30"))

# Evidence Gate Thresholds (conservative clinical defaults)
EVIDENCE_GATE_THRESHOLD = float(os.getenv("EVIDENCE_GATE_THRESHOLD", "0.7"))
CLINVAR_STRONG_THRESHOLD = float(os.getenv("CLINVAR_STRONG_THRESHOLD", "0.8"))
PATHWAY_ALIGNMENT_THRESHOLD = float(os.getenv("PATHWAY_ALIGNMENT_THRESHOLD", "0.2"))
INSUFFICIENT_SIGNAL_THRESHOLD = float(os.getenv("INSUFFICIENT_SIGNAL_THRESHOLD", "0.02"))

# Feature Flags
# Default massive modes to false for production safety; enable explicitly in research
ENABLE_MASSIVE_MODES = os.getenv("ENABLE_MASSIVE_MODES", "false").lower() == "true"
ENABLE_RESEARCH_MODE = os.getenv("ENABLE_RESEARCH_MODE", "false").lower() == "true"
ENABLE_CALIBRATION_PRELOAD = os.getenv("ENABLE_CALIBRATION_PRELOAD", "true").lower() == "true"
# Global Evo2 disable gate
DISABLE_EVO2 = os.getenv("DISABLE_EVO2", "false").lower() in ("true", "1", "yes")
# Global Literature disable gate
DISABLE_LITERATURE = os.getenv("DISABLE_LITERATURE", "false").lower() in ("true", "1", "yes")
# Global Fusion (AlphaMissense) disable gate
DISABLE_FUSION = os.getenv("DISABLE_FUSION", "false").lower() in ("true", "1", "yes")

# SAE (Sparse Autoencoder) feature flags
# Phase 1: Evo2 activations endpoint (disabled by default)
ENABLE_EVO2_SAE = os.getenv("ENABLE_EVO2_SAE", "false").lower() in ("true", "1", "yes")
# Phase 1: True SAE features from layer 26 (disabled by default)
ENABLE_TRUE_SAE = os.getenv("ENABLE_TRUE_SAE", "false").lower() in ("true", "1", "yes")
logger.info(f"DEBUG: ENABLE_TRUE_SAE resolved to: {ENABLE_TRUE_SAE}") # DEBUG STATEMENT
# Phase 2: True SAE pathway scores (disabled by default, requires feature→pathway mapping)
ENABLE_TRUE_SAE_PATHWAYS = os.getenv("ENABLE_TRUE_SAE_PATHWAYS", "false").lower() in ("true", "1", "yes")

# Spam-safety controls for Evo fan-out (defaults favor safety)
EVO_SPAM_SAFE = os.getenv("EVO_SPAM_SAFE", "true").lower() in ("true", "1", "yes")
EVO_MAX_MODELS = int(os.getenv("EVO_MAX_MODELS", "1" if EVO_SPAM_SAFE else "3"))
EVO_MAX_FLANKS = int(os.getenv("EVO_MAX_FLANKS", "1" if EVO_SPAM_SAFE else "5"))
EVO_DISABLE_TRANSCRIPT_SWEEP = os.getenv("EVO_DISABLE_TRANSCRIPT_SWEEP", "true" if EVO_SPAM_SAFE else "false").lower() in ("true", "1", "yes")
EVO_DISABLE_SYMMETRY = os.getenv("EVO_DISABLE_SYMMETRY", "true" if EVO_SPAM_SAFE else "false").lower() in ("true", "1", "yes")

# API Exposure Flags (enable in dev by default)
ENABLE_INSIGHTS_API = os.getenv("ENABLE_INSIGHTS_API", "true").lower() == "true"
ENABLE_DESIGN_API = os.getenv("ENABLE_DESIGN_API", "true").lower() == "true"
ENABLE_COMMAND_CENTER = os.getenv("ENABLE_COMMAND_CENTER", "true").lower() == "true"

# Operational Mode
OPERATIONAL_MODE = os.getenv("OPERATIONAL_MODE", "research")  # "clinical" or "research"

# Calibration Configuration
CALIBRATION_TTL_HOURS = int(os.getenv("CALIBRATION_TTL_HOURS", "24"))
CALIBRATION_REFRESH_INTERVAL_HOURS = int(os.getenv("CALIBRATION_REFRESH_INTERVAL_HOURS", "6"))

# Common MM genes for preloading
COMMON_MM_GENES = [
    "BRAF", "KRAS", "NRAS", "FGFR3", "TP53", "ATM", "MDM2", 
    "MYC", "CCND1", "CCND2", "CCND3", "BRCA1", "BRCA2", 
    "PSMB5", "CRBN", "IKZF1", "IKZF3", "DKK1", "NFKB1", 
    "RELA", "TRAF3", "PARP1", "RB1", "CDKN2A"
]

def get_evidence_weights():
    """Get current evidence weights configuration."""
    return {
        "sequence": WEIGHT_SEQUENCE,
        "pathway": WEIGHT_PATHWAY,
        "evidence": WEIGHT_EVIDENCE
    }

def get_evidence_gates():
    """Get current evidence gate thresholds."""
    return {
        "evidence_gate_threshold": EVIDENCE_GATE_THRESHOLD,
        "clinvar_strong_threshold": CLINVAR_STRONG_THRESHOLD,
        "pathway_alignment_threshold": PATHWAY_ALIGNMENT_THRESHOLD,
        "insufficient_signal_threshold": INSUFFICIENT_SIGNAL_THRESHOLD
    }

def get_feature_flags():
    """Get current feature flag configuration."""
    return {
        "enable_massive_modes": ENABLE_MASSIVE_MODES,
        "enable_research_mode": ENABLE_RESEARCH_MODE,
        "enable_calibration_preload": ENABLE_CALIBRATION_PRELOAD,
        "enable_insights_api": ENABLE_INSIGHTS_API,
        "enable_design_api": ENABLE_DESIGN_API,
        "enable_command_center": ENABLE_COMMAND_CENTER,
        "disable_evo2": DISABLE_EVO2,
        "disable_literature": DISABLE_LITERATURE,
        "disable_fusion": DISABLE_FUSION,
        # SAE flags
        "enable_evo2_sae": ENABLE_EVO2_SAE,
        "enable_true_sae": ENABLE_TRUE_SAE,
        "enable_true_sae_pathways": ENABLE_TRUE_SAE_PATHWAYS,
        # Evo spam-safety knobs
        "evo_spam_safe": EVO_SPAM_SAFE,
        "evo_max_models": EVO_MAX_MODELS,
        "evo_max_flanks": EVO_MAX_FLANKS,
        "evo_disable_transcript_sweep": EVO_DISABLE_TRANSCRIPT_SWEEP,
        "evo_disable_symmetry": EVO_DISABLE_SYMMETRY,
        # Default to delta-only to prevent upstream fan-out unless explicitly opted-in
        "evo_use_delta_only": os.getenv("EVO_USE_DELTA_ONLY", "true").lower() in ("true", "1", "yes"),
    }

def get_api_flags():
    """Return API exposure flags for conditional router includes and handlers."""
    return {
        "insights": ENABLE_INSIGHTS_API,
        "design": ENABLE_DESIGN_API,
        "command_center": ENABLE_COMMAND_CENTER,
    }

def is_clinical_mode():
    """Check if running in clinical mode (stricter validation)."""
    return OPERATIONAL_MODE.lower() == "clinical"

def is_research_mode():
    """Check if running in research mode (more permissive)."""
    return OPERATIONAL_MODE.lower() == "research"

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip()
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", os.getenv("SUPABASE_ANON_KEY", "").strip()).strip()
SUPABASE_RUNS_TABLE = os.getenv("SUPABASE_RUNS_TABLE", "mdt_runs").strip()
SUPABASE_RUN_VARIANTS_TABLE = os.getenv("SUPABASE_RUN_VARIANTS_TABLE", "mdt_run_variants").strip()
SUPABASE_EVENTS_TABLE = os.getenv("SUPABASE_EVENTS_TABLE", "mdt_events").strip()
SUPABASE_DEEP_ANALYSIS_TABLE = os.getenv("SUPABASE_DEEP_ANALYSIS_TABLE", "mdt_deep_analysis").strip()
SUPABASE_JOB_RESULTS_TABLE = os.getenv("SUPABASE_JOB_RESULTS_TABLE", "mdt_job_results").strip()

# External API tokens
DIFFBOT_TOKEN = os.getenv("DIFFBOT_TOKEN", "").strip()
ENFORMER_URL = os.getenv("ENFORMER_URL", "").strip()
BORZOI_URL = os.getenv("BORZOI_URL", "").strip()

# Evo2 service configuration
EVO_SERVICE_URL = os.getenv("EVO_SERVICE_URL", "https://crispro--evo-service-evoservice-api.modal.run")
EVO_URL_1B = os.getenv("EVO_URL_1B", "https://crispro--evo-service-evoservice1b-api-1b.modal.run")
# IMPORTANT: Do NOT default to a 7B URL. In many environments the 7B service is not deployed,
# and a non-empty default causes silent fallback behavior + noisy 404s that look like "Evo2 ran"
# when it didn't. Only use 7B when explicitly configured via env.
EVO_URL_7B = os.getenv("EVO_URL_7B", "")
EVO_URL_40B = os.getenv("EVO_URL_40B", "https://crispro--evo-service-evoservice-api.modal.run")
EVO_TIMEOUT = Timeout(60.0, connect=10.0)

# Default Evo2 model (can be overridden via DEFAULT_EVO_MODEL env var)
# Change this default to affect all Evo2 model selections system-wide
DEFAULT_EVO_MODEL = os.getenv("DEFAULT_EVO_MODEL", "evo2_1b")

# Model to base URL mapping with dynamic fallback logic
def get_model_url(model_id: str) -> str:
    """Get URL for model with fallback logic, evaluated at runtime"""
    # Re-read environment variables at runtime
    # IMPORTANT: provide sane defaults from this module so an unset env var
    # doesn't silently route to an unintended fallback URL.
    url_1b = os.getenv("EVO_URL_1B", EVO_URL_1B).strip()
    url_7b = os.getenv("EVO_URL_7B", EVO_URL_7B).strip()
    url_40b = os.getenv("EVO_URL_40B", EVO_URL_40B).strip()
    
    if model_id == "evo2_1b":
        return url_1b or url_7b or url_40b
    elif model_id == "evo2_7b":
        return url_7b or url_1b or url_40b
    elif model_id == "evo2_40b":
        return url_40b
    else:
        # Default fallback
        return url_1b or url_7b or url_40b

# Legacy dictionary for backward compatibility (will use runtime lookup)
MODEL_TO_BASE = {
    "evo2_1b": lambda: get_model_url("evo2_1b"),
    "evo2_7b": lambda: get_model_url("evo2_7b"), 
    "evo2_40b": lambda: get_model_url("evo2_40b"),
}

# Use-case configuration
USE_CASES = {
    "myeloma": {
        "id": "myeloma",
        "title": "Myeloma Digital Twin",
        "default_windows": [1024, 2048, 4096, 8192],
        "default_exon_flank": 600,
        "decision_policy": {"id": "v1", "ras_threshold": 2.0},
    }
}

# Hotspot variants for myeloma analysis
HOTSPOTS = {
    ("BRAF", "p.Val600Glu"), ("KRAS", "p.Gly12Asp"), ("KRAS", "p.Gly12Val"), ("KRAS", "p.Gly12Cys"),
    ("NRAS", "p.Gln61Lys"), ("NRAS", "p.Gln61Arg"),
}

# Mock data for YC demo
MOCK_VARIANT_SCORES = {
    "BRAF": {
        "p.Val600Glu": {"zeta": -5.0, "confidence": 0.92},
        "p.Lys601Glu": {"zeta": -2.3, "confidence": 0.81},
    }
}

# Mock responses for basic endpoints (used by health router)
MOCK_ORACLE_RESPONSE = {"assessment": "HIGH_THREAT", "confidence": 0.95, "reasoning": "Critical pathway disruption predicted"}
MOCK_FORGE_RESPONSE = {"therapeutics": [{"name": "CRISPR-Cas9 Guide RNA", "target": "BRAF V600E", "efficacy": 0.92}]}
MOCK_GAUNTLET_RESPONSE = {"trial_results": {"success_rate": 0.87, "safety_profile": "ACCEPTABLE"}}
MOCK_DOSSIER_RESPONSE = {"dossier_id": "IND-2024-001", "status": "GENERATED", "pages": 847}

# Legacy dictionary for backward compatibility (will use runtime lookup)
MODEL_TO_BASE = {
    "evo2_1b": lambda: get_model_url("evo2_1b"),
    "evo2_7b": lambda: get_model_url("evo2_7b"), 
    "evo2_40b": lambda: get_model_url("evo2_40b"),
}

# Use-case configuration
USE_CASES = {
    "myeloma": {
        "id": "myeloma",
        "title": "Myeloma Digital Twin",
        "default_windows": [1024, 2048, 4096, 8192],
        "default_exon_flank": 600,
        "decision_policy": {"id": "v1", "ras_threshold": 2.0},
    }
}

# Hotspot variants for myeloma analysis
HOTSPOTS = {
    ("BRAF", "p.Val600Glu"), ("KRAS", "p.Gly12Asp"), ("KRAS", "p.Gly12Val"), ("KRAS", "p.Gly12Cys"),
    ("NRAS", "p.Gln61Lys"), ("NRAS", "p.Gln61Arg"),
}

# Mock data for YC demo
MOCK_VARIANT_SCORES = {
    "BRAF": {
        "p.Val600Glu": {"zeta": -5.0, "confidence": 0.92},
        "p.Lys601Glu": {"zeta": -2.3, "confidence": 0.81},
    }
}

# Mock responses for basic endpoints (used by health router)
MOCK_ORACLE_RESPONSE = {"assessment": "HIGH_THREAT", "confidence": 0.95, "reasoning": "Critical pathway disruption predicted"}
MOCK_FORGE_RESPONSE = {"therapeutics": [{"name": "CRISPR-Cas9 Guide RNA", "target": "BRAF V600E", "efficacy": 0.92}]}
MOCK_GAUNTLET_RESPONSE = {"trial_results": {"success_rate": 0.87, "safety_profile": "ACCEPTABLE"}}
MOCK_DOSSIER_RESPONSE = {"dossier_id": "IND-2024-001", "status": "GENERATED", "pages": 847} 