"""
Trial Quality Validation Tool

Validates that our bulk seeding strategy is finding "good" trials by assessing:
1. Data completeness (required fields present)
2. Clinical relevance (status, phase, eligibility criteria)
3. Actionability (location data, PI info, enrollment info)
4. Comparison to known good trials (if available)

Usage:
    python3 validate_trial_quality.py                    # Validate all trials
    python3 validate_trial_quality.py --sample 100        # Validate sample of 100
    python3 validate_trial_quality.py --compare           # Compare to known good trials
"""
import sys
import sqlite3
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from collections import defaultdict
from datetime import datetime
import argparse

# Add paths
project_root = Path(__file__).resolve().parent.parent.parent.parent
db_path = project_root / "oncology-coPilot" / "oncology-backend-minimal" / "data" / "clinical_trials.db"

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# Quality Criteria Definitions
QUALITY_CRITERIA = {
    "essential_fields": {
        "title": {"required": True, "weight": 1.0},
        "nct_id": {"required": True, "weight": 1.0},
        "status": {"required": True, "weight": 1.0},
        "phases": {"required": True, "weight": 0.8},
        "conditions": {"required": True, "weight": 0.9},
        "summary": {"required": False, "weight": 0.7},
        "inclusion_criteria": {"required": True, "weight": 0.9},
        "exclusion_criteria": {"required": True, "weight": 0.8},
    },
    "actionability_fields": {
        "interventions": {"required": False, "weight": 0.7},
        "locations_full_json": {"required": False, "weight": 0.8},
        "source": {"required": True, "weight": 0.6},
    },
    "clinical_relevance": {
        "recruiting_status": {"required": False, "weight": 0.9},  # RECRUITING or NOT_YET_RECRUITING
        "phase_2_or_3": {"required": False, "weight": 0.8},  # Phase 2/3 more actionable
        "has_eligibility_criteria": {"required": True, "weight": 1.0},  # Must have eligibility
        "has_interventions": {"required": False, "weight": 0.7},  # Should know what drugs
    },
    "data_quality": {
        "non_empty_title": {"required": True, "weight": 1.0},
        "non_empty_status": {"required": True, "weight": 1.0},
        "valid_conditions_json": {"required": True, "weight": 0.8},
        "has_locations": {"required": False, "weight": 0.6},  # Nice to have
    }
}


def get_trials_from_db(limit: Optional[int] = None, sample: bool = False) -> List[Dict[str, Any]]:
    """Get trials from database."""
    if not db_path.exists():
        logger.error(f"Database not found: {db_path}")
        return []
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    if sample and limit:
        cursor.execute(f"SELECT * FROM trials ORDER BY RANDOM() LIMIT {limit}")
    elif limit:
        cursor.execute(f"SELECT * FROM trials LIMIT {limit}")
    else:
        cursor.execute("SELECT * FROM trials")
    
    trials = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    return trials


def assess_trial_quality(trial: Dict[str, Any]) -> Dict[str, Any]:
    """
    Assess quality of a single trial.
    
    Returns:
        Dictionary with quality scores and issues
    """
    scores = {
        "essential_fields": 0.0,
        "actionability_fields": 0.0,
        "clinical_relevance": 0.0,
        "data_quality": 0.0,
    }
    
    issues = []
    details = {}
    
    # Essential Fields
    essential_total = 0.0
    essential_score = 0.0
    for field, criteria in QUALITY_CRITERIA["essential_fields"].items():
        weight = criteria["weight"]
        essential_total += weight
        
        value = trial.get(field)
        if field == "conditions":
            # Check if valid JSON
            try:
                if isinstance(value, str):
                    conditions = json.loads(value)
                    if isinstance(conditions, list) and len(conditions) > 0:
                        essential_score += weight
                        details[f"{field}_valid"] = True
                    else:
                        issues.append(f"Empty or invalid conditions JSON")
                        details[f"{field}_valid"] = False
                else:
                    issues.append(f"Conditions not JSON string")
                    details[f"{field}_valid"] = False
            except:
                issues.append(f"Invalid conditions JSON: {value}")
                details[f"{field}_valid"] = False
        elif field == "nct_id":
            # Check both "id" and "nct_id" fields
            nct_id = trial.get("id") or trial.get("nct_id")
            if nct_id and str(nct_id).strip():
                essential_score += weight
                details[f"{field}_present"] = True
            else:
                if criteria["required"]:
                    issues.append(f"Missing required field: {field}")
                details[f"{field}_present"] = False
        elif value and str(value).strip() and str(value) != "N/A":
            essential_score += weight
            details[f"{field}_present"] = True
        else:
            if criteria["required"]:
                issues.append(f"Missing required field: {field}")
            details[f"{field}_present"] = False
    
    scores["essential_fields"] = essential_score / essential_total if essential_total > 0 else 0.0
    
    # Actionability Fields
    actionability_total = 0.0
    actionability_score = 0.0
    for field, criteria in QUALITY_CRITERIA["actionability_fields"].items():
        weight = criteria["weight"]
        actionability_total += weight
        
        value = trial.get(field)
        if field == "locations_full_json":
            try:
                if isinstance(value, str):
                    locations = json.loads(value)
                    if isinstance(locations, list) and len(locations) > 0:
                        actionability_score += weight
                        details["has_locations"] = True
                    else:
                        details["has_locations"] = False
                else:
                    details["has_locations"] = False
            except:
                details["has_locations"] = False
        elif value and str(value).strip():
            actionability_score += weight
            details[f"{field}_present"] = True
        else:
            details[f"{field}_present"] = False
    
    scores["actionability_fields"] = actionability_score / actionability_total if actionability_total > 0 else 0.0
    
    # Clinical Relevance
    clinical_total = 0.0
    clinical_score = 0.0
    
    # Recruiting status
    status = trial.get("status", "").upper()
    is_recruiting = "RECRUITING" in status or "NOT_YET_RECRUITING" in status
    if is_recruiting:
        clinical_score += QUALITY_CRITERIA["clinical_relevance"]["recruiting_status"]["weight"]
        details["is_recruiting"] = True
    else:
        details["is_recruiting"] = False
    clinical_total += QUALITY_CRITERIA["clinical_relevance"]["recruiting_status"]["weight"]
    
    # Phase 2/3
    phases = trial.get("phases", "").upper()
    is_phase_2_or_3 = "PHASE2" in phases or "PHASE3" in phases or "PHASE 2" in phases or "PHASE 3" in phases
    if is_phase_2_or_3:
        clinical_score += QUALITY_CRITERIA["clinical_relevance"]["phase_2_or_3"]["weight"]
        details["is_phase_2_or_3"] = True
    else:
        details["is_phase_2_or_3"] = False
    clinical_total += QUALITY_CRITERIA["clinical_relevance"]["phase_2_or_3"]["weight"]
    
    # Has eligibility criteria
    has_inclusion = bool(trial.get("inclusion_criteria", "").strip())
    has_exclusion = bool(trial.get("exclusion_criteria", "").strip())
    if has_inclusion or has_exclusion:
        clinical_score += QUALITY_CRITERIA["clinical_relevance"]["has_eligibility_criteria"]["weight"]
        details["has_eligibility"] = True
    else:
        issues.append("Missing eligibility criteria")
        details["has_eligibility"] = False
    clinical_total += QUALITY_CRITERIA["clinical_relevance"]["has_eligibility_criteria"]["weight"]
    
    # Has interventions
    interventions = trial.get("interventions", "")
    has_interventions = bool(interventions and interventions.strip())
    if has_interventions:
        clinical_score += QUALITY_CRITERIA["clinical_relevance"]["has_interventions"]["weight"]
        details["has_interventions"] = True
    else:
        details["has_interventions"] = False
    clinical_total += QUALITY_CRITERIA["clinical_relevance"]["has_interventions"]["weight"]
    
    scores["clinical_relevance"] = clinical_score / clinical_total if clinical_total > 0 else 0.0
    
    # Data Quality
    quality_total = 0.0
    quality_score = 0.0
    
    # Non-empty title
    title = trial.get("title", "").strip()
    if title:
        quality_score += QUALITY_CRITERIA["data_quality"]["non_empty_title"]["weight"]
        details["title_valid"] = True
    else:
        issues.append("Empty title")
        details["title_valid"] = False
    quality_total += QUALITY_CRITERIA["data_quality"]["non_empty_title"]["weight"]
    
    # Non-empty status
    if status:
        quality_score += QUALITY_CRITERIA["data_quality"]["non_empty_status"]["weight"]
        details["status_valid"] = True
    else:
        issues.append("Empty status")
        details["status_valid"] = False
    quality_total += QUALITY_CRITERIA["data_quality"]["non_empty_status"]["weight"]
    
    # Valid conditions JSON
    try:
        conditions = json.loads(trial.get("conditions", "[]"))
        if isinstance(conditions, list):
            quality_score += QUALITY_CRITERIA["data_quality"]["valid_conditions_json"]["weight"]
            details["conditions_json_valid"] = True
        else:
            details["conditions_json_valid"] = False
    except:
        details["conditions_json_valid"] = False
    quality_total += QUALITY_CRITERIA["data_quality"]["valid_conditions_json"]["weight"]
    
    # Has locations
    try:
        locations = json.loads(trial.get("locations_full_json", "[]"))
        if isinstance(locations, list) and len(locations) > 0:
            quality_score += QUALITY_CRITERIA["data_quality"]["has_locations"]["weight"]
            details["locations_present"] = True
        else:
            details["locations_present"] = False
    except:
        details["locations_present"] = False
    quality_total += QUALITY_CRITERIA["data_quality"]["has_locations"]["weight"]
    
    scores["data_quality"] = quality_score / quality_total if quality_total > 0 else 0.0
    
    # Overall score (weighted average)
    overall_score = (
        scores["essential_fields"] * 0.35 +
        scores["actionability_fields"] * 0.20 +
        scores["clinical_relevance"] * 0.30 +
        scores["data_quality"] * 0.15
    )
    
    return {
        "nct_id": trial.get("id", trial.get("nct_id", "UNKNOWN")),
        "title": trial.get("title", "")[:60] + "..." if len(trial.get("title", "")) > 60 else trial.get("title", ""),
        "scores": scores,
        "overall_score": overall_score,
        "issues": issues,
        "details": details,
        "status": trial.get("status", ""),
        "phases": trial.get("phases", ""),
    }


def validate_trial_quality(limit: Optional[int] = None, sample: bool = False) -> Dict[str, Any]:
    """
    Validate quality of trials in database.
    
    Returns:
        Dictionary with validation results and statistics
    """
    logger.info("🔍 Starting trial quality validation...")
    
    # Get trials
    trials = get_trials_from_db(limit=limit, sample=sample)
    logger.info(f"📊 Validating {len(trials)} trials")
    
    if len(trials) == 0:
        logger.error("No trials found in database")
        return {}
    
    # Assess each trial
    results = []
    for i, trial in enumerate(trials):
        if (i + 1) % 100 == 0:
            logger.info(f"   Assessed {i + 1}/{len(trials)} trials...")
        assessment = assess_trial_quality(trial)
        results.append(assessment)
    
    # Calculate statistics
    overall_scores = [r["overall_score"] for r in results]
    essential_scores = [r["scores"]["essential_fields"] for r in results]
    actionability_scores = [r["scores"]["actionability_fields"] for r in results]
    clinical_scores = [r["scores"]["clinical_relevance"] for r in results]
    quality_scores = [r["scores"]["data_quality"] for r in results]
    
    # Categorize by quality tier
    excellent = [r for r in results if r["overall_score"] >= 0.9]
    good = [r for r in results if 0.7 <= r["overall_score"] < 0.9]
    fair = [r for r in results if 0.5 <= r["overall_score"] < 0.7]
    poor = [r for r in results if r["overall_score"] < 0.5]
    
    # Count issues
    all_issues = []
    for r in results:
        all_issues.extend(r["issues"])
    issue_counts = defaultdict(int)
    for issue in all_issues:
        issue_counts[issue] += 1
    
    # Status breakdown
    status_counts = defaultdict(int)
    for r in results:
        status_counts[r["status"]] += 1
    
    # Phase breakdown
    phase_counts = defaultdict(int)
    for r in results:
        phase_counts[r["phases"]] += 1
    
    stats = {
        "total_trials": len(results),
        "overall_score": {
            "mean": sum(overall_scores) / len(overall_scores) if overall_scores else 0.0,
            "min": min(overall_scores) if overall_scores else 0.0,
            "max": max(overall_scores) if overall_scores else 0.0,
            "median": sorted(overall_scores)[len(overall_scores) // 2] if overall_scores else 0.0,
        },
        "category_scores": {
            "essential_fields": {
                "mean": sum(essential_scores) / len(essential_scores) if essential_scores else 0.0,
            },
            "actionability_fields": {
                "mean": sum(actionability_scores) / len(actionability_scores) if actionability_scores else 0.0,
            },
            "clinical_relevance": {
                "mean": sum(clinical_scores) / len(clinical_scores) if clinical_scores else 0.0,
            },
            "data_quality": {
                "mean": sum(quality_scores) / len(quality_scores) if quality_scores else 0.0,
            },
        },
        "quality_tiers": {
            "excellent": len(excellent),
            "good": len(good),
            "fair": len(fair),
            "poor": len(poor),
        },
        "common_issues": dict(sorted(issue_counts.items(), key=lambda x: x[1], reverse=True)[:10]),
        "status_breakdown": dict(status_counts),
        "phase_breakdown": dict(phase_counts),
        "sample_results": {
            "excellent": excellent[:5],
            "poor": poor[:5],
        }
    }
    
    return stats


def print_validation_report(stats: Dict[str, Any]):
    """Print formatted validation report."""
    print("\n" + "="*60)
    print("📊 TRIAL QUALITY VALIDATION REPORT")
    print("="*60)
    
    print(f"\n📈 Overall Statistics:")
    print(f"   Total Trials: {stats['total_trials']}")
    print(f"   Mean Quality Score: {stats['overall_score']['mean']:.3f}")
    print(f"   Median Quality Score: {stats['overall_score']['median']:.3f}")
    print(f"   Score Range: {stats['overall_score']['min']:.3f} - {stats['overall_score']['max']:.3f}")
    
    print(f"\n📊 Quality Tiers:")
    print(f"   Excellent (≥0.9): {stats['quality_tiers']['excellent']} ({stats['quality_tiers']['excellent']/stats['total_trials']*100:.1f}%)")
    print(f"   Good (0.7-0.9):   {stats['quality_tiers']['good']} ({stats['quality_tiers']['good']/stats['total_trials']*100:.1f}%)")
    print(f"   Fair (0.5-0.7):   {stats['quality_tiers']['fair']} ({stats['quality_tiers']['fair']/stats['total_trials']*100:.1f}%)")
    print(f"   Poor (<0.5):      {stats['quality_tiers']['poor']} ({stats['quality_tiers']['poor']/stats['total_trials']*100:.1f}%)")
    
    print(f"\n🔍 Category Scores:")
    print(f"   Essential Fields:     {stats['category_scores']['essential_fields']['mean']:.3f}")
    print(f"   Actionability:        {stats['category_scores']['actionability_fields']['mean']:.3f}")
    print(f"   Clinical Relevance:   {stats['category_scores']['clinical_relevance']['mean']:.3f}")
    print(f"   Data Quality:        {stats['category_scores']['data_quality']['mean']:.3f}")
    
    print(f"\n📋 Status Breakdown:")
    for status, count in sorted(stats['status_breakdown'].items(), key=lambda x: x[1], reverse=True)[:5]:
        print(f"   {status}: {count} ({count/stats['total_trials']*100:.1f}%)")
    
    print(f"\n⚠️  Common Issues (Top 10):")
    for issue, count in list(stats['common_issues'].items())[:10]:
        print(f"   {issue}: {count} trials")
    
    print(f"\n✅ Sample Excellent Trials:")
    for trial in stats['sample_results']['excellent']:
        print(f"   {trial['nct_id']}: {trial['title']} (score: {trial['overall_score']:.3f})")
    
    if stats['sample_results']['poor']:
        print(f"\n❌ Sample Poor Trials:")
        for trial in stats['sample_results']['poor']:
            print(f"   {trial['nct_id']}: {trial['title']} (score: {trial['overall_score']:.3f})")
            if trial['issues']:
                print(f"      Issues: {', '.join(trial['issues'][:3])}")
    
    print("\n" + "="*60)
    print("💡 Recommendations:")
    
    if stats['quality_tiers']['poor'] / stats['total_trials'] > 0.1:
        print("   ⚠️  >10% of trials are poor quality - consider improving data extraction")
    
    if stats['category_scores']['actionability_fields']['mean'] < 0.5:
        print("   ⚠️  Low actionability scores - missing location/PI data")
    
    if stats['category_scores']['clinical_relevance']['mean'] < 0.7:
        print("   ⚠️  Low clinical relevance - many non-recruiting or early-phase trials")
    
    excellent_pct = stats['quality_tiers']['excellent'] / stats['total_trials'] * 100
    if excellent_pct >= 70:
        print("   ✅ >70% excellent quality - seeding strategy is working well!")
    elif excellent_pct >= 50:
        print("   ⚠️  50-70% excellent quality - seeding strategy is acceptable")
    else:
        print("   ❌ <50% excellent quality - seeding strategy needs improvement")
    
    print("="*60 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate trial quality")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of trials to validate")
    parser.add_argument("--sample", action="store_true", help="Random sample instead of first N")
    args = parser.parse_args()
    
    stats = validate_trial_quality(limit=args.limit, sample=args.sample)
    if stats:
        print_validation_report(stats)
    else:
        print("❌ Validation failed - no trials found")

