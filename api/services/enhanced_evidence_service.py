"""
Enhanced Evidence Service for Food/Supplement Validation

Uses multiple sources (PubMed, LLM synthesis) to extract:
- Mechanisms of action
- Clinical trial outcomes
- Dosage recommendations
- Safety information
- Drug interactions
"""

import httpx
import json
from typing import Dict, List, Optional, Any
import asyncio
import os
import logging

logger = logging.getLogger(__name__)

# Import LLM abstraction layer (Cohere in production)
try:
    from api.services.llm_provider import get_llm_provider, LLMProvider
    LLM_AVAILABLE = True
except ImportError:
    LLM_AVAILABLE = False

# Import LLM service (legacy, may still be used elsewhere)
try:
    from api.services.llm_literature_service import get_llm_service
    LEGACY_LLM_AVAILABLE = True
except ImportError:
    LEGACY_LLM_AVAILABLE = False

# Import config for Diffbot
try:
    from api.config import DIFFBOT_TOKEN
    DIFFBOT_AVAILABLE = bool(DIFFBOT_TOKEN)
except ImportError:
    DIFFBOT_AVAILABLE = False

class EnhancedEvidenceService:
    """
    Extract comprehensive evidence for food/supplement compounds.
    
    PHASE 2 ENHANCEMENTS:
    - Multi-name compound search (canonical + aliases)
    - Evidence quality scoring (Clinical trials > RCTs > Case studies)
    - Mechanistic extraction with LLM
    """
    
    def __init__(self):
        self.pubmed_base = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
        self.timeout = 20.0
        self.cache = {}
        self.diffbot_rate_limited = False  # Track if Diffbot is rate-limited
        
        # Phase 2: Import alias resolver for multi-name search
        try:
            from api.services.compound_alias_resolver import get_resolver
            self.alias_resolver = get_resolver()
        except ImportError:
            self.alias_resolver = None
    
    async def _extract_full_text_with_diffbot(self, paper_url: str) -> Optional[str]:
        """
        Use Diffbot to extract full article text from PubMed/PMC URLs.
        
        This gives us the COMPLETE paper content, not just abstracts!
        
        Returns None if rate-limited or unavailable - gracefully falls back to abstracts-only mode.
        """
        # Skip if we've already hit rate limit
        if self.diffbot_rate_limited:
            return None
        
        try:
            from api.config import DIFFBOT_TOKEN
            
            if not DIFFBOT_TOKEN:
                return None
            
            # Convert PMID to URL if needed
            if paper_url.startswith("PMID:") or "pubmed.ncbi.nlm.nih.gov" not in paper_url:
                pmid = paper_url.replace("PMID:", "").replace("https://pubmed.ncbi.nlm.nih.gov/", "").strip()
                # Try PMC first (full text available)
                pmc_url = f"https://www.ncbi.nlm.nih.gov/pmc/articles/PMC{pmid}/" if not pmid.startswith("http") else paper_url
            else:
                pmc_url = paper_url
            
            api_url = "https://api.diffbot.com/v3/article"
            params = {
                "token": DIFFBOT_TOKEN,
                "url": pmc_url,
                "fields": "title,author,date,siteName,tags,text",
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                r = await client.get(api_url, params=params)
                
                # Handle rate limiting (429) gracefully
                if r.status_code == 429:
                    self.diffbot_rate_limited = True
                    logger.warning(f"⚠️ Diffbot rate limit reached (429). Switching to abstracts-only mode for remaining requests.")
                    return None
                
                r.raise_for_status()
                js = r.json()
            
            obj = (js.get("objects") or [None])[0]
            if obj and obj.get("text"):
                return obj.get("text")[:10000]  # Limit to 10k chars for LLM
            
            return None
            
        except httpx.HTTPStatusError as e:
            # Handle HTTP errors (including 429) gracefully
            if e.response.status_code == 429:
                self.diffbot_rate_limited = True
                logger.warning(f"⚠️ Diffbot rate limit reached (429). Switching to abstracts-only mode.")
                return None
            logger.debug(f"Diffbot HTTP error for {paper_url}: {e.response.status_code}")
            return None
        except Exception as e:
            # Only log non-rate-limit errors
            if "429" not in str(e) and "rate limit" not in str(e).lower():
                logger.debug(f"Diffbot extraction error for {paper_url}: {e}")
            return None
    
    def _get_compound_search_names(self, compound: str) -> List[str]:
        """
        PHASE 2: Get multiple search names for a compound.
        
        Returns: [canonical_name, original_name] (deduplicated)
        """
        search_names = [compound]  # Original always included
        
        if self.alias_resolver:
            canonical = self.alias_resolver.resolve_compound_alias(compound)
            if canonical and canonical.lower() != compound.lower():
                search_names.append(canonical)
        
        # Deduplicate (case-insensitive)
        seen = set()
        unique_names = []
        for name in search_names:
            name_lower = name.lower()
            if name_lower not in seen:
                seen.add(name_lower)
                unique_names.append(name)
        
        return unique_names
    
    def _build_pubmed_query(self, compound: str, disease: str, pathways: List[str] = None, treatment_line: Optional[str] = None) -> str:
        """
        Build optimized PubMed query with optional treatment line context.
        
        Example: "curcumin AND ovarian cancer AND (NF-kappa-B OR COX-2 OR inflammation) AND (first-line OR frontline OR primary)"
        """
        # Map disease codes to PubMed-friendly terms
        disease_map = {
            "ovarian_cancer_hgs": "ovarian cancer",
            "ovarian_cancer": "ovarian cancer",
            "ovarian_carcinoma": "ovarian cancer",
            "breast_cancer": "breast cancer",
            "lung_cancer": "lung cancer",
            "melanoma": "melanoma"
        }
        
        disease_term = disease_map.get(disease.lower(), disease.replace("_", " "))
        query_terms = [compound, disease_term]
        
        # Add pathway-specific terms
        pathway_keywords = {
            "angiogenesis": ["angiogenesis", "VEGF", "vascular"],
            "dna_repair": ["DNA repair", "BRCA", "PARP", "homologous recombination"],
            "inflammation": ["inflammation", "NF-kappa-B", "COX-2", "IL-6"],
            "cell_cycle": ["cell cycle", "CDK", "cyclin"],
            "apoptosis": ["apoptosis", "Bcl-2", "caspase"],
            "metabolism": ["metabolism", "mTOR", "glycolysis", "Warburg"]
        }
        
        if pathways:
            pathway_terms = []
            for pathway in pathways:
                pathway_lower = pathway.lower()
                for key, terms in pathway_keywords.items():
                    if key in pathway_lower:
                        pathway_terms.extend(terms)
            
            if pathway_terms:
                query_terms.append(f"({' OR '.join(pathway_terms[:5])})")  # Limit to 5 terms
        
        # Add treatment line context terms if provided
        if treatment_line:
            treatment_line_lower = treatment_line.lower()
            treatment_terms = []
            
            # Map treatment line to PubMed search terms
            if any(term in treatment_line_lower for term in ["l1", "first", "frontline", "primary", "initial"]):
                treatment_terms = ["first-line", "frontline", "primary", "initial treatment", "neoadjuvant"]
            elif any(term in treatment_line_lower for term in ["l2", "second", "second-line"]):
                treatment_terms = ["second-line", "second line", "salvage", "relapsed"]
            elif any(term in treatment_line_lower for term in ["l3", "third", "third-line", "maintenance"]):
                treatment_terms = ["third-line", "third line", "maintenance", "salvage", "refractory"]
            
            if treatment_terms:
                query_terms.append(f"({' OR '.join(treatment_terms[:3])})")  # Limit to 3 terms
        
        query = " AND ".join(query_terms)
        return query
    
    async def search_pubmed(self, query: str, max_results: int = 20) -> List[Dict[str, Any]]:
        """Search PubMed and return papers with abstracts. Includes retry logic."""
        import asyncio
        import httpx
        
        max_retries = 3
        retry_delay = 2.0  # seconds
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    # Search for PMIDs
                    search_url = f"{self.pubmed_base}/esearch.fcgi"
                    search_params = {
                        "db": "pubmed",
                        "term": query,
                        "retmax": max_results,
                        "retmode": "json"
                    }
                    
                    search_response = await client.get(search_url, params=search_params)
                    
                    # Check for non-200 status or empty response
                    if search_response.status_code != 200:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        print(f"⚠️ PubMed search returned status {search_response.status_code}")
                        return []
                    
                    # Try to parse JSON - handle empty/invalid responses
                    try:
                        search_data = search_response.json()
                    except json.JSONDecodeError as je:
                        if attempt < max_retries - 1:
                            print(f"⚠️ PubMed JSON parse error (attempt {attempt + 1}/{max_retries}): {je}")
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        print(f"⚠️ PubMed returned invalid JSON: {search_response.text[:200]}")
                        return []
                    
                    pmids = search_data.get("esearchresult", {}).get("idlist", [])
                    
                    if not pmids:
                        return []  # Valid empty result
                    
                    # Fetch abstracts - NOTE: efetch returns XML (not JSON)!
                    fetch_url = f"{self.pubmed_base}/efetch.fcgi"
                    fetch_params = {
                        "db": "pubmed",
                        "id": ",".join(pmids),
                        "retmode": "xml",  # efetch API only supports XML format
                        "rettype": "abstract"
                    }
                    
                    fetch_response = await client.get(fetch_url, params=fetch_params)
                    
                    if fetch_response.status_code != 200:
                        if attempt < max_retries - 1:
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        print(f"⚠️ PubMed fetch returned status {fetch_response.status_code}")
                        return []
                    
                    # Parse XML response
                    try:
                        import xml.etree.ElementTree as ET
                        root = ET.fromstring(fetch_response.text)
                    except ET.ParseError as pe:
                        if attempt < max_retries - 1:
                            print(f"⚠️ PubMed XML parse error (attempt {attempt + 1}/{max_retries}): {pe}")
                            await asyncio.sleep(retry_delay * (attempt + 1))
                            continue
                        print(f"⚠️ PubMed returned invalid XML: {fetch_response.text[:200]}")
                        return []
                    
                    papers = []
                    
                    # Parse PubMed XML response
                    for article in root.findall('.//PubmedArticle'):
                        try:
                            # Extract PMID
                            pmid_elem = article.find('.//PMID')
                            pmid = pmid_elem.text if pmid_elem is not None else ""
                            
                            # Extract title
                            title_elem = article.find('.//ArticleTitle')
                            title = title_elem.text if title_elem is not None else ""
                            
                            # Extract abstract (can be multiple AbstractText elements)
                            abstract_texts = article.findall('.//AbstractText')
                            abstract = " ".join([elem.text for elem in abstract_texts if elem.text])
                            
                            # Extract authors
                            author_elems = article.findall('.//Author')
                            authors = []
                            for auth in author_elems[:3]:  # Top 3 authors
                                last_name = auth.find('.//LastName')
                                if last_name is not None and last_name.text:
                                    authors.append(last_name.text)
                            
                            if title and pmid:
                                papers.append({
                                    "pmid": pmid,
                                    "title": title,
                                    "abstract": abstract,
                                    "authors": authors,
                                    "source": "pubmed"
                                })
                        except Exception as e:
                            print(f"⚠️ Error parsing PubMed article: {e}")
                            continue
                    
                    return papers[:max_results]  # Success! Return early
                    
            except httpx.TimeoutException:
                if attempt < max_retries - 1:
                    print(f"⚠️ PubMed timeout (attempt {attempt + 1}/{max_retries}), retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                print(f"⚠️ PubMed search timed out after {max_retries} attempts")
                return []
            except httpx.RequestError as re:
                if attempt < max_retries - 1:
                    print(f"⚠️ PubMed request error (attempt {attempt + 1}/{max_retries}): {re}, retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                print(f"⚠️ PubMed request failed after {max_retries} attempts: {re}")
                return []
            except Exception as e:
                if attempt < max_retries - 1:
                    print(f"⚠️ PubMed error (attempt {attempt + 1}/{max_retries}): {e}, retrying...")
                    await asyncio.sleep(retry_delay * (attempt + 1))
                    continue
                print(f"⚠️ Error searching PubMed after {max_retries} attempts: {e}")
                return []
        
        # Should never reach here, but just in case
        return []
    
    def score_evidence_quality(self, paper: Dict[str, Any]) -> float:
        """
        PHASE 2: Score evidence quality based on study indicators.
        
        Scoring criteria:
        - Study type: Clinical trial (0.3) > Meta-analysis (0.25) > RCT (0.2) > Case study (0.1)
        - Recency: 2020+ (0.15), 2015+ (0.10), 2010+ (0.05)
        - Citation count: >100 (0.1), >50 (0.05)
        
        Returns: Score 0.0-1.0
        """
        score = 0.5  # Base score
        
        # Extract fields
        title = paper.get("title", "").lower()
        abstract = paper.get("abstract", "").lower()
        year = paper.get("year", 0)
        citation_count = paper.get("citation_count", 0)
        
        # Check publication types from title/abstract
        text_combined = title + " " + abstract
        
        # Study type scoring (highest priority)
        if any(term in text_combined for term in ["clinical trial", "phase i", "phase ii", "phase iii", "randomized controlled"]):
            score += 0.3
        elif "meta-analysis" in text_combined or "systematic review" in text_combined:
            score += 0.25
        elif "randomized" in text_combined and "control" in text_combined:
            score += 0.2
        elif any(term in text_combined for term in ["case control", "cohort study", "prospective"]):
            score += 0.15
        elif any(term in text_combined for term in ["case report", "case series"]):
            score += 0.1
        else:
            score += 0.05  # Basic research/in vitro
        
        # Recency scoring
        if year >= 2020:
            score += 0.15
        elif year >= 2015:
            score += 0.10
        elif year >= 2010:
            score += 0.05
        
        # Citation count scoring
        if citation_count > 100:
            score += 0.1
        elif citation_count > 50:
            score += 0.05
        
        return min(score, 1.0)  # Cap at 1.0
    
    async def search_pubmed_multi_name(
        self,
        compound: str,
        disease: str,
        pathways: List[str] = None,
        max_results: int = 20
    ) -> List[Dict[str, Any]]:
        """
        PHASE 2: Multi-name PubMed search using compound aliases.
        
        Searches for:
        1. Original compound name
        2. Canonical PubChem name (if different)
        
        Aggregates results and deduplicates by PMID.
        """
        search_names = self._get_compound_search_names(compound)
        
        print(f"🔍 Multi-name search for: {search_names}")
        
        all_papers = []
        seen_pmids = set()
        
        for compound_name in search_names:
            query = self._build_pubmed_query(compound_name, disease, pathways)
            papers = await self.search_pubmed(query, max_results=max_results)
            
            # Deduplicate by PMID
            for paper in papers:
                pmid = paper.get("pmid")
                if pmid and pmid not in seen_pmids:
                    seen_pmids.add(pmid)
                    
                    # PHASE 2: Add quality score to each paper
                    paper["quality_score"] = self.score_evidence_quality(paper)
                    
                    all_papers.append(paper)
        
        # Sort by quality score (descending)
        all_papers.sort(key=lambda p: p.get("quality_score", 0), reverse=True)
        
        print(f"✅ Found {len(all_papers)} unique papers across {len(search_names)} compound names")
        
        return all_papers[:max_results]  # Return top N
    
    async def extract_mechanism_evidence(
        self,
        compound: str,
        targets: List[str],
        papers: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        PHASE 2: Extract mechanistic evidence for compound-target interactions.
        
        Uses LLM to analyze paper abstracts for:
        - Mechanism type (inhibition/activation/modulation)
        - Evidence strength (in vitro/in vivo/clinical)
        - Effect size (if quantified)
        - Confidence (low/medium/high)
        
        Returns per-target evidence aggregation.
        """
        if not LLM_AVAILABLE or not papers:
            return {"mechanism_evidence": {}, "method": "unavailable"}
        
        evidence_by_target = {}
        
        try:
            from api.services.llm_paper_reader import get_llm_paper_reader
            llm_reader = get_llm_paper_reader()
            
            for target in targets[:5]:  # Limit to top 5 targets to avoid LLM quota
                target_evidence = []
                
                for paper in papers[:10]:  # Analyze top 10 papers per target
                    abstract = paper.get("abstract", "")
                    if not abstract or len(abstract) < 50:
                        continue
                    
                    # LLM prompt for mechanism extraction
                    prompt = f"""
Analyze this paper abstract for evidence of {compound} interaction with {target}.

Abstract: {abstract[:2000]}

Extract (return JSON):
{{
    "mechanism_type": "inhibition|activation|modulation|binding|none",
    "evidence_strength": "in_vitro|in_vivo|clinical|none",
    "effect_described": "yes|no",
    "confidence": "low|medium|high"
}}
"""
                    
                    try:
                        # Call LLM for extraction
                        mechanism = await llm_reader.extract_structured_info(prompt)
                        
                        if mechanism and mechanism.get("mechanism_type") != "none":
                            target_evidence.append({
                                "pmid": paper.get("pmid"),
                                "mechanism": mechanism,
                                "quality_score": paper.get("quality_score", 0.5)
                            })
                    except Exception as e:
                        print(f"⚠️ LLM mechanism extraction failed for PMID {paper.get('pmid')}: {e}")
                        continue
                
                if target_evidence:
                    evidence_by_target[target] = target_evidence
            
            return {
                "mechanism_evidence": evidence_by_target,
                "method": "llm_extraction",
                "targets_analyzed": len(evidence_by_target)
            }
            
        except Exception as e:
            print(f"⚠️ Mechanism extraction failed: {e}")
            return {"mechanism_evidence": {}, "method": "error", "error": str(e)}
    
    async def synthesize_evidence_llm(self, compound: str, disease: str, papers: List[Dict]) -> Dict[str, Any]:
        """
        Use LLM to synthesize evidence from papers.
        
        Extracts:
        - Mechanisms of action
        - Clinical outcomes
        - Dosage information
        - Safety concerns
        - Evidence grade
        """
        if not LLM_AVAILABLE or not papers:
            # Fallback to heuristic grading
            return {
                "evidence_grade": self._heuristic_grade(papers),
                "mechanisms": [],
                "dosage": "",
                "safety": "",
                "outcomes": []
            }
        
        try:
            # Try direct LLM synthesis (read abstracts with LLM)
            llm_synthesis = await self._synthesize_with_llm_direct(compound, disease, papers)
            if llm_synthesis:
                # Use LLM-extracted mechanisms, but keep heuristic grade (more reliable)
                evidence_grade = self._heuristic_grade(papers)
                
                return {
                    "evidence_grade": evidence_grade,
                    "mechanisms": llm_synthesis.get("mechanisms", []),
                    "dosage": llm_synthesis.get("dosage", ""),
                    "safety": llm_synthesis.get("safety", ""),
                    "outcomes": llm_synthesis.get("outcomes", []),
                    "method": "llm_synthesis"
                }
        except Exception as e:
            print(f"⚠️ LLM direct synthesis failed: {e}, trying fallback")
        
        # Fallback: Try LLM service (Pubmed-LLM-Agent)
        try:
            llm_service = get_llm_service()
            llm_result = await llm_service.search_compound_evidence(
                compound=compound,
                disease=disease,
                max_results=20
            )
            
            mechanisms = []
            if llm_result.get("evidence_summary"):
                summary = llm_result.get("evidence_summary", "")
                mechanisms = self._extract_mechanisms_from_text(summary)
            
            evidence_grade = self._heuristic_grade(papers)
            
            return {
                "evidence_grade": evidence_grade,
                "mechanisms": mechanisms,
                "dosage": "",
                "safety": "",
                "outcomes": [],
                "method": "llm_service_fallback"
            }
        except Exception as e:
            print(f"⚠️ LLM service fallback failed: {e}")
        
        # Final fallback: Heuristic only
        return {
            "evidence_grade": self._heuristic_grade(papers),
            "mechanisms": [],
            "dosage": "",
            "safety": "",
            "outcomes": [],
            "method": "heuristic_only"
        }
    
    def _heuristic_grade(self, papers: List[Dict]) -> str:
        """Fallback heuristic grading when LLM unavailable."""
        if not papers:
            return "INSUFFICIENT"
        
        paper_count = len(papers)
        
        # Look for RCT indicators
        has_rct = any(
            "randomized" in p.get("title", "").lower() or 
            "randomized" in p.get("abstract", "").lower() or
            "RCT" in p.get("title", "").upper()
            for p in papers
        )
        
        if has_rct and paper_count >= 3:
            return "STRONG"
        elif paper_count >= 5:
            return "MODERATE"
        elif paper_count >= 2:
            return "WEAK"
        else:
            return "INSUFFICIENT"
    
    async def _synthesize_with_llm_direct(
        self, 
        compound: str, 
        disease: str, 
        papers: List[Dict]
    ) -> Optional[Dict[str, Any]]:
        """
        Use LLM to actually read through paper abstracts and extract structured information.
        
        This is the REAL LLM paper reading implementation.
        """
        if not papers:
            return None
        
        try:
            # Try to get full text with Diffbot for top papers (better quality)
            # Skip if rate-limited - use abstracts only
            papers_with_full_text = []
            if not self.diffbot_rate_limited:
                for p in papers[:5]:  # Limit to 5 papers for full text (expensive)
                    pmid = p.get('pmid', '')
                    url = p.get('url', '') or (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}" if pmid else None)
                    
                    full_text = None
                    if url:
                        full_text = await self._extract_full_text_with_diffbot(url)
                        # If we hit rate limit, stop trying
                        if self.diffbot_rate_limited:
                            break
                    
                    if full_text:
                        papers_with_full_text.append({
                            **p,
                            'full_text': full_text,
                        'has_full_text': True
                    })
                else:
                    # Fall back to abstract
                    papers_with_full_text.append({
                        **p,
                        'full_text': p.get('abstract', '')[:1000],
                        'has_full_text': False
                    })
            
            # Build context (prefer full text, fall back to abstract)
            papers_text = "\n\n".join([
                f"PMID: {p.get('pmid', 'N/A')}\n"
                f"Title: {p.get('title', 'N/A')}\n"
                f"{'[FULL TEXT]' if p.get('has_full_text') else '[ABSTRACT]'}\n"
                f"{p.get('full_text', '')[:2000]}"  # Limit each paper to 2k chars
                for p in papers_with_full_text
            ])
            
            # Try LLM first (uses Cohere in production via abstraction layer)
            synthesis = await self._call_llm_agnostic(compound, disease, papers_text)
            if synthesis:
                return synthesis
            
            # Fallback to Anthropic Claude
            synthesis = await self._call_anthropic_llm(compound, disease, papers_text)
            if synthesis:
                return synthesis
            
            # Fallback to OpenAI
            synthesis = await self._call_openai_llm(compound, disease, papers_text)
            if synthesis:
                return synthesis
            
            return None
            
        except Exception as e:
            print(f"⚠️ LLM direct synthesis error: {e}")
            return None
    
    async def _call_anthropic_llm(
        self, 
        compound: str, 
        disease: str, 
        papers_text: str
    ) -> Optional[Dict[str, Any]]:
        """Call Anthropic Claude API for paper synthesis."""
        try:
            import anthropic
            import os
            
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if not api_key or api_key == "your_anthropic_api_key_here":
                return None
            
            client = anthropic.Anthropic(api_key=api_key)
            
            prompt = f"""You are a biomedical research analyst. Read these research papers about {compound} for {disease} and extract structured information.

Papers:
{papers_text}

Extract and return a JSON object with this exact structure:
{{
  "mechanisms": [
    {{
      "mechanism": "brief_name",
      "description": "how it works",
      "confidence": 0.85,
      "evidence_snippet": "quote from paper"
    }}
  ],
  "dosage": {{
    "recommended_dose": "extracted dose or empty string",
    "evidence": "quote supporting dose"
  }},
  "safety": {{
    "concerns": ["list of safety concerns or empty"],
    "monitoring": ["what to monitor or empty"]
  }},
  "outcomes": [
    {{
      "outcome": "survival improvement",
      "details": "what the papers say"
    }}
  ]
}}

Return ONLY valid JSON, no markdown formatting."""

            response = client.messages.create(
                model="claude-3-sonnet-20240229",
                max_tokens=2000,
                temperature=0.3,
                system="You are a precise biomedical research analyst. Always return valid JSON only.",
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = response.content[0].text.strip()
            
            # Clean JSON (remove markdown if present)
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            # Parse JSON
            parsed = json.loads(response_text)
            
            # Format mechanisms as list of strings for compatibility
            mechanisms = []
            if isinstance(parsed.get("mechanisms"), list):
                for mech in parsed.get("mechanisms", []):
                    if isinstance(mech, dict):
                        mechanisms.append(mech.get("mechanism", ""))
                    elif isinstance(mech, str):
                        mechanisms.append(mech)
            
            return {
                "mechanisms": mechanisms[:10],  # Limit to top 10
                "dosage": parsed.get("dosage", {}).get("recommended_dose", "") or parsed.get("dosage", ""),
                "safety": parsed.get("safety", {}).get("concerns", []) or [],
                "outcomes": [o.get("outcome", "") if isinstance(o, dict) else str(o) for o in parsed.get("outcomes", [])]
            }
            
        except ImportError:
            print("⚠️ Anthropic library not installed")
            return None
        except json.JSONDecodeError as e:
            print(f"⚠️ Failed to parse Anthropic JSON response: {e}")
            return None
        except Exception as e:
            print(f"⚠️ Anthropic API error: {e}")
            return None
    
    async def _call_openai_llm(
        self, 
        compound: str, 
        disease: str, 
        papers_text: str
    ) -> Optional[Dict[str, Any]]:
        """Call OpenAI API for paper synthesis."""
        try:
            import openai
            import os
            
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                return None
            
            client = openai.AsyncOpenAI(api_key=api_key)
            
            prompt = f"""Read these research papers about {compound} for {disease} and extract:

1. Mechanisms of action (how {compound} works)
2. Dosage information (if mentioned)
3. Safety concerns
4. Clinical outcomes

Papers:
{papers_text}

Return JSON:
{{
  "mechanisms": ["mechanism1", "mechanism2"],
  "dosage": "extracted dose or empty",
  "safety": ["concern1", "concern2"],
  "outcomes": ["outcome1", "outcome2"]
}}"""

            response = await client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {"role": "system", "content": "You are a biomedical research analyst. Return valid JSON only."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                max_tokens=1500
            )
            
            response_text = response.choices[0].message.content.strip()
            
            # Clean JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            return {
                "mechanisms": parsed.get("mechanisms", [])[:10],
                "dosage": parsed.get("dosage", ""),
                "safety": parsed.get("safety", []),
                "outcomes": parsed.get("outcomes", [])
            }
            
        except ImportError:
            return None
        except Exception as e:
            print(f"⚠️ OpenAI API error: {e}")
            return None
    
    async def _call_llm_agnostic(
        self, 
        compound: str, 
        disease: str, 
        papers_text: str
    ) -> Optional[Dict[str, Any]]:
        """
        Call LLM (Cohere in production) via abstraction layer for structured extraction.
        
        Replaces _call_gemini_llm with LLM-agnostic implementation.
        """
        if not LLM_AVAILABLE:
            logger.warning("LLM abstraction layer not available")
            return None
        
        try:
            # Get LLM provider (auto-detects Cohere from env vars)
            provider = get_llm_provider()
            
            if not provider or not provider.is_available():
                logger.warning(f"LLM provider not available. Check API key.")
                return None
            
            # Rate limiting: Cohere allows 20 requests/min for Chat endpoints
            await asyncio.sleep(3.0)  # 3s delay between calls (20/min = 1 per 3s)
            
            system_message = "You are a biomedical research analyst. Extract structured information from research papers."
            
            prompt = f"""Read these research papers about {compound} for {disease} and extract structured information.

Papers:
{papers_text[:8000]}

Extract and return a JSON object with this exact structure:
{{
  "mechanisms": [
    {{
      "mechanism": "brief_name",
      "description": "how it works",
      "confidence": 0.85
    }}
  ],
  "dosage": {{
    "recommended_dose": "extracted dose or empty string",
    "evidence": "quote supporting dose"
  }},
  "safety": {{
    "concerns": ["list of safety concerns or empty"],
    "monitoring": ["what to monitor or empty"]
  }},
  "outcomes": [
    {{
      "outcome": "survival improvement",
      "details": "what the papers say"
    }}
  ]
}}

Return ONLY valid JSON, no markdown formatting."""

            # Retry logic for rate limits
            max_retries = 3
            response_text = None
            
            for attempt in range(max_retries):
                try:
                    llm_response = await provider.chat(
                        message=prompt,
                        system_message=system_message,
                        max_tokens=2000,
                        temperature=0.0
                    )
                    response_text = llm_response.text
                    break  # Success, exit retry loop
                except Exception as e:
                    error_str = str(e).lower()
                    if ("429" in error_str or "quota" in error_str or "rate limit" in error_str) and attempt < max_retries - 1:
                        # Exponential backoff: 2^attempt seconds
                        delay = (2 ** attempt) * 3.0  # 3s, 6s, 12s
                        logger.warning(f"⚠️ LLM rate limit hit (attempt {attempt + 1}/{max_retries}). Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        # Non-rate-limit error or max retries reached
                        logger.error(f"LLM error: {e}")
                        raise
            
            if not response_text:
                return None
            
            response_text = response_text.strip()
            
            # Clean JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            mechanisms = []
            if isinstance(parsed.get("mechanisms"), list):
                for mech in parsed.get("mechanisms", []):
                    if isinstance(mech, dict):
                        mechanisms.append(mech.get("mechanism", ""))
                    elif isinstance(mech, str):
                        mechanisms.append(mech)
            
            return {
                "mechanisms": mechanisms[:10],
                "dosage": parsed.get("dosage", {}).get("recommended_dose", "") if isinstance(parsed.get("dosage"), dict) else parsed.get("dosage", ""),
                "safety": parsed.get("safety", {}).get("concerns", []) if isinstance(parsed.get("safety"), dict) else parsed.get("safety", []),
                "outcomes": [o.get("outcome", "") if isinstance(o, dict) else str(o) for o in parsed.get("outcomes", [])]
            }
                
        except Exception as e:
            logger.error(f"⚠️ LLM extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # Backward compatibility alias
    async def _call_gemini_llm(self, compound: str, disease: str, papers_text: str) -> Optional[Dict[str, Any]]:
        """Backward compatibility alias - redirects to LLM-agnostic method."""
        return await self._call_llm_agnostic(compound, disease, papers_text)
    
    async def _call_llm_agnostic_comprehensive(
        self,
        compound: str,
        disease: str,
        papers_text: str,
        articles: List[Dict[str, Any]] = None,
        sub_questions: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """
        OPTIMIZED: ONE comprehensive LLM call (Cohere in production) that handles:
        - Per-article summaries (all articles at once)
        - Structured extraction (mechanisms, dosage, safety, outcomes)
        - Sub-question answers (all at once)
        
        Reduces API calls from 10+ → 1 per query.
        
        Replaces _call_gemini_llm_comprehensive with LLM-agnostic implementation.
        """
        if not LLM_AVAILABLE:
            logger.warning("LLM abstraction layer not available")
            return None
        
        try:
            # Get LLM provider (auto-detects Cohere from env vars)
            provider = get_llm_provider()
            
            if not provider or not provider.is_available():
                logger.warning(f"LLM provider not available. Check API key.")
                return None
            
            # Rate limiting: Cohere allows 20 requests/min for Chat endpoints
            await asyncio.sleep(3.0)  # 3s delay between calls (20/min = 1 per 3s)
            
            system_message = "You are a biomedical research analyst. Extract comprehensive information from research papers."
            
            # Build comprehensive prompt
            prompt_parts = [
                f"Read these research papers about {compound} for {disease} and extract comprehensive information.",
                "",
                "Papers:",
                papers_text[:12000],  # Increased limit for comprehensive call
                "",
                "Extract and return a JSON object with this exact structure:"
            ]
            
            json_structure = {
                "mechanisms": [
                    {"mechanism": "brief_name", "description": "how it works", "confidence": 0.85}
                ],
                "dosage": {
                    "recommended_dose": "extracted dose or empty string",
                    "evidence": "quote supporting dose"
                },
                "safety": {
                    "concerns": ["list of safety concerns or empty"],
                    "monitoring": ["what to monitor or empty"]
                },
                "outcomes": [
                    {"outcome": "survival improvement", "details": "what the papers say"}
                ]
            }
            
            # Add per-article summaries if articles provided
            if articles:
                json_structure["article_summaries"] = [
                    {
                        "pmid": "article_pmid",
                        "title": "article_title",
                        "summary": "brief_summary",
                        "mechanisms": ["mech1"],
                        "dosage": {},
                        "safety": {},
                        "outcomes": []
                    }
                ]
                prompt_parts.append("For each article provided, generate a brief summary, extract its key mechanisms, dosage, safety, and outcomes, and include them in an 'article_summaries' array.")
            
            # Add sub-question answers if sub-questions provided
            if sub_questions:
                json_structure["sub_question_answers"] = [
                    {
                        "sub_question": "question text",
                        "answer": "direct answer",
                        "confidence": 0.85,
                        "sources": ["pmid1", "pmid2"],
                        "mechanisms": ["mech1"]
                    }
                ]
                prompt_parts.append(f"Answer these sub-questions: {', '.join(sub_questions[:5])}")
                prompt_parts.append("Include answers in a 'sub_question_answers' array.")
            
            prompt_parts.append(json.dumps(json_structure, indent=2))
            prompt_parts.append("Return ONLY valid JSON, no markdown formatting.")
            
            prompt = "\n".join(prompt_parts)
            
            # Retry logic for rate limits
            max_retries = 3
            response_text = None
            
            for attempt in range(max_retries):
                try:
                    llm_response = await provider.chat(
                        message=prompt,
                        system_message=system_message,
                        max_tokens=4000,  # Increased for comprehensive extraction
                        temperature=0.0
                    )
                    response_text = llm_response.text
                    break
                except Exception as e:
                    error_str = str(e).lower()
                    if ("429" in error_str or "quota" in error_str or "rate limit" in error_str) and attempt < max_retries - 1:
                        delay = (2 ** attempt) * 3.0  # 3s, 6s, 12s (longer backoff)
                        logger.warning(f"⚠️ LLM rate limit hit (attempt {attempt + 1}/{max_retries}). Retrying in {delay:.1f}s...")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"LLM error: {e}")
                        raise
            
            if not response_text:
                return None
            
            response_text = response_text.strip()
            
            # Clean JSON
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            parsed = json.loads(response_text)
            
            # Extract mechanisms
            mechanisms = []
            if isinstance(parsed.get("mechanisms"), list):
                for mech in parsed.get("mechanisms", []):
                    if isinstance(mech, dict):
                        mechanisms.append(mech.get("mechanism", ""))
                    elif isinstance(mech, str):
                        mechanisms.append(mech)
            
            result = {
                "mechanisms": mechanisms[:10],
                "dosage": parsed.get("dosage", {}).get("recommended_dose", "") if isinstance(parsed.get("dosage"), dict) else parsed.get("dosage", ""),
                "safety": parsed.get("safety", {}).get("concerns", []) if isinstance(parsed.get("safety"), dict) else parsed.get("safety", []),
                "outcomes": [o.get("outcome", "") if isinstance(o, dict) else str(o) for o in parsed.get("outcomes", [])]
            }
            
            # Add article summaries if present
            if "article_summaries" in parsed:
                result["article_summaries"] = parsed["article_summaries"]
            
            # Add sub-question answers if present
            if "sub_question_answers" in parsed:
                result["sub_question_answers"] = parsed["sub_question_answers"]
            
            return result
                
        except Exception as e:
            logger.error(f"⚠️ Comprehensive LLM extraction error: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    # Backward compatibility alias
    async def _call_gemini_llm_comprehensive(
        self,
        compound: str,
        disease: str,
        papers_text: str,
        articles: List[Dict[str, Any]] = None,
        sub_questions: List[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Backward compatibility alias - redirects to LLM-agnostic method."""
        return await self._call_llm_agnostic_comprehensive(compound, disease, papers_text, articles, sub_questions)
    
    def _extract_mechanisms_from_text(self, text: str) -> List[str]:
        """Simple mechanism extraction from text (can be enhanced)."""
        mechanisms = []
        text_lower = text.lower()
        
        # Common mechanism keywords
        mechanism_keywords = {
            "anti-inflammatory": ["inflammation", "nf-kb", "nf-kappa-b", "cox-2"],
            "antioxidant": ["antioxidant", "oxidative stress", "glutathione"],
            "angiogenesis": ["angiogenesis", "vegf", "vascular"],
            "dna repair": ["dna repair", "brca", "parp"],
            "apoptosis": ["apoptosis", "cell death", "caspase"],
            "cell cycle": ["cell cycle", "cdk", "cyclin"]
        }
        
        for mechanism, keywords in mechanism_keywords.items():
            if any(keyword in text_lower for keyword in keywords):
                mechanisms.append(mechanism)
        
        return mechanisms[:5]  # Limit to top 5
    
    def grade_evidence(self, papers: List[Dict], synthesis: Dict[str, Any]) -> str:
        """
        Grade evidence strength based on:
        - Study types (RCT > Observational > Case studies)
        - Sample sizes
        - Publication quality
        - Consistency across papers
        """
        if not papers:
            return "INSUFFICIENT"
        
        # Simple grading (full implementation would analyze each paper)
        paper_count = len(papers)
        
        # Look for RCT indicators in titles/abstracts
        has_rct = any(
            "randomized" in p.get("title", "").lower() or 
            "randomized" in p.get("abstract", "").lower() or
            "RCT" in p.get("title", "").upper()
            for p in papers
        )
        
        if has_rct and paper_count >= 3:
            return "STRONG"
        elif paper_count >= 5:
            return "MODERATE"
        elif paper_count >= 2:
            return "WEAK"
        else:
            return "INSUFFICIENT"
    
    async def get_complete_evidence(
        self,
        compound: str,
        disease: str,
        pathways: List[str] = None,
        treatment_line: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get complete evidence package for compound with optional treatment line filtering.
        
        Args:
            compound: Compound name
            disease: Disease name
            pathways: List of pathways (optional)
            treatment_line: Treatment line context (e.g., "L1", "first-line", "maintenance") (optional)
        
        Returns:
            {
                "papers": [...],
                "evidence_grade": "STRONG/MODERATE/WEAK/INSUFFICIENT",
                "mechanisms": [...],
                "dosage": "...",
                "safety": "...",
                "outcomes": [...],
                "total_papers": 15,
                "rct_count": 2,
                "treatment_line_filtered": true/false
            }
        """
        # Check cache (include treatment_line in cache key if provided)
        cache_key = f"{compound.lower()}_{disease.lower()}"
        if treatment_line:
            cache_key += f"_{treatment_line.lower()}"
        
        if cache_key in self.cache:
            return self.cache[cache_key]
        
        # Build query with treatment line context
        query = self._build_pubmed_query(compound, disease, pathways, treatment_line)
        
        # Search PubMed
        papers = await self.search_pubmed(query, max_results=20)
        
        # Filter papers by treatment line relevance if treatment_line provided
        if treatment_line and papers:
            papers = self._filter_papers_by_treatment_line(papers, treatment_line)
        
        # Synthesize with LLM (includes evidence grading)
        synthesis = await self.synthesize_evidence_llm(compound, disease, papers)
        
        # Use grade from synthesis (already computed by heuristic or LLM)
        evidence_grade = synthesis.get("evidence_grade", self.grade_evidence(papers, synthesis))
        
        # Count RCTs
        rct_count = sum(
            1 for p in papers
            if "randomized" in p.get("title", "").lower() or "RCT" in p.get("title", "").upper()
        )
        
        result = {
            "compound": compound,
            "disease": disease,
            "papers": papers[:10],  # Top 10 for display
            "total_papers": len(papers),
            "rct_count": rct_count,
            "evidence_grade": evidence_grade,
            "mechanisms": synthesis.get("mechanisms", []),
            "dosage": synthesis.get("dosage", ""),
            "safety": synthesis.get("safety", ""),
            "outcomes": synthesis.get("outcomes", []),
            "query_used": query,
            "treatment_line_filtered": bool(treatment_line)
        }
        
        # Cache result
        self.cache[cache_key] = result
        
        return result
    
    def _filter_papers_by_treatment_line(self, papers: List[Dict[str, Any]], treatment_line: str) -> List[Dict[str, Any]]:
        """
        Filter and rank papers by treatment line relevance.
        
        Prioritizes papers that mention treatment line-specific terms in title/abstract.
        """
        treatment_line_lower = treatment_line.lower()
        
        # Define treatment line keywords
        if any(term in treatment_line_lower for term in ["l1", "first", "frontline", "primary", "initial"]):
            relevant_terms = ["first-line", "frontline", "primary", "initial treatment", "neoadjuvant", "adjuvant"]
        elif any(term in treatment_line_lower for term in ["l2", "second", "second-line"]):
            relevant_terms = ["second-line", "second line", "salvage", "relapsed", "recurrent"]
        elif any(term in treatment_line_lower for term in ["l3", "third", "third-line", "maintenance"]):
            relevant_terms = ["third-line", "third line", "maintenance", "salvage", "refractory", "resistant"]
        else:
            # Unknown treatment line - return papers as-is
            return papers
        
        # Score papers by treatment line relevance
        scored_papers = []
        for paper in papers:
            title = paper.get("title", "").lower()
            abstract = paper.get("abstract", "").lower()
            text_combined = title + " " + abstract
            
            # Count relevant term matches
            relevance_score = sum(1 for term in relevant_terms if term in text_combined)
            
            # Add relevance score to paper
            paper["treatment_line_relevance"] = relevance_score
            scored_papers.append(paper)
        
        # Sort by relevance score (descending), then by quality score if available
        scored_papers.sort(
            key=lambda p: (
                p.get("treatment_line_relevance", 0),
                p.get("quality_score", 0)
            ),
            reverse=True
        )
        
        return scored_papers


# Singleton
_evidence_service_instance = None

def get_enhanced_evidence_service() -> EnhancedEvidenceService:
    """Get singleton instance."""
    global _evidence_service_instance
    if _evidence_service_instance is None:
        _evidence_service_instance = EnhancedEvidenceService()
    return _evidence_service_instance

