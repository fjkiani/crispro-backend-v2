"""
Reconnaissance: Query ClinicalTrials.gov API to understand total available ovarian trials

This script queries the API to get exact counts WITHOUT downloading full data:
- Total ovarian trials
- Recruiting ONLY
- Interventional ONLY
- By phase (I, II, III, IV)
- By location (USA breakdown)

Goal: Understand the landscape before extraction
"""
import requests
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_URL = "https://clinicaltrials.gov/api/v2/studies"


def query_count(params: Dict[str, Any]) -> int:
    """Query API and return total count (not studies)"""
    try:
        # Add format and pageSize=1 (we only want count)
        query_params = {**params, "format": "json", "pageSize": 1, "countTotal": "true"}
        
        response = requests.get(API_URL, params=query_params, timeout=30)
        response.raise_for_status()
        data = response.json()
        
        # API v2 returns totalCount in top-level
        total = data.get("totalCount", 0)
        return total
        
    except Exception as e:
        logger.error(f"Query failed: {e}")
        return 0


def reconnaissance():
    """Run complete reconnaissance of ovarian trial landscape"""
    
    print("⚔️ RECONNAISSANCE: OVARIAN CANCER TRIALS ⚔️\n")
    
    # === BASE QUERY ===
    print("📊 BASE QUERY: All ovarian cancer trials")
    base_params = {
        "query.cond": "ovarian cancer"
    }
    total_all = query_count(base_params)
    print(f"   Total ovarian trials: {total_all}\n")
    
    # === RECRUITING ONLY ===
    print("📊 RECRUITING STATUS BREAKDOWN:")
    
    recruiting_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "RECRUITING"
    }
    recruiting = query_count(recruiting_params)
    print(f"   RECRUITING: {recruiting}")
    
    not_yet_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "NOT_YET_RECRUITING"
    }
    not_yet = query_count(not_yet_params)
    print(f"   NOT_YET_RECRUITING: {not_yet}")
    
    active_not_recruiting_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "ACTIVE_NOT_RECRUITING"
    }
    active_not = query_count(active_not_recruiting_params)
    print(f"   ACTIVE_NOT_RECRUITING: {active_not}")
    
    total_recruitable = recruiting + not_yet + active_not
    print(f"   ✅ Total recruitable: {total_recruitable}\n")
    
    # === INTERVENTIONAL ONLY ===
    print("📊 STUDY TYPE BREAKDOWN (Recruiting only):")
    
    interventional_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "RECRUITING",
        "filter.studyType": "INTERVENTIONAL"
    }
    interventional = query_count(interventional_params)
    print(f"   INTERVENTIONAL (treatment trials): {interventional}")
    
    observational_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "RECRUITING",
        "filter.studyType": "OBSERVATIONAL"
    }
    observational = query_count(observational_params)
    print(f"   OBSERVATIONAL (non-treatment): {observational}\n")
    
    # === PHASE BREAKDOWN ===
    print("📊 PHASE BREAKDOWN (Recruiting interventional only):")
    
    phases = ["PHASE1", "PHASE2", "PHASE3", "PHASE4", "NA"]
    phase_counts = {}
    
    for phase in phases:
        phase_params = {
            "query.cond": "ovarian cancer",
            "filter.overallStatus": "RECRUITING",
            "filter.studyType": "INTERVENTIONAL",
            "filter.phase": phase
        }
        count = query_count(phase_params)
        phase_counts[phase] = count
        print(f"   {phase}: {count}")
    
    print()
    
    # === GEOGRAPHIC BREAKDOWN ===
    print("📊 GEOGRAPHIC BREAKDOWN (Recruiting interventional only):")
    
    usa_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "RECRUITING",
        "filter.studyType": "INTERVENTIONAL",
        "filter.geo": "distance(40.785,-73.968,50mi)"  # 50 miles from NYC (approx)
    }
    usa_nyc = query_count(usa_params)
    print(f"   Within 50mi of NYC: {usa_nyc}")
    
    # Try different geo filters
    usa_all_params = {
        "query.cond": "ovarian cancer",
        "filter.overallStatus": "RECRUITING",
        "filter.studyType": "INTERVENTIONAL",
        "query.locn": "United States"
    }
    usa_all = query_count(usa_all_params)
    print(f"   USA locations: {usa_all}")
    
    print()
    
    # === RECOMMENDED EXTRACTION STRATEGY ===
    print("⚔️ RECOMMENDED EXTRACTION STRATEGY:\n")
    
    print(f"✅ PRIMARY TARGET: Recruiting interventional trials = {interventional}")
    print(f"   Phase II-IV priority: {phase_counts.get('PHASE2', 0) + phase_counts.get('PHASE3', 0) + phase_counts.get('PHASE4', 0)}")
    print(f"   USA locations: {usa_all}")
    print(f"   NYC metro (50mi): {usa_nyc}")
    
    print(f"\n📈 EXPECTED YIELD:")
    print(f"   If we extract {interventional} recruiting interventional trials:")
    print(f"   - ~50-70% will have USA sites ({int(interventional * 0.6)} trials)")
    print(f"   - ~10-20% will have NYC metro sites ({int(interventional * 0.15)} trials)")
    print(f"   - After disease/stage/line filtering: ~5-10% ({int(interventional * 0.075)} trials)")
    
    print(f"\n🎯 RECOMMENDATION:")
    if interventional < 100:
        print(f"   ⚠️ LOW VOLUME ({interventional} trials) - Extract ALL recruiting interventional")
        print(f"   Then expand disease keywords if needed")
    elif interventional < 300:
        print(f"   ✅ MODERATE VOLUME ({interventional} trials) - Extract ALL recruiting interventional")
        print(f"   Should yield 10-30 high-quality matches for Ayesha")
    else:
        print(f"   ✅ HIGH VOLUME ({interventional} trials) - Extract in waves:")
        print(f"   Wave 1: Phase II-III recruiting ({phase_counts.get('PHASE2', 0) + phase_counts.get('PHASE3', 0)} trials)")
        print(f"   Wave 2: Phase I and IV if needed")
    
    print(f"\n⚔️ NEXT COMMAND:")
    print(f"   python3 scripts/extract_fresh_ovarian_trials.py --status RECRUITING --type INTERVENTIONAL --limit {interventional}")


if __name__ == "__main__":
    reconnaissance()


