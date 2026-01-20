#!/usr/bin/env python3
"""
Update universal_disease_pathway_database.json with real TCGA frequencies
"""

import json
from pathlib import Path
from datetime import datetime

# Paths
FREQUENCIES_FILE = Path(__file__).parent / "mutation_frequencies.json"
DATABASE_FILE = Path(__file__).parent.parent.parent / "api/resources/universal_disease_pathway_database.json"
BACKUP_FILE = DATABASE_FILE.with_suffix('.json.backup')

def main():
    print("=" * 80)
    print("🔄 UPDATING UNIVERSAL DATABASE WITH REAL FREQUENCIES")
    print("=" * 80)
    
    # Load real frequencies
    if not FREQUENCIES_FILE.exists():
        print(f"❌ Frequencies file not found: {FREQUENCIES_FILE}")
        print(f"   Run extract_mutation_frequencies.py first")
        return
    
    with open(FREQUENCIES_FILE) as f:
        frequencies = json.load(f)
    
    print(f"✅ Loaded frequencies for {len(frequencies)} cancers")
    
    # Load current database
    with open(DATABASE_FILE) as f:
        database = json.load(f)
    
    # Backup original
    with open(BACKUP_FILE, 'w') as f:
        json.dump(database, f, indent=2)
    print(f"💾 Backed up original to: {BACKUP_FILE}")
    
    # Update weights for extracted cancers
    updated_count = 0
    cancers_extracted = []
    cancers_failed = []
    
    for cancer_type, pathway_data in frequencies.items():
        if cancer_type in database['diseases']:
            print(f"\n🔄 Updating {cancer_type}...")
            cancers_extracted.append(cancer_type)
            
            for pathway_name, freq_data in pathway_data.items():
                if pathway_name in database['diseases'][cancer_type]['pathways']:
                    # Update weight and add new fields
                    old_weight = database['diseases'][cancer_type]['pathways'][pathway_name]['weight']
                    new_weight = freq_data['weight']
                    
                    database['diseases'][cancer_type]['pathways'][pathway_name]['weight'] = new_weight
                    database['diseases'][cancer_type]['pathways'][pathway_name]['source'] = freq_data['source']
                    database['diseases'][cancer_type]['pathways'][pathway_name]['genes'] = freq_data['genes']
                    database['diseases'][cancer_type]['pathways'][pathway_name]['samples_altered'] = freq_data['samples_altered']
                    database['diseases'][cancer_type]['pathways'][pathway_name]['total_samples'] = freq_data['total_samples']
                    database['diseases'][cancer_type]['pathways'][pathway_name]['extraction_type'] = freq_data.get('extraction_type', 'mutation')
                    database['diseases'][cancer_type]['pathways'][pathway_name]['extracted_at'] = freq_data['extracted_at']
                    
                    print(f"  ✓ {pathway_name}: {old_weight:.3f} → {new_weight:.3f}")
                    updated_count += 1
        else:
            print(f"⚠️  {cancer_type} not found in database - skipping")
            cancers_failed.append(cancer_type)
    
    # Add metadata
    database['version'] = "1.1.0"
    database['last_updated'] = datetime.now().isoformat()
    database['extraction_metadata'] = {
        "extracted_at": datetime.now().isoformat(),
        "extraction_version": "v1",
        "cancers_extracted": len(cancers_extracted),
        "cancers_failed": len(cancers_failed),
        "pathways_updated": updated_count
    }
    database['extraction_note'] = f"Real TCGA frequencies for {len(cancers_extracted)} cancers. Other diseases use literature-based estimates (0.75 default). See limitations in extraction report."
    
    # Save updated database
    with open(DATABASE_FILE, 'w') as f:
        json.dump(database, f, indent=2)
    
    print(f"\n{'='*80}")
    print("✅ UPDATE COMPLETE")
    print(f"{'='*80}")
    print(f"Updated pathways: {updated_count}")
    print(f"Cancers extracted: {len(cancers_extracted)}")
    print(f"Cancers failed: {len(cancers_failed)}")
    print(f"Updated database: {DATABASE_FILE}")
    print(f"Backup saved: {BACKUP_FILE}")


if __name__ == "__main__":
    main()








