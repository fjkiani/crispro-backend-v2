import os
import requests
import time
import xml.etree.ElementTree as ET
import json
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

from .utils import chunked, clean_text, parse_year_from_pubdate

EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

@dataclass
class PubMedClient:
    email: Optional[str] = None
    api_key: Optional[str] = None
    tool: str = "ClinicalTrialsAgent"
    timeout: int = 30
    session: requests.Session = field(default_factory=requests.Session)
    rate_limit_delay: float = 0.1

    def _base_params(self) -> Dict[str, str]:
        params = {"tool": self.tool}
        if self.email:
            params["email"] = self.email
        if self.api_key:
            params["api_key"] = self.api_key
        return params

    def _make_request(self, url: str, params: Dict[str, str]) -> requests.Response:
        time.sleep(self.rate_limit_delay)
        try:
            r = self.session.get(url, params=params, timeout=self.timeout)
            r.raise_for_status()
            return r
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"PubMed API request failed: {e}") from e

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
        r = self._make_request(url, params)
        try:
            return r.json()["esearchresult"]
        except (json.JSONDecodeError, KeyError) as e:
            raise RuntimeError(f"Invalid ESearch response: {e}")

    def esummary(self, pmids: List[str]) -> Dict[str, Dict[str, Any]]:
        summaries: Dict[str, Dict[str, Any]] = {}
        url = f"{EUTILS_BASE}/esummary.fcgi"
        for batch in chunked(pmids, 200):
            params = self._base_params()
            params.update({
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "json",
            })
            r = self._make_request(url, params)
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
        url = f"{EUTILS_BASE}/efetch.fcgi"
        out: Dict[str, Dict[str, Any]] = {}

        for batch in chunked(pmids, 200):
            params = self._base_params()
            params.update({
                "db": "pubmed",
                "id": ",".join(batch),
                "retmode": "xml",
            })
            r = self._make_request(url, params)

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
