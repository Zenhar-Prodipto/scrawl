"""
Django middleware for global rate limiting in Scrawl application.
Provides automatic rate limiting for all requests with customizable rules.
"""
import logging
import time
from typing import Dict, Any, Optional, List
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.utils.deprecation import MiddlewareMixin
from django.urls import resolve, Resolver404
from django.conf import settings
from ..limiters.user_limiter import UserRateLimiter
from ..limiters.ip_limiter import IPRateLimiter
from ..limiters.endpoint_limiter import EndpointRateLimiter
from ..config.limits import rate_limit_config
from ..utils.exceptions import (
    RateLimitExceeded,
    UserRateLimitExceeded,
    IPRateLimitExceeded,
    EndpointRateLimitExceeded,
    RateLimitBackendError
)

logger = logging.getLogger(__name__)


class RateLimitMiddleware(MiddlewareMixin):
    """
    Django middleware for global rate limiting.
    Applies rate limits to all requests before they reach views.
    """
    
    def __init__(self, get_response=None):
        """Initialize rate limiting middleware."""
        super().__init__(get_response)
        self.get_response = get_response
        
        # Initialize rate limiters
        self._user_limiter = None
        self._ip_limiter = None
        self._endpoint_limiter = None
        
        # Cache for exempt patterns
        self._exempt_patterns = self._load_exempt_patterns()
        
        # Middleware configuration
        self._config = self._load_middleware_config()
    
    def _load_middleware_config(self) -> Dict[str, Any]:
        """
        Load middleware configuration from Django settings.
        
        Returns:
            Configuration dictionary
        """
        default_config = {
            'enabled': True,
            'apply_ip_limits': True,
            'apply_user_limits': True,
            'apply_endpoint_limits': False,  # Usually handled by DRF throttles
            'exempt_superusers': True,
            'exempt_staff_in_debug': True,
            'fail_open': True,  # Allow requests if rate limiting fails
            'add_headers': True,
            'log_violations': True,
        }
        
        # Get from Django settings
        middleware_config = getattr(settings, 'RATE_LIMIT_MIDDLEWARE', {})
        default_config.update(middleware_config)
        
        return default_config
    
    def _load_exempt_patterns(self) -> List[str]:
        """
        Load URL patterns that should be exempt from rate limiting.
        
        Returns:
            List of URL patterns to exempt
        """
        # Default exempt patterns
        default_patterns = [
            '/admin/',
            '/static/',
            '/media/',
            '/health/',
            '/metrics/',
            '/favicon.ico',
        ]
        
        # Get additional patterns from settings
        exempt_patterns = getattr(settings, 'RATE_LIMIT_EXEMPT_PATTERNS', [])
        return default_patterns + exempt_patterns
    
    def _is_request_exempt(self, request: HttpRequest) -> tuple[bool, str]:
        """
        Check if request should be exempt from rate limiting.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Tuple of (is_exempt, reason)
        """
        # Check if rate limiting is globally disabled
        if not self._config['enabled'] or not rate_limit_config.is_rate_limiting_enabled():
            return True, 'globally_disabled'
        
        # Check URL patterns
        path = request.path_info
        for pattern in self._exempt_patterns:
            if path.startswith(pattern):
                return True, f'exempt_pattern:{pattern}'
        
        # Check user exemptions
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Exempt superusers if configured
            if self._config['exempt_superusers'] and request.user.is_superuser:
                return True, 'superuser'
            
            # Exempt staff in debug mode if configured
            if self._config['exempt_staff_in_debug'] and request.user.is_staff and settings.DEBUG:
                return True, 'staff_debug'
        
        return False, ''
    
    def _get_limiters(self) -> Dict[str, Any]:
        """
        Get rate limiter instances (lazy initialization).
        
        Returns:
            Dictionary of limiter instances
        """
        limiters = {}
        
        # IP-based limiter
        if self._config['apply_ip_limits']:
            if not self._ip_limiter:
                algorithm = rate_limit_config.get_algorithm_defaults()['ip']
                self._ip_limiter = IPRateLimiter(action_type='request', algorithm=algorithm)
            limiters['ip'] = self._ip_limiter
        
        # User-based limiter (for authenticated requests)
        if self._config['apply_user_limits']:
            if not self._user_limiter:
                algorithm = rate_limit_config.get_algorithm_defaults()['user']
                self._user_limiter = UserRateLimiter(action_type='api_call', algorithm=algorithm)
            limiters['user'] = self._user_limiter
        
        # Endpoint-based limiter
        if self._config['apply_endpoint_limits']:
            if not self._endpoint_limiter:
                algorithm = rate_limit_config.get_algorithm_defaults()['endpoint']
                self._endpoint_limiter = EndpointRateLimiter(algorithm=algorithm)
            limiters['endpoint'] = self._endpoint_limiter
        
        return limiters
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process incoming request for rate limiting.
        
        Args:
            request: Django HTTP request
            
        Returns:
            HttpResponse if rate limit exceeded, None to continue
        """
        start_time = time.time()
        
        try:
            # Check if request is exempt
            is_exempt, exempt_reason = self._is_request_exempt(request)
            if is_exempt:
                logger.debug(f"Request exempt from rate limiting: {exempt_reason}")
                return None
            
            # Get active limiters
            limiters = self._get_limiters()
            if not limiters:
                return None
            
            # Apply rate limits in order of priority
            rate_limit_results = {}
            
            # 1. IP-based limits (highest priority for security)
            if 'ip' in limiters:
                is_allowed, metadata = limiters['ip'].is_allowed(request)
                rate_limit_results['ip'] = {'allowed': is_allowed, 'metadata': metadata}
                
                if not is_allowed:
                    return self._create_rate_limit_response(
                        request, 'ip', metadata, limiters['ip']
                    )
            
            # 2. User-based limits (for authenticated users)
            if 'user' in limiters and hasattr(request, 'user') and request.user.is_authenticated:
                is_allowed, metadata = limiters['user'].is_allowed(request)
                rate_limit_results['user'] = {'allowed': is_allowed, 'metadata': metadata}
                
                if not is_allowed:
                    return self._create_rate_limit_response(
                        request, 'user', metadata, limiters['user']
                    )
            
            # 3. Endpoint-based limits (lowest priority)
            if 'endpoint' in limiters:
                is_allowed, metadata = limiters['endpoint'].is_allowed(request)
                rate_limit_results['endpoint'] = {'allowed': is_allowed, 'metadata': metadata}
                
                if not is_allowed:
                    return self._create_rate_limit_response(
                        request, 'endpoint', metadata, limiters['endpoint']
                    )
            
            # Store results for response processing
            request._rate_limit_results = rate_limit_results
            
            # Log successful rate limit check
            elapsed_time = (time.time() - start_time) * 1000
            logger.debug(f"Rate limit check completed in {elapsed_time:.2f}ms: {len(limiters)} limiters")
            
            return None  # Continue processing
            
        except RateLimitBackendError as e:
            logger.error(f"Rate limit backend error: {e}")
            if self._config['fail_open']:
                return None  # Allow request to continue
            else:
                return self._create_error_response(request, "Rate limiting temporarily unavailable")
        
        except Exception as e:
            logger.error(f"Unexpected error in rate limiting middleware: {e}", exc_info=True)
            if self._config['fail_open']:
                return None  # Allow request to continue
            else:
                return self._create_error_response(request, "Internal server error")
    
    def process_response(self, request: HttpRequest, response: HttpResponse) -> HttpResponse:
        """
        Process response to add rate limiting headers.
        
        Args:
            request: Django HTTP request
            response: Django HTTP response
            
        Returns:
            Modified response with rate limit headers
        """
        if not self._config['add_headers']:
            return response
        
        try:
            # Add headers from rate limit results
            if hasattr(request, '_rate_limit_results'):
                self._add_rate_limit_headers(response, request._rate_limit_results)
            
            # Add headers from DRF throttles if present
            # if hasattr(request, '_rate_limit_headers'):
            #     for header, value in request._rate_limit_headers.items():
            #         response[header] = value
        
        except Exception as e:
            logger.error(f"Error adding rate limit headers: {e}")
        
        return response
    
    def _create_rate_limit_response(self, request: HttpRequest, limiter_type: str, 
                                  metadata: Dict[str, Any], limiter) -> HttpResponse:
        """
        Create rate limit exceeded response.
        
        Args:
            request: Django HTTP request
            limiter_type: Type of limiter that triggered ('ip', 'user', 'endpoint')
            metadata: Rate limit metadata
            limiter: Rate limiter instance
            
        Returns:
            HTTP 429 response
        """
        # Log the violation
        if self._config['log_violations']:
            self._log_rate_limit_violation(request, limiter_type, metadata)
        
        # Determine wait time
        wait_time = None
        if 'reset_time' in metadata:
            wait_time = max(0, metadata['reset_time'] - int(time.time()))
        
        # Create response data
        response_data = {
            'error': 'Rate limit exceeded',
            'message': f'{limiter_type.title()} rate limit exceeded. Please try again later.',
            'type': f'{limiter_type}_rate_limit_exceeded',
            'retry_after': wait_time,
            'details': {
                'remaining': metadata.get('remaining', 0),
                'reset_time': metadata.get('reset_time'),
                'limit_type': limiter_type,
            }
        }
        
        # Create JSON response
        response = JsonResponse(response_data, status=429)
        
        # Add rate limit headers
        self._add_rate_limit_headers_to_response(response, metadata, limiter_type)
        
        # Add Retry-After header
        if wait_time:
            response['Retry-After'] = str(wait_time)
        
        return response
    
    def _create_error_response(self, request: HttpRequest, message: str) -> HttpResponse:
        """
        Create error response for rate limiting failures.
        
        Args:
            request: Django HTTP request
            message: Error message
            
        Returns:
            HTTP 500 response
        """
        response_data = {
            'error': 'Rate limiting error',
            'message': message,
        }
        
        return JsonResponse(response_data, status=500)
    
    def _add_rate_limit_headers(self, response: HttpResponse, results: Dict[str, Dict]) -> None:
        """
        Add rate limit headers from multiple limiters to response.
        
        Args:
            response: Django HTTP response
            results: Rate limit results from multiple limiters
        """
        # Find the most restrictive limiter for headers
        most_restrictive = None
        min_remaining = float('inf')
        
        for limiter_type, result in results.items():
            if result['allowed']:
                remaining = result['metadata'].get('remaining', float('inf'))
                if remaining < min_remaining:
                    min_remaining = remaining
                    most_restrictive = (limiter_type, result['metadata'])
        
        if most_restrictive:
            limiter_type, metadata = most_restrictive
            self._add_rate_limit_headers_to_response(response, metadata, limiter_type)
    
    def _add_rate_limit_headers_to_response(self, response: HttpResponse, 
                                          metadata: Dict[str, Any], limiter_type: str) -> None:
        """
        Add rate limit headers to response.
        
        Args:
            response: Django HTTP response
            metadata: Rate limit metadata
            limiter_type: Type of limiter
        """
        if 'remaining' in metadata:
            response['X-RateLimit-Remaining'] = str(metadata['remaining'])
        
        if 'reset_time' in metadata:
            response['X-RateLimit-Reset'] = str(metadata['reset_time'])
        
        if 'current_count' in metadata:
            response['X-RateLimit-Used'] = str(metadata['current_count'])
        
        response['X-RateLimit-Type'] = f'middleware_{limiter_type}'
        
        if 'algorithm' in metadata:
            response['X-RateLimit-Algorithm'] = metadata['algorithm']
    
    def _log_rate_limit_violation(self, request: HttpRequest, limiter_type: str, 
                                 metadata: Dict[str, Any]) -> None:
        """
        Log rate limit violation with detailed information.
        
        Args:
            request: Django HTTP request
            limiter_type: Type of limiter that triggered
            metadata: Rate limit metadata
        """
        # Get request details
        user_info = 'anonymous'
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_info = f'user:{request.user.id}'
        
        # Get IP information
        ip_address = self._get_client_ip(request)
        
        # Get endpoint information
        endpoint = 'unknown'
        try:
            resolver_match = resolve(request.path_info)
            if resolver_match:
                endpoint = f"{resolver_match.app_name}.{resolver_match.url_name}"
        except Resolver404:
            endpoint = request.path_info
        
        # Log violation
        logger.warning(
            f"Rate limit exceeded - Type: {limiter_type}, "
            f"User: {user_info}, IP: {ip_address}, "
            f"Endpoint: {endpoint}, Method: {request.method}, "
            f"Used: {metadata.get('current_count', 'unknown')}, "
            f"Remaining: {metadata.get('remaining', 'unknown')}, "
            f"Algorithm: {metadata.get('algorithm', 'unknown')}"
        )
    
    def _get_client_ip(self, request: HttpRequest) -> str:
        """
        Get client IP address from request.
        
        Args:
            request: Django HTTP request
            
        Returns:
            Client IP address
        """
        # Check for IP in proxy headers
        ip_headers = [
            'HTTP_X_FORWARDED_FOR',
            'HTTP_X_REAL_IP',
            'HTTP_CF_CONNECTING_IP',
            'REMOTE_ADDR',
        ]
        
        for header in ip_headers:
            ip = request.META.get(header)
            if ip:
                if ',' in ip:
                    ip = ip.split(',')[0].strip()
                return ip
        
        return 'unknown'


class SmartRateLimitMiddleware(RateLimitMiddleware):
    """
    Smart rate limiting middleware with adaptive behavior.
    Adjusts limits based on system load and user behavior patterns.
    """
    
    def _load_middleware_config(self) -> Dict[str, Any]:
        """Load smart middleware configuration."""
        config = super()._load_middleware_config()
        
        # Smart middleware specific config
        smart_config = {
            'adaptive_limits': True,
            'burst_allowance': True,
            'system_load_threshold': 0.8,
            'user_behavior_tracking': True,
        }
        
        config.update(smart_config)
        return config
    
    def process_request(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Process request with smart adaptive behavior.
        
        Args:
            request: Django HTTP request
            
        Returns:
            HttpResponse if rate limit exceeded, None to continue
        """
        # Check system load first
        if self._config.get('adaptive_limits'):
            system_load = self._get_system_load()
            if system_load > self._config['system_load_threshold']:
                # Apply stricter limits during high load
                logger.info(f"High system load ({system_load:.2f}), applying stricter limits")
                return self._apply_strict_limits(request)
        
        # Apply normal processing
        return super().process_request(request)
    
    def _get_system_load(self) -> float:
        """
        Get current system load (0.0 to 1.0).
        
        Returns:
            System load factor
        """
        try:
            import psutil
            return psutil.cpu_percent(interval=0.1) / 100.0
        except ImportError:
            return 0.5  # Default to medium load
    
    def _apply_strict_limits(self, request: HttpRequest) -> Optional[HttpResponse]:
        """
        Apply stricter rate limits during high system load.
        
        Args:
            request: Django HTTP request
            
        Returns:
            HttpResponse if request should be blocked
        """
        # Simple implementation - block non-essential requests
        if request.method in ['GET'] and not hasattr(request, 'user'):
            return self._create_error_response(
                request, 
                "Service temporarily overloaded. Please try again later."
            )
        
        return None