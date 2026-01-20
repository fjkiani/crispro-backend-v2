"""Analyze which trials were tagged - are they aligned with Ayesha?"""
import json
import sqlite3
from pathlib import Path
from collections import defaultdict

# Load tagged vectors
vectors_file = Path(__file__).parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"
with open(vectors_file, "r") as f:
    vectors = json.load(f)

# Get the 502 new Cohere-tagged trials
cohere_trials = [nct_id for nct_id, v in vectors.items() if v.get("source") == "cohere_batch_tagging"]

print(f"📊 Analyzing {len(cohere_trials)} Cohere-tagged trials")
print("=" * 60)

# Connect to database
db_path = Path(__file__).parent.parent.parent / "data" / "clinical_trials.db"
if not db_path.exists():
    print("❌ Database not found")
    exit(1)

conn = sqlite3.connect(str(db_path))
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

# Keywords for classification
oncology_keywords = ["cancer", "carcinoma", "tumor", "tumour", "neoplasm", "malignancy", "oncology", "leukemia", "lymphoma", "sarcoma", "melanoma"]
ovarian_keywords = ["ovarian", "ovary", "fallopian", "peritoneal", "gynecologic", "gynecological", "gyn", "hgsoc", "high-grade serous"]

# Analyze all 502 trials
oncology_all = 0
ovarian_all = 0
other_all = 0
ovarian_trials = []

# Process in batches
batch_size = 100
for i in range(0, len(cohere_trials), batch_size):
    batch = cohere_trials[i:i+batch_size]
    placeholders = ",".join(["?" for _ in batch])
    query = f"SELECT id, title, conditions FROM trials WHERE id IN ({placeholders})"
    cursor.execute(query, batch)
    batch_trials = cursor.fetchall()
    
    for trial in batch_trials:
        conditions = trial["conditions"] or ""
        title = trial["title"] or ""
        conditions_lower = conditions.lower()
        title_lower = title.lower()
        
        is_ovarian = any(kw in conditions_lower or kw in title_lower for kw in ovarian_keywords)
        is_oncology = any(kw in conditions_lower or kw in title_lower for kw in oncology_keywords)
        
        if is_ovarian:
            ovarian_all += 1
            ovarian_trials.append((trial["id"], trial["title"][:70], conditions[:100]))
        elif is_oncology:
            oncology_all += 1
        else:
            other_all += 1

print(f"\n📊 Full Analysis (all {len(cohere_trials)} trials):")
print(f"   🎗️  Oncology-related: {oncology_all} ({100*oncology_all/len(cohere_trials):.1f}%)")
print(f"   🫶 Ovarian/Gynecologic: {ovarian_all} ({100*ovarian_all/len(cohere_trials):.1f}%)")
print(f"   📝 Other/Non-oncology: {other_all} ({100*other_all/len(cohere_trials):.1f}%)")

if ovarian_all > 0:
    print(f"\n✅ Found {ovarian_all} ovarian/gynecologic trials:")
    print("-" * 60)
    for nct_id, title, conditions in ovarian_trials[:15]:
        print(f"\n{nct_id}:")
        print(f"  Title: {title}")
        if conditions:
            print(f"  Conditions: {conditions[:100]}")

# Check query logic
print(f"\n" + "=" * 60)
print("🔍 Query Logic Analysis:")
print("-" * 60)
print("The script uses this query:")
print("  - Gets untagged trials from database")
print("  - Filters by: RECRUITING, ACTIVE_NOT_RECRUITING, ENROLLING_BY_INVITATION, COMPLETED")
print("  - Requires: interventions IS NOT NULL")
print("  - Orders by: RECRUITING first, then ACTIVE, then others")
print("  - NO disease type filtering")
print("  - NO alignment with Ayesha's profile")

print(f"\n⚠️  CONCLUSION:")
if ovarian_all == 0:
    print("   ❌ NO ovarian/gynecologic trials tagged")
    print("   📝 These are RANDOM trials from the database")
    print("   💡 The script does NOT filter by disease type")
    print("   💡 The script does NOT align with Ayesha's profile")
else:
    print(f"   ✅ Found {ovarian_all} ovarian trials ({100*ovarian_all/len(cohere_trials):.1f}%)")
    print("   ⚠️  But most trials are random - not aligned with Ayesha")
    print("   💡 The script does NOT filter by disease type")

conn.close()

