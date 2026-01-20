"""
Circuit Breaker Pattern for Agent Calls

Prevents cascade failures by temporarily disabling failing agents.
"""
import time
from typing import Callable, Any, Optional
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "CLOSED"  # Normal operation
    OPEN = "OPEN"  # Failing, reject requests
    HALF_OPEN = "HALF_OPEN"  # Testing if service recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern for agent calls.
    
    Prevents cascade failures by temporarily disabling failing agents
    after a threshold of failures.
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        timeout: int = 60,
        success_threshold: int = 2
    ):
        """
        Initialize circuit breaker.
        
        Args:
            failure_threshold: Number of failures before opening circuit
            timeout: Seconds to wait before attempting half-open
            success_threshold: Successes needed in half-open to close circuit
        """
        self.failure_count = 0
        self.success_count = 0
        self.failure_threshold = failure_threshold
        self.timeout = timeout
        self.success_threshold = success_threshold
        self.last_failure_time: Optional[float] = None
        self.state = CircuitState.CLOSED
        self._lock = False  # Simple lock for thread safety
    
    def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Result from func
        
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: If func raises exception
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
                logger.info(f"Circuit breaker transitioning to HALF_OPEN after {self.timeout}s timeout")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (failed {self.failure_count} times). "
                    f"Wait {self.timeout}s before retry."
                )
        
        # Execute function
        try:
            result = func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    logger.info(f"Circuit breaker CLOSED after {self.success_count} successes")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
            
            return result
            
        except Exception as e:
            # Failure - increment failure count
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed in half-open - go back to open
                logger.warning(f"Circuit breaker back to OPEN after failure in HALF_OPEN state")
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif self.failure_count >= self.failure_threshold:
                # Threshold reached - open circuit
                logger.error(
                    f"Circuit breaker OPENED after {self.failure_count} failures "
                    f"(threshold: {self.failure_threshold})"
                )
                self.state = CircuitState.OPEN
            
            raise
    
    async def call_async(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute async function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments
        
        Returns:
            Result from func
        
        Raises:
            CircuitBreakerOpenError: If circuit is OPEN
            Exception: If func raises exception
        """
        # Check circuit state
        if self.state == CircuitState.OPEN:
            # Check if timeout has passed
            if self.last_failure_time and (time.time() - self.last_failure_time) > self.timeout:
                logger.info(f"Circuit breaker transitioning to HALF_OPEN after {self.timeout}s timeout")
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN (failed {self.failure_count} times). "
                    f"Wait {self.timeout}s before retry."
                )
        
        # Execute function
        try:
            result = await func(*args, **kwargs)
            
            # Success - reset failure count
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    logger.info(f"Circuit breaker CLOSED after {self.success_count} successes")
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success
                self.failure_count = 0
            
            return result
            
        except CircuitBreakerOpenError:
            # Re-raise circuit breaker errors
            raise
        except Exception as e:
            # Failure - increment failure count
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.state == CircuitState.HALF_OPEN:
                # Failed in half-open - go back to open
                logger.warning(f"Circuit breaker back to OPEN after failure in HALF_OPEN state")
                self.state = CircuitState.OPEN
                self.success_count = 0
            elif self.failure_count >= self.failure_threshold:
                # Threshold reached - open circuit
                logger.error(
                    f"Circuit breaker OPENED after {self.failure_count} failures "
                    f"(threshold: {self.failure_threshold})"
                )
                self.state = CircuitState.OPEN
            
            raise
    
    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info("Circuit breaker manually reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
    
    def get_state(self) -> dict:
        """Get current circuit breaker state."""
        return {
            'state': self.state.value,
            'failure_count': self.failure_count,
            'failure_threshold': self.failure_threshold,
            'success_count': self.success_count,
            'last_failure_time': self.last_failure_time,
            'timeout': self.timeout
        }

