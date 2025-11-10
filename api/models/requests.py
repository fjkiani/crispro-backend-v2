"""
Request models for the oncology backend API.
"""
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class VariantRequest(BaseModel):
    mutation: str
    gene: Optional[str] = None
    
class TherapeuticRequest(BaseModel):
    target: str
    mutation: str

class DossierRequest(BaseModel):
    target: str
    mutation: str
    analysis_type: str = "comprehensive"

class MyelomaRequest(BaseModel):
    mutations: List[Dict[str, Any]]
    model_id: str = "evo2_7b"
    options: Optional[Dict[str, Any]] = None

class EvidenceRequest(BaseModel):
    gene: str
    hgvs_p: str
    disease: str = "multiple myeloma"
    time_window: str = "since 2015"
    max_results: int = 10
    include_abstracts: bool = False
    synthesize: bool = False

class DeepAnalysisRequest(BaseModel):
    gene: str
    hgvs_p: str
    assembly: str = "GRCh38"
    chrom: str
    pos: int
    ref: str
    alt: str
    clinvar_url: Optional[str] = None
    our_interpretation: Optional[str] = None
    our_confidence: Optional[float] = None

class JobRequest(BaseModel):
    job_id: Optional[str] = None

class CrawlJobRequest(JobRequest):
    urls: List[str]

class SummarizeJobRequest(JobRequest):
    extracted_texts: List[Dict[str, Any]]
    gene: Optional[str] = None
    variant: Optional[str] = None

class AlignJobRequest(JobRequest):
    summaries: List[Dict[str, Any]]
    evo2_result: Dict[str, Any]
    clinvar: Dict[str, Any] 