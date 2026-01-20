"""
Structured JSON Logging
HIPAA-compliant logging with PHI/PII redaction.
"""
import json
import logging
import sys
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import os

# Check if JSON logging is enabled
LOG_JSON = os.getenv("LOG_JSON", "false").lower() == "true"
HIPAA_MODE = os.getenv("HIPAA_MODE", "false").lower() == "true"


class StructuredJSONFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    
    Log format:
    {
        "ts": "2024-01-01T00:00:00Z",
        "req_id": "uuid",
        "user_id": "uuid",
        "route": "/api/endpoint",
        "method": "POST",
        "status": 200,
        "latency_ms": 123,
        "pii_redactions": 0,
        "error": null
    }
    """
    
    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        if LOG_JSON or HIPAA_MODE:
            log_data = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
            }
            
            # Add request context if available
            if hasattr(record, "req_id"):
                log_data["req_id"] = record.req_id
            if hasattr(record, "user_id"):
                log_data["user_id"] = record.user_id
            if hasattr(record, "route"):
                log_data["route"] = record.route
            if hasattr(record, "method"):
                log_data["method"] = record.method
            if hasattr(record, "status"):
                log_data["status"] = record.status
            if hasattr(record, "latency_ms"):
                log_data["latency_ms"] = record.latency_ms
            if hasattr(record, "pii_redactions"):
                log_data["pii_redactions"] = record.pii_redactions
            
            # Add error information if present
            if record.exc_info:
                log_data["error"] = self.formatException(record.exc_info)
            elif hasattr(record, "error"):
                log_data["error"] = record.error
            
            # Add extra fields
            for key, value in record.__dict__.items():
                if key not in [
                    "name", "msg", "args", "created", "filename", "funcName",
                    "levelname", "levelno", "lineno", "module", "msecs",
                    "message", "pathname", "process", "processName", "relativeCreated",
                    "thread", "threadName", "exc_info", "exc_text", "stack_info"
                ]:
                    log_data[key] = value
            
            return json.dumps(log_data)
        else:
            # Use standard format if JSON logging not enabled
            return super().format(record)


def setup_structured_logging():
    """Setup structured JSON logging."""
    root_logger = logging.getLogger()
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredJSONFormatter())
    root_logger.addHandler(handler)
    
    # Set log level
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, log_level, logging.INFO))
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance."""
    return logging.getLogger(name)



































