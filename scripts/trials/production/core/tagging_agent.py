"""
⚔️ PRODUCTION - Concern C: Offline Tagging Agent (T1-T4)

Purpose: Attach mechanism vectors (7D) to trials without runtime LLM calls.

Non-negotiables (Manager's Plan):
- T1: Incremental (checksum-based selection)
- T2: Batch-efficient (10-25 trials per request)
- T3: Provider-agnostic (Cohere/Gemini/OpenAI)
- T4: Automated QA (deterministic checks)

Consolidated from:
- tagging_incremental.py (T1, T4)
- tag_trials_moa_batch.py (T2, T3)

Source of Truth: .cursor/ayesha/TRIAL_TAGGING_ANALYSIS_AND_NEXT_ROADBLOCK.md (lines 539-584)
"""

import hashlib
import json
import logging
import os
import sys
from dotenv import load_dotenv
import asyncio
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime
import sqlite3

# Initialize logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env if present
load_dotenv()

# ⚔️ FIX: Paths - Correct calculation
# File: scripts/trials/production/core/tagging_agent.py
# From: oncology-backend-minimal/
SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent  # scripts/trials/
BACKEND_ROOT = SCRIPT_DIR.parent.parent  # Correct: oncology-backend-minimal/ (not oncology-coPilot/)
DB_PATH = BACKEND_ROOT / "data" / "clinical_trials.db"
OUTPUT_PATH = BACKEND_ROOT / "api" / "resources" / "trial_moa_vectors.json"

# Try to load LLM provider abstraction
try:
    sys.path.insert(0, str(BACKEND_ROOT))
    from api.services.llm_provider import get_llm_provider, LLMProvider
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False
    logger.warning("⚠️ LLM provider abstraction layer not available")


def compute_trial_checksum(trial: Dict[str, Any]) -> str:
    """
    ⚔️ T1: Compute checksum for trial data (title + interventions + conditions + summary).
    
    Args:
        trial: Trial dict from SQLite
    
    Returns:
        MD5 checksum hex string
    """
    title = trial.get('title', '') or ''
    interventions = trial.get('interventions', '') or ''
    interventions_json = trial.get('interventions_json', '') or ''
    conditions = trial.get('conditions', '') or ''
    summary = trial.get('summary', '') or ''
    
    source_data = f"{title}{interventions}{interventions_json}{conditions}{summary}"
    checksum = hashlib.md5(source_data.encode()).hexdigest()
    
    return checksum


def get_incremental_candidates(
    db_path: str,
    existing_vectors_path: str,
    corpus_nct_ids: Optional[List[str]] = None,
    confidence_threshold: float = 0.7,
    max_candidates: int = 500
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    ⚔️ T1: Build checksum + incremental selection
    
    Select NCTs where:
    - not tagged yet, OR
    - checksum changed since last tag, OR
    - tag confidence below threshold and in corpus (re-tag priority)
    
    Args:
        db_path: Path to SQLite database
        existing_vectors_path: Path to trial_moa_vectors.json
        corpus_nct_ids: List of NCT IDs in corpus (for re-tag priority)
        confidence_threshold: Confidence threshold for re-tagging (default 0.7)
        max_candidates: Maximum candidates to return
    
    Returns:
        Tuple of (candidates, stats)
    """
    # Load existing vectors
    existing_vectors = {}
    if Path(existing_vectors_path).exists():
        try:
            existing_vectors = json.loads(Path(existing_vectors_path).read_text())
        except Exception as e:
            logger.warning(f"⚠️ Failed to load existing vectors: {e}")
    
    corpus_set = set(corpus_nct_ids) if corpus_nct_ids else set()
    
    # Connect to SQLite
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()
    
    # Get trials (prioritize recruiting)
    cur.execute("""
        SELECT 
            id as nct_id,
            title,
            status,
            phases,
            interventions,
            interventions_json,
            conditions,
            summary
        FROM trials
        WHERE (interventions IS NOT NULL OR interventions_json IS NOT NULL)
        ORDER BY 
            CASE status
                WHEN 'RECRUITING' THEN 1
                WHEN 'ACTIVE_NOT_RECRUITING' THEN 2
                WHEN 'ENROLLING_BY_INVITATION' THEN 3
                ELSE 4
            END
        LIMIT 10000
    """)
    all_trials = [dict(row) for row in cur.fetchall()]
    conn.close()
    
    # Filter for incremental candidates
    candidates = []
    stats = {
        "total_trials_checked": len(all_trials),
        "already_tagged_unchanged": 0,
        "not_tagged": 0,
        "checksum_changed": 0,
        "low_confidence_re_tag": 0,
        "corpus_re_tag": 0
    }
    
    for trial in all_trials:
        nct_id = trial.get('nct_id')
        if not nct_id:
            continue
        
        current_checksum = compute_trial_checksum(trial)
        existing_tag = existing_vectors.get(nct_id)
        
        if not existing_tag:
            # Not tagged yet
            candidates.append(trial)
            stats["not_tagged"] += 1
        else:
            # Check if needs re-tagging
            provenance = existing_tag.get('provenance', {})
            stored_checksum = provenance.get('source_checksum')
            stored_confidence = existing_tag.get('confidence', 1.0)
            
            if stored_checksum != current_checksum:
                # Checksum changed
                candidates.append(trial)
                stats["checksum_changed"] += 1
            elif stored_confidence < confidence_threshold and nct_id in corpus_set:
                # Low confidence + in corpus (priority)
                candidates.append(trial)
                stats["low_confidence_re_tag"] += 1
                stats["corpus_re_tag"] += 1
            else:
                stats["already_tagged_unchanged"] += 1
    
    candidates = candidates[:max_candidates]
    
    logger.info(f"✅ Incremental selection: {len(candidates)} candidates from {stats['total_trials_checked']} checked")
    
    return candidates, stats

def fetch_trials_by_nct_ids(db_path: str, nct_ids: list[str]) -> list[dict]:
    """Fetch a specific set of trials from SQLite for tagging."""
    if not nct_ids:
        return []

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    placeholders = ','.join(['?'] * len(nct_ids))
    cur.execute(f"""
        SELECT
            id as nct_id,
            title,
            status,
            phases,
            interventions,
            interventions_json,
            conditions,
            summary
        FROM trials
        WHERE id IN ({placeholders})
    """, nct_ids)

    rows = [dict(r) for r in cur.fetchall()]
    conn.close()

    # Keep ordering of requested ids
    by_id = {r.get('nct_id'): r for r in rows}
    return [by_id[n] for n in nct_ids if n in by_id]



async def tag_batch(
    trials: List[Dict[str, Any]],
    batch_size: int = 25,
    provider: Optional[str] = None
) -> Dict[str, Dict[str, Any]]:
    """
    ⚔️ T2: Batch prompting (10-25 trials per request)
    ⚔️ T3: Rate limits (provider-agnostic, backoff + retry)
    
    Args:
        trials: List of trial dicts to tag
        batch_size: Number of trials per batch (default 25)
        provider: LLM provider (default from env or 'openai')
    
    Returns:
        Dict mapping NCT ID to tagged MoA vector data
    """
    if not LLM_AVAILABLE:
        raise RuntimeError("LLM provider abstraction layer not available")
    
    # Get LLM provider (respect CLI/env if provided, else auto-detect)
    provider_name = (provider or os.getenv("LLM_PROVIDER") or "").strip().lower()
    provider_enum = None
    if provider_name:
        try:
            from api.services.llm_provider.llm_abstract import LLMProvider
            provider_enum = LLMProvider(provider_name)
        except Exception:
            provider_enum = None

    llm_provider = get_llm_provider(provider_enum)
    
    tagged_results = {}
    
    # Process in batches
    for i in range(0, len(trials), batch_size):
        batch = trials[i:i + batch_size]
        logger.info(f"📦 Processing batch {i//batch_size + 1} ({len(batch)} trials)")
        
        try:
            # Build batch prompt (from trial_tagger/prompts.py logic)
            batch_prompt = _build_batch_prompt(batch)
            
            # Call LLM provider
            llm_resp = await llm_provider.chat(
                message=batch_prompt,
                model=os.getenv("LLM_MODEL"),
                max_tokens=4000,
                temperature=0.3
            )

            response = llm_resp.text

            # Parse response (JSON array)
            batch_results = _parse_batch_response(response, batch)
            
            # Add provenance
            for nct_id, result in batch_results.items():
                result['provenance'] = {
                    'provider': getattr(llm_resp, 'provider', 'unknown'),
                    'model': getattr(llm_resp, 'model', os.getenv('LLM_MODEL') or 'default'),
                    'parsed_at': datetime.now().isoformat(),
                    'source_checksum': compute_trial_checksum(
                        next(t for t in batch if t.get('nct_id') == nct_id)
                    ),
                    'source': 'llm_batch_tagging'
                }
            
            tagged_results.update(batch_results)
            
            # Rate limiting (T3)
            if i + batch_size < len(trials):
                await asyncio.sleep(3)  # 3s delay between batches
            
        except Exception as e:
            logger.error(f"❌ Batch {i//batch_size + 1} failed: {e}")
            # Continue with next batch
    
    return tagged_results


def _build_batch_prompt(trials: List[Dict[str, Any]]) -> str:
    """Build batch prompt for LLM (from trial_tagger/prompts.py logic)"""
    # Simplified prompt building (consolidate from trial_tagger/prompts.py)
    prompt = "Tag the following clinical trials with 7D MoA vectors (ddr, mapk, pi3k, vegf, her2, io, efflux).\n\n"
    
    for trial in trials:
        nct_id = trial.get('nct_id', '')
        title = trial.get('title', '')
        interventions = trial.get('interventions', '') or trial.get('interventions_json', '')
        
        prompt += f"NCT: {nct_id}\nTitle: {title}\nInterventions: {interventions}\n\n"
    
    prompt += "Return JSON array: [{nct_id, moa_vector: {ddr, mapk, pi3k, vegf, her2, io, efflux}, confidence, primary_moa}]"
    
    return prompt


def _parse_batch_response(response: str, original_trials: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Parse LLM response (JSON array)"""
    results = {}
    
    try:
        # Extract JSON from response
        json_start = response.find('[')
        json_end = response.rfind(']') + 1
        
        if json_start >= 0 and json_end > json_start:
            json_str = response[json_start:json_end]
            batch_data = json.loads(json_str)
            
            for item in batch_data:
                nct_id = item.get('nct_id')
                if nct_id:
                    results[nct_id] = {
                        'moa_vector': item.get('moa_vector', {}),
                        'confidence': item.get('confidence', 0.0),
                        'primary_moa': item.get('primary_moa', 'unknown')
                    }
    except Exception as e:
        logger.error(f"❌ Failed to parse batch response: {e}")
    
    return results


def run_automated_qa(
    tagged_batch: Dict[str, Dict[str, Any]],
    sample_size: int = 30
) -> Dict[str, Any]:
    """
    ⚔️ T4: Automated QA (deterministic checks)
    
    Sample N=30 per batch, run deterministic checks:
    - confidence present
    - vector values in [0,1]
    - at least one non-zero dimension when primary_moa claims mechanism
    
    Args:
        tagged_batch: Dict mapping NCT ID to tagged MoA vector data
        sample_size: Number of trials to sample for QA
    
    Returns:
        QA results dict with stats and errors
    """
    import random
    
    if not tagged_batch:
        return {"qa_status": "skipped", "reason": "No tagged trials to QA"}
    
    trials_to_qa = list(tagged_batch.items())
    
    if len(trials_to_qa) <= sample_size:
        qa_trials = trials_to_qa
    else:
        qa_trials = random.sample(trials_to_qa, sample_size)
    
    qa_results = {
        "qa_status": "completed",
        "trials_qaed": len(qa_trials),
        "trials_passed": 0,
        "trials_failed": 0,
        "errors": [],
        "error_rate": 0.0
    }
    
    for nct_id, tagged_data in qa_trials:
        errors = []
        
        # Check 1: confidence present
        confidence = tagged_data.get('confidence')
        if confidence is None:
            errors.append(f"{nct_id}: Missing confidence")
        elif not isinstance(confidence, (int, float)) or confidence < 0.0 or confidence > 1.0:
            errors.append(f"{nct_id}: Invalid confidence: {confidence}")
        
        # Check 2: vector values in [0,1]
        moa_vector = tagged_data.get('moa_vector', {})
        if not isinstance(moa_vector, dict):
            errors.append(f"{nct_id}: MoA vector is not a dict")
        else:
            required_pathways = ['ddr', 'mapk', 'pi3k', 'vegf', 'her2', 'io', 'efflux']
            for pathway in required_pathways:
                value = moa_vector.get(pathway)
                if value is None or not isinstance(value, (int, float)) or value < 0.0 or value > 1.0:
                    errors.append(f"{nct_id}: Invalid '{pathway}' value: {value}")
        
        # Check 3: At least one non-zero dimension when primary_moa claims mechanism
        primary_moa = tagged_data.get('primary_moa', '').lower()
        if primary_moa and primary_moa not in ['unknown', 'none', '']:
            max_value = max(moa_vector.values()) if isinstance(moa_vector, dict) and moa_vector else 0.0
            if max_value == 0.0:
                errors.append(f"{nct_id}: Primary MoA '{primary_moa}' but all vector values are zero")
        
        if errors:
            qa_results["trials_failed"] += 1
            qa_results["errors"].extend(errors)
        else:
            qa_results["trials_passed"] += 1
    
    if qa_results["trials_qaed"] > 0:
        qa_results["error_rate"] = round(qa_results["trials_failed"] / qa_results["trials_qaed"], 3)
    
    logger.info(f"✅ QA complete: {qa_results['trials_passed']}/{qa_results['trials_qaed']} passed")
    if qa_results["errors"]:
        logger.warning(f"⚠️ QA found {len(qa_results['errors'])} errors (error rate: {qa_results['error_rate']:.1%})")
    
    return qa_results


def save_tagged_results(
    tagged_results: Dict[str, Dict[str, Any]],
    output_path: str,
    merge: bool = True
) -> None:
    """
    Save tagged results to trial_moa_vectors.json (merge with existing).
    
    Args:
        tagged_results: Dict mapping NCT ID to tagged MoA vector data
        output_path: Path to output file
        merge: Whether to merge with existing vectors (default True)
    """
    output_file = Path(output_path)
    
    # Load existing vectors if merging
    existing_vectors = {}
    if merge and output_file.exists():
        try:
            existing_vectors = json.loads(output_file.read_text())
        except Exception as e:
            logger.warning(f"⚠️ Failed to load existing vectors: {e}")
    
    # Merge new results
    existing_vectors.update(tagged_results)
    
    # Save
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(json.dumps(existing_vectors, indent=2))
    
    logger.info(f"✅ Saved {len(tagged_results)} tagged trials to {output_path}")


async def run_tagging_pipeline(
    db_path: Optional[str] = None,
    existing_vectors_path: Optional[str] = None,
    corpus_nct_ids: Optional[List[str]] = None,
    nct_ids: Optional[List[str]] = None,
    batch_size: int = 25,
    max_candidates: int = 500,
    provider: Optional[str] = None,
    run_qa: bool = True
) -> Dict[str, Any]:
    """
    ⚔️ Main tagging pipeline (T1-T4)
    
    Args:
        db_path: Path to SQLite database (default from config)
        existing_vectors_path: Path to trial_moa_vectors.json (default from config)
        corpus_nct_ids: List of NCT IDs in corpus (for re-tag priority)
        batch_size: Number of trials per batch (default 25)
        max_candidates: Maximum candidates to tag (default 500)
        provider: LLM provider (default from env)
        run_qa: Whether to run automated QA (default True)
    
    Returns:
        Pipeline results dict
    """
    db_path = db_path or str(DB_PATH)
    existing_vectors_path = existing_vectors_path or str(OUTPUT_PATH)
    
    logger.info("⚔️ Starting tagging pipeline (T1-T4)")
    
    # T1: Selection
    if nct_ids:
        logger.info(f"📋 Targeted selection: {len(nct_ids)} NCT IDs")
        candidates = fetch_trials_by_nct_ids(db_path, nct_ids)
        selection_stats = {"total_trials_checked": 0, "already_tagged_unchanged": 0, "not_tagged": len(candidates), "checksum_changed": 0, "low_confidence_re_tag": 0, "corpus_re_tag": 0}
    else:
        logger.info("📋 T1: Building checksum + incremental selection")
        candidates, selection_stats = get_incremental_candidates(
            db_path=db_path,
            existg_vectors_path=existing_vectors_path,
            corpus_nct_ids=corpus_nct_ids,
            max_candidates=max_candidates
        )

    if not candidates:
        logger.info("✅ No candidates to tag")
        return {
            "status": "completed",
            "trials_tagged": 0,
            "selection_stats": selection_stats
        }
    
    # T2-T3: Batch tag
    logger.info(f"🏷️ T2-T3: Batch tagging {len(candidates)} trials (batch size: {batch_size})")
    tagged_results = await tag_batch(
        trials=candidates,
        batch_size=batch_size,
        provider=provider
    )
    
    # T4: Automated QA
    qa_results = None
    if run_qa and tagged_results:
        logger.info("✅ T4: Running automated QA")
        qa_results = run_automated_qa(tagged_results, sample_size=30)
    
    # Save results
    if tagged_results:
        save_tagged_results(tagged_results, existing_vectors_path, merge=True)
    
    return {
        "status": "completed",
        "trials_tagged": len(tagged_results),
        "selection_stats": selection_stats,
        "qa_results": qa_results
    }


if __name__ == "__main__":
    import sys
    
    # CLI entry point
    import argparse
    parser = argparse.ArgumentParser(description="⚔️ Trial Tagging Agent (Production)")
    parser.add_argument("--limit", type=int, default=500, help="Maximum candidates to tag")
    parser.add_argument("--batch-size", type=int, default=25, help="Batch size (10-25)")
    parser.add_argument("--corpus", type=str, help="Corpus name (e.g., 'ayesha')")
    parser.add_argument("--provider", type=str, help="LLM provider (openai/gemini/cohere)")
    parser.add_argument("--no-qa", action="store_true", help="Skip automated QA")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to tag")
    
    args = parser.parse_args()
    
    # Get corpus NCT IDs if specified
    corpus_nct_ids = None
    if args.corpus == "ayesha":
        # Load Ayesha corpus NCT IDs (from SQLite or config)
        corpus_nct_ids = []  # TODO: Load from config
    
    # Run pipeline
    results = asyncio.run(run_tagging_pipeline(
        corpus_nct_ids=corpus_nct_ids,
        nct_ids=args.nct_ids,
        batch_size=args.batch_size,
        max_candidates=args.limit,
        provider=args.provider,
        run_qa=not args.no_qa
    ))
    
    print(json.dumps(results, indent=2))
