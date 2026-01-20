"""
PGx Production Monitoring Service

Sprint 7: Production Hardening
Purpose: Monitor PGx service health, track errors, and provide observability

Research Use Only - Not for Clinical Decision Making
"""

import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
from dataclasses import dataclass, field, asdict
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class PGxServiceMetrics:
    """Metrics for PGx service monitoring."""
    service_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    average_response_time_ms: float = 0.0
    error_counts: Dict[str, int] = field(default_factory=lambda: defaultdict(int))
    last_error: Optional[str] = None
    last_error_time: Optional[str] = None
    last_success_time: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return asdict(self)


class PGxProductionMonitor:
    """
    Monitor PGx service health and performance.
    """
    
    def __init__(self):
        self.metrics: Dict[str, PGxServiceMetrics] = {}
        self._response_times: Dict[str, List[float]] = defaultdict(list)
    
    def record_request(
        self,
        service_name: str,
        success: bool,
        response_time_ms: float,
        error: Optional[str] = None
    ):
        """
        Record a service request.
        
        Args:
            service_name: Name of the service (e.g., "pgx_extraction", "pgx_screening")
            success: Whether the request succeeded
            response_time_ms: Response time in milliseconds
            error: Error message if failed
        """
        if service_name not in self.metrics:
            self.metrics[service_name] = PGxServiceMetrics(service_name=service_name)
        
        metrics = self.metrics[service_name]
        metrics.total_requests += 1
        
        if success:
            metrics.successful_requests += 1
            metrics.last_success_time = datetime.now().isoformat()
        else:
            metrics.failed_requests += 1
            metrics.last_error = error
            metrics.last_error_time = datetime.now().isoformat()
            if error:
                metrics.error_counts[error] += 1
        
        # Update average response time
        self._response_times[service_name].append(response_time_ms)
        # Keep only last 100 response times
        if len(self._response_times[service_name]) > 100:
            self._response_times[service_name] = self._response_times[service_name][-100:]
        
        metrics.average_response_time_ms = sum(self._response_times[service_name]) / len(self._response_times[service_name])
    
    def get_health_status(self) -> Dict[str, Any]:
        """
        Get overall health status of PGx services.
        
        Returns:
            Dict with health status for each service
        """
        health = {}
        
        for service_name, metrics in self.metrics.items():
            success_rate = (
                metrics.successful_requests / metrics.total_requests
                if metrics.total_requests > 0 else 0.0
            )
            
            is_healthy = (
                success_rate >= 0.95 and
                metrics.average_response_time_ms < 1000.0 and
                metrics.failed_requests < 10
            )
            
            health[service_name] = {
                "healthy": is_healthy,
                "success_rate": success_rate,
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
                "average_response_time_ms": metrics.average_response_time_ms,
                "last_error": metrics.last_error,
                "last_error_time": metrics.last_error_time
            }
        
        return health
    
    def get_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get all metrics."""
        return {
            name: metrics.to_dict()
            for name, metrics in self.metrics.items()
        }
    
    def reset_metrics(self, service_name: Optional[str] = None):
        """Reset metrics for a service or all services."""
        if service_name:
            if service_name in self.metrics:
                del self.metrics[service_name]
            if service_name in self._response_times:
                del self._response_times[service_name]
        else:
            self.metrics.clear()
            self._response_times.clear()


# Singleton instance
_monitor_instance: Optional[PGxProductionMonitor] = None


def get_pgx_monitor() -> PGxProductionMonitor:
    """Get singleton instance of PGx production monitor."""
    global _monitor_instance
    if _monitor_instance is None:
        _monitor_instance = PGxProductionMonitor()
    return _monitor_instance


