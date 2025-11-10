import os
import requests
import time
import xml.etree.ElementTree as ET
import json
import asyncio
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import hashlib
import threading
from .utils import chunked, clean_text, parse_year_from_pubdate

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

@dataclass
class PubMedClientEnhanced:
    """
    Enhanced PubMed client with intelligent rate limiting, caching, and clinical insight extraction.
    """
    email: Optional[str] = None
    api_key: Optional[str] = None
    tool: str = "ClinicalTrialsAgent"
    timeout: int = 30
    session: requests.Session = field(default_factory=requests.Session)

    # Enhanced rate limiting
    base_delay: float = 0.3  # Base delay between requests
    max_delay: float = 10.0  # Maximum delay for exponential backoff
    max_retries: int = 3
    request_history: List[float] = field(default_factory=list)
    last_request_time: float = 0.0

    # Intelligent caching
    cache: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    cache_ttl: int = 3600  # 1 hour cache TTL
    cache_lock: threading.Lock = field(default_factory=threading.Lock)

    def _get_cache_key(self, endpoint: str, params: Dict[str, Any]) -> str:
        """Generate cache key for request"""
        cache_string = f"{endpoint}:{json.dumps(params, sort_keys=True)}"
        return hashlib.md5(cache_string.encode()).hexdigest()

    def _get_cache(self, key: str) -> Optional[Dict[str, Any]]:
        """Get from cache if not expired"""
        with self.cache_lock:
            if key in self.cache:
                cached = self.cache[key]
                if time.time() - cached['timestamp'] < self.cache_ttl:
                    return cached['data']
                else:
                    del self.cache[key]
        return None

    def _set_cache(self, key: str, data: Dict[str, Any]):
        """Set cache entry"""
        with self.cache_lock:
            self.cache[key] = {
                'data': data,
                'timestamp': time.time()
            }

    def _calculate_delay(self) -> float:
        """Calculate adaptive delay based on request history"""
        if not self.request_history:
            return self.base_delay

        # Calculate requests per minute over last 60 seconds
        now = time.time()
        recent_requests = [t for t in self.request_history if now - t < 60]

        if len(recent_requests) < 3:
            return self.base_delay

        rpm = len(recent_requests)
        if rpm > 8:  # NCBI allows ~10 requests/minute without API key
            return min(self.base_delay * (rpm / 8), self.max_delay)
        elif rpm > 25 and self.api_key:  # With API key, allows ~30 requests/minute
            return min(self.base_delay * (rpm / 25), self.max_delay)

        return self.base_delay

    async def _make_request_async(self, url: str, params: Dict[str, str], retry_count: int = 0) -> requests.Response:
        """Make request with intelligent rate limiting and retries"""
        delay = self._calculate_delay()
        if delay > self.base_delay:
            print(f"⚠️ High request rate detected, delaying {delay:.1f}s")
            await asyncio.sleep(delay)

        try:
            # Check cache first
            cache_key = self._get_cache_key(url, params)
            cached = self._get_cache(cache_key)
            if cached:
                print(f"📋 Using cached result for {cache_key[:16]}...")
                return type('MockResponse', (), {'json': lambda: cached, 'text': json.dumps(cached)})()

            # Make actual request
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()

            # Track request
            self.request_history.append(time.time())
            if len(self.request_history) > 100:  # Keep only recent 100
                self.request_history = self.request_history[-100:]

            # Cache successful response
            try:
                response_data = r.json()
                self._set_cache(cache_key, response_data)
            except:
                pass  # Don't cache if not JSON

            return r

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:  # Rate limited
                if retry_count < self.max_retries:
                    retry_delay = min(self.base_delay * (2 ** retry_count), self.max_delay)
                    print(f"⏳ Rate limited, retrying in {retry_delay:.1f}s (attempt {retry_count + 1}/{self.max_retries})")
                    await asyncio.sleep(retry_delay)
                    return await self._make_request_async(url, params, retry_count + 1)
                else:
                    raise RuntimeError("PubMed API rate limit exceeded. Please wait and try again, or use an NCBI API key for higher limits.")
            else:
                raise RuntimeError(f"PubMed API request failed: {e}") from e

        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"PubMed API request failed: {e}") from e

    def _base_params(self) -> Dict[str, str]:
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def esearch(
        self,
        query: str,
        retmax: int = 200,
        retstart: int = 0,
        mindate: Optional[int] = None,
        maxdate: Optional[int] = None,
        sort: str = "relevance",
        pmc_only: bool = False
    ) -> Dict[str, Any]:
        """Enhanced esearch with caching and rate limiting"""
        if pmc_only:
            query = f"({query}) AND pubmed pmc[sb]"

        params = self._base_params()
        params.update({
            "db": "pubmed",
            "term": query,
            "retmode": "json",
            "retmax": str(retmax),
            "retstart": str(retstart),
            "sort": sort,
        })

        if mindate or maxdate:
            params["mindate"] = str(mindate) if mindate else ""
            params["maxdate"] = str(maxdate) if maxdate else ""
            params["datetype"] = "pdat"

        url = f"{EUTILS_BASE}/esearch.fcgi"

        # Run async request in sync context
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            r = loop.run_until_complete(self._make_request_async(url, params))
        finally:
            loop.close()

        try:
            return r.json()["esearchresult"]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Invalid ESearch response: {e}")

    def esummary(self, pmids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Enhanced esummary with batching and caching"""
        summaries: Dict[str, Dict[str, Any]] = {}
        url = f"{EUTILS_BASE}/esummary.fcgi"

        for batch in chunked(pmids, 50):  # Smaller batches for better rate limiting
            params = self._base_params()
            params.update({
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "json",
            })

            # Run async request in sync context
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                r = loop.run_until_complete(self._make_request_async(url, params))
            finally:
                loop.close()

            try:
                data = r.json()
                result = data.get("result", {})
                for pid in batch:
                    if pid in result:
                        summaries[pid] = result[pid]
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Invalid ESummary: {e}")

        return summaries

    def efetch_abstracts(self, pmids: List[str]) -> Dict[str, Dict[str, Any]]:
        """Enhanced efetch with better error handling and caching"""
        url = f"{EUTILS_BASE}/efetch.fcgi"
        out: Dict[str, Dict[str, Any]] = {}

        for batch in chunked(pmids, 20):  # Even smaller batches for abstracts
            params = self._base_params()
            params.update({
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            })

            # Run async request in sync context
            import asyncio
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                r = loop.run_until_complete(self._make_request_async(url, params))
            finally:
                loop.close()

            try:
                root = ET.fromstring(r.text)
                for art in root.findall(".//PubmedArticle"):
                    pid = self._get_text(art, ".//MedlineCitation/PMID")
                    if not pid: continue

                    pmcid = "NA"
                    for aid in art.findall(".//ArticleIdList/ArticleId"):
                        if aid.get("IdType") == "pmc":
                            val = "".join(aid.itertext()).strip()
                            if val.startswith("PMC"):
                                pmcid = val
                            break

                    license_info = "NA"
                    lic_tag = art.find(".//License")
                    if lic_tag is not None:
                        license_info = clean_text(lic_tag.text or "")
                    else:
                        copy_info = art.find(".//CopyrightInformation")
                        if copy_info is not None:
                            license_info = clean_text("".join(copy_info.itertext()))
                    if license_info == "NA" and pmcid != "NA":
                        license_info = "cc by"

                    record = {
                        "abstract": self._extract_abstract(art),
                        "publication_types": self._extract_pubtypes(art),
                        "mesh_headings": self._extract_mesh(art),
                        "journal": self._get_text(art, ".//Journal/Title"),
                        "journal_iso": self._get_text(art, ".//Journal/ISOAbbreviation"),
                        "year": self._extract_year(art),
                        "pmcid": pmcid,
                        "license": license_info,
                    }
                    out[pid] = record
            except ET.ParseError as e:
                raise RuntimeError(f"Invalid XML: {e}")

        return out

    def _get_text(self, node: ET.Element, path: str) -> str:
        el = node.find(path)
        return clean_text(el.text if el is not None and el.text else "")

    def _extract_abstract(self, art: ET.Element) -> str:
        texts = []
        for ab in art.findall(".//Article/Abstract/AbstractText"):
            label = ab.attrib.get("Label") or ab.attrib.get("NlmCategory") or ""
            content = "".join(ab.itertext()).strip()
            if label:
                texts.append(f"{label}: {content}")
            else:
                texts.append(content)
        return clean_text(" ".join(texts))

    def _extract_pubtypes(self, art: ET.Element) -> List[str]:
        types = []
        for pt in art.findall(".//PublicationTypeList/PublicationType"):
            txt = "".join(pt.itertext()).strip()
            if txt:
                types.append(txt)
        return types

    def _extract_mesh(self, art: ET.Element) -> List[str]:
        mhs = []
        for mh in art.findall(".//MeshHeadingList/MeshHeading/DescriptorName"):
            txt = "".join(mh.itertext()).strip()
            if txt:
                mhs.append(txt)
        return mhs

    def _extract_year(self, art: ET.Element) -> Optional[int]:
        y = self._get_text(art, ".//ArticleDate/Year")
        if y.isdigit():
            return int(y)
        y = self._get_text(art, ".//JournalIssue/PubDate/Year")
        if y.isdigit():
            return int(y)
        md = self._get_text(art, ".//JournalIssue/PubDate/MedlineDate")
        return parse_year_from_pubdate(md)
