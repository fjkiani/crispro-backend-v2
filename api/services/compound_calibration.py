"""
Compound Calibration Service

Calibrates compound S/P/E scores using empirical distributions from historical runs.

The calibration system converts raw scores into percentile rankings, providing
context-aware confidence intervals based on empirical evidence.

Key Features:
- Percentile ranking with linear interpolation
- Provenance tracking (source cohort, date, sample size)
- Minimum sample size enforcement (n≥10)
- Dynamic calibration from run history

Author: CrisPRO Platform
Date: November 5, 2025
"""

import json
import logging
from typing import Optional, Dict, List, Any
from datetime import datetime
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)


class CompoundCalibrationService:
    """
    Calibrate compound scores across diseases using empirical distributions.
    
    This service transforms raw S/P/E scores into calibrated percentiles based on
    historical run data, providing better interpretability and confidence bounds.
    
    Approach:
    - Build calibration from historical run data (when available)
    - Use percentile ranking with linear interpolation
    - Track provenance (source cohort, date, sample size)
    - Enforce minimum sample size (n≥10) for statistical validity
    
    Examples:
        >>> calibrator = CompoundCalibrationService()
        >>> percentile = calibrator.get_percentile("vitamin_d", "ovarian_cancer_hgs", 0.65)
        >>> print(percentile)  # e.g., 0.75 (75th percentile)
    """
    
    def __init__(self, calibration_file: Optional[str] = None):
        """
        Initialize the calibration service.
        
        Args:
            calibration_file: Path to calibration JSON file (optional)
        """
        self.calibration_file = calibration_file or self._get_default_calibration_path()
        self.calibration_data = self._load_calibration()
        
        logger.info(
            f"CompoundCalibrationService initialized with {len(self.calibration_data.get('compounds', {}))} "
            f"calibrated compounds"
        )
    
    def _get_default_calibration_path(self) -> str:
        """Get default path for calibration data file."""
        return str(
            Path(__file__).parent.parent / "resources" / "compound_calibration.json"
        )
    
    def _load_calibration(self) -> Dict[str, Any]:
        """
        Load pre-computed calibration data from JSON file.
        
        Returns:
            Calibration data dictionary with structure:
            {
                "version": "1.0.0",
                "metadata": {...},
                "compounds": {
                    "compound_name": {
                        "canonical_name": "...",
                        "diseases": {
                            "disease_id": {
                                "percentiles": {"p10": 0.45, "p25": 0.55, ...},
                                "sample_size": 50,
                                "source": "empirical_run_history",
                                "date": "2025-11-05T12:00:00Z",
                                "mean_score": 0.65,
                                "std_dev": 0.12
                            }
                        }
                    }
                }
            }
        """
        calibration_path = Path(self.calibration_file)
        
        if not calibration_path.exists():
            logger.warning(
                f"⚠️ No calibration file found at {calibration_path}, "
                f"using empty calibration (will create on first save)"
            )
            return self._create_empty_calibration()
        
        try:
            with open(calibration_path, 'r') as f:
                data = json.load(f)
            
            logger.info(
                f"✅ Loaded calibration data: {len(data.get('compounds', {}))} compounds, "
                f"version {data.get('version', 'unknown')}"
            )
            return data
            
        except json.JSONDecodeError as e:
            logger.error(f"🔥 Failed to parse calibration file: {e}")
            return self._create_empty_calibration()
        except Exception as e:
            logger.error(f"🔥 Error loading calibration: {e}")
            return self._create_empty_calibration()
    
    def _create_empty_calibration(self) -> Dict[str, Any]:
        """Create empty calibration data structure."""
        return {
            "version": "1.0.0",
            "metadata": {
                "last_updated": datetime.now().isoformat(),
                "total_compounds": 0,
                "total_runs": 0,
                "description": "Empirical calibration data for compound S/P/E scores"
            },
            "compounds": {}
        }
    
    def get_percentile(
        self,
        compound: str,
        disease: str,
        raw_score: float
    ) -> Optional[float]:
        """
        Convert raw S/P/E score to calibrated percentile.
        
        This method looks up the empirical distribution for a given compound-disease
        pair and interpolates the raw score to find its percentile rank.
        
        Args:
            compound: Compound identifier (normalized, e.g., "vitamin_d")
            disease: Disease identifier (e.g., "ovarian_cancer_hgs")
            raw_score: Raw S/P/E score to calibrate (0-1 range)
            
        Returns:
            Calibrated percentile (0-1) or None if insufficient calibration data
            
        Examples:
            >>> calibrator = CompoundCalibrationService()
            >>> # Compound with raw score 0.65
            >>> percentile = calibrator.get_percentile("vitamin_d", "ovarian_cancer_hgs", 0.65)
            >>> print(f"Score 0.65 is at {percentile*100:.0f}th percentile")
            Score 0.65 is at 75th percentile
        """
        # Normalize compound key (lowercase, replace spaces with underscores)
        compound_key = compound.lower().replace(" ", "_").replace("-", "_")
        
        # Check if calibration exists for this compound
        if compound_key not in self.calibration_data.get("compounds", {}):
            logger.debug(f"⚠️ No calibration for compound: {compound}")
            return None
        
        compound_cal = self.calibration_data["compounds"][compound_key]
        
        # Check if calibration exists for this disease
        if disease not in compound_cal.get("diseases", {}):
            logger.debug(f"⚠️ No calibration for {compound} in {disease}")
            return None
        
        disease_cal = compound_cal["diseases"][disease]
        
        # Enforce minimum sample size for statistical validity
        sample_size = disease_cal.get("sample_size", 0)
        if sample_size < 10:
            logger.warning(
                f"⚠️ Insufficient calibration data for {compound} in {disease} "
                f"(n={sample_size}, minimum=10)"
            )
            return None
        
        # Get percentile distribution
        percentiles = disease_cal.get("percentiles", {})
        if not percentiles:
            logger.warning(f"⚠️ No percentile data for {compound} in {disease}")
            return None
        
        # Interpolate percentile from empirical distribution
        interpolated = self._interpolate_percentile(raw_score, percentiles)
        
        logger.debug(
            f"✅ Calibrated {compound} in {disease}: "
            f"raw_score={raw_score:.3f} → percentile={interpolated:.3f} "
            f"(n={sample_size})"
        )
        
        return interpolated
    
    def _interpolate_percentile(
        self,
        raw_score: float,
        percentiles: Dict[str, float]
    ) -> float:
        """
        Linear interpolation between percentile points.
        
        Given a raw score and a distribution of percentile benchmarks,
        interpolates to find the score's percentile rank.
        
        Args:
            raw_score: Score to calibrate (0-1)
            percentiles: Dict of {percentile: score} mappings
                        e.g., {"p25": 0.3, "p50": 0.5, "p75": 0.7, "p90": 0.85}
            
        Returns:
            Interpolated percentile (0-1)
            
        Algorithm:
            1. Convert percentile keys to numeric values (e.g., "p25" → 0.25)
            2. Sort by score value
            3. Handle edge cases (score below min or above max)
            4. Linear interpolation between two closest points
        
        Examples:
            >>> percentiles = {"p10": 0.3, "p50": 0.5, "p90": 0.8}
            >>> calibrator._interpolate_percentile(0.65, percentiles)
            0.7  # Between p50 (0.5) and p90 (0.8)
        """
        if not percentiles:
            logger.debug("⚠️ Empty percentiles, returning raw score")
            return raw_score
        
        # Convert percentile strings to numeric (0-1 range)
        # e.g., "p25" → 0.25, "p90" → 0.90
        points = []
        for key, score_value in percentiles.items():
            try:
                # Extract numeric part from "pXX" format
                percentile_num = float(key.replace('p', '')) / 100.0
                points.append((percentile_num, score_value))
            except (ValueError, AttributeError) as e:
                logger.warning(f"⚠️ Invalid percentile key '{key}': {e}")
                continue
        
        if not points:
            logger.warning("⚠️ No valid percentile points, returning raw score")
            return raw_score
        
        # Sort by score value (ascending)
        points.sort(key=lambda x: x[1])
        
        # EDGE CASE 1: Score below minimum percentile
        if raw_score <= points[0][1]:
            logger.debug(
                f"Score {raw_score:.3f} below min {points[0][1]:.3f}, "
                f"returning {points[0][0]:.3f}"
            )
            return points[0][0]
        
        # EDGE CASE 2: Score above maximum percentile
        if raw_score >= points[-1][1]:
            logger.debug(
                f"Score {raw_score:.3f} above max {points[-1][1]:.3f}, "
                f"returning {points[-1][0]:.3f}"
            )
            return points[-1][0]
        
        # LINEAR INTERPOLATION: Find two closest points and interpolate
        for i in range(len(points) - 1):
            percentile_1, score_1 = points[i]
            percentile_2, score_2 = points[i + 1]
            
            # Check if raw_score falls between these two points
            if score_1 <= raw_score <= score_2:
                # Linear interpolation formula:
                # percentile = p1 + (raw_score - s1) / (s2 - s1) * (p2 - p1)
                ratio = (raw_score - score_1) / (score_2 - score_1)
                interpolated = percentile_1 + ratio * (percentile_2 - percentile_1)
                
                logger.debug(
                    f"Interpolated between p{percentile_1*100:.0f} ({score_1:.3f}) "
                    f"and p{percentile_2*100:.0f} ({score_2:.3f}): "
                    f"score={raw_score:.3f} → percentile={interpolated:.3f}"
                )
                
                return interpolated
        
        # Fallback (should not reach here if data is valid)
        logger.warning(f"⚠️ Interpolation fallback, returning raw score {raw_score:.3f}")
        return raw_score
    
    def build_calibration_from_runs(
        self,
        compound: str,
        disease: str,
        runs: List[Dict[str, Any]],
        score_field: str = "spe_score"
    ) -> Optional[Dict[str, Any]]:
        """
        Build calibration from historical run data.
        
        This method computes empirical percentiles from a collection of historical
        runs for a specific compound-disease pair.
        
        Args:
            compound: Compound identifier
            disease: Disease identifier
            runs: List of run data dicts with score field
            score_field: Field name containing the score (default: "spe_score")
            
        Returns:
            Calibration dict with structure:
            {
                "percentiles": {"p10": 0.45, "p25": 0.55, ...},
                "source": "empirical_run_history",
                "sample_size": 50,
                "date": "2025-11-05T12:00:00Z",
                "mean_score": 0.65,
                "std_dev": 0.12
            }
            or None if insufficient data
            
        Examples:
            >>> runs = [
            ...     {"spe_score": 0.45}, {"spe_score": 0.62}, {"spe_score": 0.78},
            ...     # ... more runs
            ... ]
            >>> calibration = calibrator.build_calibration_from_runs(
            ...     "vitamin_d", "ovarian_cancer_hgs", runs
            ... )
            >>> print(calibration["percentiles"])
            {"p10": 0.48, "p25": 0.55, "p50": 0.65, "p75": 0.72, "p90": 0.82}
        """
        # Validate minimum sample size
        if len(runs) < 10:
            logger.warning(
                f"⚠️ Insufficient runs for calibration: {len(runs)} < 10 (minimum)"
            )
            return None
        
        # Extract scores from runs
        scores = []
        for run in runs:
            if score_field in run:
                score = run[score_field]
                if isinstance(score, (int, float)) and 0 <= score <= 1:
                    scores.append(float(score))
                else:
                    logger.warning(
                        f"⚠️ Invalid score value: {score} (must be 0-1)"
                    )
            else:
                logger.warning(f"⚠️ Missing score field '{score_field}' in run")
        
        if len(scores) < 10:
            logger.warning(
                f"⚠️ Insufficient valid scores: {len(scores)} < 10 (minimum)"
            )
            return None
        
        # Sort scores for percentile calculation
        scores_sorted = sorted(scores)
        n = len(scores_sorted)
        
        # Compute percentiles using numpy for accuracy
        percentiles = {
            "p10": float(np.percentile(scores_sorted, 10)),
            "p25": float(np.percentile(scores_sorted, 25)),
            "p50": float(np.percentile(scores_sorted, 50)),  # median
            "p75": float(np.percentile(scores_sorted, 75)),
            "p90": float(np.percentile(scores_sorted, 90))
        }
        
        # Compute statistics
        mean_score = float(np.mean(scores_sorted))
        std_dev = float(np.std(scores_sorted))
        
        calibration = {
            "percentiles": percentiles,
            "source": "empirical_run_history",
            "sample_size": n,
            "date": datetime.now().isoformat(),
            "mean_score": mean_score,
            "std_dev": std_dev,
            "min_score": float(scores_sorted[0]),
            "max_score": float(scores_sorted[-1])
        }
        
        logger.info(
            f"✅ Built calibration for {compound} in {disease}: "
            f"n={n}, mean={mean_score:.3f}±{std_dev:.3f}, "
            f"p50={percentiles['p50']:.3f}"
        )
        
        return calibration
    
    def add_calibration(
        self,
        compound: str,
        disease: str,
        calibration: Dict[str, Any],
        canonical_name: Optional[str] = None
    ) -> bool:
        """
        Add or update calibration for a compound-disease pair.
        
        Args:
            compound: Compound identifier
            disease: Disease identifier
            calibration: Calibration dict from build_calibration_from_runs()
            canonical_name: Canonical compound name (optional)
            
        Returns:
            True if successfully added, False otherwise
        """
        # Normalize compound key
        compound_key = compound.lower().replace(" ", "_").replace("-", "_")
        
        # Initialize compound entry if needed
        if compound_key not in self.calibration_data["compounds"]:
            self.calibration_data["compounds"][compound_key] = {
                "canonical_name": canonical_name or compound,
                "diseases": {}
            }
        
        # Add disease calibration
        self.calibration_data["compounds"][compound_key]["diseases"][disease] = calibration
        
        # Update metadata
        self.calibration_data["metadata"]["last_updated"] = datetime.now().isoformat()
        self.calibration_data["metadata"]["total_compounds"] = len(
            self.calibration_data["compounds"]
        )
        
        logger.info(
            f"✅ Added calibration: {compound} in {disease} "
            f"(n={calibration.get('sample_size', 0)})"
        )
        
        return True
    
    def save_calibration(self) -> bool:
        """
        Save calibration data to JSON file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            calibration_path = Path(self.calibration_file)
            
            # Create directory if needed
            calibration_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Write JSON with nice formatting
            with open(calibration_path, 'w') as f:
                json.dump(self.calibration_data, f, indent=2)
            
            logger.info(
                f"✅ Saved calibration data to {calibration_path} "
                f"({len(self.calibration_data.get('compounds', {}))} compounds)"
            )
            return True
            
        except Exception as e:
            logger.error(f"🔥 Failed to save calibration: {e}")
            return False
    
    def get_calibration_info(self, compound: str, disease: str) -> Optional[Dict[str, Any]]:
        """
        Get calibration metadata for a compound-disease pair.
        
        Returns:
            Dict with sample_size, date, source, statistics, or None if not calibrated
        """
        compound_key = compound.lower().replace(" ", "_").replace("-", "_")
        
        if compound_key not in self.calibration_data.get("compounds", {}):
            return None
        
        diseases = self.calibration_data["compounds"][compound_key].get("diseases", {})
        if disease not in diseases:
            return None
        
        return diseases[disease]


# Singleton instance for application-wide use
_calibrator_instance: Optional[CompoundCalibrationService] = None


def get_calibrator() -> CompoundCalibrationService:
    """
    Get or create the singleton CompoundCalibrationService instance.
    
    Returns:
        CompoundCalibrationService singleton instance
    """
    global _calibrator_instance
    if _calibrator_instance is None:
        _calibrator_instance = CompoundCalibrationService()
    return _calibrator_instance





