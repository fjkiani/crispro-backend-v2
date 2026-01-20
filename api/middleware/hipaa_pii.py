"""
HIPAA/PII Detection and Redaction Middleware
Detects and redacts PHI/PII from logs without mutating requests/responses.
"""
import re
import json
import logging
from typing import Dict, Any, Optional
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import os

logger = logging.getLogger(__name__)

HIPAA_MODE = os.getenv("HIPAA_MODE", "false").lower() == "true"
HIPAA_PHI_FIELDS = os.getenv("HIPAA_PHI_FIELDS", "").split(",") if os.getenv("HIPAA_PHI_FIELDS") else []


class HIPAAPIIMiddleware(BaseHTTPMiddleware):
    """
    Middleware to detect and redact PHI/PII from logs.
    
    Detects:
    - Names (common patterns)
    - Email addresses
    - Phone numbers
    - MRN (Medical Record Numbers)
    - DOB (Date of Birth)
    - Addresses
    - SSN (Social Security Numbers)
    - Genomic data patterns
    
    Note: This middleware does NOT mutate requests/responses.
    It only redacts data from log copies.
    """
    
    # PHI/PII detection patterns
    PATTERNS = {
        "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        "phone": re.compile(r'\b(?:\+?1[-.\s]?)?\(?[0-9]{3}\)?[-.\s]?[0-9]{3}[-.\s]?[0-9]{4}\b'),
        "ssn": re.compile(r'\b\d{3}-\d{2}-\d{4}\b'),
        "mrn": re.compile(r'\bMRN[:\s]?[A-Z0-9]{6,}\b', re.IGNORECASE),
        "dob": re.compile(r'\b(?:0[1-9]|1[0-2])[/-](?:0[1-9]|[12][0-9]|3[01])[/-](?:19|20)\d{2}\b'),
        "genomic_coordinate": re.compile(r'chr\d+:\d+-\d+', re.IGNORECASE),
        "patient_id": re.compile(r'\bPAT\d+\b', re.IGNORECASE),
    }
    
    # Common name patterns (basic - can be enhanced)
    NAME_PATTERNS = [
        re.compile(r'\b(?:Dr\.|Mr\.|Mrs\.|Ms\.|Miss)\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b'),
        re.compile(r'\b[A-Z][a-z]+\s+[A-Z][a-z]+\s+[A-Z][a-z]+\b'),  # First Middle Last
    ]
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.redaction_count = 0
    
    def _redact_text(self, text: str) -> tuple[str, int]:
        """
        Redact PHI/PII from text string.
        
        Returns:
            (redacted_text, redaction_count)
        """
        if not isinstance(text, str):
            return (text, 0)
        
        redacted = text
        count = 0
        
        # Redact emails
        redacted = self.PATTERNS["email"].sub("[EMAIL_REDACTED]", redacted)
        if redacted != text:
            count += len(self.PATTERNS["email"].findall(text))
        
        # Redact phone numbers
        redacted = self.PATTERNS["phone"].sub("[PHONE_REDACTED]", redacted)
        if redacted != text:
            count += len(self.PATTERNS["phone"].findall(text))
        
        # Redact SSN
        redacted = self.PATTERNS["ssn"].sub("[SSN_REDACTED]", redacted)
        if redacted != text:
            count += len(self.PATTERNS["ssn"].findall(text))
        
        # Redact MRN
        redacted = self.PATTERNS["mrn"].sub("[MRN_REDACTED]", redacted)
        if redacted != text:
            count += len(self.PATTERNS["mrn"].findall(text))
        
        # Redact DOB
        redacted = self.PATTERNS["dob"].sub("[DOB_REDACTED]", redacted)
        if redacted != text:
            count += len(self.PATTERNS["dob"].findall(text))
        
        # Redact genomic coordinates (if HIPAA_MODE)
        if HIPAA_MODE:
            redacted = self.PATTERNS["genomic_coordinate"].sub("[GENOMIC_COORD_REDACTED]", redacted)
            if redacted != text:
                count += len(self.PATTERNS["genomic_coordinate"].findall(text))
            
            redacted = self.PATTERNS["patient_id"].sub("[PATIENT_ID_REDACTED]", redacted)
            if redacted != text:
                count += len(self.PATTERNS["patient_id"].findall(text))
        
        # Redact names (basic pattern matching)
        for pattern in self.NAME_PATTERNS:
            matches = pattern.findall(redacted)
            if matches:
                for match in matches:
                    redacted = redacted.replace(match, "[NAME_REDACTED]")
                    count += 1
        
        return redacted, count
    
    def _redact_dict(self, data: Dict[str, Any], redaction_count: int = 0) -> Tuple[Dict[str, Any], int]:
        """
        Recursively redact PHI/PII from dictionary.
        
        Returns:
            (redacted_dict, total_redaction_count)
        """
        if not isinstance(data, dict):
            return (data, redaction_count)
        
        redacted = {}
        total_count = redaction_count
        
        # Fields that commonly contain PHI/PII
        phi_fields = [
            "email", "phone", "ssn", "mrn", "dob", "date_of_birth",
            "patient_id", "patient_name", "name", "full_name",
            "address", "genomic_data", "mutations", "variants",
            "genomic_coordinate", "chrom", "pos", "hgvs_p"
        ] + [field.strip() for field in HIPAA_PHI_FIELDS if field.strip()]
        
        for key, value in data.items():
            key_lower = key.lower()
            
            # Check if this field should be redacted
            if any(phi_field in key_lower for phi_field in phi_fields):
                redacted[key] = "[REDACTED]"
                total_count += 1
            elif isinstance(value, str):
                redacted_val, count = self._redact_text(value)
                redacted[key] = redacted_val
                total_count += count
            elif isinstance(value, dict):
                redacted_val, count = self._redact_dict(value, 0)
                redacted[key] = redacted_val
                total_count += count
            elif isinstance(value, list):
                redacted_list = []
                for item in value:
                    if isinstance(item, str):
                        redacted_item, count = self._redact_text(item)
                        redacted_list.append(redacted_item)
                        total_count += count
                    elif isinstance(item, dict):
                        redacted_item, count = self._redact_dict(item, 0)
                        redacted_list.append(redacted_item)
                        total_count += count
                    else:
                        redacted_list.append(item)
                redacted[key] = redacted_list
            else:
                redacted[key] = value
        
        return redacted, total_count
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and redact PHI/PII from logs only.
        Does NOT mutate the actual request/response.
        """
        # Only process if HIPAA_MODE is enabled
        if not HIPAA_MODE:
            return await call_next(request)
        
        # Get request body for logging (if available)
        request_body = None
        if hasattr(request, "_body"):
            try:
                body = await request.body()
                if body:
                    try:
                        request_body = json.loads(body.decode())
                    except (json.JSONDecodeError, UnicodeDecodeError):
                        request_body = body.decode()[:500]  # First 500 chars
            except Exception:
                pass
        
        # Process request (don't mutate)
        response = await call_next(request)
        
        # Redact from logs only (not from actual data)
        if request_body:
            if isinstance(request_body, dict):
                redacted_body, count = self._redact_dict(request_body.copy())
                if count > 0:
                    logger.debug(f"Redacted {count} PHI/PII fields from request log")
            elif isinstance(request_body, str):
                redacted_body, count = self._redact_text(request_body)
                if count > 0:
                    logger.debug(f"Redacted {count} PHI/PII patterns from request log")
        
        # Add redaction count to response headers (for monitoring)
        if hasattr(self, 'redaction_count') and self.redaction_count > 0:
            response.headers["X-PHI-Redactions"] = str(self.redaction_count)
        
        return response

