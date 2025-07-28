"""
Base rate limiter class for Scrawl application.
Provides abstract interface for all rate limiting implementations.
"""
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, Tuple
from django.http import HttpRequest
# Import backend lazily to avoid circular imports
from ..utils.exceptions import RateLimitExceeded, RateLimitConfigurationError
from ...monitoring.metrics.collectors import record_rate_limit_violation, record_rate_limit_request

logger = logging.getLogger(__name__)


class BaseRateLimiter(ABC):
    """
    Abstract base class for all rate limiters.
    Defines common interface and shared functionality.
    """
    
    def __init__(self, algorithm: str = 'fixed_window', backend=None):
        """
        Initialize base rate limiter.
        
        Args:
            algorithm: Rate limiting algorithm ('sliding_window', 'token_bucket', 'fixed_window')
            backend: Rate limiting backend (defaults to Redis)
        """
        self.algorithm = algorithm
        # Import backend lazily to avoid circular imports
        if backend is None:
            from ..backends.redis_backend import rate_limit_backend
            self.backend = rate_limit_backend
        else:
            self.backend = backend
        self._validate_algorithm()
    
    def _validate_algorithm(self):
        """Validate that the algorithm is supported."""
        supported_algorithms = ['sliding_window', 'token_bucket', 'fixed_window']
        if self.algorithm not in supported_algorithms:
            raise RateLimitConfigurationError(
                f"Unsupported algorithm '{self.algorithm}'. "
                f"Supported: {supported_algorithms}"
            )
    
    @abstractmethod
    def get_rate_limit_key(self, request: HttpRequest, view: Any = None) -> str:
        """
        Generate rate limit key for the request.
        Must be implemented by subclasses.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            String key for rate limiting
        """
        pass
    
    @abstractmethod
    def get_rate_limit_config(self, request: HttpRequest, view: Any = None) -> Dict[str, int]:
        """
        Get rate limit configuration for the request.
        Must be implemented by subclasses.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Dictionary with 'limit' and 'window' keys
        """
        pass
    
    def is_allowed(self, request: HttpRequest, view: Any = None) -> Tuple[bool, Dict[str, Any]]:
        """
        Check if request is allowed based on rate limits.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            # Get rate limit key and configuration
            key = self.get_rate_limit_key(request, view)
            config = self.get_rate_limit_config(request, view)
            
            if not key or not config:
                logger.warning(f"Missing key or config for {self.__class__.__name__}")
                return True, {}
            
            limit = config.get('limit')
            window = config.get('window')
            
            if not limit or not window:
                logger.warning(f"Invalid config for {key}: {config}")
                return True, {}
            
            # Check rate limit using specified algorithm
            result = self._check_rate_limit(key, limit, window, config)
            is_allowed, metadata = result
            record_rate_limit_request(
            limiter_type=self.__class__.__name__,
            user_tier='unknown',  # We'll enhance this later
            action='unknown',     # We'll enhance this later
            allowed=is_allowed
            )
            return result
            
        except Exception as e:
            logger.error(f"Rate limit check error: {e}")
            # Fail open - allow request if rate limiting fails
            return True, {'error': str(e)}
    
    def _check_rate_limit(self, key: str, limit: int, window: int, config: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
        """
        Perform rate limit check using specified algorithm.
        
        Args:
            key: Rate limit key
            limit: Request limit
            window: Time window in seconds
            config: Additional configuration
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            if self.algorithm == 'sliding_window':
                return self.backend.sliding_window_check(key, limit, window)
            
            elif self.algorithm == 'token_bucket':
                burst_size = config.get('burst_size')
                return self.backend.token_bucket_check(key, limit, window, burst_size)
            
            elif self.algorithm == 'fixed_window':
                return self.backend.fixed_window_check(key, limit, window)
            
            else:
                logger.error(f"Unknown algorithm: {self.algorithm}")
                return True, {}
                
        except Exception as e:
            logger.error(f"Backend rate limit check failed for {key}: {e}")
            # Fail open - allow request if backend fails
            return True, {'backend_error': str(e)}
    
    def get_exception_class(self):
        """
        Get the appropriate exception class for this limiter.
        Can be overridden by subclasses.
        
        Returns:
            Exception class to raise when rate limit exceeded
        """
        return RateLimitExceeded
    
    def raise_rate_limit_exception(self, metadata: Dict[str, Any]):
        """
        Raise appropriate rate limit exception.
        
        Args:
            metadata: Rate limit metadata from backend
        """
        exception_class = self.get_exception_class()
        
        record_rate_limit_violation(
        limiter_type=self.__class__.__name__,
        user_tier='unknown',  # We'll enhance this later
        action='unknown',     # We'll enhance this later  
        algorithm=metadata.get('algorithm', self.algorithm)
        )
        
        # Calculate wait time from metadata, Ensure it's a number
        wait_time = None
        if 'reset_time' in metadata:
            import time
            try:
                reset_time = int(metadata['reset_time'])  # Ensure it's an integer
                wait_time = max(0, reset_time - int(time.time()))
            except (ValueError, TypeError):
                wait_time = None  # If conversion fails, just use None
        
        # Create detailed error message
        remaining = metadata.get('remaining', 0)
        algorithm = metadata.get('algorithm', self.algorithm)
        
        detail = f"Rate limit exceeded. Remaining: {remaining}. Algorithm: {algorithm}."
        
        raise exception_class(
            detail=detail,
            wait=wait_time,  
            limit_type=self.__class__.__name__,
            limit_value=metadata.get('current_count', 0)
        )
    
    def get_usage_stats(self, request: HttpRequest, view: Any = None) -> Dict[str, Any]:
        """
        Get current usage statistics for the request.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            key = self.get_rate_limit_key(request, view)
            config = self.get_rate_limit_config(request, view)
            
            if not key or not config:
                return {}
            
            window = config.get('window', 3600)
            return self.backend.get_current_usage(key, self.algorithm, window)
            
        except Exception as e:
            logger.error(f"Failed to get usage stats: {e}")
            return {'error': str(e)}
    
    def reset_limit(self, request: HttpRequest, view: Any = None) -> bool:
        """
        Reset rate limit for the request.
        Useful for testing or administrative purposes.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = self.get_rate_limit_key(request, view)
            if not key:
                return False
            
            return self.backend.reset_limit(key, self.algorithm)
            
        except Exception as e:
            logger.error(f"Failed to reset limit: {e}")
            return False
    
    def __str__(self):
        """String representation of the rate limiter."""
        return f"{self.__class__.__name__}(algorithm={self.algorithm})"
    
    def __repr__(self):
        """Developer representation of the rate limiter."""
        return f"{self.__class__.__name__}(algorithm='{self.algorithm}', backend={self.backend})"