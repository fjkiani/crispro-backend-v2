"""Verify Cohere-tagged vectors have complete metadata."""
import json
from pathlib import Path

output_file = Path(__file__).parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"

with open(output_file, "r") as f:
    vectors = json.load(f)

# Check only the new cohere_batch_tagging vectors
cohere_vectors = {k: v for k, v in vectors.items() if v.get('source') == 'cohere_batch_tagging'}

print(f'📊 Cohere Batch Tagging Vectors: {len(cohere_vectors)}')
print('=' * 60)

# Check metadata completeness
missing_provider = 0
missing_model = 0
missing_checksum = 0
has_all_metadata = 0

for nct_id, vector in cohere_vectors.items():
    prov = vector.get('provenance', {})
    if not prov.get('provider'):
        missing_provider += 1
    if not prov.get('model'):
        missing_model += 1
    if not prov.get('source_checksum'):
        missing_checksum += 1
    if prov.get('provider') and prov.get('model') and prov.get('source_checksum'):
        has_all_metadata += 1

print(f'\n✅ Complete metadata: {has_all_metadata}/{len(cohere_vectors)} ({100*has_all_metadata/len(cohere_vectors):.1f}%)')
print(f'❌ Missing provider: {missing_provider}')
print(f'❌ Missing model: {missing_model}')
print(f'❌ Missing checksum: {missing_checksum}')

# Sample a few complete ones
print(f'\n📋 Sample of vectors with complete metadata:')
print('-' * 60)
count = 0
for nct_id, vector in cohere_vectors.items():
    prov = vector.get('provenance', {})
    if prov.get('provider') and prov.get('model') and prov.get('source_checksum'):
        print(f'\n{nct_id}:')
        print(f'  Provider: {prov.get("provider")}')
        print(f'  Model: {prov.get("model")}')
        print(f'  Confidence: {vector.get("confidence", 0):.2f}')
        primary_moa = prov.get('primary_moa', 'unknown')[:50]
        print(f'  Primary MoA: {primary_moa}')
        count += 1
        if count >= 5:
            break

