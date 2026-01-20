#!/usr/bin/env python3
"""
⚔️ ZO'S IMPROVED TRIAL INTELLIGENCE GENERATOR V2 ⚔️

Multi-Layer Filtering Architecture:
1. Hard Filters (status, disease, stage)
2. Trial Type Classification (interventional vs observational)
3. Location Filtering (NYC metro required)
4. LLM Pre-Screening (quick classification before full analysis)
5. Full LLM Analysis (only for trials that pass all filters)

Author: Zo (Lead Commander)
Date: November 15, 2025
"""

import json
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# Import LLM API
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src" / "tools"))
try:
    from llm_api import get_llm_chat_response
    LLM_AVAILABLE = True
    GEMINI_MODEL = "gemini-2.5-pro"
except ImportError:
    print("⚠️ Warning: LLM API not available. Trial fit analysis will be skipped.")
    LLM_AVAILABLE = False
    GEMINI_MODEL = None

# Import Ayesha profile
from ayesha_patient_profile import get_ayesha_complete_profile

# File paths
CANDIDATES_FILE = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "50_vector_candidates_for_jr2.json"
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / ".cursor" / "ayesha" / "zo_intelligence_reports_v2"

# NYC Metro zip codes (within 50 miles of 10029)
NYC_METRO_ZIPS = {
    'NY': ['10001', '10002', '10003', '10004', '10005', '10006', '10007', '10009', '10010', '10011', 
           '10012', '10013', '10014', '10016', '10017', '10018', '10019', '10020', '10021', '10022',
           '10023', '10024', '10025', '10026', '10027', '10028', '10029', '10030', '10031', '10032',
           '10033', '10034', '10035', '10036', '10037', '10038', '10039', '10040', '10044', '10065',
           '10069', '10075', '10128', '10280', '10282', '10451', '10452', '10453', '10454', '10455',
           '10456', '10457', '10458', '10459', '10460', '10461', '10462', '10463', '10464', '10465',
           '10466', '10467', '10468', '10469', '10470', '10471', '10472', '10473', '10474', '10475',
           '11201', '11202', '11203', '11204', '11205', '11206', '11207', '11208', '11209', '11210',
           '11211', '11212', '11213', '11214', '11215', '11216', '11217', '11218', '11219', '11220',
           '11221', '11222', '11223', '11224', '11225', '11226', '11228', '11229', '11230', '11231',
           '11232', '11233', '11234', '11235', '11236', '11237', '11238', '11239', '11249', '11251',
           '10301', '10302', '10303', '10304', '10305', '10306', '10307', '10308', '10309', '10310',
           '10311', '10312', '10314'],
    'NJ': ['07001', '07002', '07003', '07006', '07007', '07010', '07011', '07012', '07013', '07016',
           '07017', '07018', '07020', '07021', '07022', '07023', '07024', '07026', '07028', '07029',
           '07030', '07031', '07032', '07033', '07036', '07040', '07041', '07042', '07043', '07044',
           '07045', '07046', '07047', '07050', '07052', '07054', '07055', '07057', '07058', '07060',
           '07062', '07063', '07064', '07065', '07066', '07067', '07068', '07069', '07070', '07071',
           '07072', '07073', '07074', '07075', '07076', '07077', '07078', '07079', '07080', '07081',
           '07082', '07083', '07086', '07087', '07088', '07090', '07092', '07093', '07094', '07095',
           '07096', '07097', '07099', '07102', '07103', '07104', '07105', '07106', '07107', '07108',
           '07109', '07110', '07111', '07112', '07114', '07175', '07184', '07188', '07189', '07191',
           '07192', '07193', '07194', '07195', '07198', '07199', '07201', '07202', '07203', '07204',
           '07205', '07206', '07207', '07208', '07302', '07303', '07304', '07305', '07306', '07307',
           '07308', '07310', '07311', '07410', '07430', '07450', '07452', '07457', '07458', '07470',
           '07480', '07501', '07502', '07503', '07504', '07505', '07506', '07507', '07508', '07509',
           '07510', '07511', '07512', '07513', '07514', '07522', '07524', '07533', '07538', '07543',
           '07544', '07601', '07602', '07603', '07604', '07605', '07606', '07607', '07608', '07620',
           '07621', '07624', '07626', '07627', '07628', '07630', '07631', '07632', '07640', '07641',
           '07642', '07643', '07644', '07645', '07646', '07647', '07648', '07649', '07650', '07652',
           '07653', '07656', '07657', '07660', '07661', '07662', '07663', '07666', '07670', '07675',
           '07676', '07677', '07699', '07701', '07702', '07703', '07704', '07711', '07712', '07715',
           '07716', '07717', '07718', '07719', '07720', '07721', '07722', '07723', '07724', '07726',
           '07727', '07728', '07730', '07731', '07732', '07733', '07734', '07735', '07737', '07738',
           '07739', '07740', '07746', '07747', '07748', '07750', '07751', '07752', '07753', '07754',
           '07755', '07756', '07757', '07758', '07760', '07762', '07763', '07764', '07765', '07799'],
    'CT': ['06801', '06804', '06807', '06810', '06811', '06812', '06813', '06814', '06816', '06817',
           '06820', '06824', '06825', '06828', '06829', '06830', '06831', '06836', '06838', '06840',
           '06850', '06851', '06852', '06853', '06854', '06855', '06856', '06857', '06858', '06859',
           '06860', '06870', '06875', '06876', '06877', '06878', '06879', '06880', '06881', '06883',
           '06888', '06889', '06890', '06896', '06897', '06901', '06902', '06903', '06904', '06905',
           '06906', '06907', '06910', '06911', '06912', '06913', '06914']
}

NYC_METRO_CITIES = ['New York', 'Brooklyn', 'Bronx', 'Queens', 'Staten Island', 'Manhattan',
                    'Jersey City', 'Newark', 'Hoboken', 'Paterson', 'Elizabeth', 'Edison',
                    'Woodbridge', 'Lakewood', 'Toms River', 'Hamilton', 'Trenton', 'New Brunswick',
                    'Bridgeport', 'New Haven', 'Stamford', 'Norwalk', 'Danbury', 'Waterbury']

def classify_trial_type(trial):
    """
    Classify trial as INTERVENTIONAL (treatment) vs OBSERVATIONAL (data collection).
    Returns: ('INTERVENTIONAL' | 'OBSERVATIONAL' | 'CORRELATIVE', confidence, reasoning)
    """
    title = trial.get('title', '').lower()
    description = trial.get('description_text', '').lower()
    eligibility = trial.get('eligibility_text', '').lower()
    combined_text = f"{title} {description} {eligibility}"
    
    # Observational keywords (strong signals)
    observational_keywords = [
        'observational', 'non-interventional', 'noninterventional', 'registry',
        'tissue procurement', 'tissue collection', 'biobank', 'biorepository',
        'correlative study', 'biomarker study', 'imaging study', 'ai model',
        'retrospective', 'archived tissue', 'tumor samples', 'specimen collection',
        'data collection', 'natural history', 'epidemiology', 'surveillance'
    ]
    
    # Interventional keywords (strong signals)
    interventional_keywords = [
        'randomized', 'treatment', 'therapy', 'drug', 'medication', 'intervention',
        'experimental', 'investigational', 'phase i', 'phase ii', 'phase iii',
        'clinical trial', 'dosing', 'safety', 'efficacy', 'response', 'survival'
    ]
    
    # Count matches
    obs_count = sum(1 for keyword in observational_keywords if keyword in combined_text)
    int_count = sum(1 for keyword in interventional_keywords if keyword in combined_text)
    
    # Decision logic
    if obs_count > int_count and obs_count >= 2:
        return ('OBSERVATIONAL', 0.9, f"Observational keywords: {obs_count} (vs {int_count} interventional)")
    elif int_count > obs_count and int_count >= 2:
        return ('INTERVENTIONAL', 0.9, f"Interventional keywords: {int_count} (vs {obs_count} observational)")
    elif 'phase' in combined_text and ('i' in combined_text or 'ii' in combined_text or 'iii' in combined_text):
        return ('INTERVENTIONAL', 0.8, "Phase I/II/III trial (typically interventional)")
    elif obs_count >= 1:
        return ('OBSERVATIONAL', 0.7, f"Observational keywords detected: {obs_count}")
    else:
        return ('UNKNOWN', 0.5, "Insufficient signals - needs LLM classification")

def has_nyc_metro_location(trial):
    """
    Check if trial has NYC metro area locations (NY/NJ/CT within 50 miles).
    Returns: (has_nyc, locations_list, reasoning)
    """
    locations = trial.get('locations_data', [])
    if not locations:
        return (False, [], "No location data available")
    
    nyc_locations = []
    for loc in locations:
        city = loc.get('city', '').lower()
        state = loc.get('state', '').upper()
        zip_code = loc.get('zip', '')
        
        # Check city match
        if any(nyc_city.lower() in city for nyc_city in NYC_METRO_CITIES):
            nyc_locations.append(loc)
            continue
        
        # Check state + zip
        if state in ['NY', 'NJ', 'CT']:
            if zip_code and zip_code[:5] in NYC_METRO_ZIPS.get(state, []):
                nyc_locations.append(loc)
                continue
        
        # Check state only (NY/NJ/CT are close enough)
        if state in ['NY', 'NJ', 'CT']:
            # Additional check: if it's a major medical center city, likely accessible
            major_centers = ['new york', 'brooklyn', 'bronx', 'queens', 'manhattan', 
                           'jersey city', 'newark', 'bridgeport', 'stamford', 'new haven']
            if any(center in city for center in major_centers):
                nyc_locations.append(loc)
    
    if nyc_locations:
        return (True, nyc_locations, f"Found {len(nyc_locations)} NYC metro location(s)")
    else:
        return (False, [], f"No NYC metro locations (found {len(locations)} other locations)")

def llm_quick_classify_trial(trial):
    """
    Use LLM for quick trial type classification (before full dossier generation).
    Returns: (trial_type, is_treatment, reasoning)
    """
    if not LLM_AVAILABLE:
        return (None, None, "LLM unavailable")
    
    title = trial.get('title', 'N/A')[:200]
    description = trial.get('description_text', 'N/A')[:500]
    
    prompt = f"""Classify this clinical trial as INTERVENTIONAL (treatment) or OBSERVATIONAL (data collection).

Title: {title}
Description: {description[:500]}

Respond with ONLY one word: "INTERVENTIONAL" or "OBSERVATIONAL"
If it's a treatment trial with drugs/therapy, say INTERVENTIONAL.
If it's just data collection, imaging, tissue studies, or AI model development, say OBSERVATIONAL."""

    try:
        conversation_history = [
            {"role": "system", "content": "You are a clinical trial classification expert. Respond with only one word."},
            {"role": "user", "content": prompt}
        ]
        
        response = get_llm_chat_response(
            conversation_history=conversation_history,
            provider="gemini",
            model_name=GEMINI_MODEL
        )
        
        response_clean = response.strip().upper()
        if "INTERVENTIONAL" in response_clean:
            return ("INTERVENTIONAL", True, "LLM classified as interventional treatment trial")
        elif "OBSERVATIONAL" in response_clean:
            return ("OBSERVATIONAL", False, "LLM classified as observational study")
        else:
            return ("UNKNOWN", None, f"LLM response unclear: {response[:100]}")
    except Exception as e:
        return (None, None, f"LLM classification failed: {e}")

def filter_recruiting_trials(candidates):
    """Filter for RECRUITING trials only"""
    recruiting_statuses = ['RECRUITING', 'NOT_YET_RECRUITING', 'ACTIVE_NOT_RECRUITING']
    recruiting = [t for t in candidates if t.get('status') in recruiting_statuses]
    print(f"✅ Filtered {len(recruiting)} recruiting trials from {len(candidates)} total")
    return recruiting

def assess_trial_for_ayesha_v2(trial, use_llm_classification=True):
    """
    IMPROVED assessment with multi-layer filtering.
    Returns: (is_match, tier, match_score, reasons, rejection_reason)
    """
    reasons = []
    rejection_reasons = []
    match_score = 0.0
    
    # LAYER 1: Hard Filters (status, disease, stage)
    disease_category = trial.get('disease_category', '').lower()
    if 'gynecologic' not in disease_category and 'ovarian' not in disease_category:
        return (False, 'REJECTED', 0.0, [], "❌ Not ovarian/gynecologic cancer")
    reasons.append("✅ Ovarian cancer trial")
    match_score += 0.2
    
    status = trial.get('status', '')
    if status not in ['RECRUITING', 'NOT_YET_RECRUITING', 'ACTIVE_NOT_RECRUITING']:
        return (False, 'REJECTED', 0.0, [], f"❌ Status: {status} (not recruiting)")
    reasons.append(f"✅ {status}")
    match_score += 0.1
    
    eligibility = trial.get('eligibility_text', '').lower()
    if 'stage iv' in eligibility or 'stage 4' in eligibility or 'advanced' in eligibility:
        reasons.append("✅ Stage IV eligible")
        match_score += 0.2
    elif 'stage iii' in eligibility:
        reasons.append("⚠️ Stage III (may include IV)")
        match_score += 0.1
    
    # LAYER 2: Trial Type Classification
    trial_type, confidence, reasoning = classify_trial_type(trial)
    
    # If classification is uncertain, use LLM for quick check
    if trial_type == 'UNKNOWN' and use_llm_classification and LLM_AVAILABLE:
        llm_type, is_treatment, llm_reasoning = llm_quick_classify_trial(trial)
        if llm_type == 'OBSERVATIONAL':
            return (False, 'REJECTED', 0.0, [], f"❌ Observational study (LLM): {llm_reasoning}")
        elif llm_type == 'INTERVENTIONAL':
            trial_type = 'INTERVENTIONAL'
            reasoning = llm_reasoning
    
    if trial_type == 'OBSERVATIONAL':
        return (False, 'REJECTED', 0.0, [], f"❌ Observational study (not treatment): {reasoning}")
    elif trial_type == 'INTERVENTIONAL':
        reasons.append(f"✅ Interventional treatment trial ({confidence:.0%} confidence)")
        match_score += 0.3
    else:
        reasons.append(f"⚠️ Trial type uncertain: {reasoning}")
        match_score += 0.1
    
    # LAYER 3: Location Filtering (NYC metro required)
    has_nyc, nyc_locations, location_reasoning = has_nyc_metro_location(trial)
    if not has_nyc:
        return (False, 'REJECTED', 0.0, [], f"❌ No NYC metro locations: {location_reasoning}")
    reasons.append(f"✅ NYC metro location(s): {len(nyc_locations)}")
    match_score += 0.2
    
    # LAYER 4: Treatment line check
    if 'first' in eligibility or 'frontline' in eligibility or 'primary' in eligibility:
        reasons.append("✅ First-line treatment")
        match_score += 0.1
    elif 'maintenance' in eligibility:
        reasons.append("⚠️ Maintenance (after first-line)")
        match_score += 0.05
    
    # Classify tier
    if match_score >= 0.8:
        tier = 'TOP_TIER'
    elif match_score >= 0.6:
        tier = 'GOOD_TIER'
    elif match_score >= 0.4:
        tier = 'OK_TIER'
    else:
        tier = 'REJECTED'
    
    return (match_score >= 0.4, tier, match_score, reasons, None)

# ... (rest of the file continues with generate_trial_fit_analysis, etc.)
# For now, I'll create the main function that uses the improved filtering

async def main():
    """Generate intelligence reports with improved filtering"""
    print("⚔️ ZO'S IMPROVED TRIAL INTELLIGENCE GENERATOR V2 ⚔️\n")
    
    # Load Ayesha's complete profile
    ayesha = get_ayesha_complete_profile()
    print(f"✅ Loaded Ayesha's complete profile")
    
    # Load candidates
    with open(CANDIDATES_FILE) as f:
        data = json.load(f)
    
    all_candidates = data['candidates']
    print(f"📊 Loaded {len(all_candidates)} candidates from vector search")
    
    # LAYER 1: Filter recruiting
    recruiting = filter_recruiting_trials(all_candidates)
    
    # LAYER 2-4: Multi-layer assessment
    print(f"\n🔍 MULTI-LAYER FILTERING:")
    assessed = []
    rejected = []
    
    for trial in recruiting:
        assessment = assess_trial_for_ayesha_v2(trial, use_llm_classification=True)
        is_match, tier, score, reasons, rejection = assessment
        
        if is_match:
            assessed.append((trial, assessment))
        else:
            rejected.append((trial, rejection))
    
    print(f"   ✅ Passed filters: {len(assessed)}")
    print(f"   ❌ Rejected: {len(rejected)}")
    
    # Show rejection reasons
    if rejected:
        print(f"\n   Rejection breakdown:")
        rejection_counts = {}
        for _, reason in rejected:
            key = reason[:50] if reason else "Unknown"
            rejection_counts[key] = rejection_counts.get(key, 0) + 1
        for reason, count in sorted(rejection_counts.items(), key=lambda x: x[1], reverse=True)[:5]:
            print(f"      - {reason}: {count}")
    
    # Sort by match score
    assessed.sort(key=lambda x: x[1][2], reverse=True)
    
    print(f"\n🎯 FINAL ASSESSMENT:")
    print(f"   Top-Tier: {sum(1 for _, a in assessed if a[1][1] == 'TOP_TIER')}")
    print(f"   Good-Tier: {sum(1 for _, a in assessed if a[1][1] == 'GOOD_TIER')}")
    
    # Generate intelligence reports (only for passed trials)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    print(f"\n📝 GENERATING INTELLIGENCE REPORTS:\n")
    # Import the markdown generator from the original file
    from generate_zo_intelligence_dossiers import generate_intelligence_dossier_markdown
    
    for i, (trial, assessment) in enumerate(assessed[:10], 1):  # Top 10
        nct_id = trial['nct_id']
        tier = assessment[1]
        match_score = assessment[2]
        
        # Generate markdown (reuse existing function)
        markdown = generate_intelligence_dossier_markdown(trial, ayesha, assessment)
        
        # Save
        filename = f"INTELLIGENCE_{nct_id}_{tier}.md"
        filepath = OUTPUT_DIR / filename
        with open(filepath, 'w') as f:
            f.write(markdown)
        
        print(f"{i}. {nct_id} - {tier} ({match_score:.2f}) - {trial['title'][:60]}...")
    
    print(f"\n✅ Generated {min(10, len(assessed))} intelligence reports")
    print(f"📁 Output: {OUTPUT_DIR}")
    print(f"\n⚔️ IMPROVED FILTERING COMPLETE!")

if __name__ == "__main__":
    asyncio.run(main())


