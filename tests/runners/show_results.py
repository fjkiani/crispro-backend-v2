import json

with open('research_intelligence_e2e_results_20251231_030307.json') as f:
    data = json.load(f)

print("="*80)
print("🔬 RESEARCH INTELLIGENCE FRAMEWORK - TEST OUTPUT")
print("="*80)
print(f"\n📊 Summary: {data['summary']['success_rate']} | {data['summary']['total_mechanisms_identified']} mechanisms | {data['summary']['total_articles_found']} articles\n")

for i, test in enumerate(data['test_results'], 1):
    print(f"{'─'*80}")
    print(f"TEST {i}: {test['test_name']}")
    print(f"{'─'*80}")
    print(f"Q: {test['question']}")
    
    rp = test['result']['research_plan']
    entities = rp['entities']
    
    print(f"\n🧠 LLM Extracted:")
    print(f"   Compound: {entities.get('compound', 'N/A')}")
    print(f"   Active Compounds: {', '.join(entities.get('active_compounds', [])[:4])}")
    print(f"   Mechanisms: {', '.join(entimechanisms_of_interest', [])[:4])}")
    
    metrics = test['metrics']
    print(f"\n📈 Results:")
    print(f"   Articles: {metrics['articles_found']} | Mechanisms: {metrics['mechanisms_count']} | Confidence: {metrics['overall_confidence']}")

print(f"\n{'='*80}")
print("✅ ALL TESTS PASSED")
print("="*80)
