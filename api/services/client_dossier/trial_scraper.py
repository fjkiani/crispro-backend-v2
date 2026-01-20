"""
Trial Scraper - Scrape full trial pages using Diffbot.

Uses existing Diffbot integration for robust scraping with caching.
"""
import httpx
import json
import sqlite3
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import logging
import os

logger = logging.getLogger(__name__)

# Cache directory
CACHE_DIR = Path(__file__).parent.parent.parent.parent / "data" / "dossier_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_HOURS = 24

def get_cached_trial_data(nct_id: str) -> Optional[Dict[str, Any]]:
    """
    Get cached trial data if fresh.
    
    Checks:
    1. File cache (24hr TTL)
    2. SQLite (if file cache expired/missing)
    """
    # Check file cache first
    cache_file = CACHE_DIR / f"{nct_id}.json"
    if cache_file.exists():
        try:
            with open(cache_file, 'r') as f:
                data = json.load(f)
            
            # Check TTL
            cached_time = datetime.fromisoformat(data.get('cached_at', '2000-01-01'))
            if datetime.now() - cached_time <= timedelta(hours=CACHE_TTL_HOURS):
                logger.info(f"✅ File cache hit for {nct_id}")
                return data.get('trial_data')
        except Exception as e:
            logger.warning(f"Cache read error for {nct_id}: {e}")
    
    # Fallback: Check SQLite
    scraped_data = get_scraped_data_from_sqlite(nct_id)
    if scraped_data:
        logger.info(f"✅ SQLite cache hit for {nct_id}")
        # Refresh file cache
        cache_trial_data(nct_id, scraped_data)
        return scraped_data
    
    return None

def get_scraped_data_from_sqlite(nct_id: str) -> Optional[Dict[str, Any]]:
    """
    Get trial data from SQLite (primary source for inclusion/exclusion criteria).
    
    Uses existing columns: inclusion_criteria, exclusion_criteria, interventions, etc.
    Also checks for scraped_data_json if it exists.
    """
    current_file = Path(__file__).resolve()
    backend_root = current_file.parent.parent.parent.parent
    db_path = backend_root / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        return None
    
    try:
        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Get trial data (use 'id' field which contains NCT ID)
        cursor.execute("SELECT * FROM trials WHERE id = ? OR id LIKE ?", (nct_id, f"%{nct_id}%"))
        row = cursor.fetchone()
        
        if not row:
            conn.close()
            return None
        
        # Build data dict from row
        trial_dict = dict(row)
        
        # Check for scraped_data_json (enriched data)
        if trial_dict.get('scraped_data_json'):
            try:
                scraped = json.loads(trial_dict['scraped_data_json'])
                # Merge scraped data with base data
                trial_dict.update(scraped)
            except:
                pass
        
        # Ensure we have inclusion/exclusion criteria from existing columns
        if not trial_dict.get('inclusion_criteria_full') and trial_dict.get('inclusion_criteria'):
            trial_dict['inclusion_criteria_full'] = trial_dict['inclusion_criteria']
        if not trial_dict.get('exclusion_criteria_full') and trial_dict.get('exclusion_criteria'):
            trial_dict['exclusion_criteria_full'] = trial_dict['exclusion_criteria']
        
        conn.close()
        return trial_dict
        
    except Exception as e:
        logger.warning(f"SQLite read error for {nct_id}: {e}")
        return None

def cache_trial_data(nct_id: str, trial_data: Dict[str, Any]):
    """Cache trial data with timestamp."""
    cache_file = CACHE_DIR / f"{nct_id}.json"
    try:
        with open(cache_file, 'w') as f:
            json.dump({
                'cached_at': datetime.now().isoformat(),
                'trial_data': trial_data
            }, f, indent=2)
        logger.info(f"✅ Cached {nct_id}")
    except Exception as e:
        logger.warning(f"Cache write error for {nct_id}: {e}")

def save_scraped_data_to_sqlite(nct_id: str, scraped_data: Dict[str, Any]):
    """
    Persist Diffbot scraped data to SQLite trials table.
    
    Updates existing trial record with full scraped data.
    """
    # Get database path
    # From: api/services/client_dossier/trial_scraper.py
    # To: oncology-backend-minimal/data/clinical_trials.db
    current_file = Path(__file__).resolve()
    backend_root = current_file.parent.parent.parent.parent
    db_path = backend_root / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        logger.warning(f"Database not found: {db_path} - skipping SQLite persistence")
        return
    
    try:
        conn = sqlite3.connect(str(db_path))
        cursor = conn.cursor()
        
        # Check if trial exists
        cursor.execute("SELECT id FROM trials WHERE id = ? OR id LIKE ?", (nct_id, f"%{nct_id}%"))
        existing = cursor.fetchone()
        
        if existing:
            # Update existing trial with scraped data
            # Store full scraped data as JSON in a new column or update existing columns
            # For now, update inclusion/exclusion criteria if they're more complete
            inclusion_full = scraped_data.get('inclusion_criteria_full', '')
            exclusion_full = scraped_data.get('exclusion_criteria_full', '')
            
            # Try to add columns if they don't exist (graceful if they do)
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN inclusion_criteria_full TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN exclusion_criteria_full TEXT")
            except sqlite3.OperationalError:
                pass  # Column already exists
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN primary_endpoint TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN interventions_json TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN locations_full_json TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN scraped_data_json TEXT")
            except sqlite3.OperationalError:
                pass
            
            try:
                cursor.execute("ALTER TABLE trials ADD COLUMN scraped_at TEXT")
            except sqlite3.OperationalError:
                pass
            
            # Update trial with scraped data
            cursor.execute("""
                UPDATE trials 
                SET inclusion_criteria_full = ?,
                    exclusion_criteria_full = ?,
                    primary_endpoint = ?,
                    interventions_json = ?,
                    locations_full_json = ?,
                    scraped_data_json = ?,
                    scraped_at = ?
                WHERE id = ? OR id LIKE ?
            """, (
                inclusion_full,
                exclusion_full,
                scraped_data.get('primary_endpoint', ''),
                json.dumps(scraped_data.get('interventions', [])),
                json.dumps(scraped_data.get('locations_full', [])),
                json.dumps(scraped_data),  # Full scraped data as JSON
                datetime.now().isoformat(),
                nct_id,
                f"%{nct_id}%"
            ))
            
            conn.commit()
            logger.info(f"✅ Updated SQLite with scraped data for {nct_id}")
        else:
            logger.warning(f"Trial {nct_id} not found in SQLite - cannot update")
        
        conn.close()
        
    except Exception as e:
        logger.error(f"❌ SQLite persistence failed for {nct_id}: {e}")
        # Don't raise - file cache is sufficient for now

async def scrape_trial_page(nct_id: str) -> Dict[str, Any]:
    """
    Scrape full ClinicalTrials.gov page using Diffbot.
    
    Uses existing Diffbot integration. Returns structured trial data.
    
    Args:
        nct_id: NCT identifier (e.g., "NCT06819007")
    
    Returns:
        {
            'inclusion_criteria_full': str,
            'exclusion_criteria_full': str,
            'interventions': List[str],
            'primary_endpoint': str,
            'study_start_date': str,
            'primary_completion_date': str,
            'locations_full': List[dict],
            'full_html': str,
            'full_text': str
        }
    """
    # Check cache first
    cached = get_cached_trial_data(nct_id)
    if cached:
        return cached
    
    # PRIMARY: Get base data from SQLite (already has inclusion/exclusion criteria)
    sqlite_data = get_scraped_data_from_sqlite(nct_id)
    base_data = sqlite_data or {}
    
    # Get Diffbot token
    diffbot_token = os.getenv("DIFFBOT_TOKEN")
    if not diffbot_token:
        logger.warning(f"DIFFBOT_TOKEN not configured - using SQLite data only for {nct_id}")
        # Return SQLite data with proper structure
        return {
            'inclusion_criteria_full': base_data.get('inclusion_criteria_full') or base_data.get('inclusion_criteria', '[Not available]'),
            'exclusion_criteria_full': base_data.get('exclusion_criteria_full') or base_data.get('exclusion_criteria', '[Not available]'),
            'interventions': base_data.get('interventions', []),
            'primary_endpoint': base_data.get('primary_endpoint', ''),
            'study_start_date': base_data.get('study_start_date', ''),
            'primary_completion_date': base_data.get('primary_completion_date', ''),
            'locations_full': base_data.get('locations_full', []),
            'full_html': base_data.get('full_html', ''),
            'full_text': base_data.get('full_text', '')
        }
    
    url = f"https://clinicaltrials.gov/study/{nct_id}"
    
    # Use Diffbot API
    api_url = "https://api.diffbot.com/v3/article"
    params = {
        "token": diffbot_token,
        "url": url,
        "fields": "title,author,date,siteName,tags,images,html,text",
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            js = response.json()
        
        obj = (js.get("objects") or [None])[0]
        if not obj:
            raise ValueError(f"Diffbot failed to extract data from {url}")
        
        # Parse HTML to extract structured data
        from bs4 import BeautifulSoup
        html = obj.get("html", "")
        text = obj.get("text", "")
        soup = BeautifulSoup(html, 'html.parser') if html else None
        
        # Extract inclusion/exclusion criteria
        inclusion_text = ""
        exclusion_text = ""
        
        # Method 1: Try HTML parsing with flexible selectors
        if soup:
            # Look for eligibility sections (various possible IDs/classes)
            for selector in [
                {"id": "eligibility-section"},
                {"id": "eligibility-criteria-inclusion"},
                {"id": "eligibility-criteria-exclusion"},
                {"class": lambda x: x and "eligibility" in str(x).lower()},
            ]:
                section = soup.find(**selector) if isinstance(selector, dict) else soup.find(selector)
                if section:
                    # Look for inclusion/exclusion within section
                    for inc_elem in section.find_all(string=lambda t: t and "inclusion" in t.lower()):
                        parent = inc_elem.find_parent()
                        if parent:
                            inclusion_text = parent.get_text(separator="\n", strip=True)
                            break
                    for exc_elem in section.find_all(string=lambda t: t and "exclusion" in t.lower()):
                        parent = exc_elem.find_parent()
                        if parent:
                            exclusion_text = parent.get_text(separator="\n", strip=True)
                            break
        
        # Method 2: Extract from text content if HTML parsing failed
        if not inclusion_text or not exclusion_text:
            text_lower = text.lower()
            # Find inclusion criteria section
            inc_start = text_lower.find("inclusion criteria")
            exc_start = text_lower.find("exclusion criteria")
            
            if inc_start >= 0:
                # Extract text until exclusion or next major section
                inc_end = exc_start if exc_start > inc_start else text_lower.find("\n\n", inc_start)
                if inc_end < 0:
                    inc_end = len(text)
                inclusion_text = text[inc_start:inc_end].strip()
            
            if exc_start >= 0:
                # Extract text until next major section (look for common section headers)
                exc_end = len(text)
                for marker in ["\n\nprimary", "\n\nsecondary", "\n\nstudy", "\n\nlocation"]:
                    marker_pos = text_lower.find(marker, exc_start)
                    if marker_pos > exc_start:
                        exc_end = min(exc_end, marker_pos)
                exclusion_text = text[exc_start:exc_end].strip()
        
        # Extract interventions
        interventions = []
        intervention_section = soup.find(id="interventions-section")
        if intervention_section:
            for li in intervention_section.find_all("li"):
                interventions.append(li.get_text(strip=True))
        
        # Extract primary endpoint
        primary_endpoint = ""
        endpoint_section = soup.find(id="primary-outcome-measure")
        if endpoint_section:
            primary_endpoint = endpoint_section.get_text(strip=True)
        
        # Extract dates
        study_start = ""
        primary_completion = ""
        dates_section = soup.find(id="study-dates-section")
        if dates_section:
            start_elem = dates_section.find(string=lambda t: t and "Start Date" in t)
            if start_elem:
                study_start = start_elem.find_next().get_text(strip=True) if start_elem.find_next() else ""
            
            completion_elem = dates_section.find(string=lambda t: t and "Primary Completion" in t)
            if completion_elem:
                primary_completion = completion_elem.find_next().get_text(strip=True) if completion_elem.find_next() else ""
        
        # Extract locations
        locations_full = []
        locations_section = soup.find(id="locations-section")
        if locations_section:
            for location in locations_section.find_all("li", class_="location"):
                loc_data = {
                    'facility': location.find("span", class_="facility-name").get_text(strip=True) if location.find("span", class_="facility-name") else "",
                    'city': location.find("span", class_="city").get_text(strip=True) if location.find("span", class_="city") else "",
                    'state': location.find("span", class_="state").get_text(strip=True) if location.find("span", class_="state") else "",
                    'country': location.find("span", class_="country").get_text(strip=True) if location.find("span", class_="country") else "",
                }
                locations_full.append(loc_data)
        
        # Merge Diffbot data with SQLite base data (prefer Diffbot if available, fallback to SQLite)
        trial_data = {
            'inclusion_criteria_full': inclusion_text or base_data.get('inclusion_criteria', ''),
            'exclusion_criteria_full': exclusion_text or base_data.get('exclusion_criteria', ''),
            'interventions': interventions or base_data.get('interventions', []),
            'primary_endpoint': primary_endpoint or base_data.get('primary_endpoint', ''),
            'study_start_date': study_start or base_data.get('study_start_date', ''),
            'primary_completion_date': primary_completion or base_data.get('primary_completion_date', ''),
            'locations_full': locations_full or base_data.get('locations_full', []),
            'full_html': html or base_data.get('full_html', ''),
            'full_text': obj.get("text", "") or base_data.get('full_text', '')
        }
        
        # Cache it (file-based for fast lookup)
        cache_trial_data(nct_id, trial_data)
        
        # Persist to SQLite for long-term storage
        save_scraped_data_to_sqlite(nct_id, trial_data)
        
        logger.info(f"✅ Scraped {nct_id}")
        return trial_data
        
    except Exception as e:
        logger.error(f"❌ Scraping failed for {nct_id}: {e}")
        raise

