"""Runtime settings for orchestrators.

Goal: centralize timeouts + base URLs (env overrides) so orchestrators aren't full of magic numbers.
"""

from __future__ import annotations

import os


def get_orchestrator_api_base_url() -> str:
    # Used only where internal HTTP calls remain (Task B aims to reduce these).
    return os.getenv("API_BASE_URL", "http://localhost:8000")


def get_internal_http_timeout_seconds() -> float:
    # Conservative default for internal calls that may do heavy work.
    try:
        return float(os.getenv("ORCHESTRATOR_HTTP_TIMEOUT_SECONDS", "60.0"))
    except Exception:
        return 60.0


def get_code_version() -> str:
    # Prefer CI-provided values; fall back to "unknown" (deterministic).
    return (
        os.getenv("CODE_VERSION")
        or os.getenv("GIT_SHA")
        or os.getenv("COMMIT_SHA")
        or "unknown"
    )


def get_contract_version() -> str:
    # Bump manually when making breaking contract changes.
    return os.getenv("RESISTANCE_CONTRACT_VERSION", "resistance_contract_v1")

































