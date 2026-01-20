#!/usr/bin/env python3
"""
⚔️ SAE BIOMARKER CORRELATION SERVICE
====================================

Agent: Zo (Lead Commander)
Date: January 15, 2025
Priority: HIGH
Status: Sprint 1 - Phase 2 Core

Objective: Compute statistical correlations between SAE features and platinum outcomes.
This service loads the SAE cohort data extracted by extract_sae_features_cohort.py and
performs rigorous statistical analysis to identify which SAE features are predictive
of platinum response.

Guardrails:
- RUO/validation-only (NOT for production scoring)
- Statistical rigor (Pearson r, chi-square, cross-validation)
- Stability testing (bootstrap resampling)
- Multiple testing correction (Bonferroni/FDR)
- Manager approval required before integration into WIWFM

Inputs:
- data/validation/sae_cohort/sae_features_tcga_ov_platinum.json

Outputs:
- data/validation/sae_cohort/sae_tcga_ov_platinum_biomarkers.json
- Top-N features ranked by:
  1. Pearson correlation with outcome (continuous: sensitive=1.0, refractory=0.0, resistant=0.5)
  2. Chi-square test (categorical: sensitive vs resistant vs refractory)
  3. Cross-validation stability (feature selection consistency)
  4. Effect size (Cohen's d)

Success Criteria:
- Process all patients in SAE cohort
- Compute correlation for all 32K SAE features
- Rank by statistical significance + effect size
- Identify top 100 features with p < 0.01
- Bootstrap confidence intervals for top features
- Multiple testing correction applied
"""

import json
import numpy as np
from pathlib import Path
from typing import Dict, List, Any, Tuple, Optional
from dataclasses import dataclass, asdict
from datetime import datetime
from loguru import logger
from scipy import stats
from sklearn.model_selection import KFold
from sklearn.preprocessing import StandardScaler
from collections import Counter
import sys

# --- Configuration ---
SAE_COHORT_FILE = Path("data/validation/sae_cohort/sae_features_tcga_ov_platinum.json")
OUTPUT_FILE = Path("data/validation/sae_cohort/sae_tcga_ov_platinum_biomarkers.json")
LOG_FILE = Path("data/validation/sae_cohort/biomarker_correlation_log.log")

# Statistical thresholds
P_VALUE_THRESHOLD = 0.01
EFFECT_SIZE_THRESHOLD = 0.3  # Cohen's d >= 0.3 (small to medium effect)
CV_STABILITY_THRESHOLD = 0.6  # Feature selected in >=60% of CV folds
TOP_N_FEATURES = 100
BOOTSTRAP_ITERATIONS = 1000
RANDOM_SEED = 42

# Outcome encoding (continuous for correlation analysis)
OUTCOME_ENCODING = {
    "sensitive": 1.0,      # Best outcome
    "resistant": 0.5,      # Intermediate
    "refractory": 0.0      # Worst outcome
}

# --- Logging Setup ---
logger.remove()
logger.add(sys.stderr, level="INFO")
logger.add(LOG_FILE, rotation="10 MB", level="DEBUG")

# --- Data Structures ---
@dataclass
class FeatureCorrelation:
    """Statistical correlation result for a single SAE feature."""
    feature_index: int
    pearson_r: float
    pearson_p: float
    spearman_r: float
    spearman_p: float
    chi_square: float
    chi_square_p: float
    cohen_d: float
    cv_stability: float  # Fraction of CV folds where feature was significant
    bootstrap_ci_lower: float
    bootstrap_ci_upper: float
    rank: int = 0

@dataclass
class BiomarkerSummary:
    """Summary of biomarker discovery analysis."""
    top_features: List[Dict[str, Any]]
    total_features_analyzed: int
    significant_features_count: int
    p_value_threshold: float
    effect_size_threshold: float
    cv_stability_threshold: float
    correction_method: str
    cohort_size: int
    outcome_distribution: Dict[str, int]
    provenance: Dict[str, Any]

# --- Helper Functions ---
def load_sae_cohort_data(cohort_file: Optional[Path] = None) -> Tuple[List[Dict], List[float], List[str]]:
    """
    Loads SAE cohort data and prepares feature matrix + outcomes.
    
    Args:
        cohort_file: Optional path to SAE cohort file. Defaults to SAE_COHORT_FILE.
    
    Returns:
        patients: List of patient dicts with SAE features
        outcome_vector: Encoded outcome values
        patient_ids: List of patient IDs
    """
    file_path = cohort_file or SAE_COHORT_FILE
    
    if not file_path.exists():
        raise FileNotFoundError(f"SAE cohort file not found: {file_path}")
    
    with open(file_path, 'r') as f:
        cohort_data = json.load(f)
    
    # Handle both old format (list) and new format (dict with 'patients' key)
    if isinstance(cohort_data, dict) and "patients" in cohort_data:
        patients = cohort_data["patients"]
    else:
        patients = cohort_data
    
    # Filter for patients with variants that have SAE features
    patients_with_features = [
        p for p in patients 
        if p.get("variants") and any(v.get("top_features") for v in p.get("variants", []))
    ]
    
    logger.info(f"Loaded {len(patients)} patients. {len(patients_with_features)} have SAE features.")
    
    # Encode outcomes
    outcome_vector = []
    patient_ids = []
    
    for patient in patients_with_features:
        # Handle both 'platinum_response' and 'outcome' fields
        outcome = patient.get("platinum_response") or patient.get("outcome")
        if outcome in OUTCOME_ENCODING:
            outcome_vector.append(OUTCOME_ENCODING[outcome])
            patient_ids.append(patient["patient_id"])
        else:
            logger.warning(f"Unknown outcome '{outcome}' for patient {patient['patient_id']}. Skipping.")
    
    logger.info(f"Prepared {len(outcome_vector)} patients with valid outcomes.")
    
    outcome_counts = Counter([p.get("platinum_response") or p.get("outcome") for p in patients_with_features])
    logger.info(f"Outcome distribution: {dict(outcome_counts)}")
    
    return patients_with_features, outcome_vector, patient_ids

def build_feature_matrix(patients: List[Dict]) -> np.ndarray:
    """
    Builds feature matrix from patient SAE features.
    Aggregates top_features from all variants per patient into a 32K-dim vector.
    
    Returns:
        feature_matrix: [n_patients, n_features] numpy array
    """
    SAE_D_HIDDEN = 32768
    feature_lists = []
    
    for patient in patients:
        # Initialize patient-level feature vector (32K dimensions)
        patient_features = np.zeros(SAE_D_HIDDEN)
        
        # Aggregate features from all variants
        variants = patient.get("variants", [])
        for variant in variants:
            top_features = variant.get("top_features", [])
            for feat in top_features:
                idx = feat.get("index")
                val = feat.get("value", 0.0)
                if idx is not None and 0 <= idx < SAE_D_HIDDEN:
                    # Sum feature activations across variants (could also use max/mean)
                    patient_features[idx] += val
        
        # Normalize by number of variants to get mean activation
        if len(variants) > 0:
            patient_features = patient_features / len(variants)
        
        feature_lists.append(patient_features)
        
        if len(feature_lists) % 10 == 0:
            logger.debug(f"Processed {len(feature_lists)}/{len(patients)} patients...")
    
    feature_matrix = np.array(feature_lists)
    logger.info(f"Built feature matrix: {feature_matrix.shape}")
    logger.info(f"Non-zero features per patient (mean): {np.count_nonzero(feature_matrix, axis=1).mean():.1f}")
    
    return feature_matrix

def compute_pearson_correlation(
    feature_matrix: np.ndarray, 
    outcome_vector: List[float]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Pearson correlation between each SAE feature and outcome.
    
    Returns:
        r_values: Pearson correlation coefficients
        p_values: P-values for each correlation
    """
    n_features = feature_matrix.shape[1]
    r_values = np.zeros(n_features)
    p_values = np.ones(n_features)
    
    for i in range(n_features):
        if i % 1000 == 0:
            logger.debug(f"Computing Pearson correlation for feature {i}/{n_features}...")
        
        feature_values = feature_matrix[:, i]
        
        # Skip features with zero variance
        if np.std(feature_values) == 0:
            continue
        
        r, p = stats.pearsonr(feature_values, outcome_vector)
        r_values[i] = r
        p_values[i] = p
    
    logger.info(f"Computed Pearson correlation for {n_features} features.")
    return r_values, p_values

def compute_spearman_correlation(
    feature_matrix: np.ndarray, 
    outcome_vector: List[float]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes Spearman correlation (non-parametric) for robustness.
    
    Returns:
        rho_values: Spearman correlation coefficients
        p_values: P-values for each correlation
    """
    n_features = feature_matrix.shape[1]
    rho_values = np.zeros(n_features)
    p_values = np.ones(n_features)
    
    for i in range(n_features):
        if i % 1000 == 0:
            logger.debug(f"Computing Spearman correlation for feature {i}/{n_features}...")
        
        feature_values = feature_matrix[:, i]
        
        # Skip features with zero variance
        if np.std(feature_values) == 0:
            continue
        
        rho, p = stats.spearmanr(feature_values, outcome_vector)
        rho_values[i] = rho
        p_values[i] = p
    
    logger.info(f"Computed Spearman correlation for {n_features} features.")
    return rho_values, p_values

def compute_chi_square(
    feature_matrix: np.ndarray, 
    outcome_labels: List[str]
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Computes chi-square test for categorical outcome analysis.
    Discretizes features into high/low based on median split.
    
    Returns:
        chi2_values: Chi-square statistics
        p_values: P-values for each test
    """
    n_features = feature_matrix.shape[1]
    chi2_values = np.zeros(n_features)
    p_values = np.ones(n_features)
    
    # Convert outcome labels to categorical codes
    outcome_codes = [
        0 if o == "sensitive" else (1 if o == "resistant" else 2)
        for o in outcome_labels
    ]
    
    for i in range(n_features):
        if i % 1000 == 0:
            logger.debug(f"Computing chi-square for feature {i}/{n_features}...")
        
        feature_values = feature_matrix[:, i]
        
        # Skip zero-variance features
        if np.std(feature_values) == 0:
            continue
        
        # Median split for discretization
        median_val = np.median(feature_values)
        feature_high_low = (feature_values > median_val).astype(int)
        
        # Contingency table: feature (high/low) x outcome (sensitive/resistant/refractory)
        contingency = np.zeros((2, 3))
        for feat_val, outcome_code in zip(feature_high_low, outcome_codes):
            contingency[feat_val, outcome_code] += 1
        
        # Chi-square test (skip if expected frequencies too low)
        try:
            chi2, p, _, expected = stats.chi2_contingency(contingency)
            # Skip if any expected frequency is < 1 (chi-square assumption violation)
            if np.any(expected < 1):
                continue
            chi2_values[i] = chi2
            p_values[i] = p
        except (ValueError, ZeroDivisionError):
            # Skip features that cause chi-square errors
            continue
    
    logger.info(f"Computed chi-square test for {n_features} features.")
    return chi2_values, p_values

def compute_cohen_d(
    feature_matrix: np.ndarray, 
    outcome_labels: List[str]
) -> np.ndarray:
    """
    Computes Cohen's d effect size (sensitive vs refractory).
    
    Returns:
        cohen_d_values: Effect sizes for each feature
    """
    n_features = feature_matrix.shape[1]
    cohen_d_values = np.zeros(n_features)
    
    # Split into sensitive and refractory groups
    sensitive_mask = np.array([o == "sensitive" for o in outcome_labels])
    refractory_mask = np.array([o == "refractory" for o in outcome_labels])
    
    for i in range(n_features):
        if i % 1000 == 0:
            logger.debug(f"Computing Cohen's d for feature {i}/{n_features}...")
        
        feature_values = feature_matrix[:, i]
        
        sensitive_values = feature_values[sensitive_mask]
        refractory_values = feature_values[refractory_mask]
        
        if len(sensitive_values) == 0 or len(refractory_values) == 0:
            continue
        
        # Cohen's d = (mean1 - mean2) / pooled_std
        mean_diff = np.mean(sensitive_values) - np.mean(refractory_values)
        pooled_std = np.sqrt(
            (np.var(sensitive_values) + np.var(refractory_values)) / 2
        )
        
        if pooled_std == 0:
            continue
        
        cohen_d_values[i] = abs(mean_diff / pooled_std)
    
    logger.info(f"Computed Cohen's d for {n_features} features.")
    return cohen_d_values

def compute_cv_stability(
    feature_matrix: np.ndarray,
    outcome_vector: List[float],
    p_value_threshold: float = P_VALUE_THRESHOLD,
    n_folds: int = 5
) -> np.ndarray:
    """
    Computes cross-validation stability: fraction of folds where feature is significant.
    
    Returns:
        stability_scores: [n_features] array of stability scores (0.0-1.0)
    """
    n_features = feature_matrix.shape[1]
    feature_selection_counts = np.zeros(n_features)
    
    kfold = KFold(n_splits=n_folds, shuffle=True, random_state=RANDOM_SEED)
    
    for fold_idx, (train_idx, test_idx) in enumerate(kfold.split(feature_matrix)):
        logger.debug(f"Computing CV stability for fold {fold_idx+1}/{n_folds}...")
        
        X_train = feature_matrix[train_idx]
        y_train = np.array(outcome_vector)[train_idx]
        
        # Compute Pearson correlation on training fold
        for i in range(n_features):
            if np.std(X_train[:, i]) == 0:
                continue
            
            r, p = stats.pearsonr(X_train[:, i], y_train)
            
            if p < p_value_threshold:
                feature_selection_counts[i] += 1
    
    stability_scores = feature_selection_counts / n_folds
    logger.info(f"Computed CV stability for {n_features} features.")
    
    return stability_scores

def compute_bootstrap_ci(
    feature_matrix: np.ndarray,
    outcome_vector: List[float],
    feature_indices: List[int],
    n_iterations: int = BOOTSTRAP_ITERATIONS
) -> Dict[int, Tuple[float, float]]:
    """
    Computes bootstrap confidence intervals for top features.
    
    Returns:
        ci_dict: {feature_index: (lower_95ci, upper_95ci)}
    """
    ci_dict = {}
    n_patients = len(outcome_vector)
    
    for feature_idx in feature_indices:
        logger.debug(f"Computing bootstrap CI for feature {feature_idx}...")
        
        bootstrap_correlations = []
        
        for _ in range(n_iterations):
            # Resample with replacement
            resample_indices = np.random.choice(
                n_patients, size=n_patients, replace=True
            )
            
            resampled_features = feature_matrix[resample_indices, feature_idx]
            resampled_outcomes = np.array(outcome_vector)[resample_indices]
            
            if np.std(resampled_features) == 0:
                bootstrap_correlations.append(0.0)
                continue
            
            r, _ = stats.pearsonr(resampled_features, resampled_outcomes)
            bootstrap_correlations.append(r)
        
        # 95% CI
        lower = np.percentile(bootstrap_correlations, 2.5)
        upper = np.percentile(bootstrap_correlations, 97.5)
        
        ci_dict[feature_idx] = (lower, upper)
    
    logger.info(f"Computed bootstrap CIs for {len(feature_indices)} features.")
    return ci_dict

def apply_multiple_testing_correction(
    p_values: np.ndarray,
    method: str = "fdr_bh"
) -> np.ndarray:
    """
    Applies multiple testing correction.
    
    Args:
        p_values: Array of p-values
        method: "bonferroni" or "fdr_bh" (Benjamini-Hochberg FDR)
    
    Returns:
        corrected_p_values: Adjusted p-values
    """
    from scipy.stats import false_discovery_control
    
    if method == "bonferroni":
        corrected = p_values * len(p_values)
        corrected = np.minimum(corrected, 1.0)  # Cap at 1.0
    elif method == "fdr_bh":
        # Use scipy's false_discovery_control for FDR correction
        corrected = false_discovery_control(p_values, method='bh')
    else:
        raise ValueError(f"Unknown correction method: {method}")
    
    logger.info(f"Applied {method} correction to {len(p_values)} p-values.")
    return corrected

# --- Main Service Class ---
class BiomarkerCorrelationService:
    """Service for computing SAE feature-outcome correlations."""
    
    def __init__(self):
        self.patients = None
        self.feature_matrix = None
        self.outcome_vector = None
        self.outcome_labels = None
        self.patient_ids = None
        
    def load_data(self, cohort_file: Optional[Path] = None):
        """Loads and prepares SAE cohort data."""
        patients, outcome_vector, patient_ids = load_sae_cohort_data(cohort_file)
        
        self.patients = patients
        self.outcome_vector = outcome_vector
        self.patient_ids = patient_ids
        
        # Extract categorical labels for chi-square (handle both 'platinum_response' and 'outcome' fields)
        self.outcome_labels = [p.get("platinum_response") or p.get("outcome") for p in patients]
        
        # Build feature matrix
        self.feature_matrix = build_feature_matrix(patients)
        
        logger.info(f"Data loaded: {len(self.patients)} patients, {self.feature_matrix.shape[1]} features.")
    
    def compute_correlations(self) -> List[FeatureCorrelation]:
        """
        Computes all statistical correlations for SAE features.
        
        Returns:
            List of FeatureCorrelation objects
        """
        if self.feature_matrix is None:
            raise ValueError("Data not loaded. Call load_data() first.")
        
        n_features = self.feature_matrix.shape[1]
        
        logger.info("Computing Pearson correlations...")
        pearson_r, pearson_p = compute_pearson_correlation(
            self.feature_matrix, self.outcome_vector
        )
        
        logger.info("Computing Spearman correlations...")
        spearman_r, spearman_p = compute_spearman_correlation(
            self.feature_matrix, self.outcome_vector
        )
        
        logger.info("Computing chi-square tests...")
        chi2, chi2_p = compute_chi_square(
            self.feature_matrix, self.outcome_labels
        )
        
        logger.info("Computing Cohen's d effect sizes...")
        cohen_d = compute_cohen_d(
            self.feature_matrix, self.outcome_labels
        )
        
        logger.info("Computing cross-validation stability...")
        cv_stability = compute_cv_stability(
            self.feature_matrix, self.outcome_vector
        )
        
        # Apply multiple testing correction to Pearson p-values
        logger.info("Applying FDR correction...")
        pearson_p_corrected = apply_multiple_testing_correction(pearson_p, method="fdr_bh")
        
        # Build FeatureCorrelation objects
        correlations = []
        for i in range(n_features):
            correlations.append(FeatureCorrelation(
                feature_index=i,
                pearson_r=float(pearson_r[i]),
                pearson_p=float(pearson_p_corrected[i]),  # Use corrected p-value
                spearman_r=float(spearman_r[i]),
                spearman_p=float(spearman_p[i]),
                chi_square=float(chi2[i]),
                chi_square_p=float(chi2_p[i]),
                cohen_d=float(cohen_d[i]),
                cv_stability=float(cv_stability[i]),
                bootstrap_ci_lower=0.0,  # Will compute for top features
                bootstrap_ci_upper=0.0
            ))
        
        logger.info(f"Created {len(correlations)} FeatureCorrelation objects.")
        return correlations
    
    def rank_and_filter_features(
        self, 
        correlations: List[FeatureCorrelation]
    ) -> List[FeatureCorrelation]:
        """
        Ranks features by statistical significance and filters.
        
        Ranking criteria:
        1. p < P_VALUE_THRESHOLD
        2. Cohen's d >= EFFECT_SIZE_THRESHOLD
        3. CV stability >= CV_STABILITY_THRESHOLD
        4. Ranked by |Pearson r| descending
        
        Returns:
            Top N features meeting criteria
        """
        # Filter by thresholds
        significant_features = [
            fc for fc in correlations
            if (fc.pearson_p < P_VALUE_THRESHOLD and
                fc.cohen_d >= EFFECT_SIZE_THRESHOLD and
                fc.cv_stability >= CV_STABILITY_THRESHOLD)
        ]
        
        logger.info(f"Found {len(significant_features)}/{len(correlations)} significant features.")
        
        # Rank by absolute Pearson r
        significant_features.sort(key=lambda x: abs(x.pearson_r), reverse=True)
        
        # Assign ranks
        for rank, fc in enumerate(significant_features, 1):
            fc.rank = rank
        
        # Take top N
        top_features = significant_features[:TOP_N_FEATURES]
        
        logger.info(f"Selected top {len(top_features)} features.")
        return top_features
    
    def compute_bootstrap_cis_for_top_features(
        self, 
        top_features: List[FeatureCorrelation]
    ):
        """Computes bootstrap CIs for top features (in-place update)."""
        feature_indices = [fc.feature_index for fc in top_features]
        
        logger.info(f"Computing bootstrap CIs for {len(feature_indices)} top features...")
        ci_dict = compute_bootstrap_ci(
            self.feature_matrix, self.outcome_vector, feature_indices
        )
        
        # Update FeatureCorrelation objects
        for fc in top_features:
            if fc.feature_index in ci_dict:
                fc.bootstrap_ci_lower, fc.bootstrap_ci_upper = ci_dict[fc.feature_index]
        
        logger.info("Bootstrap CIs updated for top features.")
    
    def generate_summary(
        self, 
        top_features: List[FeatureCorrelation]
    ) -> BiomarkerSummary:
        """Generates biomarker summary report."""
        outcome_distribution = Counter(self.outcome_labels)
        
        return BiomarkerSummary(
            top_features=[asdict(fc) for fc in top_features],
            total_features_analyzed=self.feature_matrix.shape[1],
            significant_features_count=len(top_features),
            p_value_threshold=P_VALUE_THRESHOLD,
            effect_size_threshold=EFFECT_SIZE_THRESHOLD,
            cv_stability_threshold=CV_STABILITY_THRESHOLD,
            correction_method="fdr_bh",
            cohort_size=len(self.patients),
            outcome_distribution=dict(outcome_distribution),
            provenance={
                "script": "api/services/biomarker_correlation_service.py",
                "timestamp": datetime.now().isoformat(),
                "random_seed": RANDOM_SEED,
                "bootstrap_iterations": BOOTSTRAP_ITERATIONS,
                "cv_folds": 5,
                "outcome_encoding": OUTCOME_ENCODING,
                "input_file": str(SAE_COHORT_FILE),
                "output_file": str(OUTPUT_FILE)
            }
        )
    
    def run_analysis(self) -> BiomarkerSummary:
        """
        Runs complete biomarker correlation analysis.
        
        Returns:
            BiomarkerSummary object with top features
        """
        logger.info("🚀 Starting SAE biomarker correlation analysis...")
        
        # Step 1: Load data
        self.load_data()
        
        # Step 2: Compute correlations
        correlations = self.compute_correlations()
        
        # Step 3: Rank and filter
        top_features = self.rank_and_filter_features(correlations)
        
        # Step 4: Bootstrap CIs for top features
        self.compute_bootstrap_cis_for_top_features(top_features)
        
        # Step 5: Generate summary
        summary = self.generate_summary(top_features)
        
        logger.info(f"🎉 Analysis complete! Top {len(top_features)} features identified.")
        
        return summary

# --- Standalone Execution ---
def main():
    """Main execution for standalone use."""
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    
    # Set random seed for reproducibility
    np.random.seed(RANDOM_SEED)
    
    # Initialize service
    service = BiomarkerCorrelationService()
    
    # Run analysis
    summary = service.run_analysis()
    
    # Save results
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(asdict(summary), f, indent=2)
    
    logger.info(f"✅ Biomarker analysis saved to {OUTPUT_FILE}")
    
    # Print summary
    print("\n" + "="*80)
    print("⚔️ SAE BIOMARKER CORRELATION SUMMARY")
    print("="*80)
    print(f"Total features analyzed: {summary.total_features_analyzed}")
    print(f"Significant features (p<{summary.p_value_threshold}, d>={summary.effect_size_threshold}, CV>={summary.cv_stability_threshold}): {summary.significant_features_count}")
    print(f"Cohort size: {summary.cohort_size}")
    print(f"Outcome distribution: {summary.outcome_distribution}")
    print(f"\nTop 10 Features:")
    print("-"*80)
    for i, feature in enumerate(summary.top_features[:10], 1):
        print(f"{i}. Feature {feature['feature_index']}: "
              f"r={feature['pearson_r']:.3f} (p={feature['pearson_p']:.2e}), "
              f"d={feature['cohen_d']:.3f}, "
              f"CV={feature['cv_stability']:.2f}")
    print("="*80)

if __name__ == "__main__":
    main()

