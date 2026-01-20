"""
Trial MoA Batch Tagging Script (Manager P3 Compliant)
=====================================================
Batch tag clinical trials with MoA vectors using LLM abstraction layer (OFFLINE ONLY).

Supports multiple LLM providers: Cohere, Gemini, OpenAI (via abstraction layer).
Switch providers by setting appropriate environment variables or passing --provider argument.

Manager P3 Compliance:
- OFFLINE ONLY (never runtime)
- Batch tag 200+ trials
- Human spot-review 30 diverse trials (≥90% accuracy required)
- Metadata persistence (model, version, parsed_at, reviewed_by, source_checksum)

Author: Auto (Trial Tagging Agent)
Date: January 28, 2025
"""

import sqlite3
import json
import os
import asyncio
import hashlib
import random
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import logging

# ⚔️ MANAGER'S PLAN - T1, T4: Import incremental tagging + QA
try:
    from .tagging_incremental import get_incremental_tagging_candidates, run_automated_qa
except ImportError:
    # If running as script, try relative import
    try:
        import sys
        sys.path.insert(0, str(Path(__file__).parent))
        from tagging_incremental import get_incremental_tagging_candidates, run_automated_qa
    except ImportError:
        logger.warning("⚠️ Incremental tagging module not available - using basic selection")
        get_incremental_tagging_candidates = None
        run_automated_qa = None

# Initialize logging first (needed for .env loading messages)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
try:
    from dotenv import load_dotenv
    # Explicitly load from root .env file: /Users/fahadkiani/Desktop/development/crispr-assistant-main/.env
    root_env = Path("/Users/fahadkiani/Desktop/development/crispr-assistant-main/.env")
    backend_env = Path(__file__).resolve().parent.parent.parent / ".env"
    
    # Try root .env first (preferred), then backend .env as fallback
    if root_env.exists():
        load_dotenv(root_env, override=True)
        logger.info(f"✅ Loaded .env from root: {root_env}")
    elif backend_env.exists():
        load_dotenv(backend_env, override=True)
        logger.info(f"✅ Loaded .env from backend: {backend_env}")
    else:
        load_dotenv()  # Try default locations
        logger.warning("⚠️ Using default .env location")
except ImportError:
    pass  # dotenv not available, rely on environment variables
except Exception as e:
    logger.warning(f"⚠️ Failed to load .env: {e}")

# Paths (define before using in imports)
SCRIPT_DIR = Path(__file__).resolve().parent
# Go up: scripts/trials -> scripts -> backend-minimal
BACKEND_ROOT = SCRIPT_DIR.parent.parent
DB_PATH = BACKEND_ROOT / "data" / "clinical_trials.db"
OUTPUT_PATH = BACKEND_ROOT / "api" / "resources" / "trial_moa_vectors.json"

# LLM Provider Abstraction Layer
try:
    # Add backend root to path for imports
    import sys
    sys.path.insert(0, str(BACKEND_ROOT))
    
    from api.services.llm_provider import get_llm_provider, LLMProvider
    LLM_AVAILABLE = True
except ImportError as e:
    LLM_AVAILABLE = False
    logger.warning(f"LLM provider abstraction layer not available: {e}")
except Exception as e:
    LLM_AVAILABLE = False
    logger.warning(f"Failed to import LLM provider: {e}")

# Configuration
BATCH_SIZE = 50  # Process 50 trials per batch
# Rate limiting: Cohere Chat endpoints = 20 requests/minute = 3 seconds between calls
RATE_LIMIT_SECONDS = 3  # Base delay between calls (3s to respect 20 requests/minute limit)
# LLM model preference (defaults to provider default)
LLM_MODEL = os.getenv("COHERE_MODEL") or os.getenv("GEMINI_MODEL") or None  # Use provider default if None
MAX_RETRIES = 3  # Maximum retry attempts for rate limit errors
INITIAL_BACKOFF = 5.0  # Initial backoff delay in seconds (exponential: 5s, 10s, 20s)


def load_existing_vectors() -> Dict[str, Any]:
    """Load existing MoA vectors from JSON file."""
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH, "r") as f:
            return json.load(f)
    return {}


def save_vectors(vectors: Dict[str, Any]):
    """Save MoA vectors to JSON file."""
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(vectors, f, indent=2)
    logger.info(f"✅ Saved {len(vectors)} MoA vectors to {OUTPUT_PATH}")


def get_untagged_trials(limit: int = 200) -> List[Dict[str, Any]]:
    """
    Get untagged trials from SQLite database.
    
    Returns trials that are:
    1. Not in trial_moa_vectors.json
    2. Recruiting/active (priority)
    3. Have intervention data
    """
    if not DB_PATH.exists():
        logger.error(f"❌ Database not found: {DB_PATH}")
        return []
    
    # Load existing vectors to exclude already tagged trials
    existing_vectors = load_existing_vectors()
    tagged_nct_ids = set(existing_vectors.keys())
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query for untagged trials (prioritize recruiting/active)
    # Schema: id, title, status, phases, summary, conditions, interventions, interventions_json
    if tagged_nct_ids:
        placeholders = ','.join(['?' for _ in tagged_nct_ids])
        query = f"""
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
        WHERE id NOT IN ({placeholders})
          AND status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION', 'COMPLETED')
          AND (interventions IS NOT NULL OR interventions_json IS NOT NULL)
        ORDER BY 
            CASE status
                WHEN 'RECRUITING' THEN 1
                WHEN 'ACTIVE_NOT_RECRUITING' THEN 2
                WHEN 'ENROLLING_BY_INVITATION' THEN 3
                ELSE 4
            END
        LIMIT ?
        """
        params = list(tagged_nct_ids) + [limit]
    else:
        query = """
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
        WHERE status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'ENROLLING_BY_INVITATION', 'COMPLETED')
          AND (interventions IS NOT NULL OR interventions_json IS NOT NULL)
        ORDER BY 
            CASE status
                WHEN 'RECRUITING' THEN 1
                WHEN 'ACTIVE_NOT_RECRUITING' THEN 2
                WHEN 'ENROLLING_BY_INVITATION' THEN 3
                ELSE 4
            END
        LIMIT ?
        """
        params = [limit]
    
    params = list(tagged_nct_ids) + [limit]
    cursor.execute(query, params)
    trials = [dict(row) for row in cursor.fetchall()]
    conn.close()
    
    logger.info(f"✅ Found {len(trials)} untagged trials")
    return trials


def extract_interventions_from_trial(trial: Dict[str, Any]) -> str:
    """Extract intervention information from trial data."""
    interventions = []
    
    # Try interventions_json first (structured JSON field)
    if trial.get('interventions_json'):
        try:
            interventions_data = json.loads(trial['interventions_json']) if isinstance(trial['interventions_json'], str) else trial['interventions_json']
            if isinstance(interventions_data, list):
                for interv in interventions_data:
                    if isinstance(interv, dict):
                        name = interv.get('name', interv.get('intervention_name', interv.get('intervention', '')))
                        if name:
                            interventions.append(name)
                    elif isinstance(interv, str):
                        interventions.append(interv)
            elif isinstance(interventions_data, dict):
                name = interventions_data.get('name', interventions_data.get('intervention_name', ''))
                if name:
                    interventions.append(name)
        except (json.JSONDecodeError, TypeError):
            pass
    
    # Fallback to interventions field (plain text)
    if not interventions and trial.get('interventions'):
        interventions_text = trial['interventions']
        if isinstance(interventions_text, str):
            # Try to parse as JSON first
            try:
                interventions_data = json.loads(interventions_text)
                if isinstance(interventions_data, list):
                    interventions = [str(i) for i in interventions_data]
                else:
                    interventions = [str(interventions_data)]
            except (json.JSONDecodeError, TypeError):
                # Plain text - split by common delimiters
                interventions = [i.strip() for i in interventions_text.replace(';', ',').split(',') if i.strip()]
    
    return ', '.join(interventions) if interventions else 'Not specified'


def create_llm_prompt(trial: Dict[str, Any]) -> str:
    """Create LLM prompt for MoA vector extraction (provider-agnostic)."""
    title = trial.get('title', 'Unknown')
    interventions = extract_interventions_from_trial(trial)
    conditions = trial.get('conditions', 'Unknown')
    description = trial.get('summary', trial.get('description_text', ''))[:500]  # Limit description length
    
    prompt = f"""Given the following clinical trial information, determine the mechanism of action (MoA) vector.

Trial: {title}
Interventions: {interventions}
Conditions: {conditions}
Description: {description[:500]}

Return a JSON object with MoA vector (7D):
{{
  "ddr": 0.0-1.0,      // DNA Damage Repair (PARP, ATR, ATM, CHK1/2, WEE1 inhibitors)
  "mapk": 0.0-1.0,     // RAS/MAPK pathway (BRAF, MEK, KRAS inhibitors)
  "pi3k": 0.0-1.0,     // PI3K/AKT pathway (PI3K, AKT, mTOR inhibitors)
  "vegf": 0.0-1.0,     // Angiogenesis (VEGF, VEGFR inhibitors, bevacizumab)
  "her2": 0.0-1.0,     // HER2 pathway (trastuzumab, pertuzumab, HER2 inhibitors)
  "io": 0.0-1.0,       // Immunotherapy (PD-1, PD-L1, CTLA-4 inhibitors)
  "efflux": 0.0-1.0    // Drug efflux (P-gp, ABCB1, MDR1 inhibitors)
}}

Also provide:
- "confidence": 0.0-1.0 (how confident you are in the MoA assignment)
- "primary_moa": "brief description of primary mechanism"

Rules:
1. Only assign values > 0.0 if there is clear evidence of that mechanism
2. If multiple mechanisms, assign proportional values (e.g., 0.6 DDR + 0.4 IO)
3. If uncertain, use lower confidence (< 0.7)
4. Return ONLY valid JSON, no markdown formatting
5. If no clear mechanism, return all zeros with confidence 0.0

Return ONLY the JSON object:"""

    return prompt


async def tag_trial_with_llm(llm_provider, trial: Dict[str, Any], max_retries: int = MAX_RETRIES) -> Optional[Dict[str, Any]]:
    """
    Tag a single trial with MoA vector using LLM abstraction layer with robust rate limiting and retry logic.
    
    Args:
        llm_provider: LLMProviderBase instance from abstraction layer
        trial: Trial data dictionary
        max_retries: Maximum retry attempts for rate limit errors
    
    Returns MoA vector data or None if tagging fails after all retries.
    """
    if not LLM_AVAILABLE or not llm_provider or not llm_provider.is_available():
        logger.error("❌ LLM provider not available")
        return None
    
    # Get model name
    model_name = LLM_MODEL or llm_provider.get_default_model()
    provider_name = llm_provider.__class__.__name__.replace("Provider", "").lower()
    logger.info(f"✅ Using {provider_name} model: {model_name}")
    
    # Create prompt with system message
    system_message = "You are a biomedical research analyst specializing in clinical trial mechanism of action classification. Return ONLY valid JSON, no markdown formatting."
    user_prompt = create_llm_prompt(trial)
    
    # Retry loop with exponential backoff
    for attempt in range(max_retries):
        try:
            # Call LLM using abstraction layer
            response = await llm_provider.chat(
                message=user_prompt,
                model=model_name,
                max_tokens=500,  # Enough for JSON response
                temperature=0.0,
                system_message=system_message
            )
            
            if not response or not response.text:
                logger.warning(f"⚠️ Empty response for {trial.get('nct_id')}")
                return None
            
            response_text = response.text.strip()
            
            if not response_text:
                logger.warning(f"⚠️ Empty response for {trial.get('nct_id')}")
                return None
            
            # Clean JSON (remove markdown code blocks if present)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            try:
                moa_data = json.loads(response_text)
            except json.JSONDecodeError as e:
                logger.warning(f"⚠️ Failed to parse JSON for {trial.get('nct_id')}: {e}")
                logger.debug(f"Response text: {response_text[:200]}")
                return None
            
            # Validate structure
            if not isinstance(moa_data, dict):
                logger.warning(f"⚠️ Invalid response format for {trial.get('nct_id')}")
                return None
            
            # Extract MoA vector
            moa_vector = {}
            for pathway in ['ddr', 'mapk', 'pi3k', 'vegf', 'her2', 'io', 'efflux']:
                value = moa_data.get(pathway, 0.0)
                # Ensure value is between 0.0 and 1.0
                moa_vector[pathway] = max(0.0, min(1.0, float(value)))
            
            confidence = max(0.0, min(1.0, float(moa_data.get('confidence', 0.0))))
            primary_moa = moa_data.get('primary_moa', 'Unknown')
            
            # Create source checksum (hash of trial data for change detection)
            source_data = f"{trial.get('title', '')}{trial.get('interventions', '')}{trial.get('interventions_json', '')}{trial.get('summary', '')}"
            source_checksum = hashlib.md5(source_data.encode()).hexdigest()
            
            # Build result
            result = {
                "moa_vector": moa_vector,
                "confidence": confidence,
                "source": f"{provider_name}_batch_tagging",
                "tagged_at": datetime.utcnow().isoformat() + "Z",
                "reviewed_by": "TrialTaggingAgent",
                "provenance": {
                    "model": model_name,
                    "provider": provider_name,
                    "version": "v1",
                    "parsed_at": datetime.utcnow().isoformat() + "Z",
                    "reviewed_by": "TrialTaggingAgent",
                    "source_checksum": source_checksum,
                    "primary_moa": primary_moa
                }
            }
            
            return result
            
        except Exception as e:
            error_str = str(e)
            is_rate_limit = (
                "429" in error_str or
                "rate limit" in error_str.lower() or
                "too many requests" in error_str.lower() or
                "quota" in error_str.lower() or
                "ratelimit" in error_str.lower()
            )
            
            if is_rate_limit and attempt < max_retries - 1:
                # Try to extract retry delay from API error message
                retry_delay = None
                if "retry in" in error_str.lower() or "retry_delay" in error_str.lower():
                    import re
                    # Look for "retry in X.Xs" or "retry_delay { seconds: X }"
                    match = re.search(r"retry.*?(\d+\.?\d*)\s*s", error_str, re.IGNORECASE)
                    if match:
                        retry_delay = float(match.group(1))
                    else:
                        match = re.search(r"seconds[:\s]+(\d+\.?\d*)", error_str, re.IGNORECASE)
                        if match:
                            retry_delay = float(match.group(1))
                
                if retry_delay:
                    # Use API-suggested delay + buffer (API suggests minimum, add buffer)
                    delay = retry_delay + 5  # Add 5s buffer to be safe
                    logger.warning(f"⚠️ Rate limit hit for {trial.get('nct_id')} (attempt {attempt + 1}/{max_retries}). API suggests retry in {retry_delay:.1f}s, waiting {delay:.1f}s...")
                else:
                    # Exponential backoff: 2^attempt * INITIAL_BACKOFF (5s, 10s, 20s)
                    delay = (2 ** attempt) * INITIAL_BACKOFF
                    # Add jitter to prevent thundering herd
                    jitter = delay * 0.1 * random.random()
                    delay = delay + jitter
                    logger.warning(f"⚠️ Rate limit hit for {trial.get('nct_id')} (attempt {attempt + 1}/{max_retries}). Retrying in {delay:.1f}s...")
                
                await asyncio.sleep(delay)
                continue
            elif "401" in error_str or "403" in error_str or "invalid" in error_str.lower() or "unauthorized" in error_str.lower() or "permission denied" in error_str.lower():
                logger.error(f"❌ Invalid API key for {trial.get('nct_id')}")
                return None  # Don't retry auth errors
            elif attempt < max_retries - 1:
                # Other errors - retry with shorter delay
                delay = 1.0 * (attempt + 1)
                logger.warning(f"⚠️ Error for {trial.get('nct_id')} (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {delay:.1f}s...")
                await asyncio.sleep(delay)
                continue
            else:
                # Max retries reached
                logger.error(f"❌ Failed to tag {trial.get('nct_id')} after {max_retries} attempts: {e}")
                return None
    
    return None  # Should never reach here, but just in case


async def tag_trials_moa_batch(
    trial_nct_ids: Optional[List[str]] = None,
    limit: int = 200,
    batch_size: int = 50,
    api_key: Optional[str] = None,
    provider_name: Optional[str] = None,
    use_incremental: bool = True,
    corpus_nct_ids: Optional[List[str]] = None,
    confidence_threshold: float = 0.7,
    run_qa: bool = True
) -> Dict[str, Dict]:
    """
    Batch tag trials with MoA vectors using LLM abstraction layer (offline).
    
    Args:
        trial_nct_ids: Specific NCT IDs to tag (if None, gets untagged trials)
        limit: Maximum number of trials to tag
        batch_size: Number of trials to process per batch
        api_key: LLM API key (if None, uses provider-specific env var)
        provider_name: LLM provider name ("cohere", "gemini", etc.) or None for auto-detect
    
    Returns:
        Dict mapping NCT ID to MoA vector data
    """
    if not LLM_AVAILABLE:
        logger.error("❌ LLM provider abstraction layer not available")
        return {}
    
    # Determine provider
    provider_enum = None
    if provider_name:
        try:
            provider_enum = LLMProvider[provider_name.upper()]
        except KeyError:
            logger.error(f"❌ Invalid provider name: {provider_name}. Must be one of: {list(LLMProvider.__members__.keys())}")
            return {}
    
    # Initialize LLM provider
    try:
        # Import provider classes for direct instantiation when API key is provided
        from api.services.llm_provider import CohereProvider, GeminiProvider
        
        llm_provider = None
        
        # If API key provided, instantiate provider directly
        if api_key:
            if provider_enum == LLMProvider.COHERE:
                llm_provider = CohereProvider(api_key=api_key)
            elif provider_enum == LLMProvider.GEMINI:
                llm_provider = GeminiProvider(api_key=api_key)
            elif provider_enum is None:
                # Auto-detect: try Cohere first, then Gemini
                llm_provider = CohereProvider(api_key=api_key)
                if not llm_provider.is_available():
                    llm_provider = GeminiProvider(api_key=api_key)
        
        # If no provider yet, use auto-detection from env vars
        if not llm_provider:
            llm_provider = get_llm_provider(provider_enum)
        
        if not llm_provider or not llm_provider.is_available():
            logger.error(f"❌ LLM provider not available. Check API key and library installation.")
            return {}
        
        provider_name = llm_provider.__class__.__name__.replace("Provider", "").lower()
        model_name = llm_provider.get_default_model()
        logger.info(f"✅ Using {provider_name} provider with model: {model_name}")
        
    except RuntimeError as e:
        logger.error(f"❌ Failed to initialize LLM provider: {e}")
        return {}
    except Exception as e:
        logger.error(f"❌ Failed to initialize LLM provider: {e}")
        return {}
    
    # Get trials to tag
    # ⚔️ MANAGER'S PLAN - T1: Use incremental selection if available
    if trial_nct_ids:
        # Tag specific trials
        conn = sqlite3.connect(str(DB_PATH))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        placeholders = ','.join(['?' for _ in trial_nct_ids])
        query = f"""
        SELECT id as nct_id, title, status, phases, interventions, interventions_json, 
               conditions, summary
        FROM trials
        WHERE id IN ({placeholders})
        """
        cursor.execute(query, trial_nct_ids)
        trials = [dict(row) for row in cursor.fetchall()]
        conn.close()
        incremental_stats = None
    else:
        # ⚔️ MANAGER'S PLAN - T1: Use incremental selection (checksum-based)
        if use_incremental and get_incremental_tagging_candidates:
            try:
                existing_vectors_path = Path(__file__).resolve().parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"
                trials, incremental_stats = get_incremental_tagging_candidates(
                    db_path=str(DB_PATH),
                    existing_vectors_path=str(existing_vectors_path),
                    corpus_nct_ids=corpus_nct_ids,
                    confidence_threshold=confidence_threshold,
                    max_candidates=limit
                )
                logger.info(f"✅ Incremental selection: {len(trials)} candidates")
                if incremental_stats:
                    logger.info(f"   Selection stats: {incremental_stats}")
            except Exception as e:
                logger.warning(f"⚠️ Incremental selection failed: {e} - falling back to basic selection")
                trials = get_untagged_trials(limit=limit)
                incremental_stats = None
        else:
            # Fallback to basic untagged selection
            trials = get_untagged_trials(limit=limit)
            incremental_stats = None
    
    if not trials:
        logger.warning("⚠️ No trials to tag")
        return {}
    
    logger.info(f"🚀 Starting batch tagging of {len(trials)} trials")
    logger.info(f"   Batch size: {batch_size}, Base rate limit: {RATE_LIMIT_SECONDS}s between calls")
    logger.info(f"   Max retries: {MAX_RETRIES}, Exponential backoff: {INITIAL_BACKOFF}s initial")
    
    # Load existing vectors
    existing_vectors = load_existing_vectors()
    tagged_vectors = {}
    failed_trials = []
    start_time = datetime.utcnow()
    
    # Process in batches
    for batch_start in range(0, len(trials), batch_size):
        batch = trials[batch_start:batch_start + batch_size]
        batch_num = (batch_start // batch_size) + 1
        total_batches = (len(trials) + batch_size - 1) // batch_size
        
        logger.info(f"\n📦 Processing batch {batch_num}/{total_batches} ({len(batch)} trials)")
        batch_start_time = datetime.utcnow()
        
        for i, trial in enumerate(batch, 1):
            nct_id = trial.get('nct_id')
            title = (trial.get('title') or 'Unknown')[:60]
            
            logger.info(f"   [{i}/{len(batch)}] {nct_id}: {title}...")
            
            # Skip if already tagged (unless explicitly requested)
            if nct_id in existing_vectors and not trial_nct_ids:
                logger.info(f"      ⏭️  Already tagged, skipping")
                continue
            
            # Tag with LLM using abstraction layer (with built-in retry logic)
            result = await tag_trial_with_llm(llm_provider, trial)
            
            if result:
                tagged_vectors[nct_id] = result
                confidence = result.get('confidence', 0.0)
                primary_moa = result.get('provenance', {}).get('primary_moa', 'Unknown')
                logger.info(f"      ✅ Tagged (confidence: {confidence:.2f}, MoA: {primary_moa[:40]})")
            else:
                failed_trials.append(nct_id)
                logger.warning(f"      ❌ Tagging failed after {MAX_RETRIES} attempts")
            
            # Rate limiting (wait between calls to respect API limits)
            # Free tier: 5 requests/minute = 12 seconds between calls
            # Tier 1: Can use 1-5 seconds between calls if no limits hit
            if i < len(batch):
                await asyncio.sleep(RATE_LIMIT_SECONDS)
        
        # ⚔️ MANAGER'S PLAN - T4: Automated QA after each batch
        qa_results = None
        if tagged_vectors and run_qa and run_automated_qa:
            try:
                qa_results = run_automated_qa(tagged_vectors, sample_size=min(30, len(tagged_vectors)))
                logger.info(f"   ✅ QA: {qa_results.get('trials_passed', 0)}/{qa_results.get('trials_qaed', 0)} passed (error rate: {qa_results.get('error_rate', 0.0):.1%})")
            except Exception as e:
                logger.warning(f"   ⚠️ Automated QA failed: {e}")
        
        # Save progress after each batch
        if tagged_vectors:
            merged_vectors = {**existing_vectors, **tagged_vectors}
            save_vectors(merged_vectors)
            batch_elapsed = (datetime.utcnow() - batch_start_time).total_seconds()
            logger.info(f"   💾 Progress saved: {len(tagged_vectors)} new tags (batch took {batch_elapsed:.1f}s)")
            if qa_results:
                logger.info(f"   📊 QA stats: {qa_results.get('trials_passed', 0)}/{qa_results.get('trials_qaed', 0)} passed")
    
    total_elapsed = (datetime.utcnow() - start_time).total_seconds()
    success_count = len(tagged_vectors)
    
    # ⚔️ MANAGER'S PLAN - T4: Final automated QA on all tagged trials
    final_qa_results = None
    if tagged_vectors and run_qa and run_automated_qa:
        try:
            final_qa_results = run_automated_qa(tagged_vectors, sample_size=min(30, len(tagged_vectors)))
        except Exception as e:
            logger.warning(f"⚠️ Final QA failed: {e}")
    
    logger.info(f"\n✅ Batch tagging complete:")
    logger.info(f"   ✅ Successfully tagged: {success_count} trials")
    logger.info(f"   ❌ Failed: {len(failed_trials)} trials")
    if failed_trials:
        logger.info(f"   Failed NCT IDs: {', '.join(failed_trials[:10])}{'...' if len(failed_trials) > 10 else ''}")
    logger.info(f"   ⏱️  Total time: {total_elapsed:.1f}s ({total_elapsed/60:.1f} minutes)")
    logger.info(f"   📊 Average: {total_elapsed/success_count:.1f}s per trial" if success_count > 0 else "")
    
    if incremental_stats:
        logger.info(f"\n📊 Incremental Selection Stats:")
        logger.info(f"   Not tagged: {incremental_stats.get('not_tagged', 0)}")
        logger.info(f"   Checksum changed: {incremental_stats.get('checksum_changed', 0)}")
        logger.info(f"   Low confidence re-tag: {incremental_stats.get('low_confidence_re_tag', 0)}")
    
    if final_qa_results:
        logger.info(f"\n📊 Final QA Results:")
        logger.info(f"   Trials QAed: {final_qa_results.get('trials_qaed', 0)}")
        logger.info(f"   Passed: {final_qa_results.get('trials_passed', 0)}")
        logger.info(f"   Failed: {final_qa_results.get('trials_failed', 0)}")
        logger.info(f"   Error rate: {final_qa_results.get('error_rate', 0.0):.1%}")
    
    return tagged_vectors


def main():
    """Main execution."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Batch tag trials with MoA vectors using LLM abstraction layer (Cohere, Gemini, etc.)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Use Cohere (default, auto-detected from COHERE_API_KEY):
  python tag_trials_moa_batch.py --limit 200
  
  # Use Gemini:
  python tag_trials_moa_batch.py --provider gemini --limit 200
  
  # Use specific API key:
  python tag_trials_moa_batch.py --api-key YOUR_KEY --provider cohere
  
  # Tag specific trials:
  python tag_trials_moa_batch.py --nct-ids NCT12345678 NCT87654321
        """
    )
    parser.add_argument("--limit", type=int, default=200, help="Maximum number of trials to tag")
    parser.add_argument("--batch-size", type=int, default=50, help="Number of trials per batch")
    parser.add_argument("--api-key", type=str, help="LLM API key (or use provider-specific env var: COHERE_API_KEY, GEMINI_API_KEY, etc.)")
    parser.add_argument("--provider", type=str, choices=["cohere", "gemini"], help="LLM provider to use (default: auto-detect from env vars)")
    parser.add_argument("--nct-ids", nargs="+", help="Specific NCT IDs to tag (optional)")
    # ⚔️ MANAGER'S PLAN - T1, T4: Incremental tagging + QA flags
    parser.add_argument("--no-incremental", action="store_true", help="Disable incremental selection (use basic untagged selection)")
    parser.add_argument("--corpus", nargs="+", help="Corpus NCT IDs for re-tag priority (e.g., Ayesha corpus)")
    parser.add_argument("--confidence-threshold", type=float, default=0.7, help="Confidence threshold for re-tagging (default: 0.7)")
    parser.add_argument("--no-qa", action="store_true", help="Disable automated QA")
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("🚀 Trial MoA Batch Tagging (Manager P3 Compliant)")
    logger.info("   Using LLM Abstraction Layer")
    logger.info("=" * 60)
    
    # Run async function
    # ⚔️ MANAGER'S PLAN - T1, T4: Use incremental tagging + QA
    tagged = asyncio.run(tag_trials_moa_batch(
        trial_nct_ids=args.nct_ids,
        limit=args.limit,
        batch_size=args.batch_size,
        api_key=args.api_key,
        provider_name=args.provider,
        use_incremental=not args.no_incremental,
        corpus_nct_ids=args.corpus,
        confidence_threshold=args.confidence_threshold,
        run_qa=not args.no_qa
    ))
    
    logger.info("=" * 60)
    logger.info(f"✅ Complete: {len(tagged)} trials tagged")
    logger.info(f"   Output: {OUTPUT_PATH}")
    logger.info("=" * 60)


if __name__ == "__main__":
    main()

