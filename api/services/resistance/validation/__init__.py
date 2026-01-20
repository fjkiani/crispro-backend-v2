"""
Validation utilities for Timing & Chemosensitivity Engine.

Provides synthetic data generation and validation tools for proxy validation.
"""

from .synthetic_data_generator import (
    generate_synthetic_timing_test_cases,
    generate_synthetic_ca125_trajectories,
    save_synthetic_data,
)

__all__ = [
    "generate_synthetic_timing_test_cases",
    "generate_synthetic_ca125_trajectories",
    "save_synthetic_data",
]
