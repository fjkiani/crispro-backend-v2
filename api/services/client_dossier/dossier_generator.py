"""
Dossier Generator - Main orchestrator for generating 10-section oncologist dossiers.

JR2's core service that coordinates all components.
"""
from typing import Dict, Any, List
from datetime import datetime
import logging
import json
from pathlib import Path

from .trial_querier import get_trials_from_sqlite
from .trial_scraper import scrape_trial_page
from .trial_filter import filter_50_candidates

logger = logging.getLogger(__name__)

# Drug mechanism database (pre-populated with 20 common ovarian cancer drugs)
DRUG_MECHANISM_DB = {
    "carboplatin": {
        "mechanism": "Platinum-based alkylating agent. Forms DNA cross-links, causing double-strand breaks and apoptosis.",
        "layman": "A chemotherapy drug that damages cancer cell DNA, preventing cell division.",
        "evidence_tier": "STANDARD"
    },
    "paclitaxel": {
        "mechanism": "Microtubule stabilizer. Binds to β-tubulin, preventing microtubule depolymerization and blocking mitosis.",
        "layman": "A chemotherapy drug that stops cancer cells from dividing by freezing their internal skeleton.",
        "evidence_tier": "STANDARD"
    },
    "bevacizumab": {
        "mechanism": "Anti-VEGF monoclonal antibody. Blocks vascular endothelial growth factor, inhibiting angiogenesis.",
        "layman": "A targeted therapy that starves tumors by cutting off their blood supply.",
        "evidence_tier": "SUPPORTED"
    },
    "olaparib": {
        "mechanism": "PARP inhibitor. Traps PARP on DNA, causing synthetic lethality in HRD+ cells.",
        "layman": "A targeted therapy that exploits DNA repair defects in cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "niraparib": {
        "mechanism": "PARP inhibitor. Similar to olaparib, causes synthetic lethality in HRD+ cells.",
        "layman": "A targeted therapy that exploits DNA repair defects in cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "pembrolizumab": {
        "mechanism": "Anti-PD-1 checkpoint inhibitor. Blocks PD-1/PD-L1 interaction, restoring T-cell function.",
        "layman": "An immunotherapy that helps your immune system recognize and attack cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "dostarlimab": {
        "mechanism": "Anti-PD-1 checkpoint inhibitor. Similar to pembrolizumab.",
        "layman": "An immunotherapy that helps your immune system recognize and attack cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "mirvetuximab soravtansine": {
        "mechanism": "FRα-targeted ADC. Delivers cytotoxic payload (DM4) to FRα-expressing cells.",
        "layman": "A targeted chemotherapy that delivers poison directly to cancer cells with a specific marker.",
        "evidence_tier": "SUPPORTED"
    },
    "tisotumab vedotin": {
        "mechanism": "Tissue factor-targeted ADC. Delivers MMAE to TF-expressing cells.",
        "layman": "A targeted chemotherapy that delivers poison directly to cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "rucaparib": {
        "mechanism": "PARP inhibitor. Similar to olaparib/niraparib.",
        "layman": "A targeted therapy that exploits DNA repair defects in cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "talazoparib": {
        "mechanism": "PARP inhibitor. Most potent PARP trapper, causes synthetic lethality in HRD+ cells.",
        "layman": "A targeted therapy that exploits DNA repair defects in cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "avelumab": {
        "mechanism": "Anti-PD-L1 checkpoint inhibitor. Blocks PD-1/PD-L1 interaction.",
        "layman": "An immunotherapy that helps your immune system recognize and attack cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "durvalumab": {
        "mechanism": "Anti-PD-L1 checkpoint inhibitor. Similar to avelumab.",
        "layman": "An immunotherapy that helps your immune system recognize and attack cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "atezolizumab": {
        "mechanism": "Anti-PD-L1 checkpoint inhibitor. Similar to durvalumab.",
        "layman": "An immunotherapy that helps your immune system recognize and attack cancer cells.",
        "evidence_tier": "SUPPORTED"
    },
    "ipilimumab": {
        "mechanism": "Anti-CTLA-4 checkpoint inhibitor. Blocks CTLA-4, enhancing T-cell activation.",
        "layman": "An immunotherapy that boosts your immune system's ability to attack cancer.",
        "evidence_tier": "SUPPORTED"
    },
    "tremelimumab": {
        "mechanism": "Anti-CTLA-4 checkpoint inhibitor. Similar to ipilimumab.",
        "layman": "An immunotherapy that boosts your immune system's ability to attack cancer.",
        "evidence_tier": "SUPPORTED"
    },
    "gemcitabine": {
        "mechanism": "Nucleoside analog. Incorporates into DNA during replication, causing chain termination.",
        "layman": "A chemotherapy drug that tricks cancer cells into using fake DNA building blocks.",
        "evidence_tier": "STANDARD"
    },
    "topotecan": {
        "mechanism": "Topoisomerase I inhibitor. Prevents DNA unwinding during replication.",
        "layman": "A chemotherapy drug that tangles cancer cell DNA, preventing cell division.",
        "evidence_tier": "STANDARD"
    },
    "doxorubicin": {
        "mechanism": "Anthracycline. Intercalates into DNA and inhibits topoisomerase II.",
        "layman": "A chemotherapy drug that damages cancer cell DNA.",
        "evidence_tier": "STANDARD"
    },
    "cyclophosphamide": {
        "mechanism": "Alkylating agent. Forms DNA cross-links, causing apoptosis.",
        "layman": "A chemotherapy drug that damages cancer cell DNA.",
        "evidence_tier": "STANDARD"
    }
}

def get_drug_mechanism(drug_name: str) -> Dict[str, str]:
    """
    Get drug mechanism with 3-tier fallback.
    
    Tier 1: DRUG_MECHANISM_DB
    Tier 2: EnhancedEvidenceService (future)
    Tier 3: Flag for Zo review
    """
    drug_lower = drug_name.lower()
    
    # Check exact match
    if drug_lower in DRUG_MECHANISM_DB:
        return DRUG_MECHANISM_DB[drug_lower]
    
    # Check partial match
    for db_drug, mechanism in DRUG_MECHANISM_DB.items():
        if db_drug in drug_lower or drug_lower in db_drug:
            return mechanism
    
    # Tier 3: Flag for review
    return {
        "mechanism": f"[NEEDS VERIFICATION] Mechanism not found in database for {drug_name}",
        "layman": f"[NEEDS VERIFICATION] Please consult oncologist for mechanism explanation.",
        "evidence_tier": "UNKNOWN"
    }

def generate_eligibility_table(trial: Dict[str, Any], patient_profile: Dict[str, Any], scraped_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate eligibility criteria table (pass/fail/pending).
    
    Returns list of criteria with assessment.
    """
    criteria = []
    
    # Disease match
    from .trial_filter import assess_disease_match, assess_treatment_line_match, assess_biomarker_match, assess_location_match
    
    disease_match, disease_conf, disease_reason = assess_disease_match(trial, patient_profile['disease'])
    criteria.append({
        'criterion': 'Disease Match',
        'status': 'PASS' if disease_match else 'FAIL',
        'confidence': disease_conf,
        'notes': disease_reason
    })
    
    # Treatment line
    line_match, line_conf, line_reason = assess_treatment_line_match(trial, patient_profile.get('treatment_line', 'first-line'))
    criteria.append({
        'criterion': 'Treatment Line',
        'status': 'PASS' if line_match else 'FAIL',
        'confidence': line_conf,
        'notes': line_reason
    })
    
    # Biomarkers
    biomarker_match, biomarker_conf, pending_gates, biomarker_reason = assess_biomarker_match(
        trial, patient_profile.get('biomarkers', {})
    )
    criteria.append({
        'criterion': 'Biomarker Requirements',
        'status': 'PASS' if biomarker_match else 'PENDING' if pending_gates else 'FAIL',
        'confidence': biomarker_conf,
        'notes': biomarker_reason,
        'pending_tests': pending_gates
    })
    
    # Location
    location_match, location_conf, location_reason = assess_location_match(trial, patient_profile.get('location', 'NYC'))
    criteria.append({
        'criterion': 'Location (NYC Metro)',
        'status': 'PASS' if location_match else 'FAIL',
        'confidence': location_conf,
        'notes': location_reason
    })
    
    # Parse inclusion/exclusion from scraped data
    inclusion_text = scraped_data.get('inclusion_criteria_full', '')
    exclusion_text = scraped_data.get('exclusion_criteria_full', '')
    
    # Add key inclusion criteria
    if inclusion_text:
        criteria.append({
            'criterion': 'Inclusion Criteria (Full Text Available)',
            'status': 'REVIEW',
            'confidence': 0.8,
            'notes': f'See full text: {inclusion_text[:200]}...'
        })
    
    if exclusion_text:
        criteria.append({
            'criterion': 'Exclusion Criteria (Full Text Available)',
            'status': 'REVIEW',
            'confidence': 0.8,
            'notes': f'See full text: {exclusion_text[:200]}...'
        })
    
    return criteria

def generate_strategic_scenarios(trial: Dict[str, Any], patient_profile: Dict[str, Any], eligibility_table: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate 3 strategic scenarios: Best-Case, Most-Likely, Challenge.
    
    Returns scenarios with eligibility probability.
    """
    # Calculate eligibility probability
    pass_count = sum(1 for c in eligibility_table if c['status'] == 'PASS')
    pending_count = sum(1 for c in eligibility_table if c['status'] == 'PENDING')
    total_criteria = len(eligibility_table)
    
    base_probability = pass_count / total_criteria if total_criteria > 0 else 0.0
    
    # Best-case: All pending tests pass
    best_case_prob = (pass_count + pending_count) / total_criteria if total_criteria > 0 else 0.0
    
    # Most-likely: 50% of pending tests pass
    most_likely_prob = (pass_count + pending_count * 0.5) / total_criteria if total_criteria > 0 else 0.0
    
    # Challenge: Some pending tests fail
    challenge_prob = pass_count / total_criteria if total_criteria > 0 else 0.0
    
    return {
        'best_case': {
            'probability': best_case_prob,
            'scenario': 'All pending biomarker tests return favorable results',
            'eligibility': 'HIGH'
        },
        'most_likely': {
            'probability': most_likely_prob,
            'scenario': '50% of pending tests pass, some may require additional screening',
            'eligibility': 'MODERATE'
        },
        'challenge': {
            'probability': challenge_prob,
            'scenario': 'Some pending tests fail, may need alternative trials',
            'eligibility': 'LOW'
        }
    }

def generate_tactical_recommendations(eligibility_table: List[Dict[str, Any]], patient_profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Generate actionable recommendations based on pending gates.
    
    Returns list of recommendations with labs, costs, timelines.
    """
    recommendations = []
    
    # Check for pending gates
    for criterion in eligibility_table:
        if criterion.get('status') == 'PENDING':
            pending_tests = criterion.get('pending_tests', [])
            for test in pending_tests:
                if 'HRD' in test:
                    recommendations.append({
                        'action': 'Order HRD Test (MyChoice CDx)',
                        'lab': 'Myriad Genetics',
                        'cost': '$4,000-$6,000',
                        'timeline': '10-14 days',
                        'priority': 'HIGH',
                        'rationale': 'Required for PARP inhibitor trials'
                    })
                elif 'BRCA' in test:
                    recommendations.append({
                        'action': 'Order BRCA Germline Test',
                        'lab': 'Myriad Genetics or Invitae',
                        'cost': '$250-$500',
                        'timeline': '7-10 days',
                        'priority': 'MEDIUM',
                        'rationale': 'Required for BRCA+ trials'
                    })
                elif 'TMB' in test:
                    recommendations.append({
                        'action': 'Order TMB Test (FoundationOne CDx)',
                        'lab': 'Foundation Medicine',
                        'cost': '$5,000-$7,000',
                        'timeline': '7-10 days',
                        'priority': 'HIGH',
                        'rationale': 'Required for immunotherapy trials'
                    })
                elif 'MSI' in test:
                    recommendations.append({
                        'action': 'Order MSI Test',
                        'lab': 'Foundation Medicine or Tempus',
                        'cost': '$500-$1,000',
                        'timeline': '7-10 days',
                        'priority': 'MEDIUM',
                        'rationale': 'Required for MSI-High trials'
                    })
                elif 'HER2' in test:
                    recommendations.append({
                        'action': 'Order HER2 IHC Test',
                        'lab': 'Local pathology lab',
                        'cost': '$200-$500',
                        'timeline': '3-5 days',
                        'priority': 'MEDIUM',
                        'rationale': 'Required for HER2-targeted trials'
                    })
    
    # If no pending gates, add general recommendation
    if not recommendations:
        recommendations.append({
            'action': 'Proceed with trial enrollment',
            'lab': 'N/A',
            'cost': 'N/A',
            'timeline': 'Immediate',
            'priority': 'HIGH',
            'rationale': 'All eligibility criteria met'
        })
    
    return recommendations

async def generate_dossier(nct_id: str, patient_profile: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate complete 10-section dossier for a trial.
    
    Args:
        nct_id: NCT identifier
        patient_profile: Patient data
    
    Returns:
        Complete dossier dictionary
    """
    logger.info(f"⚔️ Generating dossier for {nct_id}")
    
    # Step 1: Get trial from SQLite
    all_trials = get_trials_from_sqlite()
    # Try both 'id' and 'nct_id' fields (trials table uses 'id')
    trial = next((t for t in all_trials if t.get('id') == nct_id or t.get('nct_id') == nct_id), None)
    if not trial:
        raise ValueError(f"Trial {nct_id} not found in database (searched {len(all_trials)} trials)")
    
    # Step 2: Scrape full trial page
    scraped_data = await scrape_trial_page(nct_id)
    
    # Step 3: Generate eligibility table
    eligibility_table = generate_eligibility_table(trial, patient_profile, scraped_data)
    
    # Step 4: Generate strategic scenarios
    scenarios = generate_strategic_scenarios(trial, patient_profile, eligibility_table)
    
    # Step 5: Generate tactical recommendations
    recommendations = generate_tactical_recommendations(eligibility_table, patient_profile)
    
    # Step 6: Get S/P/E efficacy predictions (if mutations available)
    efficacy_analysis = None
    if patient_profile.get('mutations'):
        try:
            from api.services.efficacy_orchestrator.orchestrator import EfficacyOrchestrator
            from api.services.efficacy_orchestrator.models import EfficacyRequest
            
            orchestrator = EfficacyOrchestrator()
            efficacy_request = EfficacyRequest(
                mutations=patient_profile['mutations'],
                model_id="evo2_1b",
                disease=patient_profile.get('disease', 'ovarian_cancer'),
                options={
                    'ablation_mode': 'SPE',
                    'adaptive': True
                },
                api_base="http://127.0.0.1:8000"
            )
            
            efficacy_response = await orchestrator.predict(efficacy_request)
            
            # Extract top 5 drugs with S/P/E breakdown
            top_drugs = sorted(efficacy_response.drugs, key=lambda d: d.confidence, reverse=True)[:5]
            efficacy_analysis = {
                'top_drugs': [
                    {
                        'name': drug.name,
                        'efficacy_score': drug.efficacy_score,
                        'confidence': drug.confidence,
                        'evidence_tier': drug.evidence_tier,
                        'badges': drug.badges,
                        'rationale': drug.rationale[:2] if drug.rationale else []  # Top 2 rationale points
                    }
                    for drug in top_drugs
                ],
                'run_signature': efficacy_response.run_signature,
                'scoring_strategy': efficacy_response.scoring_strategy,
                'evidence_tier': efficacy_response.evidence_tier,
                'provenance': efficacy_response.provenance
            }
            logger.info(f"✅ Efficacy predictions generated for {len(top_drugs)} drugs")
        except Exception as e:
            logger.warning(f"⚠️  Efficacy prediction failed: {e}, continuing without efficacy analysis")
            efficacy_analysis = None
    
    # Step 7: Get drug mechanisms
    interventions = scraped_data.get('interventions', [])
    if isinstance(interventions, str):
        # If it's a string, try to parse it
        try:
            interventions = json.loads(interventions)
        except:
            interventions = [interventions] if interventions else []
    
    drug_mechanisms = {}
    for intervention in interventions:
        # Extract drug name (simple parsing)
        if not intervention or not isinstance(intervention, str):
            continue
        intervention_clean = intervention.strip()
        if not intervention_clean:
            continue
        parts = intervention_clean.split()
        drug_name = parts[0] if parts else ""
        if drug_name:
            drug_mechanisms[drug_name] = get_drug_mechanism(drug_name)
    
    # Step 7: Build complete dossier
    dossier = {
        'nct_id': nct_id,
        'trial_title': trial.get('title', ''),
        'patient_id': patient_profile.get('patient_id', 'unknown'),
        'generated_at': datetime.now().isoformat(),
        'sections': {
            '1_trial_overview': {
                'title': trial.get('title', ''),
                'phase': trial.get('phase', ''),
                'status': trial.get('status', ''),
                'sponsor': trial.get('sponsor_name', ''),
                'estimated_enrollment': trial.get('estimated_enrollment', 0),
                'primary_endpoint': scraped_data.get('primary_endpoint', '')
            },
            '2_eligibility_assessment': {
                'table': eligibility_table,
                'summary': f"{sum(1 for c in eligibility_table if c['status'] == 'PASS')}/{len(eligibility_table)} criteria met"
            },
            '3_strategic_scenarios': scenarios,
            '4_tactical_recommendations': recommendations,
            '5_drug_mechanisms': drug_mechanisms,
            '6_drug_efficacy_analysis': efficacy_analysis if efficacy_analysis else {'status': 'not_available', 'reason': 'No mutations provided'},
            '7_location_details': scraped_data.get('locations_full', []),
            '8_timeline': {
                'study_start': scraped_data.get('study_start_date', ''),
                'primary_completion': scraped_data.get('primary_completion_date', '')
            },
            '9_full_eligibility_text': {
                'inclusion_criteria': scraped_data.get('inclusion_criteria_full', '') or trial.get('inclusion_criteria', ''),
                'exclusion_criteria': scraped_data.get('exclusion_criteria_full', '') or trial.get('exclusion_criteria', '')
            },
            '10_contact_information': trial.get('locations_data', []),
            '11_provenance': {
                'generated_by': 'JR2',
                'data_sources': ['SQLite', 'Diffbot', 'DRUG_MECHANISM_DB'],
                'confidence_flags': ['[INFERRED]', '[NEEDS VERIFICATION]']
            }
        }
    }
    
    logger.info(f"✅ Dossier generated for {nct_id}")
    return dossier

