"""
Audit Trail Writer
Append-only audit log with SHA-256 hash chaining for HIPAA compliance.
"""
import hashlib
import json
import logging
import os
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from pathlib import Path

logger = logging.getLogger(__name__)

AUDIT_ENABLED = os.getenv("AUDIT_ENABLED", "false").lower() == "true"
AUDIT_LOG_DIR = os.getenv("AUDIT_LOG_DIR", "./audit_logs")
AUDIT_TTL_DAYS = int(os.getenv("HIPAA_AUDIT_TTL_DAYS", "2555"))  # Default: 7 years (HIPAA requirement)


class AuditWriter:
    """
    Append-only audit log writer with SHA-256 hash chaining.
    
    Each audit record includes:
    - timestamp
    - user_id (if authenticated)
    - action
    - resource_type
    - resource_id
    - phi_accessed (boolean)
    - ip_address
    - user_agent
    - previous_hash (for chain verification)
    - current_hash (SHA-256 of previous_hash + record)
    
    Hash chaining ensures audit log integrity:
    - Each record's hash includes the previous record's hash
    - Any tampering breaks the chain
    - Can verify integrity by recalculating hashes
    """
    
    def __init__(self, log_dir: str = AUDIT_LOG_DIR):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.current_file = None
        self.last_hash = None
        self._load_last_hash()
    
    def _get_log_file(self) -> Path:
        """Get current log file (daily rotation)."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        return self.log_dir / f"audit_{today}.log"
    
    def _load_last_hash(self):
        """Load the last hash from the most recent log file."""
        try:
            # Find the most recent log file
            log_files = sorted(self.log_dir.glob("audit_*.log"), reverse=True)
            if log_files:
                with open(log_files[0], "r") as f:
                    lines = f.readlines()
                    if lines:
                        # Get last line's hash
                        last_line = lines[-1].strip()
                        if last_line:
                            try:
                                record = json.loads(last_line)
                                self.last_hash = record.get("current_hash")
                            except json.JSONDecodeError:
                                pass
        except Exception as e:
            logger.warning(f"Failed to load last hash: {e}")
        
        # If no previous hash, start with genesis hash
        if not self.last_hash:
            self.last_hash = hashlib.sha256(b"GENESIS").hexdigest()
    
    def _calculate_hash(self, record: Dict[str, Any], previous_hash: Optional[str] = None) -> str:
        """
        Calculate SHA-256 hash of record with previous hash.
        
        Hash = SHA256(previous_hash + JSON.stringify(record))
        """
        prev = previous_hash or self.last_hash or hashlib.sha256(b"GENESIS").hexdigest()
        record_str = json.dumps(record, sort_keys=True, default=str)
        combined = f"{prev}{record_str}".encode("utf-8")
        return hashlib.sha256(combined).hexdigest()
    
    def write(
        self,
        user_id: Optional[str],
        action: str,
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
        phi_accessed: bool = False,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        session_id: Optional[str] = None,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Write an audit record.
        
        Args:
            user_id: User UUID (if authenticated)
            action: Action performed (e.g., "login", "view_patient", "update_profile")
            resource_type: Type of resource accessed (e.g., "patient", "analysis")
            resource_id: ID of resource accessed
            phi_accessed: Whether PHI was accessed
            ip_address: Client IP address
            user_agent: Client user agent
            session_id: Session ID
            additional_data: Additional metadata
            
        Returns:
            True if write successful, False otherwise
        """
        if not AUDIT_ENABLED:
            return False
        
        try:
            # Create audit record
            record = {
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "user_id": user_id,
                "action": action,
                "resource_type": resource_type,
                "resource_id": resource_id,
                "phi_accessed": phi_accessed,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "session_id": session_id,
                "previous_hash": self.last_hash,
            }
            
            # Add additional data if provided
            if additional_data:
                record["additional_data"] = additional_data
            
            # Calculate hash
            current_hash = self._calculate_hash(record, self.last_hash)
            record["current_hash"] = current_hash
            
            # Write to log file (append-only)
            log_file = self._get_log_file()
            with open(log_file, "a") as f:
                f.write(json.dumps(record) + "\n")
            
            # Update last hash
            self.last_hash = current_hash
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to write audit record: {e}")
            return False
    
    def verify_chain(self, log_file: Optional[Path] = None) -> tuple[bool, int]:
        """
        Verify the hash chain integrity of a log file.
        
        Returns:
            (is_valid, error_count)
        """
        if log_file is None:
            log_file = self._get_log_file()
        
        if not log_file.exists():
            return True, 0
        
        try:
            previous_hash = hashlib.sha256(b"GENESIS").hexdigest()
            error_count = 0
            
            with open(log_file, "r") as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()
                    if not line:
                        continue
                    
                    try:
                        record = json.loads(line)
                        expected_hash = record.get("current_hash")
                        expected_prev = record.get("previous_hash")
                        
                        # Verify previous hash matches
                        if expected_prev != previous_hash:
                            logger.warning(f"Hash chain broken at line {line_num}: previous hash mismatch")
                            error_count += 1
                        
                        # Verify current hash
                        # Recalculate without the hash fields
                        record_for_hash = {k: v for k, v in record.items() if k not in ("current_hash", "previous_hash")}
                        calculated_hash = self._calculate_hash(record_for_hash, previous_hash)
                        
                        if calculated_hash != expected_hash:
                            logger.warning(f"Hash chain broken at line {line_num}: hash mismatch")
                            error_count += 1
                        
                        previous_hash = expected_hash
                        
                    except json.JSONDecodeError as e:
                        logger.warning(f"Invalid JSON at line {line_num}: {e}")
                        error_count += 1
            
            return error_count == 0, error_count
            
        except Exception as e:
            logger.error(f"Failed to verify hash chain: {e}")
            return False, 1


# Global audit writer instance
_audit_writer: Optional[AuditWriter] = None


def get_audit_writer() -> AuditWriter:
    """Get global audit writer instance (singleton)."""
    global _audit_writer
    if _audit_writer is None:
        _audit_writer = AuditWriter()
    return _audit_writer



































