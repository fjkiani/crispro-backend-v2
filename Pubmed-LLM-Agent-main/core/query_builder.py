from typing import Dict, Any, Optional

from .llm_client import LLMClient

QUERY_BUILDER_SYSTEM = """Return JSON: {"pubmed_query": str, "notes": str, "inferred_filters": {}}"""

def build_pubmed_query(llm: LLMClient, cleaned_query: str, from_year: Optional[int], to_year: Optional[int], require_trials: bool) -> Dict[str, Any]:
    constraints = []
    if from_year or to_year:
        constraints.append(f"date {from_year or 1800}-{to_year or 3000}")
    if require_trials:
        constraints.append("clinical trials")
    constraints_str = "; ".join(constraints)

    user = f"""
Query: "{cleaned_query}"
Constraints: {constraints_str}

Guidelines:
- Use [tiab], [mh], [pt]
- Include synonyms with OR
- For trials: (randomized controlled trial[pt] OR clinical trial[pt])
- Filter: english[lang]

Return JSON only.
"""
    try:
        return llm.complete_json(QUERY_BUILDER_SYSTEM, user)
    except:
        return {"pubmed_query": cleaned_query, "notes": "Fallback", "inferred_filters": {}}
