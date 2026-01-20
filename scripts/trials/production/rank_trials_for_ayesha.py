"""
Rank Trials for Ayesha

Rank active ovarian cancer trials by alignment to Ayesha's profile.

This version adds intent gates to avoid non-treatment studies (fertility/QoL/registry/observational/diagnostic).
"""

import sys
import sqlite3
import json
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(backend_root))

DB_PATH = backend_root / "data" / "clinical_trials.db"
VECTORS_PATH = backend_root / "api" / "resources" / "trial_moa_vectors.json"


# Hard exclusions: these are typically NOT enrollment-relevant therapeutic trials for AK
NON_THERAPEUTIC_TITLE_PATTERNS = [
    "cryopreservation",
    "fertility",
    "ovarian reserve",
    "quality of life",
    "questionnaire",
    "survey",
    "observational",
    "registry",
    "real-world",
    "biobank",
    "specimen",
    "tissue",
    "imaging",
    "diagnostic",
    "screening",
    "correlation",
    "dose intensity",
]

# Strong negatives from Ayesha profile
NEGATIVE_THERAPY_TERMS = [
    # FOLR1 negative (<1%) => deprioritize FRα-targeted agents
    "folr1",
    "folate receptor alpha",
    "frα",
    "mirvetuximab",
    "elahere",
    # HER2 negative
    "her2",
    "trastuzumab",
    "pertuzumab",
]


def is_non_therapeutic(title: str) -> bool:
    t = (title or "").lower()
    return any(p in t for p in NON_THERAPEUTIC_TITLE_PATTERNS)


def negative_term_penalty(text: str) -> float:
    t = (text or "").lower()
    # Penalize each negative match (cap)
    hits = sum(1 for term in NEGATIVE_THERAPY_TERMS if term in t)
    return min(2.0, hits * 0.75)

def has_drug_like_intervention(interventions: str, interventions_json: str) -> bool:
    """Return True if the trial has a DRUG/BIOLOGICAL-type intervention (avoid behavioral/QoL)."""
    try:
        import json
        data = json.loads(interventions_json) if interventions_json else []
        types = {str(item.get('type', '')).upper() for item in (data or []) if isinstance(item, dict)}
        if types.intersection({'DRUG', 'BIOLOGICAL'}):
            return True
        # Some CT.gov entries use OTHER; fallback to text heuristic
    except Exception:
        pass

    t = (interventions or '').lower()
    # Exclude common non-drug intervention types
    if any(x in t for x in ['behavior', 'behaviour', 'exercise', 'diet', 'mindfulness', 'counsel', 'education', 'support', 'cope', 'questionnaire', 'survey']):
        return False

    # Weak positive heuristic: if it looks like a medication name/class
    return any(x in t for x in ['-ib', 'inib', 'mab', 'parp', 'olaparib', 'niraparib', 'rucaparib', 'pembrolizumab', 'nivolumab', 'bevacizumab'])



# Ayesha's profile keywords (weighted by clinical relevance)
AYESHA_KEYWORDS = {
    'PARP': {
        'variants': ['PARP', 'olaparib', 'niraparib', 'rucaparib'],
        'weight': 1.0,
        'priority': 'P0',
        'reason': 'BER deficient → PARP sensitive'
    },
    'TP53': {
        'variants': ['TP53', 'p53'],
        'weight': 1.0,
        'priority': 'P2',
        'reason': 'TP53 mutant → checkpoint bypass'
    },
    'PD-L1': {
        'variants': ['PD-L1', 'PDL1', 'pembrolizumab', 'nivolumab', 'checkpoint'],
        'weight': 0.8,
        'priority': 'P1',
        'reason': 'CPS 10 positive → IO eligible'
    },
    'MBD4': {
        'variants': ['MBD4', 'base excision', 'BER'],
        'weight': 1.0,
        'priority': 'P0',
        'reason': 'Germline MBD4 mutation'
    },
    'DDR': {
        'variants': ['DDR', 'DNA damage repair', 'homologous recombination'],
        'weight': 0.9,
        'priority': 'P1',
        'reason': 'MBD4 = DDR gene'
    },
    'ATR': {
        'variants': ['ATR', 'ceralasertib', 'ATR inhibitor'],
        'weight': 0.9,
        'priority': 'P0',
        'reason': 'TP53 mutant → ATR combos'
    },
    'WEE1': {
        'variants': ['WEE1', 'adavosertib', 'WEE1 inhibitor'],
        'weight': 0.9,
        'priority': 'P0',
        'reason': 'TP53 mutant → WEE1 combos'
    },
}


def score_trial_for_ayesha(trial: tuple, keywords: dict) -> dict:
    """Score trial by therapy-fit for Ayesha (intent-gated)."""
    nct_id, title, conditions, interventions, interventions_json, status, phases = trial

    # Gate 1: drop obvious non-therapeutic studies from ranking
    if is_non_therapeutic(title):
        return {
            'nct_id': nct_id,
            'title': title,
            'status': status,
            'phases': phases or 'N/A',
            'keyword_matches': {},
            'combo_matches': [],
            'total_score': -999.0,
            'match_count': 0,
            'excluded_reason': 'non_therapeutic_title'
        }

    # Gate 2: require intervention signal (avoid pure registries/assays)
    if not (interventions or '').strip():
        return {
            'nct_id': nct_id,
            'title': title,
            'status': status,
            'phases': phases or 'N/A',
            'keyword_matches': {},
            'combo_matches': [],
            'total_score': -999.0,
            'match_count': 0,
            'excluded_reason': 'no_interventions'
        }


    # Gate 3: require DRUG/BIOLOGICAL interventions for Ayesha fit
    if not has_drug_like_intervention(interventions, interventions_json):
        return {
            'nct_id': nct_id,
            'title': title,
            'status': status,
            'phases': phases or 'N/A',
            'keyword_matches': {},
            'combo_matches': [],
            'total_score': -999.0,
            'match_count': 0,
            'excluded_reason': 'non_drug_intervention'
        }
    text = f"{title or ''} {conditions or ''} {interventions or ''}".upper()

    keyword_matches = {}
    total_score = 0.0

    # Base scoring by therapy keywords
    for keyword, data in keywords.items():
        matches = sum(1 for variant in data['variants'] if variant.upper() in text)
        if matches > 0:
            score = data['weight'] * min(matches, 3)
            keyword_matches[keyword] = matches
            total_score += score

    # Synthetic lethality combos matter most for TP53 mutant + BER deficient
    combo_bonus = 0.0
    combo_matches = []
    has_parp = 'PARP' in keyword_matches
    has_atr = 'ATR' in keyword_matches
    has_wee1 = 'WEE1' in keyword_matches

    if has_parp and has_atr:
        combo_bonus += 2.0
        combo_matches.append('PARP+ATR')
    if has_parp and has_wee1:
        combo_bonus += 2.0
        combo_matches.append('PARP+WEE1')

    total_score += combo_bonus

    # Penalize known mismatches from her profile (FOLR1-, HER2-)
    total_score -= negative_term_penalty(f"{title or ''} {interventions or ''}")

    return {
        'nct_id': nct_id,
        'title': title,
        'status': status,
        'phases': phases or 'N/A',
        'keyword_matches': keyword_matches,
        'combo_matches': combo_matches,
        'total_score': total_score,
        'match_count': len(keyword_matches),
        'excluded_reason': None
    }



def main():
    """Main entry point."""
    print("🎯 Ranking active ovarian cancer trials for Ayesha (intent-gated)")
    print("=" * 100)
    print()
    
    # Load tagged trials
    tagged_nct_ids = set()
    if VECTORS_PATH.exists():
        with open(VECTORS_PATH) as f:
            vectors = json.load(f)
        tagged_nct_ids = set(vectors.keys())
        print(f"✅ Loaded {len(tagged_nct_ids)} tagged trials")
    
    # Get all active ovarian cancer trials
    conn = sqlite3.connect(str(DB_PATH))
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT id, title, conditions, interventions, interventions_json, status, phases
        FROM trials 
        WHERE status IN ('RECRUITING', 'ACTIVE_NOT_RECRUITING', 'NOT_YET_RECRUITING')
        AND (LOWER(conditions) LIKE '%ovarian%' OR LOWER(title) LIKE '%ovarian%')
    """)
    trials = cursor.fetchall()
    
    print(f"✅ Loaded {len(trials)} active ovarian cancer trials")
    print()
    
    # Score all trials
    scored_trials = []
    for trial in trials:
        scored = score_trial_for_ayesha(trial, AYESHA_KEYWORDS)
        if scored.get('excluded_reason') is None and scored['total_score'] > 0:
            scored['is_tagged'] = scored['nct_id'] in tagged_nct_ids
            scored_trials.append(scored)
    
    # Sort by score
    scored_trials.sort(key=lambda x: x['total_score'], reverse=True)
    
    print(f"✅ Scored {len(scored_trials)} trials with keyword matches")
    print()
    
    # Top 20
    print("🎯 TOP 20 TRIALS FOR AYESHA")
    print("=" * 100)
    print()
    
    for i, trial in enumerate(scored_trials[:20], 1):
        tag_icon = '🏷️' if trial['is_tagged'] else '  '
        title_short = (trial['title'] or 'N/A')[:70]
        score = trial['total_score']
        matches_str = ', '.join([f"{kw}({count})" for kw, count in 
                                sorted(trial['keyword_matches'].items(), key=lambda x: x[1], reverse=True)[:5]])
        if trial['combo_matches']:
            matches_str += f" | Combos: {', '.join(trial['combo_matches'])}"
        
        print(f'{i:2d}. {tag_icon} {trial["nct_id"]} [score: {score:.2f}] [{trial["status"]:22s}]')
        print(f'    {title_short}')
        print(f'    Matches: {matches_str}')
        print()
    
    # Statistics
    print("=" * 100)
    print("📊 RANKING STATISTICS")
    print("=" * 100)
    print(f"Total active trials: {len(trials)}")
    print(f"Trials with matches: {len(scored_trials)} ({len(scored_trials) / len(trials) * 100:.1f}%)")
    print()
    print(f"Top 10 average score: {sum(t['total_score'] for t in scored_trials[:10]) / 10:.2f}")
    print(f"Top 20 average score: {sum(t['total_score'] for t in scored_trials[:20]) / 20:.2f}")
    print(f"Top 50 average score: {sum(t['total_score'] for t in scored_trials[:50]) / 50:.2f}")
    print(f"All matched average: {sum(t['total_score'] for t in scored_trials) / len(scored_trials):.2f}")
    print()
    print(f"Tagged trials in top 10: {sum(1 for t in scored_trials[:10] if t['is_tagged'])} / 10")
    print(f"Tagged trials in top 20: {sum(1 for t in scored_trials[:20] if t['is_tagged'])} / 20")
    print(f"Tagged trials in top 50: {sum(1 for t in scored_trials[:50] if t['is_tagged'])} / 50")
    print()
    
    # Keyword frequency in top 20
    print("📋 KEYWORD FREQUENCY (Top 20):")
    keyword_counts = {}
    for trial in scored_trials[:20]:
        for kw in trial['keyword_matches'].keys():
            keyword_counts[kw] = keyword_counts.get(kw, 0) + 1
    
    for kw in sorted(keyword_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {kw[0]:8s}: {kw[1]:2d} trials")
    
    conn.close()
    print()
    print("✅ Ranking complete!")


if __name__ == "__main__":
    main()
