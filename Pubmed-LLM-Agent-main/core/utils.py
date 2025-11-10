import os
import re
import json
import textwrap
import hashlib
import time
from datetime import datetime
from typing import List, Dict, Any, Optional, Iterable, Tuple

def safe_json_loads(text: str) -> dict:
    if text is None:
        raise ValueError("No text to parse (got None)")
    
    s = str(text).strip()
    if not s:
        raise ValueError("Empty text to parse")

    s = re.sub(r"^```(?:json)?\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s*```$", "", s)
    s = s.replace("‘", "'").replace("’", "'").replace("“", '"').replace("”", '"')
    s = s.replace("''", '"').replace("''", '"')

    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass

    s = re.sub(r",(\s*[}\]])", r"\1", s)
    s = re.sub(r'([{,]\s*)(\w+)(\s*:)', r'\1"\2"\3', s)

    brace_depth = 0
    square_depth = 0
    in_string = False
    escape = False
    start = -1

    for i, c in enumerate(s):
        if start == -1:
            if c == '{':
                start = i
                brace_depth = 1
                square_depth = 0
            elif c == '[':
                start = i
                brace_depth = 0
                square_depth = 1
            continue

        if not in_string:
            if c == '{': brace_depth += 1
            elif c == '}': brace_depth -= 1
            elif c == '[': square_depth += 1
            elif c == ']': square_depth -= 1
            elif c == '"': in_string = True
        else:
            if c == '"' and not escape: in_string = False
            elif c == '\\' and not escape: escape = True
            else: escape = False

        if (brace_depth == 0 and square_depth == 0) and not in_string:
            try: return json.loads(s[start:i+1])
            except json.JSONDecodeError: pass

    try:
        cleaned = re.sub(r",(\s*[}\]])", r"\1", s)
        cleaned = re.sub(r'(\w+):', r'"\1":', cleaned)
        cleaned = cleaned.replace("'", '"')
        return json.loads(cleaned)
    except json.JSONDecodeError: pass

    lines = s.strip().splitlines()
    results = []
    for line in lines:
        line = line.strip()
        if not line or line.startswith(('#', '//', '/*', '*/', '```')): continue
        try:
            obj = json.loads(line)
            results.append(obj)
        except json.JSONDecodeError:
            fixed = re.sub(r'(\w+):', r'"\1":', line)
            fixed = fixed.replace("'", '"')
            try:
                obj = json.loads(fixed)
                results.append(obj)
            except: continue

    if len(results) == 1:
        return results[0]
    elif results:
        return results

    raise ValueError("Could not extract valid JSON from response")

def chunked(seq: List[Any], size: int) -> Iterable[List[Any]]:
    for i in range(0, len(seq), size):
        yield seq[i:i+size]

def now_ms() -> int:
    return int(time.time() * 1000)

def coalesce(*args, default=None):
    for a in args:
        if a is not None:
            return a
    return default

def clean_text(s: Optional[str]) -> str:
    if not s:
        return ""
    return re.sub(r"\s+", " ", s).strip()

def parse_year_from_pubdate(pubdate: str) -> Optional[int]:
    m = re.search(r"(\d{4})", pubdate or "")
    return int(m.group(1)) if m else None

def extract_date_range_from_query(query: str) -> Tuple[Optional[int], Optional[int], str]:
    current_year = datetime.now().year
    from_year = None
    to_year = None
    cleaned_query = query
    range_patterns = [
        r'(?:from|since)\s*(\d{4})\s*(?:to|until|-|through)\s*(\d{4})',
        r'(\d{4})\s*(?:to|-|through)\s*(\d{4})',
        r'between\s*(\d{4})\s*and\s*(\d{4})',
    ]
    for pattern in range_patterns:
        match = re.search(pattern, query.lower())
        if match:
            from_year = int(match.group(1))
            to_year = int(match.group(2))
            cleaned_query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
            break
    if not from_year:
        since_patterns = [
            (r'(?:since|from|after)\s*(\d{4})', 'since'),
            (r'(?:in the )?last\s*(\d+)\s*years?', 'last'),
            (r'(?:past|recent)\s*(\d+)\s*years?', 'past'),
        ]
        for pattern, pattern_type in since_patterns:
            match = re.search(pattern, query.lower())
            if match:
                if pattern_type in ['last', 'past']:
                    years_back = int(match.group(1))
                    from_year = current_year - years_back
                else:
                    from_year = int(match.group(1))
                cleaned_query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
                break
        until_patterns = [r'(?:until|before|up to)\s*(\d{4})']
        for pattern in until_patterns:
            match = re.search(pattern, query.lower())
            if match:
                to_year = int(match.group(1))
                cleaned_query = re.sub(pattern, '', query, flags=re.IGNORECASE).strip()
                break
    cleaned_query = re.sub(r'\s+', ' ', cleaned_query).strip()
    return from_year, to_year, cleaned_query

def generate_output_filename(query: str) -> str:
    filename = re.sub(r'[^\w\s-]', '', query.lower())
    filename = re.sub(r'\s+', '_', filename)
    filename = filename[:50]
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return f"{filename}_{timestamp}.json"

def assemble_records(pmids: List[str], summaries: Dict, efetched: Dict) -> List[Dict[str, Any]]:
    records = []
    for pid in pmids:
        s = summaries.get(pid, {})
        f = efetched.get(pid, {})
        title = s.get("title") or s.get("sorttitle") or ""
        journal = s.get("fulljournalname") or f.get("journal") or s.get("source") or ""
        pubdate = s.get("pubdate") or ""
        year = coalesce(parse_year_from_pubdate(pubdate), f.get("year"))
        pubtypes = list(dict.fromkeys(s.get("pubtype", []) + f.get("publication_types", [])))
        doi = s.get("elocationid", "")
        if isinstance(doi, str) and doi.lower().startswith("doi:"):
            doi = doi[4:]

        records.append({
            "pmid": pid,
            "title": clean_text(title),
            "journal": clean_text(journal),
            "pubdate": clean_text(pubdate),
            "year": year,
            "publication_types": pubtypes,
            "mesh_headings": f.get("mesh_headings", []),
            "abstract": f.get("abstract", ""),
            "doi": doi or None,
            "pmcid": f.get("pmcid", "NA"),
            "license": f.get("license", "NA"),
        })
    return records
