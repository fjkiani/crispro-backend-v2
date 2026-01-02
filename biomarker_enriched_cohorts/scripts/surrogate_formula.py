#!/usr/bin/env python3
"""
Generic Surrogate Biomarker Formula Engine

Purpose:
- Compute surrogate biomarkers from clinical variables using configurable formulas
- Create high/low groups based on thresholds
- Support ECW/TBW and other surrogate biomarkers

Example:
    formula = "(BMI / albumin) * (1 + (age - 60) * 0.01)"
    threshold = 0.42
    threshold_direction = "greater"  # high = bad
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from typing import Any, Dict, Optional


def compute_surrogate_biomarker(
    cohort_df: pd.DataFrame,
    formula: str,
    threshold: float,
    threshold_direction: str = "greater",
    surrogate_name: str = "surrogate_value",
    group_name: str = "surrogate_group",
) -> pd.DataFrame:
    """
    Compute surrogate biomarker and create groups.
    
    Args:
        cohort_df: DataFrame with patient data (must include columns referenced in formula)
        formula: Python expression string (e.g., "(BMI / albumin) * (1 + (age - 60) * 0.01)")
        threshold: Threshold value for grouping
        threshold_direction: "greater" (high > threshold) or "less" (high < threshold)
        surrogate_name: Column name for computed surrogate value
        group_name: Column name for group labels ("High" or "Low")
    
    Returns:
        DataFrame with added columns: surrogate_name and group_name
    
    Example:
        >>> df = pd.DataFrame({'BMI': [25, 30], 'albumin': [4.0, 3.5], 'age': [55, 65]})
        >>> result = compute_surrogate_biomarker(
        ...     df, 
        ...     formula="(BMI / albumin) * (1 + (age - 60) * 0.01)",
        ...     threshold=0.42,
        ...     threshold_direction="greater"
        ... )
        >>> 'surrogate_value' in result.columns
        True
        >>> 'surrogate_group' in result.columns
        True
    """
    df = cohort_df.copy()
    
    # Create a safe evaluation context (only allow math operations)
    safe_dict = {
        '__builtins__': {},
        'np': np,
        'pd': pd,
    }
    
    # Add all DataFrame columns to the evaluation context
    for col in df.columns:
        safe_dict[col] = df[col].values
    
    # Evaluate formula
    try:
        surrogate_values = eval(formula, safe_dict)
        
        # Handle numpy arrays and pandas Series
        if isinstance(surrogate_values, (np.ndarray, pd.Series)):
            df[surrogate_name] = surrogate_values
        else:
            # If formula returns a scalar, broadcast it
            df[surrogate_name] = surrogate_values
    except Exception as e:
        raise ValueError(f"Failed to evaluate formula '{formula}': {e}")
    
    # Create groups based on threshold
    if threshold_direction == "greater":
        # High = values > threshold (bad)
        df[group_name] = np.where(
            df[surrogate_name] > threshold, 
            'High', 
            'Low'
        )
    elif threshold_direction == "less":
        # High = values < threshold (bad)
        df[group_name] = np.where(
            df[surrogate_name] < threshold, 
            'High', 
            'Low'
        )
    else:
        raise ValueError(f"threshold_direction must be 'greater' or 'less', got '{threshold_direction}'")
    
    # Handle NaN values
    df[group_name] = df[group_name].where(
        pd.notna(df[surrogate_name]), 
        'Unknown'
    )
    
    return df


def compute_ecw_tbw_surrogate(
    cohort_df: pd.DataFrame,
    threshold: float = 0.42,
    bmi_col: str = 'bmi',
    albumin_col: str = 'albumin',
    age_col: str = 'age',
) -> pd.DataFrame:
    """
    Compute ECW/TBW surrogate biomarker (validated from Katsura et al. 2023).
    
    Formula: ECW_TBW_surrogate = (BMI / albumin) * age_factor
    Where: age_factor = 1.0 + (age - 60) * 0.01
    
    Args:
        cohort_df: DataFrame with BMI, albumin, and age columns
        threshold: Threshold for high/low grouping (default: 0.42 from Katsura 2023)
        bmi_col: Column name for BMI
        albumin_col: Column name for albumin
        age_col: Column name for age
    
    Returns:
        DataFrame with added columns: 'ecw_tbw_surrogate' and 'ecw_tbw_group'
    """
    # Build formula string
    formula = f"({bmi_col} / {albumin_col}) * (1.0 + ({age_col} - 60) * 0.01)"
    
    return compute_surrogate_biomarker(
        cohort_df=cohort_df,
        formula=formula,
        threshold=threshold,
        threshold_direction="greater",  # High ECW/TBW = bad
        surrogate_name="ecw_tbw_surrogate",
        group_name="ecw_tbw_group",
    )


if __name__ == '__main__':
    # Example usage
    import json
    from pathlib import Path
    
    # Load test cohort
    cohort_path = Path(__file__).parent.parent / 'data' / 'tcga_ov_enriched_v2.json'
    if cohort_path.exists():
        with open(cohort_path) as f:
            data = json.load(f)
        
        patients = data['cohort']['patients']
        df = pd.DataFrame(patients)
        
        # Test ECW/TBW computation
        if all(col in df.columns for col in ['bmi', 'albumin', 'age']):
            result = compute_ecw_tbw_surrogate(df)
            print(f"✅ Computed ECW/TBW surrogate for {len(result)} patients")
            print(f"   High ECW/TBW: {sum(result['ecw_tbw_group'] == 'High')} patients")
            print(f"   Low ECW/TBW: {sum(result['ecw_tbw_group'] == 'Low')} patients")
            print(f"   Unknown: {sum(result['ecw_tbw_group'] == 'Unknown')} patients")
        else:
            print("⚠️  Missing required columns (bmi, albumin, age) in cohort")
    else:
        print("⚠️  Test cohort not found, skipping example")

