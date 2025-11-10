#!/usr/bin/env python3
"""
PubMed LLM Agent (Natural-Language → PubMed → Ranked JSON)

Environment:
- GEMINI_API_KEY: Required for LLM
- NCBI_EMAIL: Recommended
- NCBI_API_KEY: Optional (increases rate limit)
"""

import os
import sys
import json
import argparse
import tqdm
from typing import Optional, Dict, Any

from core.pubmed_client import PubMedClient
from core.llm_client import LLMClient
from core.utils import (
    extract_date_range_from_query,
    generate_output_filename,
    assemble_records,
)
from core.llm_rerank import rerank_records_with_llm_batched
from core.query_builder import build_pubmed_query


def run_pubmed_search(
    query: str,
    from_year: Optional[int] = None,
    to_year: Optional[int] = None,
    max_results: int = 200,
    top_k: Optional[int] = None,
    pmc_only: bool = False,
    llm_rerank: bool = False,
    batch_size: int = 50,
    no_abstracts: bool = False,
    only_trials: bool = False,
    extra_filters: Optional[str] = None,
    llm_model: str = "gemini-2.5-pro",
    pubmed_email: Optional[str] = None,
    pubmed_api_key: Optional[str] = None,
    llm_api_key: Optional[str] = None
) -> Dict[str, Any]:
    """
    Executes the PubMed search and ranking logic.

    Args:
        query (str): The natural language query.
        from_year (Optional[int]): Start year for publication date filter.
        to_year (Optional[int]): End year for publication date filter.
        max_results (int): Maximum number of PubMed IDs to retrieve.
        top_k (int): Number of top ranked results to return.
        pmc_only (bool): If True, search only PubMed Central full-text articles.
        llm_rerank (bool): If True, use LLM to re-rank results by relevance.
        batch_size (int): Batch size for LLM reranking.
        no_abstracts (bool): If True, skip fetching abstracts.
        only_trials (bool): If True, filter for only clinical trials.
        extra_filters (Optional[str]): Additional PubMed filters to apply.
        llm_model (str): The LLM model to use for query building and reranking.
        pubmed_email (Optional[str]): NCBI email for PubMed API.
        pubmed_api_key (Optional[str]): NCBI API key for PubMed API.
        llm_api_key (Optional[str]): Gemini API key for LLM.

    Returns:
        Dict[str, Any]: A dictionary containing the search results and metadata.
    """

    require_trials = only_trials
    fetch_abstracts = not no_abstracts

    # Print to stderr for CLI execution, Streamlit will handle its own output
    # if sys.stderr.isatty():
    #     print(f"🚀 Starting search: {query}", file=sys.stderr)

    # Extract dates from query
    extracted_from_year, extracted_to_year, cleaned_query = extract_date_range_from_query(query)
    final_from = from_year or extracted_from_year
    final_to = to_year or extracted_to_year

    # Set environment variables for clients (Streamlit needs this for os.getenv)
    os.environ["GEMINI_API_KEY"] = llm_api_key or os.getenv("GEMINI_API_KEY", "")
    
    pm = PubMedClient(email=pubmed_email, api_key=pubmed_api_key)
    llm = LLMClient(model=llm_model)

    # Step 1: Build the PubMed query using the LLM
    try:
        plan = build_pubmed_query(llm, cleaned_query, final_from, final_to, require_trials)
        pubmed_query = plan["pubmed_query"]
        if require_trials and "clinical trial[pt]" not in pubmed_query.lower():
            pubmed_query = f"({pubmed_query}) AND (randomized controlled trial[pt] OR clinical trial[pt])"
        if "english[lang]" not in pubmed_query.lower():
            pubmed_query = f"({pubmed_query}) AND english[lang]"
        if extra_filters:
            pubmed_query = f"({pubmed_query}) AND ({extra_filters})"
    except Exception as e:
        # print(f"⚠️ LLM query builder failed: {e}. Falling back to original query.", file=sys.stderr)
        pubmed_query = cleaned_query
        plan = {"notes": "LLM failed to build query", "inferred_filters": {}}

    # Step 2: Search PubMed for PMIDs
    ids = []
    total_found = 0
    try:
        res = pm.esearch(pubmed_query, retmax=1, mindate=final_from, maxdate=final_to, pmc_only=pmc_only)
        total_found = int(res.get("count", 0))
        # print(f"🔍 Total results found: {total_found}", file=sys.stderr)

        effective_max = min(max_results, total_found, 10000)
        # print(f"📥 Retrieving up to {effective_max} PMIDs...", file=sys.stderr)

        retstart = 0
        with tqdm.tqdm(total=effective_max, desc="Fetching PMIDs", unit="id", disable=not sys.stderr.isatty()) as pbar:
            while len(ids) < effective_max:
                remaining = effective_max - len(ids)
                request_size = min(200, remaining)
                res = pm.esearch(pubmed_query, retmax=request_size, retstart=retstart, mindate=final_from, maxdate=final_to, pmc_only=pmc_only)
                batch_ids = res.get("idlist", [])
                if not batch_ids:
                    break
                ids.extend(batch_ids)
                pbar.update(len(batch_ids))
                retstart += len(batch_ids)

    except Exception as e:
        # print(f"⚠️ PubMed search failed: {e}", file=sys.stderr)
        pass # Streamlit will show errors

    # Step 3 & 4: Fetch summaries and full article details (abstracts, etc.)
    summaries = {}
    efetched = {}
    if ids:
        with tqdm.tqdm(total=len(ids), desc="Fetching Summaries", unit="id", disable=not sys.stderr.isatty()) as pbar:
            summaries = pm.esummary(ids)
            pbar.update(len(ids))
        if fetch_abstracts:
            with tqdm.tqdm(total=len(ids), desc="Fetching Abstracts", unit="id", disable=not sys.stderr.isatty()) as pbar:
                efetched = pm.efetch_abstracts(ids)
                pbar.update(len(ids))

    # Step 5: Assemble and filter records
    records = assemble_records(ids, summaries, efetched)
    if require_trials:
        filtered = [r for r in records if any("trial" in t.lower() for t in r["publication_types"])]
        if not filtered:
            # print("⚠️ Trial filter removed all results. Using unfiltered.", file=sys.stderr)
            pass # Streamlit will handle message
        else:
            records = filtered

    # Step 6: Re-rank with LLM or default
    if llm_rerank and records:
        try:
            ranked = rerank_records_with_llm_batched(cleaned_query, records, llm, batch_size=batch_size)
        except Exception as e:
            # print(f"LLM rerank failed: {e}, falling back to default sorting.", file=sys.stderr)
            ranked = sorted(records, key=lambda r: -(r.get("year") or 0))
            for r in ranked:
                r["relevance"] = 50
                r["relevance_reason"] = "LLM rerank failed"
    else:
        ranked = sorted(records, key=lambda r: -(r.get("year") or 0))
        for r in ranked:
            r["relevance"] = 50
            r["relevance_reason"] = "No LLM re-ranking"

    if top_k is not None:
        top = ranked[:top_k]
    else:
        top = ranked

    result = {
        "natural_query": query,
        "cleaned_query": cleaned_query,
        "extracted_date_range": {"from_year": final_from, "to_year": final_to},
        "pubmed_query": pubmed_query,
        "llm_notes": plan.get("notes", ""),
        "inferred_filters": plan.get("inferred_filters", {}),
        "total_found": total_found,
        "retrieved_count": len(ids),
        "considered_count": len(records),
        "returned_count": len(top),
        "results": top
    }
    return result

def parse_cli_args():
    p = argparse.ArgumentParser(description="PubMed LLM Agent")
    p.add_argument("--query", required=True, help="Natural language query")
    p.add_argument("--config", type=str, help="Path to a JSON config file")
    p.add_argument("--from-year", type=int, help="Start year")
    p.add_argument("--to-year", type=int, help="End year")
    p.add_argument("--max-results", type=int, help="Max to retrieve")
    p.add_argument("--top-k", type=int, help="Top results to return")
    p.add_argument("--pmc-only", action="store_true", help="Only PMC full-text articles")
    p.add_argument("--llm-rerank", action="store_true", help="Use LLM to score relevance (1–100)")
    p.add_argument("--batch-size", type=int, help="LLM batch size")
    p.add_argument("--no-abstracts", action="store_true", help="Skip abstract fetch")
    p.add_argument("--only-trials", action="store_true", help="Filter for only clinical trials")
    p.add_argument("--extra-filters", type=str, help="Extra PubMed filters")
    p.add_argument("--llm-model", type=str, help="LLM model")
    p.add_argument("--out", type=str, help="Output file")
    p.add_argument("--stdout", action="store_true", help="Print to stdout")
    p.add_argument("--verbose", "-v", action="store_true")
    return p.parse_args()


def load_config(config_path):
    if config_path and os.path.exists(config_path):
        with open(config_path, 'r') as f:
            return json.load(f)
    return {}


def cli_main():
    args = parse_cli_args()
    config = load_config(args.config)

    def get_value(arg_val, config_key, default_val):
        if arg_val is not None and not isinstance(arg_val, bool):
            return arg_val
        if config_key in config.get('general', {}):
            return config['general'][config_key]
        return default_val

    def get_bool_value(arg_val, config_key, default_val):
        if arg_val:
            return True
        if config.get('general', {}).get(config_key) is not None:
            return config['general'][config_key]
        return default_val

    final_max_results = get_value(args.max_results, 'max_results', 200)
    final_top_k = get_value(args.top_k, 'top_k', 30)
    final_pmc_only = get_bool_value(args.pmc_only, 'pmc_only', False)
    final_llm_rerank = get_bool_value(args.llm_rerank, 'llm_rerank', False)
    final_batch_size = get_value(args.batch_size, 'batch_size', 50)
    final_no_abstracts = get_bool_value(args.no_abstracts, 'no_abstracts', False)
    final_only_trials = get_bool_value(args.only_trials, 'only_trials', False)
    final_extra_filters = get_value(args.extra_filters, 'extra_filters', None)
    
    final_llm_model = args.llm_model or config.get('llm', {}).get('model', 'gemini-2.5-flash')
    llm_api_key = os.getenv("GEMINI_API_KEY") or config.get('llm', {}).get('api_key')
    pubmed_email = os.getenv("NCBI_EMAIL") or config.get('pubmed', {}).get('email')
    pubmed_api_key = os.getenv("NCBI_API_KEY") or config.get('pubmed', {}).get('api_key')

    result = run_pubmed_search(
        query=args.query,
        from_year=args.from_year,
        to_year=args.to_year,
        max_results=final_max_results,
        top_k=final_top_k,
        pmc_only=final_pmc_only,
        llm_rerank=final_llm_rerank,
        batch_size=final_batch_size,
        no_abstracts=final_no_abstracts,
        only_trials=final_only_trials,
        extra_filters=final_extra_filters,
        llm_model=final_llm_model,
        pubmed_email=pubmed_email,
        pubmed_api_key=pubmed_api_key,
        llm_api_key=llm_api_key
    )

    js = json.dumps(result, ensure_ascii=False, indent=2)
    if args.stdout:
        print(js)
    else:
        out_file = args.out or generate_output_filename(result["cleaned_query"])
        with open(out_file, "w", encoding="utf-8") as f:
            f.write(js)
        print(f"✅ Results saved to {out_file}", file=sys.stderr)

if __name__ == "__main__":
    cli_main()
