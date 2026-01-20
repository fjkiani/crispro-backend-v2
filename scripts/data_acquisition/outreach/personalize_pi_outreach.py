#!/usr/bin/env python3
"""Personalize PI Outreach - Extract Intelligence and Create Targeted Messages"""

import json
import requests
from pathlib import Path
from datetime import datetime
import time

output_dir = Path('/Users/fahadkiani/Desktop/development/crispr-assistant-main/oncology-coPilot/oncology-backend-minimal/data/kelim_resurrection/s4_deliverables')

print("=" * 80)
print("Personalizing Outreach - Extracting PI Intelligence")
print("=" * 80)

# Load PI contacts
with open(output_dir / 'ctgov_pi_contacts.json', 'r') as f:
    pi_data = json.load(f)

pi_contacts = pi_data.get('pi_contacts', [])

print(f"\n📋 Processing {len(pi_contacts)} PIs...")

personalized_profiles = []

for i, contact in enumerate(pi_contacts[:15], 1):  # Process first 15
    pi_name = contact.get('pi_name', '')
    nct_id = contact.get('nct_id', '')
    institution = contact.get('pi_institution', '')
    
    print(f"\n[{i}/15] Researching: {pi_name}")
    print(f"   Institution: {institution}")
    
    profile = {
        'pi_name': pi_name,
        'institution': institution,
        'nct_id': nct_id,
        'research_focus': [],
        'publications': [],
        'trial_details': {},
        'kelim_fit': {},
        'personalized_value_prop': '',
        'outreach_angle': '',
        'email_template': ''
    }
    
    # 1. Get detailed trial information
    print(f"   🔍 Fetching trial details...")
    try:
        trial_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
        response = requests.get(trial_url, params={'format': 'json'}, timeout=15)
        if response.status_code == 200:
            trial_data = response.json()
            protocol = trial_data.get('protocolSection', {})
            
            ident = protocol.get('identificationModule', {})
            design = protocol.get('designModule', {})
            arms = protocol.get('armsInterventionsModule', {})
            conditions = protocol.get('conditionsModule', {})
            eligibility = protocol.get('eligibilityModule', {})
            
            profile['trial_details'] = {
                'title': ident.get('briefTitle', ''),
                'official_title': ident.get('officialTitle', ''),
                'phase': design.get('phases', []),
                'study_type': design.get('studyType', ''),
                'enrollment': design.get('enrollment', {}),
                'interventions': [i.get('name', '') for i in arms.get('interventions', [])],
                'conditions': conditions.get('conditions', []),
                'primary_outcome': [o.get('measure', '') for o in design.get('primaryOutcomeMeasures', [])],
                'secondary_outcome': [o.get('measure', '') for o in design.get('secondaryOutcomeMeasures', [])]
            }
            
            print(f"      ✅ {profile['trial_details']['title'][:50]}...")
            
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
    
    # 2. Search PubMed for publications
    print(f"   🔍 Searching PubMed...")
    try:
        # Extract first and last name for search
        name_parts = pi_name.split(',')[0].split() if ',' in pi_name else pi_name.split()
        if len(name_parts) >= 2:
            last_name = name_parts[-1]
            first_initial = name_parts[0][0] if name_parts else ''
            search_term = f'{last_name} {first_initial}[Author] AND (ovarian[Title/Abstract] OR "CA-125"[Title/Abstract] OR platinum[Title/Abstract])'
        else:
            search_term = f'"{pi_name}"[Author] AND ovarian[Title/Abstract]'
        
        search_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={search_term}&retmax=5&retmode=json"
        response = requests.get(search_url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            pmids = data.get('esearchresult', {}).get('idlist', [])
            
            if pmids:
                print(f"      ✅ Found {len(pmids)} publications")
                profile['publications'] = pmids
                
                # Get title of first publication
                if pmids:
                    fetch_url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmids[0]}&retmode=json"
                    pub_response = requests.get(fetch_url, timeout=10)
                    if pub_response.status_code == 200:
                        pub_data = pub_response.json()
                        result = pub_data.get('result', {}).get(pmids[0], {})
                        profile['research_focus'] = [
                            result.get('title', ''),
                            result.get('source', ''),
                            result.get('pubdate', '')
                        ]
    except Exception as e:
        print(f"      ⚠️  Error: {e}")
    
    # 3. Analyze KELIM fit
    trial_details = profile.get('trial_details', {})
    interventions = trial_details.get('interventions', [])
    outcomes = trial_details.get('primary_outcome', []) + trial_details.get('secondary_outcome', [])
    
    fit_reasons = []
    if any('platinum' in str(i).lower() for i in interventions):
        fit_reasons.append("Uses platinum-based therapy")
    if any('ca-125' in str(o).lower() or 'ca125' in str(o).lower() for o in outcomes):
        fit_reasons.append("Monitors CA-125 as outcome")
    if trial_details.get('conditions') and any('ovarian' in str(c).lower() for c in trial_details.get('conditions', [])):
        fit_reasons.append("Ovarian cancer focus")
    
    profile['kelim_fit'] = {
        'is_relevant': len(fit_reasons) > 0,
        'fit_reasons': fit_reasons,
        'fit_score': len(fit_reasons)
    }
    
    # 4. Create personalized value proposition
    value_points = []
    
    if profile.get('research_focus') and profile['research_focus'][0]:
        pub_title = profile['research_focus'][0][:60]
        value_points.append(f"Your research on {pub_title}... aligns with KELIM validation")
    
    if fit_reasons:
        value_points.append(f"Your trial's {fit_reasons[0]} makes it ideal for validation")
    
    if trial_details.get('phase'):
        phases = trial_details.get('phase', [])
        if any('3' in str(p) for p in phases):
            value_points.append("Phase 3 data would provide robust validation evidence")
    
    profile['personalized_value_prop'] = ' '.join(value_points) if value_points else "Your trial involves CA-125 monitoring"
    
    # 5. Create outreach angle
    if profile.get('research_focus') and profile['research_focus'][0]:
        angle = f"Building on your work on {profile['research_focus'][0][:50]}..."
    elif fit_reasons:
        angle = f"Your trial's {fit_reasons[0]} makes it ideal for KELIM validation"
    else:
        angle = "Your expertise in ovarian cancer trials"
    
    profile['outreach_angle'] = angle
    
    # 6. Generate personalized email
    email = f"""Subject: KELIM Biomarker Validation - Collaboration Opportunity

Dear Dr. {pi_name.split(',')[0] if ',' in pi_name else pi_name.split()[0]},

{angle}, I am reaching out regarding a research collaboration opportunity for validating the KELIM (CA-125 elimination rate) biomarker for predicting platinum resistance in ovarian cancer.

**Why Your Trial is Ideal:**
{chr(10).join(['- ' + reason for reason in fit_reasons[:3]])}

**What We Need:**
- Serial CA-125 measurements (≥2 per patient)
- Platinum-free interval (PFI) outcomes
- 50-100 patients minimum

**Benefits:**
- Co-authorship on validation publication
- Access to validated biomarker for your research
- Contribution to advancing ovarian cancer treatment

I noticed your trial "{trial_details.get('title', 'N/A')}" (NCT{nct_id}) involves CA-125 monitoring, which makes it an ideal candidate for this validation study.

We would be happy to discuss data sharing agreements, IRB considerations, and co-authorship details.

Thank you for your consideration.

Best regards,
[Your Name]
"""
    
    profile['email_template'] = email
    
    personalized_profiles.append(profile)
    time.sleep(0.5)  # Rate limiting

# Save
output_file = output_dir / 'personalized_pi_profiles.json'
with open(output_file, 'w') as f:
    json.dump({'profiles': personalized_profiles, 'date': datetime.now().isoformat()}, f, indent=2)

print(f"\n{'='*80}")
print("✅ PERSONALIZATION COMPLETE")
print(f"{'='*80}")
print(f"\n📊 Summary:")
print(f"   - Profiles: {len(personalized_profiles)}")
print(f"   - With publications: {len([p for p in personalized_profiles if p.get('publications')])}")
print(f"   - High fit: {len([p for p in personalized_profiles if p.get('kelim_fit', {}).get('is_relevant')])}")
print(f"\n💾 Saved to: {output_file}")





