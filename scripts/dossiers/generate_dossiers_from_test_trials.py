#!/usr/bin/env python3
"""
Generate dossiers for trials from SQLite database (1000 trials)
and save them to .cursor/ayesha/test_trials/

Usage:
    # Process all ovarian cancer trials (default)
    python generate_dossiers_from_test_trials.py
    
    # Process ALL 1000 trials
    PROCESS_ALL_TRIALS=true python generate_dossiers_from_test_trials.py
    
    # Process first 100 trials
    MAX_TRIALS=100 python generate_dossiers_from_test_trials.py
    
    # Process all 1000 trials
    PROCESS_ALL_TRIALS=true MAX_TRIALS=0 python generate_dossiers_from_test_trials.py
"""
import asyncio
import json
from pathlib import Path
from datetime import datetime
import sys
import sqlite3
import os

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from api.services.client_dossier.dossier_generator import generate_dossier
from api.services.client_dossier.dossier_renderer import render_dossier_markdown
from api.services.client_dossier.trial_querier import get_trials_from_sqlite
from api.services.client_dossier.trial_filter import filter_50_candidates

AYESHA_PROFILE = {
    'patient_id': 'ayesha_001',
    'disease': 'ovarian_cancer_hgs',
    'treatment_line': 'first-line',
    'location': 'NYC',
    'biomarkers': {
        'brca': 'NEGATIVE',
        'hrd': 'UNKNOWN',
        'tmb': 'UNKNOWN',
        'msi': 'UNKNOWN',
        'her2': 'UNKNOWN'
    }
}

def get_ovarian_trials_from_db(limit: int = 0) -> list:
    """Get ovarian cancer trials directly from SQLite database."""
    current_file = Path(__file__).resolve()
    backend_root = current_file.parent
    db_path = backend_root / "data" / "clinical_trials.db"
    
    if not db_path.exists():
        raise FileNotFoundError(f"Database not found: {db_path}")
    
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Query for ovarian cancer trials
    query = """
        SELECT * FROM trials 
        WHERE conditions LIKE '%ovarian%' OR title LIKE '%ovarian%'
    """
    if limit > 0:
        query += f" LIMIT {limit}"
    
    cursor.execute(query)
    trials = [dict(row) for row in cursor.fetchall()]
    
    # Parse JSON fields
    for trial in trials:
        for json_field in ['interventions_json', 'locations_full_json', 'scraped_data_json']:
            if trial.get(json_field) and isinstance(trial[json_field], str):
                try:
                    trial[json_field] = json.loads(trial[json_field])
                except:
                    trial[json_field] = []
    
    conn.close()
    return trials

async def main():
    print("⚔️ Generating Dossiers from SQLite Database (1000 trials)\n")
    
    # Configuration from environment variables
    process_all = os.getenv("PROCESS_ALL_TRIALS", "false").lower() == "true"
    max_trials = int(os.getenv("MAX_TRIALS", "0"))  # 0 = all, default = all ovarian
    disease_filter = os.getenv("DISEASE_FILTER", "ovarian")  # Default: ovarian cancer
    
    if process_all:
        # Process ALL trials from database
        print("1. Querying database for ALL trials...")
        all_trials = get_trials_from_sqlite(limit=0)  # 0 = all
        print(f"   ✅ Found {len(all_trials)} total trials in database")
        
        if max_trials > 0:
            trials_to_process = all_trials[:max_trials]
            print(f"   Processing first {len(trials_to_process)} trials (MAX_TRIALS={max_trials})")
        else:
            trials_to_process = all_trials
            print(f"   Processing ALL {len(trials_to_process)} trials")
    else:
        # Process ovarian cancer trials only (default)
        print(f"1. Querying database for {disease_filter} cancer trials...")
        ovarian_trials = get_ovarian_trials_from_db()
        print(f"   ✅ Found {len(ovarian_trials)} {disease_filter} cancer trials in database")
        
        if not ovarian_trials:
            print("   ⚠️ No ovarian cancer trials found, using all trials...")
            all_trials = get_trials_from_sqlite(limit=max_trials if max_trials > 0 else 0)
            print(f"   ✅ Found {len(all_trials)} total trials")
            trials_to_process = all_trials
        else:
            # Use all ovarian trials (or limit if specified)
            if max_trials > 0 and max_trials < len(ovarian_trials):
                trials_to_process = ovarian_trials[:max_trials]
                print(f"   Processing first {len(trials_to_process)} ovarian trials (MAX_TRIALS={max_trials})")
            else:
                trials_to_process = ovarian_trials
                print(f"   Processing ALL {len(trials_to_process)} ovarian cancer trials")
    
    # Create output directory
    output_dir = Path(__file__).parent.parent.parent / ".cursor" / "ayesha" / "test_trials"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n2. Generating dossiers for {len(trials_to_process)} trials...")
    print(f"   Output directory: {output_dir}")
    print(f"   (Skipping trials that already have dossiers)\n")
    
    generated = 0
    failed = 0
    skipped = 0
    
    for i, trial in enumerate(trials_to_process, 1):
        nct_id = trial.get('nct_id') or trial.get('id', 'UNKNOWN')
        title = trial.get('title', 'Unknown Trial')[:60]
        
        # Progress indicator
        if i % 10 == 0 or i == len(trials_to_process):
            print(f"   Progress: {i}/{len(trials_to_process)} ({100*i/len(trials_to_process):.1f}%) - Generated: {generated}, Skipped: {skipped}, Failed: {failed}")
        
        # Check if already exists
        existing = list(output_dir.glob(f"dossier_{nct_id.replace('/', '_')}_*.md"))
        if existing:
            skipped += 1
            if i <= 10 or i % 50 == 0:  # Show first 10 and every 50th
                print(f"   [{i}/{len(trials_to_process)}] {nct_id} - ⏭️  Skipped (exists)")
            continue
        
        try:
            # Generate dossier
            dossier = await generate_dossier(nct_id, AYESHA_PROFILE)
            
            # Render markdown
            markdown = render_dossier_markdown(dossier)
            
            # Save files
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            safe_nct_id = nct_id.replace('/', '_')
            
            markdown_file = output_dir / f"dossier_{safe_nct_id}_{timestamp}.md"
            json_file = output_dir / f"dossier_{safe_nct_id}_{timestamp}.json"
            
            markdown_file.write_text(markdown)
            json_file.write_text(json.dumps(dossier, indent=2))
            
            generated += 1
            if i <= 10 or i % 50 == 0:  # Show first 10 and every 50th
                print(f"   [{i}/{len(trials_to_process)}] {nct_id} - ✅ Generated ({len(markdown)} chars)")
            
        except ValueError as e:
            if "not found in database" in str(e):
                skipped += 1
                if i <= 10:
                    print(f"   [{i}/{len(trials_to_process)}] {nct_id} - ⚠️  Skipped (not in DB)")
            else:
                failed += 1
                if i <= 10:
                    print(f"   [{i}/{len(trials_to_process)}] {nct_id} - ❌ Failed: {e}")
        except Exception as e:
            failed += 1
            if i <= 10:
                print(f"   [{i}/{len(trials_to_process)}] {nct_id} - ❌ Failed: {e}")
            # Don't print full traceback for every failure (too verbose)
            if i <= 5:
                import traceback
                traceback.print_exc()
            continue
    
    print(f"\n{'='*60}")
    print(f"✅ COMPLETE!")
    print(f"{'='*60}")
    print(f"   Total processed: {len(trials_to_process)}")
    print(f"   Generated: {generated} dossiers")
    print(f"   Skipped: {skipped} dossiers (already exist or not in DB)")
    print(f"   Failed: {failed} dossiers")
    print(f"   Location: {output_dir}")
    
    # List generated files
    all_files = sorted(output_dir.glob("dossier_*.md"))
    if all_files:
        total_size_mb = sum(f.stat().st_size for f in all_files) / (1024 * 1024)
        print(f"\n   Total files in directory: {len(all_files)}")
        print(f"   Total size: {total_size_mb:.2f} MB")
        print(f"   Recent files (last 10):")
        for f in all_files[-10:]:
            size_kb = f.stat().st_size / 1024
            print(f"      - {f.name} ({size_kb:.1f} KB)")

if __name__ == "__main__":
    asyncio.run(main())
