#!/usr/bin/env python3
"""
ADC Resistance Prediction Model Training for Yale T-DXd Project

Trains therapy-specific prediction models using:
1. S/P/E scores (Sequence, Pathway, Evidence)
2. Mutation patterns  
3. Expression data (when available)
4. Clinical features

Models:
- Logistic Regression (interpretable, fast)
- XGBoost (higher accuracy, feature importance)

Target: AUROC ≥0.70 (clinically useful)

Output: Trained models + performance metrics + feature importance
"""

import pandas as pd
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Any
from datetime import datetime
import json

# ML libraries
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    roc_auc_score, 
    average_precision_score,
    precision_recall_curve,
    roc_curve,
    classification_report,
    confusion_matrix
)
from sklearn.preprocessing import StandardScaler

# Plotting
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import seaborn as sns

# Paths
DATA_DIR = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/yale_tdzd_project")
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = DATA_DIR / "models"
RESULTS_DIR = DATA_DIR / "results"

MODELS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# Model hyperparameters
LOGISTIC_PARAMS = {
    'max_iter': 1000,
    'random_state': 42,
    'class_weight': 'balanced'
}

XGBOOST_PARAMS = {
    'max_depth': 3,
    'n_estimators': 100,
    'learning_rate': 0.1,
    'random_state': 42,
    'eval_metric': 'logloss'
}


def load_labeled_data() -> pd.DataFrame:
    """Load labeled cohort data"""
    
    cohort_file = PROCESSED_DIR / "brca_adc_resistance_cohort.csv"
    
    if not cohort_file.exists():
        raise FileNotFoundError(f"Labeled data not found: {cohort_file}\nRun label_adc_resistance.py first.")
    
    df = pd.read_csv(cohort_file)
    print(f"✅ Loaded {len(df)} labeled patients")
    print(f"   Studies: {df['study_id'].unique()}")
    
    return df


def prepare_features(df: pd.DataFrame) -> Tuple[pd.DataFrame, List[str]]:
    """
    Prepare feature matrix for model training
    
    Features:
    - Mutation binary flags (TP53, PIK3CA, ERBB2, ESR1, etc.)
    - Mutation counts (total mutations per patient)
    - Resistance scores (from labeling pipeline)
    - Expression features (if available)
    
    Returns: (feature_df, feature_names)
    """
    
    # Mutation features
    mutation_features = [
        'tp53_mut', 'pik3ca_mut', 'erbb2_mut', 'esr1_mut',
        'brca1_mut', 'brca2_mut', 'top1_mut'
    ]
    
    # Score features (from labeling pipeline)
    score_features = [
        'adc_resistance_score',
        'sg_cross_resistance_score',
        'endocrine_sensitivity_score',
        'eribulin_sensitivity_score'
    ]
    
    # Combine
    all_features = mutation_features + score_features
    
    # Create feature matrix
    X = df[all_features].copy()
    
    # Handle missing values (fill with 0 - wild-type/no mutation)
    X = X.fillna(0)
    
    print(f"✅ Prepared {X.shape[1]} features for {X.shape[0]} patients")
    
    return X, all_features


def create_binary_labels(df: pd.DataFrame, target_risk_column: str, high_risk_only: bool = True) -> pd.Series:
    """
    Convert risk labels to binary for classification
    
    Args:
        target_risk_column: e.g., 'adc_resistance_risk', 'sg_cross_resistance_risk'
        high_risk_only: If True, HIGH_RISK=1, all else=0
                       If False, HIGH/MEDIUM=1, LOW=0
    
    Returns: Binary labels (0/1)
    """
    
    if high_risk_only:
        # HIGH_RISK = 1, MEDIUM/LOW = 0
        y = (df[target_risk_column] == 'HIGH_RISK').astype(int)
        positive_label = "HIGH_RISK"
    else:
        # HIGH/MEDIUM = 1, LOW = 0
        y = (df[target_risk_column].isin(['HIGH_RISK', 'MEDIUM_RISK'])).astype(int)
        positive_label = "HIGH_RISK or MEDIUM_RISK"
    
    print(f"\n📊 Label distribution for {target_risk_column}:")
    print(f"   Positive ({positive_label}): {y.sum()} ({y.mean()*100:.1f}%)")
    print(f"   Negative: {len(y) - y.sum()} ({(1-y.mean())*100:.1f}%)")
    
    return y


def train_logistic_model(X_train, y_train, X_test, y_test) -> Tuple[Any, Dict]:
    """
    Train Logistic Regression model
    
    Returns: (trained_model, metrics_dict)
    """
    
    print("\n🔧 Training Logistic Regression...")
    
    # Scale features
    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)
    
    # Train
    model = LogisticRegression(**LOGISTIC_PARAMS)
    model.fit(X_train_scaled, y_train)
    
    # Predict
    y_pred_proba = model.predict_proba(X_test_scaled)[:, 1]
    y_pred = model.predict(X_test_scaled)
    
    # Metrics
    auroc = roc_auc_score(y_test, y_pred_proba)
    auprc = average_precision_score(y_test, y_pred_proba)
    
    print(f"   ✅ AUROC: {auroc:.3f}")
    print(f"   ✅ AUPRC: {auprc:.3f}")
    
    metrics = {
        'model_type': 'LogisticRegression',
        'auroc': auroc,
        'auprc': auprc,
        'predictions': y_pred_proba,
        'true_labels': y_test,
        'scaler': scaler
    }
    
    return model, metrics


def train_xgboost_model(X_train, y_train, X_test, y_test) -> Tuple[Any, Dict]:
    """
    Train XGBoost model (DISABLED - using Logistic only for speed)
    
    Returns: (trained_model, metrics_dict)
    """
    
    print("\n⏭️  Skipping XGBoost (using Logistic only)")
    
    # Return None to skip
    return None, None


def cross_validate_model(X, y, model_type='logistic', n_folds=5) -> Dict:
    """
    Perform k-fold cross-validation
    
    Returns: CV metrics (mean ± std)
    """
    
    print(f"\n🔄 {n_folds}-Fold Cross-Validation ({model_type})...")
    
    if model_type == 'logistic':
        model = LogisticRegression(**LOGISTIC_PARAMS)
        # Need to scale within CV
        X_scaled = StandardScaler().fit_transform(X)
    else:
        model = xgb.XGBClassifier(**XGBOOST_PARAMS)
        X_scaled = X
    
    cv = StratifiedKFold(n_splits=n_folds, shuffle=True, random_state=42)
    
    # Cross-validate AUROC
    auroc_scores = cross_val_score(model, X_scaled, y, cv=cv, scoring='roc_auc')
    
    print(f"   ✅ AUROC: {auroc_scores.mean():.3f} ± {auroc_scores.std():.3f}")
    print(f"   Fold scores: {[f'{s:.3f}' for s in auroc_scores]}")
    
    return {
        'auroc_mean': auroc_scores.mean(),
        'auroc_std': auroc_scores.std(),
        'auroc_folds': auroc_scores.tolist()
    }


def plot_roc_curve(metrics_dict: Dict, target_name: str, output_dir: Path):
    """Plot ROC curve comparing models"""
    
    plt.figure(figsize=(8, 6))
    
    for model_name, metrics in metrics_dict.items():
        fpr, tpr, _ = roc_curve(metrics['true_labels'], metrics['predictions'])
        auroc = metrics['auroc']
        plt.plot(fpr, tpr, label=f"{model_name} (AUROC={auroc:.3f})")
    
    plt.plot([0, 1], [0, 1], 'k--', label='Random')
    plt.xlabel('False Positive Rate')
    plt.ylabel('True Positive Rate')
    plt.title(f'ROC Curve: {target_name}')
    plt.legend()
    plt.grid(alpha=0.3)
    
    output_file = output_dir / f"roc_curve_{target_name.lower().replace(' ', '_')}.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"   📊 Saved ROC curve: {output_file}")


def plot_feature_importance(feature_names: List[str], importance_values: np.ndarray, target_name: str, output_dir: Path):
    """Plot feature importance from XGBoost"""
    
    # Sort by importance
    indices = np.argsort(importance_values)[::-1][:15]  # Top 15
    
    plt.figure(figsize=(10, 6))
    plt.barh(range(len(indices)), importance_values[indices])
    plt.yticks(range(len(indices)), [feature_names[i] for i in indices])
    plt.xlabel('Feature Importance')
    plt.title(f'Top 15 Features: {target_name}')
    plt.gca().invert_yaxis()
    
    output_file = output_dir / f"feature_importance_{target_name.lower().replace(' ', '_')}.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    plt.close()
    
    print(f"   📊 Saved feature importance: {output_file}")


def train_therapy_model(df: pd.DataFrame, target_column: str, target_name: str):
    """
    Train models for a specific therapy prediction task
    
    Args:
        df: Labeled patient data
        target_column: Risk column to predict (e.g., 'adc_resistance_risk')
        target_name: Human-readable name (e.g., 'ADC Resistance')
    """
    
    print(f"\n{'='*80}")
    print(f"TRAINING: {target_name}")
    print(f"{'='*80}")
    
    # Prepare features
    X, feature_names = prepare_features(df)
    
    # Create binary labels
    y = create_binary_labels(df, target_column, high_risk_only=True)
    
    # Check class balance
    if y.sum() < 10:
        print(f"⚠️  Too few positive samples ({y.sum()}), skipping {target_name}")
        return None
    
    # Train/test split
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=0.2, random_state=42, stratify=y
    )
    
    print(f"\n📊 Data split:")
    print(f"   Train: {len(X_train)} samples ({y_train.sum()} positive)")
    print(f"   Test:  {len(X_test)} samples ({y_test.sum()} positive)")
    
    # Train logistic model only (fast)
    logistic_model, logistic_metrics = train_logistic_model(X_train, y_train, X_test, y_test)
    
    # Cross-validation
    cv_logistic = cross_validate_model(X, y, model_type='logistic')
    
    # Plots
    metrics_dict = {
        'Logistic': logistic_metrics
    }
    plot_roc_curve(metrics_dict, target_name, RESULTS_DIR)
    
    # Save models
    import pickle
    model_file = MODELS_DIR / f"{target_name.lower().replace(' ', '_')}_models.pkl"
    with open(model_file, 'wb') as f:
        pickle.dump({
            'logistic_model': logistic_model,
            'scaler': logistic_metrics['scaler'],
            'feature_names': feature_names
        }, f)
    
    print(f"\n💾 Saved models: {model_file}")
    
    # Save metrics
    results = {
        'target_name': target_name,
        'target_column': target_column,
        'n_train': len(X_train),
        'n_test': len(X_test),
        'n_positive': int(y.sum()),
        'logistic': {
            'auroc': float(logistic_metrics['auroc']),
            'auprc': float(logistic_metrics['auprc']),
            'cv_auroc_mean': float(cv_logistic['auroc_mean']),
            'cv_auroc_std': float(cv_logistic['auroc_std'])
        },
        'feature_names': feature_names
    }
    
    results_file = RESULTS_DIR / f"{target_name.lower().replace(' ', '_')}_metrics.json"
    with open(results_file, 'w') as f:
        json.dump(results, f, indent=2)
    
    print(f"💾 Saved metrics: {results_file}")
    
    return results


def generate_summary_report(all_results: List[Dict]):
    """Generate summary report of all models"""
    
    print(f"\n{'='*80}")
    print("📊 SUMMARY REPORT")
    print(f"{'='*80}\n")
    
    summary_data = []
    
    for result in all_results:
        if result is None:
            continue
        
        summary_data.append({
            'Therapy': result['target_name'],
            'Logistic AUROC': f"{result['logistic']['auroc']:.3f}",
            'Logistic CV': f"{result['logistic']['cv_auroc_mean']:.3f} ± {result['logistic']['cv_auroc_std']:.3f}",
            'N Samples': result['n_train'] + result['n_test'],
            'N Positive': result['n_positive']
        })
    
    df_summary = pd.DataFrame(summary_data)
    
    print(df_summary.to_string(index=False))
    
    # Save summary
    summary_file = RESULTS_DIR / "model_performance_summary.csv"
    df_summary.to_csv(summary_file, index=False)
    print(f"\n💾 Saved summary: {summary_file}")
    
    # Check if we hit target
    print(f"\n{'='*80}")
    print("🎯 TARGET CHECK (AUROC ≥ 0.70)")
    print(f"{'='*80}\n")
    
    for result in all_results:
        if result is None:
            continue
        
        best_auroc = result['logistic']['auroc']
        status = "✅ PASS" if best_auroc >= 0.70 else "⚠️  BELOW TARGET" if best_auroc >= 0.60 else "❌ FAIL"
        
        print(f"{result['target_name']}: {best_auroc:.3f} {status}")


def main():
    """Main training pipeline"""
    
    print("=" * 80)
    print("🤖 ADC RESISTANCE MODEL TRAINING PIPELINE")
    print("=" * 80)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Load data
    df = load_labeled_data()
    
    # Train models for each therapy prediction task
    all_results = []
    
    tasks = [
        ('adc_resistance_risk', 'ADC Resistance'),
        ('sg_cross_resistance_risk', 'SG Cross-Resistance'),
        ('endocrine_sensitivity', 'Endocrine Sensitivity'),
        ('eribulin_sensitivity', 'Eribulin Sensitivity')
    ]
    
    for target_column, target_name in tasks:
        result = train_therapy_model(df, target_column, target_name)
        all_results.append(result)
    
    # Generate summary
    generate_summary_report(all_results)
    
    print(f"\n{'='*80}")
    print("✅ TRAINING COMPLETE")
    print(f"{'='*80}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\nNext step: Validate models on external cohort (Yale data)")


if __name__ == "__main__":
    main()

