"""Audit script for MoA vectors quality and completeness."""
import json
from pathlib import Path
from collections import defaultdict

def audit_moa_vectors():
    """Audit the MoA vectors file for quality and completeness."""
    output_file = Path(__file__).parent.parent.parent / "api" / "resources" / "trial_moa_vectors.json"
    
    if not output_file.exists():
        print("❌ Output file not found!")
        return
    
    with open(output_file, "r") as f:
        vectors = json.load(f)
    
    print("=" * 60)
    print("🔍 MoA Vectors Audit Report")
    print("=" * 60)
    print(f"\n✅ Total MoA vectors in file: {len(vectors)}")
    
    # Sample structure check
    print("\n📊 Sample structure check:")
    print("-" * 60)
    sample_keys = list(vectors.keys())[:3]
    for nct_id in sample_keys:
        vector = vectors[nct_id]
        print(f"\n🔬 {nct_id}:")
        print(f"   Source: {vector.get('source', 'unknown')}")
        print(f"   Confidence: {vector.get('confidence', 0.0):.2f}")
        prov = vector.get("provenance", {})
        print(f"   Provider: {prov.get('provider', 'unknown')}")
        print(f"   Model: {prov.get('model', 'unknown')}")
        primary_moa = prov.get('primary_moa', 'unknown')[:60]
        print(f"   Primary MoA: {primary_moa}")
        
        # Check MoA vector structure
        moa = vector.get('moa_vector', {})
        pathways = ['ddr', 'mapk', 'pi3k', 'vegf', 'her2', 'io', 'efflux']
        active_pathways = [p for p in pathways if moa.get(p, 0.0) > 0.0]
        print(f"   Active pathways: {len(active_pathways)}/{len(pathways)}")
        if active_pathways:
            print(f"   Pathways: {active_pathways}")
    
    # Statistics
    print("\n" + "=" * 60)
    print("📈 Statistics:")
    print("-" * 60)
    
    sources = defaultdict(int)
    providers = defaultdict(int)
    confidences = []
    pathways_count = {'ddr': 0, 'mapk': 0, 'pi3k': 0, 'vegf': 0, 'her2': 0, 'io': 0, 'efflux': 0}
    total_pathways = 0
    pathways = ['ddr', 'mapk', 'pi3k', 'vegf', 'her2', 'io', 'efflux']
    
    for nct_id, vector in vectors.items():
        # Source statistics
        source = vector.get('source', 'unknown')
        sources[source] += 1
        
        # Provider statistics
        provider = vector.get('provenance', {}).get('provider', 'unknown')
        providers[provider] += 1
        
        # Confidence statistics
        conf = vector.get('confidence', 0.0)
        confidences.append(conf)
        
        # Pathway statistics
        moa = vector.get('moa_vector', {})
        for pathway in pathways_count.keys():
            if moa.get(pathway, 0.0) > 0.0:
                pathways_count[pathway] += 1
                total_pathways += 1
    
    print(f"\n📦 Sources:")
    for source, count in sorted(sources.items(), key=lambda x: x[1], reverse=True):
        print(f"   {source}: {count}")
    
    print(f"\n🤖 Providers:")
    for provider, count in sorted(providers.items(), key=lambda x: x[1], reverse=True):
        print(f"   {provider}: {count}")
    
    print(f"\n📊 Confidence scores:")
    if confidences:
        print(f"   Average: {sum(confidences)/len(confidences):.2f}")
        print(f"   Min: {min(confidences):.2f}")
        print(f"   Max: {max(confidences):.2f}")
        high_conf = len([c for c in confidences if c >= 0.7])
        print(f"   High confidence (≥0.7): {high_conf}/{len(confidences)} ({100*high_conf/len(confidences):.1f}%)")
    
    print(f"\n🧬 Pathway distribution:")
    for pathway, count in sorted(pathways_count.items(), key=lambda x: x[1], reverse=True):
        pct = 100 * count / len(vectors) if vectors else 0
        print(f"   {pathway.upper()}: {count} ({pct:.1f}%)")
    
    if vectors:
        print(f"\n✅ Average pathways per trial: {total_pathways/len(vectors):.2f}")
    
    # Quality checks
    print("\n" + "=" * 60)
    print("🔍 Quality checks:")
    print("-" * 60)
    
    issues = []
    checks_passed = 0
    total_checks = 0
    
    # Check 1: All vectors have required fields
    total_checks += 1
    missing_fields = []
    for nct_id, vector in vectors.items():
        if 'moa_vector' not in vector:
            missing_fields.append(nct_id)
        if 'confidence' not in vector:
            missing_fields.append(nct_id)
        if 'provenance' not in vector:
            missing_fields.append(nct_id)
    
    if missing_fields:
        issues.append(f"Missing required fields in {len(missing_fields)} vectors")
    else:
        checks_passed += 1
        print("✅ All vectors have required fields (moa_vector, confidence, provenance)")
    
    # Check 2: All MoA vectors have 7 pathways
    total_checks += 1
    incomplete_pathways = []
    for nct_id, vector in vectors.items():
        moa = vector.get('moa_vector', {})
        if len(moa) != 7:
            incomplete_pathways.append(nct_id)
        for pathway in pathways:
            if pathway not in moa:
                incomplete_pathways.append(nct_id)
    
    if incomplete_pathways:
        issues.append(f"Incomplete pathway vectors in {len(incomplete_pathways)} trials")
    else:
        checks_passed += 1
        print("✅ All MoA vectors have all 7 pathways defined")
    
    # Check 3: Pathway values are in valid range [0.0, 1.0]
    total_checks += 1
    invalid_values = []
    for nct_id, vector in vectors.items():
        moa = vector.get('moa_vector', {})
        for pathway, value in moa.items():
            try:
                val = float(value)
                if not (0.0 <= val <= 1.0):
                    invalid_values.append(f"{nct_id}:{pathway}={value}")
            except (ValueError, TypeError):
                invalid_values.append(f"{nct_id}:{pathway}={value} (invalid type)")
    
    if invalid_values:
        issues.append(f"Invalid pathway values in {len(invalid_values)} entries")
        if len(invalid_values) <= 10:
            for iv in invalid_values:
                print(f"   ⚠️  {iv}")
    else:
        checks_passed += 1
        print("✅ All pathway values are in valid range [0.0, 1.0]")
    
    # Check 4: Confidence values are in valid range [0.0, 1.0]
    total_checks += 1
    invalid_conf = []
    for nct_id, vector in vectors.items():
        conf = vector.get('confidence', 0.0)
        try:
            val = float(conf)
            if not (0.0 <= val <= 1.0):
                invalid_conf.append(f"{nct_id}:{conf}")
        except (ValueError, TypeError):
            invalid_conf.append(f"{nct_id}:{conf} (invalid type)")
    
    if invalid_conf:
        issues.append(f"Invalid confidence values in {len(invalid_conf)} vectors")
        if len(invalid_conf) <= 10:
            for ic in invalid_conf:
                print(f"   ⚠️  {ic}")
    else:
        checks_passed += 1
        print("✅ All confidence values are in valid range [0.0, 1.0]")
    
    # Check 5: All vectors have provider metadata
    total_checks += 1
    missing_provider = []
    for nct_id, vector in vectors.items():
        prov = vector.get('provenance', {}).get('provider')
        if not prov:
            missing_provider.append(nct_id)
    
    if missing_provider:
        issues.append(f"Missing provider metadata in {len(missing_provider)} vectors")
        if len(missing_provider) <= 10:
            for mp in missing_provider:
                print(f"   ⚠️  {mp}")
    else:
        checks_passed += 1
        print("✅ All vectors have provider metadata")
    
    # Check 6: All vectors have model metadata
    total_checks += 1
    missing_model = []
    for nct_id, vector in vectors.items():
        model = vector.get('provenance', {}).get('model')
        if not model:
            missing_model.append(nct_id)
    
    if missing_model:
        issues.append(f"Missing model metadata in {len(missing_model)} vectors")
        if len(missing_model) <= 10:
            for mm in missing_model:
                print(f"   ⚠️  {mm}")
    else:
        checks_passed += 1
        print("✅ All vectors have model metadata")
    
    # Check 7: All vectors have source checksum for change detection
    total_checks += 1
    missing_checksum = []
    for nct_id, vector in vectors.items():
        checksum = vector.get('provenance', {}).get('source_checksum')
        if not checksum:
            missing_checksum.append(nct_id)
    
    if missing_checksum:
        issues.append(f"Missing source checksum in {len(missing_checksum)} vectors")
    else:
        checks_passed += 1
        print("✅ All vectors have source checksum for change detection")
    
    # Summary
    print(f"\n📋 Summary: {checks_passed}/{total_checks} checks passed")
    
    if issues:
        print("\n⚠️  Issues found:")
        for issue in issues:
            print(f"   - {issue}")
    else:
        print("\n✅ No issues found - all quality checks passed!")
    
    print("\n" + "=" * 60)
    return checks_passed == total_checks

if __name__ == "__main__":
    success = audit_moa_vectors()
    exit(0 if success else 1)

