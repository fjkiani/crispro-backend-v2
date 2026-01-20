#!/usr/bin/env python3
"""
⚔️ PRODUCTION - Unified Trial Pipeline

Single command to fetch, dedupe, save, tag, and sync trials.

Usage:
    python run_pipeline.py --disease "ovarian cancer" --count 500 --tag --sync

Flow:
    1. Fetch trials from CT.gov API (disease-specific)
    2. Dedupe against existing SQLite trials
    3. Save new trials to SQLite (correct schema)
    4. Tag for MoA (if --tag flag)
    5. Sync to AstraDB (if --sync flag)
"""

import asyncio
import argparse
import logging
import json
import sqlite3
import sys
import os
from dotenv import load_dotenv
from pathlib import Path
from typing import Dict, List, Any, Optional, Set
from datetime import datetime

# Load environment variables from .env if present
load_dotenv()

# Initialize logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add parent directories to path
# Fix: scripts/trials/production/run_pipeline.py -> scripts/trials/production -> scripts/trials -> scripts -> oncology-backend-minimal
script_dir = Path(__file__).resolve().parent  # scripts/trials/production/
backend_dir = script_dir.parent.parent.parent  # oncology-backend-minimal/
sys.path.insert(0, str(backend_dir))
os.chdir(str(backend_dir))

# Import services
try:
    from api.services.ctgov_query_builder import CTGovQueryBuilder, execute_query
    CTGOV_AVAILABLE = True
except ImportError as e:
    CTGOV_AVAILABLE = False
    logger.warning(f"⚠️ CT.gov query ber not available: {e}")

try:
    from scripts.trials.production.core.tagging_agent import run_tagging_pipeline
    TAGGING_AVAILABLE = True
except ImportError as e:
    TAGGING_AVAILABLE = False
    logger.warning(f"⚠️ Tagging agent not available: {e}")

try:
    from scripts.trials.utilities.seed_astradb_from_sqlite import seed_astradb
    ASTRA_SYNC_AVAILABLE = True
except ImportError as e:
    ASTRA_SYNC_AVAILABLE = False
    logger.warning(f"⚠️ AstraDB sync not available: {e}")




# Database path - Fix: scripts/trials/production/run_pipeline.py -> scripts/trials/production -> scripts/trials -> scripts -> oncology-backend-minimal
SCRIPT_DIR = Path(__file__).resolve().parent  # scripts/trials/production/
BACKEND_ROOT = SCRIPT_DIR.parent.parent.parent  # oncology-backend-minimal/
DB_PATH = BACKEND_ROOT / "data" / "clinical_trials.db"


# --- Capture quality gates (reduce non-therapeutic studies) ---
_NON_THERAPEUTIC_TITLE_PATTERNS = [
    "cryopreservation",
    "fertility",
    "ovarian reserve",
    "quality of life",
    "questionnaire",
    "survey",
    "observational",
    "registry",
    "real-world",
    "biobank",
    "specimen",
    "tissue",
    "imaging",
    "diagnostic",
]


def _trial_is_non_therapeutic_title(title: str) -> bool:
    t = (title or "").lower()
    return any(p in t for p in _NON_THERAPEUTIC_TITLE_PATTERNS)


def _extract_study_type_and_purpose(trial: Dict[str, Any]) -> tuple[str, str]:
    protocol = trial.get("protocolSection", {}) or {}
    design = protocol.get("designModule", {}) or {}
    study_type = (design.get("studyType") or "").upper()

    purpose = ""
    design_info = design.get("designInfo") or {}
    if isinstance(design_info, dict):
        purpose = (design_info.get("primaryPurpose") or "")
    if not purpose:
        purpose = (design.get("primaryPurpose") or "")

    return study_type, (purpose or "").upper()


def _trial_passes_capture_gates(
    trial: Dict[str, Any],
    require_interventional: bool = True,
    require_treatment: bool = True,
    require_intervention: bool = True
) -> bool:
    protocol = trial.get("protocolSection", {}) or {}
    ident = protocol.get("identificationModule", {}) or {}
    title = ident.get("briefTitle") or ""

    if _trial_is_non_therapeutic_title(title):
        return False

    study_type, purpose = _extract_study_type_and_purpose(trial)
    if require_interventional and study_type and study_type != "INTERVENTIONAL":
        return False
    if require_treatment and purpose and purpose != "TREATMENT":
        return False

    if require_intervention:
        arms = protocol.get("armsInterventionsModule", {}) or {}
        interventions = arms.get("interventions") or []
        if not interventions:
            return False

        # Prefer drug-like interventions (avoid behavioral/support studies)
        types = {str(i.get('type', '')).upper() for i in interventions if isinstance(i, dict)}
        if types and not (types.intersection({'DRUG', 'BIOLOGICAL'}) ):
            return False

    return True



def get_existing_nct_ids() -> Set[str]:
    """Get set of existing NCT IDs from SQLite for deduplication."""
    if not DB_PATH.exists():
        logger.warning(f"⚠️ Database not found: {DB_PATH}")
        return set()
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id FROM trials")
        existing_ids = {row['id'] for row in cur.fetchall()}
        conn.close()
        logger.info(f"✅ Found {len(existing_ids)} existing trials in database")
        return existing_ids
    except Exception as e:
        logger.error(f"❌ Failed to get existing NCT IDs: {e}")
        return set()


async def fetch_trials_from_ctgov(
    disease: str,
    count: int,
    filters: Optional[Dict[str, Any]] = None
) -> List[Dict[str, Any]]:
    """
    Fetch trials from CT.gov API.
    
    Args:
        disease: Disease name (e.g., "ovarian cancer")
        count: Number of trials to fetch
        filters: Optional filters (location, phase, status, etc.)
    
    Returns:
        List of trial objects from CT.gov API
    """
    if not CTGOV_AVAILABLE:
        raise RuntimeError("CT.gov query builder not available")
    
    logger.info(f"🔍 Fetching {count} trials for '{disease}' from CT.gov...")
    
    # Build query
    builder = CTGovQueryBuilder()
    builder.add_condition(disease)
    if filters and filters.get("study_type"):
        builder.add_study_type(filters["study_type"])
    
    if filters:
        if filters.get("location"):
            # Note: CTGovQueryBuilder uses add_geo() for location, or add_keyword()
            builder.add_keyword(filters["location"])
        if filters.get("phase"):
            # Note: add_phase expects List[str]
            phase_list = [filters["phase"]] if isinstance(filters["phase"], str) else filters["phase"]
            builder.add_phase(phase_list)
        if filters.get("status"):
            # Note: add_status expects List[str]
            status_list = [filters["status"]] if isinstance(filters["status"], str) else filters["status"]
            builder.add_status(status_list)
    
    # Execute query
    trials = await execute_query(builder, max_results=count * 2)  # Over-fetch for filtering
    
    logger.info(f"✅ Fetched {len(trials)} trials from CT.gov")
    return trials


def normalize_trial_for_sqlite(
    trial: Dict[str, Any],
    disease: str
) -> Dict[str, Any]:
    """
    Normalize CT.gov trial data to SQLite schema.
    
    Schema: id, title, status, phases, conditions, interventions, 
            interventions_json, locations_full_json, inclusion_criteria, etc.
    """
    # Extract from CT.gov API format
    protocol_section = trial.get("protocolSection", {})
    identification = protocol_section.get("identificationModule", {})
    status_module = protocol_section.get("statusModule", {})
    design_module = protocol_section.get("designModule", {})
    eligibility_module = protocol_section.get("eligibilityModule", {})
    contacts_module = protocol_section.get("contactsLocationsModule", {})
    
    nct_id = identification.get("nctId", "")
    
    # Extract conditions
    conditions = []
    if identification.get("briefTitle"):
        conditions.append(identification["briefTitle"])
    if protocol_section.get("conditionsModule", {}).get("conditions"):
        # Handle both string and dict formats
        for c in protocol_section["conditionsModule"]["conditions"]:
            if isinstance(c, dict):
                conditions.append(c.get("name", ""))
            elif isinstance(c, str):
                conditions.append(c)
    
    # Extract interventions
    interventions = []
    interventions_json = []
    if protocol_section.get("armsInterventionsModule", {}).get("interventions"):
        for intervention in protocol_section["armsInterventionsModule"]["interventions"]:
            name = intervention.get("name", "")
            intervention_type = intervention.get("type", "")
            if name:
                interventions.append(name)
                interventions_json.append({
                    "name": name,
                    "type": intervention_type,
                    "description": intervention.get("description", "")
                })
    
    # Extract locations
    locations = []
    if contacts_module.get("locations"):
        for location in contacts_module["locations"]:
            loc_dict = {
                "facility": location.get("facility", ""),
                "city": location.get("city", ""),
                "state": location.get("state", ""),
                "country": location.get("country", ""),
                "status": location.get("status", ""),
                "contact": location.get("contact", {})
            }
            locations.append(loc_dict)
    
    # Extract eligibility
    eligibility_text = ""
    if eligibility_module.get("eligibilityCriteria"):
        eligibility_text = eligibility_module["eligibilityCriteria"]
    
    # Extract phases
    phases = design_module.get("phases", [])
    phase_str = ", ".join(phases) if phases else ""
    
    # Extract status
    overall_status = status_module.get("overallStatus", "UNKNOWN")
    
    return {
        "id": nct_id,
        "nct_id": nct_id,
        "title": identification.get("briefTitle", "Unknown"),
        "status": overall_status,
        "phases": phase_str,
        "conditions": ", ".join(conditions) if conditions else disease,
        "interventions": ", ".join(interventions) if interventions else "",
        "interventions_json": json.dumps(interventions_json) if interventions_json else None,
        "locations_full_json": json.dumps(locations) if locations else None,
        "inclusion_criteria": eligibility_text,
        "summary": protocol_section.get("descriionModule", {}).get("briefSummary", ""),
        "source": "ctgov_api_v2",
        "scraped_data_json": json.dumps(trial),
        "scraped_at": datetime.utcnow().isoformat()
        # Note: last_refreshed_at removed - not in trials table schema
    }


def save_trials_to_sqlite(
    trials: List[Dict[str, Any]],
    existing_ids: Set[str]
) -> tuple[int, int]:
    """
    Save trials to SQLite with deduplication.
    
    Args:
        trials: List of normalized trial dicts
        existing_ids: Set of existing NCT IDs
    
    Returns:
        Tuple of (new_trials_saved, duplicates_skipped)
    """
    if not DB_PATH.exists():
        logger.error(f"❌ Database not found: {DB_PATH}")
        return 0, 0
    
    new_trials = []
    duplicates = 0
    
    for trial in trials:
        nct_id = trial.get("id") or trial.get("nct_id")
        if not nct_id:
            continue
        
        if nct_id in existing_ids:
            duplicates += 1
            continue
        
        new_trials.append(trial)
        existing_ids.add(nct_id)  # Track in-memory for this batch
    
    if not new_trials:
        logger.info(f"✅ No new trials to save ({duplicates} duplicates skipped)")
        return 0, duplicates
    
    try:
        conn = sqlite3.connect(str(DB_PATH))
        cur = conn.cursor()
        
        # Prepare insert statement (match SQLite schema)
        insert_sql = """
            INSERT OR REPLACE INTO trials (
                id, title, status, phases, conditions, interventions,
                interventions_json, locations_full_json, inclusion_criteria,
                summary, source, scraped_data_json, scraped_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        saved = 0
        for trial in new_trials:
            try:
                cur.execute(insert_sql, (
                    trial.get("id"),
                    trial.get("title"),
                    trial.get("status"),
                    trial.get("phases"),
                    trial.get("conditions"),
                    trial.get("interventions"),
                    trial.get("interventions_json"),
                    trial.get("locations_full_json"),
                    trial.get("inclusion_criteria"),
                    trial.get("summary"),
                    trial.get("source"),
                    trial.get("scraped_data_json"),
                    trial.get("scraped_at")
                ))
                saved += 1
            except Exception as e:
                logger.error(f"❌ Failed to save trial {trial.get('id')}: {e}")
        
        conn.commit()
        conn.close()
        
        logger.info(f"✅ Saved {saved} new trials to SQLite ({duplicates} duplicates skipped)")
        return saved, duplicates
        
    except Exception as e:
        logger.error(f"❌ Failed to save trials: {e}", exc_info=True)
        return 0, duplicates


async def tag_new_trials(nct_ids: List[str]) -> int:
    """
    Tag new trials for MoA vectors.
    
    Args:
        nct_ids: List of NCT IDs to tag
    
    Returns:
        Number of trials tagged
    """
    if not TAGGING_AVAILABLE:
        logger.warning("⚠️ Tagging agent not available - skipping")
        return 0
    
    logger.info(f"🏷️ Tagging {len(nct_ids)} trials for MoA vectors...")
    
    try:
        # Run tagging pipeline on new trials
        # Note: tagging_agent expects db_path and can filter by nct_ids
        result = await run_tagging_pipeline(
            db_path=str(DB_PATH),
            existing_vectors_path=str(BACKEND_ROOT / "api" / "resources" / "trial_moa_vectors.json"),
            nct_ids=nct_ids  # Only tag new trials
        )
        
        tagged_count = result.get("tagged_count", 0) if isinstance(result, dict) else 0
        logger.info(f"✅ Tagged {tagged_count} trials for MoA")
        return tagged_count
        
    except Exception as e:
        logger.error(f"❌ Tagging failed: {e}", exc_info=True)
        return 0


async def sync_to_astradb(nct_ids: Optional[List[str]] = None) -> int:
    """
    Sync trials to AstraDB for vector search.
    
    Args:
        nct_ids: Optional list of NCT IDs to sync (if None, syncs all)
    
    Returns:
        Number of trials synced
    """
    if not ASTRA_SYNC_AVAILABLE:
        logger.warning("⚠️ AstraDB sync not available - skipping")
        return 0
    
    logger.info(f"🔄 Syncing trials to AstraDB...")
    
    try:
        # Call AstraDB sync utility
        # Note: seed_astradb function runs async, so we need to await it
        from scripts.trials.utilities.seed_astradb_from_sqlite import seed_astradb
        await seed_astradb(batch_size=50, limit=0)
        
        # Note: seed_astradb doesn't return a count, it logs the count
        # For now, return the number of nct_ids if provided, otherwise 0
        synced_count = len(nct_ids) if nct_ids else 0
        logger.info(f"✅ AstraDB sync completed (check logs for count)")
        return synced_count
        
    except Exception as e:
        logger.error(f"❌ AstraDB sync failed: {e}", exc_info=True)
        return 0


async def run_pipeline(
    disease: str,
    count: int,
    tag: bool = False,
    sync: bool = False,
    filters: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Main pipeline: fetch → dedupe → save → tag → sync
    
    Returns:
        Pipeline results dict
    """
    logger.info(f"🚀 Starting unified pipeline for '{disease}' (count={count}, tag={tag}, sync={sync})")
    
    results = {
        "disease": disease,
        "count_requested": count,
        "fetched": 0,
        "new": 0,
        "duplicates": 0,
        "tagged": 0,
        "synced": 0,
        "errors": []
    }
    
    try:
        # Step 1: Get existing NCT IDs for deduplication
        existing_ids = get_existing_nct_ids()
        
        # Step 2: Fetch trials from CT.gov
        ctgov_trials = await fetch_trials_from_ctgov(disease, count, filters)
        # Capture gates: interventional + treatment + interventions present
        gated = [t for t in ctgov_trials if _trial_passes_capture_gates(t, True, True, True)]
        if gated:
            logger.info(f"✅ Capture gates kept {len(gated)}/{len(ctgov_trials)} trials (filtered {len(ctgov_trials)-len(gated)})")
            ctgov_trials = gated
        results["fetched"] = len(ctgov_trials)
        
        if not ctgov_trials:
            logger.warning("⚠️ No trials fetched from CT.gov")
            return results
        
        # Step 3: Normalize and dedupe
        normalized_trials = [normalize_trial_for_sqlite(t, disease) for t in ctgov_trials]
        new_nct_ids = [t["id"] for t in normalized_trials if t["id"] not in existing_ids]
        
        # Step 4: Save to SQLite
        saved, duplicates = save_trials_to_sqlite(normalized_trials, existing_ids)
        results["new"] = saved
        results["duplicates"] = duplicates
        
        # Step 5: Tag for MoA (if requested)
        if tag and new_nct_ids:
            tagged = await tag_new_trials(new_nct_ids)
            results["tagged"] = tagged
        
        # Step 6: Sync to AstraDB (if requested)
        if sync and new_nct_ids:
            synced = await sync_to_astradb(new_nct_ids)
            results["synced"] = synced
        
        logger.info(f"✅ Pipeline complete: {saved} new, {duplicates} duplicates, {results.get('tagged', 0)} tagged, {results.get('synced', 0)} synced")
        
    except Exception as e:
        logger.error(f"❌ Pipeline failed: {e}", exc_info=True)
        results["errors"].append(str(e))
    
    return results


def main():
    """Command-line entry point."""
    parser = argparse.ArgumentParser(
        description="⚔️ Unified Trial Pipeline: Fetch, Dedupe, Save, Tag, Sync"
    )
    parser.add_argument(
        "--disease",
        type=str,
        required=True,
        help="Disease name (e.g., 'ovarian cancer')"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=100,
        help="Number of trials to fetch (default: 100)"
    )
    parser.add_argument(
        "--tag",
        action="store_true",
        help="Tag new trials for MoA vectors"
    )
    parser.add_argument(
        "--sync",
        action="store_true",
        help="Sync new trials to AstraDB"
    )
    parser.add_argument(
        "--location",
        type=str,
        help="Location filter (e.g., 'NY')"
    )
    parser.add_argument(
        "--phase",
        type=str,
        help="Phase filter (e.g., 'PHASE3')"
    )
    parser.add_argument(
        "--study-type",
        type=str,
        default="INTERVENTIONAL",
        help="CT.gov study type filter (default: INTERVENTIONAL)"
    )

    parser.add_argument(
        "--status",
        type=str,
        default="RECRUITING",
        help="Status filter (default: RECRUITING)"
    )
    
    args = parser.parse_args()
    
    filters = {}
    if args.location:
        filters["location"] = args.location
    if args.phase:
        filters["phase"] = args.phase
    if args.status:
        filters["status"] = args.status
    
    # Run pipeline
    results = asyncio.run(run_pipeline(
        disease=args.disease,
        count=args.count,
        tag=args.tag,
        sync=args.sync,
        filters=filters
    ))
    
    # Print results
    print("\n" + "="*60)
    print("📊 PIPELINE RESULTS")
    print("="*60)
    print(f"Disease: {results['disease']}")
    print(f"Requested: {results['count_requested']}")
    print(f"Fetched: {results['fetched']}")
    print(f"New saved: {results['new']}")
    print(f"Duplicates skipped: {results['duplicates']}")
    if args.tag:
        print(f"Tagged for MoA: {results['tagged']}")
    if args.sync:
        print(f"Synced to AstraDB: {results['synced']}")
    if results['errors']:
        print(f"\n❌ Errors: {results['errors']}")
    print("="*60)
    
    # Exit with error if no new trials
    if results['new'] == 0:
        print("⚠️ No new trials saved")
        sys.exit(1)
    
    print("✅ Pipeline complete!")
    sys.exit(0)


if __name__ == "__main__":
    main()
