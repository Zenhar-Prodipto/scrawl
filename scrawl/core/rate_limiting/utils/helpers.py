"""
Utility helpers and decorators for Scrawl rate limiting.
Provides convenient tools for applying rate limits throughout the application.
"""
import functools
import logging
from typing import Dict, Any, Optional, Callable, Union, List
from django.http import HttpRequest, JsonResponse
from django.core.cache import cache
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from rest_framework.response import Response
from rest_framework import status
# Remove direct imports to avoid circular imports - import lazily when needed
from ..utils.exceptions import RateLimitExceeded
import time  # Add this import

logger = logging.getLogger(__name__)


# =====================================
# FUNCTION DECORATORS
# =====================================


def rate_limit(limit_type: str = 'user', action_type: str = 'api_call', 
               algorithm: Optional[str] = None, fail_open: bool = True):
    """
    Decorator to apply rate limiting to any function or view.
    
    Args:
        limit_type: Type of rate limiter ('user', 'ip', 'endpoint')
        action_type: Action being rate limited (e.g., 'post', 'follow', 'like')
        algorithm: Rate limiting algorithm (defaults from config)
        fail_open: Allow function to proceed if rate limiting fails
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Extract request from function arguments
            request = _extract_request_from_args(args, kwargs)
            if not request:
                logger.warning(f"Could not extract request from {func.__name__} arguments")
                if fail_open:
                    return func(*args, **kwargs)
                else:
                    raise ValueError("Request object required for rate limiting")
            
            # Get appropriate limiter
            limiter = _get_limiter_for_type(limit_type, action_type, algorithm)
            if not limiter:
                logger.warning(f"Could not create limiter for {limit_type}/{action_type}")
                if fail_open:
                    return func(*args, **kwargs)
                else:
                    raise ValueError(f"Invalid rate limiter configuration: {limit_type}")
            
            try:
                # Check rate limit
                is_allowed, metadata = limiter.is_allowed(request)
                
                if not is_allowed:
                    logger.info(f"Rate limit exceeded for {func.__name__}: {metadata}")
                    # Always return 429 response for DRF views (your current pattern works)
                    return _create_api_rate_limit_response(metadata, limiter)
                
                # Add rate limit info to request for headers
                _add_rate_limit_info_to_request(request, metadata, limit_type)
                
                # Call original function
                return func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Rate limiting error in {func.__name__}: {e}")
                if fail_open:
                    return func(*args, **kwargs)
                else:
                    # For system errors, return a clean 429 response
                    return _create_api_rate_limit_response({
                        'remaining': 0,
                        'reset_time': int(time.time()) + 3600,  # 1 hour default
                        'algorithm': 'unknown'
                    }, limiter)
        
        return wrapper
    return decorator


def rate_limit_user(action_type: str = 'api_call', algorithm: Optional[str] = None):
    """
    Convenience decorator for user-based rate limiting.
    
    Args:
        action_type: Action being rate limited
        algorithm: Rate limiting algorithm
        
    Usage:
        @rate_limit_user('post')
        def create_post_view(request):
            pass
    """
    return rate_limit('user', action_type, algorithm)


def rate_limit_ip(action_type: str = 'request', algorithm: Optional[str] = None):
    """
    Convenience decorator for IP-based rate limiting.
    
    Args:
        action_type: Action being rate limited
        algorithm: Rate limiting algorithm
        
    Usage:
        @rate_limit_ip('login')
        def login_view(request):
            pass
    """
    return rate_limit('ip', action_type, algorithm)


def rate_limit_endpoint(algorithm: Optional[str] = None):
    """
    Convenience decorator for endpoint-based rate limiting.
    
    Args:
        algorithm: Rate limiting algorithm
        
    Usage:
        @rate_limit_endpoint()
        def expensive_view(request):
            pass
    """
    return rate_limit('endpoint', 'request', algorithm)


# =====================================
# CLASS DECORATORS FOR VIEWS
# =====================================

def rate_limit_view(limit_configs: List[Dict[str, Any]]):
    """
    Class decorator to apply multiple rate limits to a view class.
    
    Args:
        limit_configs: List of rate limit configurations
        
    Usage:
        @rate_limit_view([
            {'type': 'ip', 'action': 'request'},
            {'type': 'user', 'action': 'post'},
        ])
        class PostCreateView(APIView):
            pass
    """
    def decorator(view_class):
        original_dispatch = view_class.dispatch
        
        @functools.wraps(original_dispatch)
        def wrapped_dispatch(self, request, *args, **kwargs):
            # Apply all rate limits
            for config in limit_configs:
                limiter = _get_limiter_for_type(
                    config.get('type', 'user'),
                    config.get('action', 'api_call'),
                    config.get('algorithm')
                )
                
                if limiter:
                    is_allowed, metadata = limiter.is_allowed(request)
                    if not is_allowed:
                        return _create_api_rate_limit_response(metadata, limiter)
                    
                    _add_rate_limit_info_to_request(request, metadata, config.get('type'))
            
            return original_dispatch(self, request, *args, **kwargs)
        
        view_class.dispatch = wrapped_dispatch
        return view_class
    
    return decorator


# =====================================
# SERVICE LAYER HELPERS
# =====================================

def check_rate_limit(request: HttpRequest, limit_type: str, action_type: str, 
                     algorithm: Optional[str] = None) -> tuple[bool, Dict[str, Any]]:
    """
    Check rate limit without applying it (for conditional logic).
    
    Args:
        request: Django HTTP request
        limit_type: Type of rate limiter
        action_type: Action being checked
        algorithm: Rate limiting algorithm
        
    Returns:
        Tuple of (is_allowed, metadata)
        
    Usage:
        is_allowed, metadata = check_rate_limit(request, 'user', 'post')
        if not is_allowed:
            return Response({'error': 'Rate limit exceeded'}, status=429)
    """
    limiter = _get_limiter_for_type(limit_type, action_type, algorithm)
    if not limiter:
        return True, {}
    
    try:
        return limiter.is_allowed(request)
    except Exception as e:
        logger.error(f"Rate limit check failed: {e}")
        return True, {}  # Fail open


def get_rate_limit_status(request: HttpRequest, limit_type: str, action_type: str) -> Dict[str, Any]:
    """
    Get current rate limit status for a user/IP/endpoint.
    
    Args:
        request: Django HTTP request
        limit_type: Type of rate limiter
        action_type: Action being checked
        
    Returns:
        Dictionary with rate limit status
        
    Usage:
        status = get_rate_limit_status(request, 'user', 'post')
        remaining = status.get('remaining', 0)
    """
    limiter = _get_limiter_for_type(limit_type, action_type)
    if not limiter:
        return {}
    
    try:
        return limiter.get_usage_stats(request)
    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        return {}


def reset_rate_limit(request: HttpRequest, limit_type: str, action_type: str) -> bool:
    """
    Reset rate limit for testing or administrative purposes.
    
    Args:
        request: Django HTTP request
        limit_type: Type of rate limiter
        action_type: Action to reset
        
    Returns:
        True if reset successful
        
    Usage:
        success = reset_rate_limit(request, 'user', 'post')
    """
    limiter = _get_limiter_for_type(limit_type, action_type)
    if not limiter:
        return False
    
    try:
        return limiter.reset_limit(request)
    except Exception as e:
        logger.error(f"Failed to reset rate limit: {e}")
        return False


# =====================================
# CONTEXT MANAGERS
# =====================================

class RateLimitContext:
    """
    Context manager for rate limiting within code blocks.
    
    Usage:
        with RateLimitContext(request, 'user', 'post') as rl:
            if not rl.is_allowed:
                return Response({'error': 'Rate limit exceeded'}, status=429)
            # Proceed with logic
    """
    
    def __init__(self, request: HttpRequest, limit_type: str, action_type: str, 
                 algorithm: Optional[str] = None):
        self.request = request
        self.limit_type = limit_type
        self.action_type = action_type
        self.algorithm = algorithm
        self.limiter = None
        self.is_allowed = True
        self.metadata = {}
    
    def __enter__(self):
        self.limiter = _get_limiter_for_type(self.limit_type, self.action_type, self.algorithm)
        if self.limiter:
            try:
                self.is_allowed, self.metadata = self.limiter.is_allowed(self.request)
            except Exception as e:
                logger.error(f"Rate limit context error: {e}")
                self.is_allowed = True  # Fail open
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        # Clean up if needed
        pass


# =====================================
# UTILITY FUNCTIONS
# =====================================

def _extract_request_from_args(args: tuple, kwargs: dict) -> Optional[HttpRequest]:
    """Extract Django HttpRequest from function arguments."""
    # Check positional arguments
    for arg in args:
        if isinstance(arg, HttpRequest):
            return arg
        # Check if it's a DRF request
        if hasattr(arg, '_request') and isinstance(arg._request, HttpRequest):
            return arg._request
    
    # Check keyword arguments
    for key, value in kwargs.items():
        if isinstance(value, HttpRequest):
            return value
        if hasattr(value, '_request') and isinstance(value._request, HttpRequest):
            return value._request
    
    return None


def _get_limiter_for_type(limit_type: str, action_type: str, 
                         algorithm: Optional[str] = None):
    """Get appropriate rate limiter instance - lazy import to avoid circular imports."""
    # Import here to avoid circular import issues
    from ..limiters.user_limiter import UserRateLimiter
    from ..limiters.ip_limiter import IPRateLimiter
    from ..limiters.endpoint_limiter import EndpointRateLimiter
    from ..config.limits import rate_limit_config
    
    if not algorithm:
        algorithm = rate_limit_config.get_algorithm_defaults().get(limit_type, 'fixed_window')
    
    try:
        if limit_type == 'user':
            return UserRateLimiter(action_type=action_type, algorithm=algorithm)
        elif limit_type == 'ip':
            return IPRateLimiter(action_type=action_type, algorithm=algorithm)
        elif limit_type == 'endpoint':
            return EndpointRateLimiter(algorithm=algorithm)
        else:
            logger.error(f"Unknown rate limiter type: {limit_type}")
            return None
    except Exception as e:
        logger.error(f"Failed to create rate limiter {limit_type}: {e}")
        return None


def _is_api_view_function(func: Callable) -> bool:
    """Check if function is likely an API view that should return JSON responses."""
    # Check function name patterns
    api_patterns = ['api', 'view', 'create', 'update', 'delete', 'list', 'retrieve']
    func_name = func.__name__.lower()
    
    if any(pattern in func_name for pattern in api_patterns):
        return True
    
    # Check if function is decorated with DRF decorators
    if hasattr(func, '__wrapped__'):
        return True
    
    return False


def _create_api_rate_limit_response(metadata: Dict[str, Any], limiter) -> Response:
    """Create DRF Response for rate limit exceeded."""
    import time  # FIX: Move import to top to avoid issues
    
    wait_time = None
    if 'reset_time' in metadata:
        wait_time = max(0, metadata['reset_time'] - int(time.time()))
    
    response_data = {
        'status': 'error',  # FIX: Match your API response format
        'message': 'Rate limit exceeded. Please try again later.',  # FIX: Simpler message
        'retry_after': wait_time,
        'remaining': metadata.get('remaining', 0),
        'details': {
            'reset_time': metadata.get('reset_time'),
            'limit_type': limiter.__class__.__name__,
            'algorithm': metadata.get('algorithm', 'unknown'),
        }
    }
    
    response = Response(response_data, status=status.HTTP_429_TOO_MANY_REQUESTS)
    
    # Add rate limit headers
    if 'remaining' in metadata:
        response['X-RateLimit-Remaining'] = str(metadata['remaining'])
    if 'reset_time' in metadata:
        response['X-RateLimit-Reset'] = str(metadata['reset_time'])
    if wait_time:
        response['Retry-After'] = str(wait_time)
    
    return response


def _add_rate_limit_info_to_request(request: HttpRequest, metadata: Dict[str, Any], 
                                   limit_type: str) -> None:
    """Add rate limit information to request for header processing."""
    if not hasattr(request, '_rate_limit_headers'):
        request._rate_limit_headers = {}
    
    request._rate_limit_headers.update({
        f'X-RateLimit-{limit_type.title()}-Remaining': str(metadata.get('remaining', 0)),
        f'X-RateLimit-{limit_type.title()}-Reset': str(metadata.get('reset_time', 0)),
    })


# =====================================
# MONITORING AND ANALYTICS HELPERS
# =====================================

def get_rate_limit_analytics(time_period: int = 3600) -> Dict[str, Any]:
    """
    Get rate limiting analytics for monitoring.
    
    Args:
        time_period: Time period in seconds to analyze
        
    Returns:
        Dictionary with analytics data
    """
    try:
        # This would typically integrate with your monitoring system
        # For now, return basic structure
        return {
            'time_period': time_period,
            'total_requests': 0,
            'rate_limited_requests': 0,
            'rate_limit_types': {
                'user': 0,
                'ip': 0,
                'endpoint': 0,
            },
            'top_limited_users': [],
            'top_limited_ips': [],
            'top_limited_endpoints': [],
        }
    except Exception as e:
        logger.error(f"Failed to get rate limit analytics: {e}")
        return {}


def log_rate_limit_metrics(limit_type: str, action_type: str, 
                          is_allowed: bool, metadata: Dict[str, Any]) -> None:
    """
    Log rate limiting metrics for monitoring systems.
    
    Args:
        limit_type: Type of rate limiter
        action_type: Action that was rate limited
        is_allowed: Whether request was allowed
        metadata: Rate limit metadata
    """
    try:
        # Log to structured logging system
        logger.info(
            "Rate limit check",
            extra={
                'rate_limit_type': limit_type,
                'action_type': action_type,
                'is_allowed': is_allowed,
                'remaining': metadata.get('remaining'),
                'used': metadata.get('current_count'),
                'algorithm': metadata.get('algorithm'),
            }
        )
        
        # Send to metrics system (Prometheus, etc.)
        # This would integrate with your existing metrics system
        
    except Exception as e:
        logger.error(f"Failed to log rate limit metrics: {e}")


# =====================================
# TESTING HELPERS
# =====================================

def create_test_request(user=None, ip_address='127.0.0.1', path='/test/'):
    """
    Create a test HTTP request for rate limiting tests.
    
    Args:
        user: Django user object
        ip_address: IP address for the request
        path: Request path
        
    Returns:
        Mock HttpRequest object
    """
    from django.test import RequestFactory
    
    factory = RequestFactory()
    request = factory.get(path)
    
    # Set user
    if user:
        request.user = user
    else:
        from django.contrib.auth.models import AnonymousUser
        request.user = AnonymousUser()
    
    # Set IP address
    request.META['REMOTE_ADDR'] = ip_address
    
    return request


def simulate_rate_limit_scenario(request: HttpRequest, limit_type: str, 
                                action_type: str, num_requests: int) -> List[Dict[str, Any]]:
    """
    Simulate multiple requests to test rate limiting behavior.
    
    Args:
        request: Django HTTP request
        limit_type: Type of rate limiter
        action_type: Action being tested
        num_requests: Number of requests to simulate
        
    Returns:
        List of results for each request
    """
    results = []
    limiter = _get_limiter_for_type(limit_type, action_type)
    
    if not limiter:
        return results
    
    for i in range(num_requests):
        try:
            is_allowed, metadata = limiter.is_allowed(request)
            results.append({
                'request_number': i + 1,
                'is_allowed': is_allowed,
                'remaining': metadata.get('remaining', 0),
                'used': metadata.get('current_count', 0),
            })
        except Exception as e:
            results.append({
                'request_number': i + 1,
                'error': str(e),
            })
    
    return results