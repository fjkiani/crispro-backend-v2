import sys
import textwrap
from typing import List, Dict, Any

from tqdm import tqdm

from .llm_client import LLMClient
from .utils import chunked

def rerank_records_with_llm_batched(
    cleaned_query: str,
    records: List[Dict[str, Any]],
    llm: LLMClient,
    batch_size: int = 50,
    abstract_length: int = 600
) -> List[Dict[str, Any]]:
    ranked = []
    system_prompt = """
You are a clinical research expert. Score relevance of each paper to the query on a 1–100 scale.

Scoring:
- 90–100: Direct match (PICO)
- 70–89: High relevance
- 50–69: Partial
- 30–49: Tangential
- 1–29: Not relevant

Return ONLY JSON array: [{"pmid":"...","relevance":int,"reason":"..."}]
"""

    print(f"🔍 Scoring {len(records)} papers in batches of {batch_size}...", file=sys.stderr)
    scored_count = 0

    for batch in tqdm(list(chunked(records, batch_size)), desc="LLM Scoring", unit="batch"):
        user_prompt = f"QUERY: {cleaned_query}\n\n"
        for rec in batch:
            user_prompt += f"""
--- PMID {rec['pmid']} ---
Title: {rec.get('title', '')}
Abstract: {textwrap.shorten(rec.get('abstract', ''), width=abstract_length, placeholder='...')}
MeSH: {', '.join(rec.get('mesh_headings', [])[:5])}
Types: {', '.join(rec.get('publication_types', []))}
"""
        user_prompt += "\nReturn JSON array: [{\"pmid\": \"...\", \"relevance\": 0–100, \"reason\": \"...\"}]"

        try:
            resp = llm.complete_json(system_prompt, user_prompt, max_tokens=2000)
            if isinstance(resp, dict):
                resp = resp.get("results", [])
            if not isinstance(resp, list):
                raise ValueError("Not a list")

            result_map = {r["pmid"]: r for r in resp if isinstance(r, dict) and "pmid" in r}

            for rec in batch:
                item = result_map.get(rec["pmid"])
                if item:
                    relevance = max(1, min(100, item.get("relevance", 50)))
                    reason = item.get("reason", "No reason")
                else:
                    relevance, reason = 50, "LLM did not score; default"
                rec2 = dict(rec)
                rec2["relevance"] = relevance
                rec2["relevance_reason"] = reason
                ranked.append(rec2)
                scored_count += 1
        except Exception as e:
            print(f"⚠️ Batch failed: {e}. Falling back to individual scoring.", file=sys.stderr)
            for rec in batch:
                try:
                    item = _make_individual_scorer(llm, cleaned_query)(rec)
                except:
                    item = {"relevance": 50, "reason": "Scoring failed"}
                rec2 = dict(rec)
                rec2["relevance"] = item["relevance"]
                rec2["relevance_reason"] = item["reason"]
                ranked.append(rec2)
                scored_count += 1

    print(f"📊 New scored: {scored_count}", file=sys.stderr)
    ranked.sort(key=lambda r: -r["relevance"])
    return ranked

def _make_individual_scorer(llm: LLMClient, cleaned_query: str):
    def score(rec: Dict[str, Any]) -> Dict[str, Any]:
        system = 'Return JSON: {"relevance": int, "reason": str}'
        user = f"""
Query: {cleaned_query}
Title: {rec.get('title', '')}
Abstract: {textwrap.shorten(rec.get('abstract', ''), 800)}
MeSH: {', '.join(rec.get('mesh_headings', [])[:5])}
Return: {{"relevance": 1–100, "reason": "..."}}
"""
        resp = llm.complete_json(system, user, max_tokens=200)
        return {
            "relevance": max(1, min(100, resp.get("relevance", 50))),
            "reason": resp.get("reason", "No reason")
        }
    return score
