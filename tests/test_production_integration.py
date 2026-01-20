#!/usr/bin/env python3
"""
Production Integration Test for CLINICAL_MASTER.md capabilities.

Tests:
1. Holistic Score (Mechanism Fit + Eligibility + PGx Safety)
2. Trial Matching with Status Preserved
3. PGx Screening for Drug Safety
4. MoA Vector Coverage
5. Complete Care Flow

Run with: python tests/test_production_integration.py
"""

import asyncio
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


async def test_holistic_score():
    """Test holistic score service standalone."""
    from api.services.holistic_score_service import get_holistic_score_service
    service = get_holistic_score_service()
    
    patient = {
        'disease': 'Ovarian Cancer',
        'mechanism_vector': [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0],
        'germline_variants': [{'gene': 'DPYD', 'variant': '*2A'}]
    }
    trial = {
        'nct_id': 'NCT-PARP-001',
        'moa_vector': {'ddr': 0.95, 'mapk': 0.0, 'pi3k': 0.0, 'vegf': 0.0, 'her2': 0.0, 'io': 0.0, 'efflux': 0.0},
        'overall_status': 'RECRUITING',
        'conditions': ['Ovarian Cancer'],
        'interventions': [{'drug_names': ['olaparib']}]
    }
    
    result = await service.compute_holistic_score(patient, trial)
    
    assert result.holistic_score > 0.9, f'Expected >0.9, got {result.holistic_score}'
    assert result.interpretation == 'HIGH', f'Expected HIGH, got {result.interpretation}'
    
    return {
        'holistic_score': result.holistic_score,
        'interpretation': result.interpretation,
        'mechanism_fit': result.mechanism_fit_score,
        'eligibility': result.eligibility_score,
        'pgx_safety': result.pgx_safety_score
    }


async def test_trial_matching():
    """Test trial matching E2E with holistic scores."""
    from scripts.trials.production.core.matching_agent import match_patient_to_trials
    
    patient_profile = {
        'disease': 'Ovarian Cancer',
        'mechanism_vector': [0.88, 0.12, 0.15, 0.10, 0.05, 0.2, 0.0],
        'germline_variants': [{'gene': 'DPYD', 'variant': '*2A'}]
    }
    
    result = await match_patient_to_trials(patient_profile, max_results=5)
    matches = result.get('matches', [])
    
    assert result.get('total_candidates', 0) > 0, 'No candidates discovered'
    assert len(matches) > 0, 'No matches returned'
    
    # Check status is preserved
    has_real_status = any(
        m.get('overall_status') in ['RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING'] 
        for m in matches
    )
    assert has_real_status, 'Status not preserved from discovery'
    
    # Check holistic scores computed
    has_holistic = all(isinstance(m.get('holistic_score'), (int, float)) for m in matches)
    assert has_holistic, 'Holistic scores not computed'
    
    return {
        'total_candidates': result.get('total_candidates', 0),
        'matches': len(matches),
        'status_preserved': has_real_status,
        'holistic_computed': has_holistic,
        'top_3': [
            {
                'nct_id': m.get('nct_id'),
                'status': m.get('overall_status'),
                'holistic': m.get('holistic_score'),
                'interpretation': m.get('holistic_interpretation')
            }
            for m in matches[:3]
        ]
    }


async def test_pgx_screening():
    """Test PGx screening service."""
    from api.services.pgx_screening_service import PGxScreeningService
    pgx = PGxScreeningService()
    
    # Correct format: list of dicts with "name" field
    drugs = [
        {'name': '5-fluorouracil'},
        {'name': 'olaparib'},
        {'name': 'capecitabine'}
    ]
    variants = [{'gene': 'DPYD', 'variant': '*2A'}]
    
    result = await pgx.screen_drugs(drugs, variants)
    
    assert len(result) == 3, f'Expected 3 drugs, got {len(result)}'
    
    # 5-FU and capecitabine should have DPYD warnings
    fu_result = result.get('5-fluorouracil', {})
    assert fu_result.get('screened') == True, '5-FU not screened'
    assert fu_result.get('toxicity_tier') in ['HIGH', 'MODERATE'], f'Expected HIGH/MODERATE for 5-FU'
    
    return {
        'drugs_screened': len(result),
        'results': {
            drug: {
                'tier': r.get('toxicity_tier'),
                'adjustment': r.get('adjustment_factor')
            }
            for drug, r in result.items()
        }
    }


def test_moa_coverage():
    """Test MoA vector coverage."""
    moa_path = Path('api/resources/trial_moa_vectors.json')
    assert moa_path.exists(), 'MoA vectors file not found'
    
    with open(moa_path) as f:
        moa_vectors = json.load(f)
    
    assert len(moa_vectors) >= 500, f'Expected >=500 vectors, got {len(moa_vectors)}'
    
    # Check vector format
    sample = list(moa_vectors.values())[0]
    assert 'moa_vector' in sample, 'moa_vector field missing'
    expected_keys = {'ddr', 'mapk', 'pi3k', 'vegf', 'her2', 'io', 'efflux'}
    actual_keys = set(sample['moa_vector'].keys())
    assert expected_keys == actual_keys, f'Vector keys mismatch: {actual_keys}'
    
    return {
        'total_vectors': len(moa_vectors),
        'vector_keys': list(sample['moa_vector'].keys())
    }


async def run_all_tests():
    """Run all production integration tests."""
    print('=' * 70)
    print('PRODUCTION INTEGRATION TEST - CLINICAL_MASTER.md')
    print('=' * 70)
    
    results = {'passed': 0, 'failed': 0, 'tests': {}}
    
    # Test 1: Holistic Score
    print('\n[1/4] Holistic Score Service...')
    try:
        result = await test_holistic_score()
        print(f'   Holistic: {result["holistic_score"]} ({result["interpretation"]})')
        print(f'   Mech: {result["mechanism_fit"]}, Elig: {result["eligibility"]}, PGx: {result["pgx_safety"]}')
        print('   PASS')
        results['passed'] += 1
        results['tests']['holistic_score'] = {'status': 'PASS', 'data': result}
    except Exception as e:
        print(f'   FAIL: {e}')
        results['failed'] += 1
        results['tests']['holistic_score'] = {'status': 'FAIL', 'error': str(e)}
    
    # Test 2: Trial Matching
    print('\n[2/4] Trial Matching E2E...')
    try:
        result = await test_trial_matching()
        print(f'   Candidates: {result["total_candidates"]}')
        print(f'   Matches: {result["matches"]}')
        print(f'   Status preserved: {result["status_preserved"]}')
        for trial in result['top_3']:
            print(f'     - {trial["nct_id"]}: {trial["status"]}, holistic={trial["holistic"]}')
        print('   PASS')
        results['passed'] += 1
        results['tests']['trial_matching'] = {'status': 'PASS', 'data': result}
    except Exception as e:
        print(f'   FAIL: {e}')
        results['failed'] += 1
        results['tests']['trial_matching'] = {'status': 'FAIL', 'error': str(e)}
    
    # Test 3: PGx Screening
    print('\n[3/4] PGx Screening...')
    try:
        result = await test_pgx_screening()
        print(f'   Drugs screened: {result["drugs_screened"]}')
        for drug, data in result['results'].items():
            print(f'     - {drug}: {data["tier"]} (adj: {data["adjustment"]})')
        print('   PASS')
        results['passed'] += 1
        results['tests']['pgx_screening'] = {'status': 'PASS', 'data': result}
    except Exception as e:
        print(f'   FAIL: {e}')
        results['failed'] += 1
        results['tests']['pgx_screening'] = {'status': 'FAIL', 'error': str(e)}
    
    # Test 4: MoA Coverage
    print('\n[4/4] MoA Vector Coverage...')
    try:
        result = test_moa_coverage()
        print(f'   Total vectors: {result["total_vectors"]}')
        print(f'   Keys: {result["vector_keys"]}')
        print('   PASS')
        results['passed'] += 1
        results['tests']['moa_coverage'] = {'status': 'PASS', 'data': result}
    except Exception as e:
        print(f'   FAIL: {e}')
        results['failed'] += 1
        results['tests']['moa_coverage'] = {'status': 'FAIL', 'error': str(e)}
    
    # Summary
    print('\n' + '=' * 70)
    print('RESULTS SUMMARY')
    print('=' * 70)
    print(f'Passed: {results["passed"]}/4')
    print(f'Failed: {results["failed"]}/4')
    
    for test_name, test_result in results['tests'].items():
        icon = 'OK' if test_result['status'] == 'PASS' else 'XX'
        print(f'  [{icon}] {test_name}: {test_result["status"]}')
    
    if results['failed'] == 0:
        print('\n✅ PRODUCTION READY')
    else:
        print('\n❌ NOT PRODUCTION READY - FIX FAILURES')
    
    return results


if __name__ == '__main__':
    results = asyncio.run(run_all_tests())
    sys.exit(0 if results['failed'] == 0 else 1)
