"""
Compare Seeding Strategies - Benchmark Quality

Compares different seeding strategies to determine which finds the best trials.
Uses quality validation metrics to rank strategies.

Usage:
    python3 compare_seeding_strategies.py                    # Compare all strategies
    python3 compare_seeding_strategies.py --strategy ovarian # Compare specific strategy
"""
import sys
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from collections import defaultdict
from datetime import datetime
import argparse

# Import validation tool
from validate_trial_quality import assess_trial_quality, get_trials_from_db

project_root = Path(__file__).resolve().parent.parent.parent.parent
db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def analyze_strategy_quality(condition_filter: Optional[str] = None, 
                             status_filter: Optional[str] = None,
                             phase_filter: Optional[str] = None) -> Dict[str, Any]:
    """
    Analyze quality of trials from a specific seeding strategy.
    
    Args:
        condition_filter: Filter by condition (e.g., "ovarian")
        status_filter: Filter by status (e.g., "RECRUITING")
        phase_filter: Filter by phase (e.g., "PHASE2")
    """
    # Get all trials
    all_trials = get_trials_from_db()
    
    # Filter trials
    filtered_trials = []
    for trial in all_trials:
        # Condition filter
        if condition_filter:
            conditions = trial.get("conditions", "[]")
            try:
                conditions_list = json.loads(conditions) if isinstance(conditions, str) else conditions
                if not any(condition_filter.lower() in str(c).lower() for c in conditions_list):
                    continue
            except:
                if condition_filter.lower() not in str(conditions).lower():
                    continue
        
        # Status filter
        if status_filter:
            status = trial.get("status", "").upper()
            if status_filter.upper() not in status:
                continue
        
        # Phase filter
        if phase_filter:
            phases = trial.get("phases", "").upper()
            if phase_filter.upper() not in phases:
                continue
        
        filtered_trials.append(trial)
    
    if len(filtered_trials) == 0:
        return {
            "strategy": f"{condition_filter or 'all'}_{status_filter or 'all'}_{phase_filter or 'all'}",
            "count": 0,
            "mean_score": 0.0,
            "excellent_pct": 0.0,
            "recruiting_pct": 0.0,
        }
    
    # Assess quality
    assessments = [assess_trial_quality(trial) for trial in filtered_trials]
    scores = [a["overall_score"] for a in assessments]
    
    excellent = [a for a in assessments if a["overall_score"] >= 0.9]
    recruiting = [t for t in filtered_trials if "RECRUITING" in t.get("status", "").upper()]
    
    return {
        "strategy": f"{condition_filter or 'all'}_{status_filter or 'all'}_{phase_filter or 'all'}",
        "count": len(filtered_trials),
        "mean_score": sum(scores) / len(scores) if scores else 0.0,
        "excellent_pct": len(excellent) / len(assessments) * 100 if assessments else 0.0,
        "recruiting_pct": len(recruiting) / len(filtered_trials) * 100 if filtered_trials else 0.0,
        "min_score": min(scores) if scores else 0.0,
        "max_score": max(scores) if scores else 0.0,
    }


def compare_all_strategies() -> List[Dict[str, Any]]:
    """Compare all seeding strategies."""
    strategies = [
        {"condition": "ovarian", "status": "RECRUITING", "phase": None},
        {"condition": "ovarian", "status": None, "phase": None},
        {"condition": "breast", "status": "RECRUITING", "phase": None},
        {"condition": "lung", "status": "RECRUITING", "phase": None},
        {"condition": None, "status": "RECRUITING", "phase": "PHASE2"},
        {"condition": None, "status": "RECRUITING", "phase": "PHASE3"},
        {"condition": None, "status": "RECRUITING", "phase": None},
        {"condition": None, "status": None, "phase": None},  # All trials
    ]
    
    results = []
    for strategy in strategies:
        logger.info(f"Analyzing strategy: {strategy}")
        result = analyze_strategy_quality(
            condition_filter=strategy["condition"],
            status_filter=strategy["status"],
            phase_filter=strategy["phase"]
        )
        results.append(result)
    
    # Sort by mean score (descending)
    results.sort(key=lambda x: x["mean_score"], reverse=True)
    
    return results


def print_comparison_report(results: List[Dict[str, Any]]):
    """Print formatted comparison report."""
    print("\n" + "="*80)
    print("📊 SEEDING STRATEGY COMPARISON REPORT")
    print("="*80)
    
    print(f"\n{'Strategy':<40} {'Count':<8} {'Mean Score':<12} {'Excellent %':<12} {'Recruiting %':<12}")
    print("-" * 80)
    
    for result in results:
        strategy = result["strategy"]
        count = result["count"]
        mean_score = result["mean_score"]
        excellent_pct = result["excellent_pct"]
        recruiting_pct = result["recruiting_pct"]
        
        print(f"{strategy:<40} {count:<8} {mean_score:<12.3f} {excellent_pct:<12.1f} {recruiting_pct:<12.1f}")
    
    print("\n" + "="*80)
    print("💡 Key Insights:")
    
    # Best overall quality
    best_quality = max(results, key=lambda x: x["mean_score"])
    print(f"\n✅ Best Quality Strategy: {best_quality['strategy']}")
    print(f"   Mean Score: {best_quality['mean_score']:.3f}")
    print(f"   Excellent Trials: {best_quality['excellent_pct']:.1f}%")
    
    # Best for recruiting
    recruiting_strategies = [r for r in results if r["recruiting_pct"] > 0]
    if recruiting_strategies:
        best_recruiting = max(recruiting_strategies, key=lambda x: x["recruiting_pct"])
        print(f"\n🎯 Best Recruiting Strategy: {best_recruiting['strategy']}")
        print(f"   Recruiting: {best_recruiting['recruiting_pct']:.1f}%")
        print(f"   Mean Score: {best_recruiting['mean_score']:.3f}")
    
    # Recommendations
    print(f"\n📋 Recommendations:")
    
    if best_quality["mean_score"] < 0.7:
        print("   ⚠️  All strategies have mean score <0.7 - consider improving data extraction")
    
    if best_quality["excellent_pct"] < 20:
        print("   ⚠️  <20% excellent trials - need better filtering criteria")
    
    high_quality_strategies = [r for r in results if r["mean_score"] >= 0.75 and r["count"] >= 100]
    if high_quality_strategies:
        print(f"   ✅ {len(high_quality_strategies)} strategies have good quality (≥0.75) with sufficient volume (≥100)")
        print(f"      Focus on: {', '.join([s['strategy'] for s in high_quality_strategies[:3]])}")
    
    print("="*80 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare seeding strategies")
    parser.add_argument("--strategy", type=str, help="Compare specific strategy (e.g., 'ovarian')")
    args = parser.parse_args()
    
    if args.strategy:
        # Single strategy
        result = analyze_strategy_quality(condition_filter=args.strategy)
        print_comparison_report([result])
    else:
        # All strategies
        results = compare_all_strategies()
        print_comparison_report(results)











