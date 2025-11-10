"""
Sequence Scorers Utils: Shared utility functions for scoring.
"""
from typing import Any


def percentile_like(value: float) -> float:
    """Lightweight piecewise mapping to approximate percentiles in [0,1]."""
    try:
        v = float(max(0.0, value))
        if v <= 0.005:
            return 0.05
        if v <= 0.01:
            return 0.10
        if v <= 0.02:
            return 0.20
        if v <= 0.05:
            return 0.50
        if v <= 0.10:
            return 0.80
        return 1.0
    except Exception:
        return 0.0


def classify_impact_level(score: float) -> str:
    """Classify impact level based on score magnitude."""
    try:
        v = abs(float(score or 0.0))
        if v >= 20000:
            return "catastrophic_impact"
        if v >= 10000:
            return "major_impact"
        if v >= 1000:
            return "moderate_impact"
        if v >= 100:
            return "minor_impact"
        return "no_impact"
    except Exception:
        return "no_impact"


def safe_float(value: Any, default: float = 0.0) -> float:
    """Safely convert value to float."""
    try:
        return float(value or default)
    except (ValueError, TypeError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """Safely convert value to int."""
    try:
        return int(value or default)
    except (ValueError, TypeError):
        return default


def safe_str(value: Any, default: str = "") -> str:
    """Safely convert value to string."""
    try:
        return str(value or default)
    except Exception:
        return default


