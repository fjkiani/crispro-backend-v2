"""
Response models for the oncology backend API.
"""
from pydantic import BaseModel
from typing import Dict, Any, List, Optional

class HealthResponse(BaseModel):
    status: str
    services: str

class JobResponse(BaseModel):
    job_id: str
    status: str

class JobStatusResponse(BaseModel):
    job_id: str
    job_type: str
    status: str
    progress: Dict[str, int]
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str 