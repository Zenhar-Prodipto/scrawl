"""
Endpoint-specific rate limiter for Scrawl application.
Provides granular rate limiting for different API endpoints based on their resource usage.
"""
import logging
from typing import Dict, Any, Optional
from django.http import HttpRequest
from django.urls import resolve
from .base_limiter import BaseRateLimiter
from ..utils.exceptions import EndpointRateLimitExceeded

logger = logging.getLogger(__name__)


class EndpointRateLimiter(BaseRateLimiter):
    """
    Rate limiter based on specific API endpoints.
    Perfect for protecting expensive operations like feed generation, search, etc.
    """
    
    def __init__(self, algorithm: str = 'fixed_window', backend=None):
        """
        Initialize endpoint rate limiter.
        
        Args:
            algorithm: Rate limiting algorithm (fixed_window recommended for endpoints)
            backend: Rate limiting backend
        """
        super().__init__(algorithm, backend)
        
        # Cache for endpoint configurations to avoid repeated lookups
        self._endpoint_config_cache = {}
    
    def get_rate_limit_key(self, request: HttpRequest, view: Any = None) -> str:
        """
        Generate rate limit key based on endpoint and user.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Rate limit key: 'rate_limit:endpoint:{endpoint}:{user_id}'
        """
        # Get normalized endpoint path
        endpoint = self._get_endpoint_identifier(request, view)
        if not endpoint:
            return None
        
        # Include user ID if authenticated for per-user-per-endpoint limits
        user_part = ""
        if hasattr(request, 'user') and request.user.is_authenticated:
            user_part = f":{request.user.id}"
        
        return f"rate_limit:endpoint:{endpoint}{user_part}"
    
    def get_rate_limit_config(self, request: HttpRequest, view: Any = None) -> Dict[str, int]:
        """
        Get rate limit configuration for the specific endpoint.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Dictionary with rate limit configuration
        """
        endpoint = self._get_endpoint_identifier(request, view)
        if not endpoint:
            return {}
        
        # Check cache first
        if endpoint in self._endpoint_config_cache:
            return self._endpoint_config_cache[endpoint]
        
        # Get endpoint-specific configuration
        config = self._get_endpoint_config(endpoint, request)
        
        # Cache the configuration
        self._endpoint_config_cache[endpoint] = config
        
        logger.debug(f"Endpoint {endpoint} rate limit config: {config}")
        return config
    
    def _get_endpoint_identifier(self, request: HttpRequest, view: Any = None) -> Optional[str]:
        """
        Get normalized endpoint identifier from request.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Normalized endpoint string (e.g., 'posts.create', 'feed.get')
        """
        try:
            # Try to get from URL resolver first
            resolver_match = resolve(request.path_info)
            if resolver_match:
                # Create identifier from app and view name
                app_name = getattr(resolver_match, 'app_name', '')
                view_name = getattr(resolver_match, 'url_name', '')
                
                if app_name and view_name:
                    return f"{app_name}.{view_name}"
                elif view_name:
                    return view_name
            
            # Fallback: try to get from view class if provided
            if view:
                view_class_name = view.__class__.__name__.lower()
                return f"view.{view_class_name}"
            
            # Final fallback: use normalized path
            normalized_path = self._normalize_path(request.path_info)
            return f"path.{normalized_path}"
            
        except Exception as e:
            logger.warning(f"Could not determine endpoint identifier for {request.path}: {e}")
            return None
    
    def _normalize_path(self, path: str) -> str:
        """
        Normalize URL path for rate limiting.
        Removes dynamic segments and creates a consistent identifier.
        
        Args:
            path: URL path
            
        Returns:
            Normalized path string
        """
        # Remove leading/trailing slashes
        path = path.strip('/')
        
        # Split path into segments
        segments = path.split('/')
        
        # Replace numeric segments with placeholder
        normalized_segments = []
        for segment in segments:
            if segment.isdigit():
                normalized_segments.append('{id}')
            elif segment:
                normalized_segments.append(segment)
        
        return '.'.join(normalized_segments)
    def _get_endpoint_config(self, endpoint: str, request: HttpRequest) -> Dict[str, int]:
        """Get rate limit configuration from centralized config."""
        from ..config.limits import rate_limit_config
        
        method = request.method.upper()
        endpoint_configs = rate_limit_config.get_endpoint_rate_limits()
        
        # Try exact match first
        if endpoint in endpoint_configs:
            endpoint_config = endpoint_configs[endpoint]
            if method in endpoint_config:
                return endpoint_config[method]
        
        # Fallback to default
        default_config = endpoint_configs.get('_default', {})
        return default_config.get(method, {'limit': 100, 'window': 3600})
    
    def _matches_pattern(self, endpoint: str, pattern: str) -> bool:
        """
        Check if endpoint matches a wildcard pattern.
        
        Args:
            endpoint: Endpoint identifier
            pattern: Pattern with wildcards (e.g., 'admin.*')
            
        Returns:
            True if endpoint matches pattern
        """
        if '*' not in pattern:
            return endpoint == pattern
        
        # Simple wildcard matching
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return endpoint.startswith(prefix)
        
        if pattern.startswith('*'):
            suffix = pattern[1:]
            return endpoint.endswith(suffix)
        
        # More complex patterns could be added here
        return False
    
    def _get_default_endpoint_config(self, method: str) -> Dict[str, int]:
        """
        Get default rate limit configuration for unspecified endpoints.
        
        Args:
            method: HTTP method
            
        Returns:
            Default rate limit configuration
        """
        default_configs = {
            'GET': {'limit': 500, 'window': 3600},     # 500 GET requests per hour
            'POST': {'limit': 100, 'window': 3600},    # 100 POST requests per hour
            'PATCH': {'limit': 100, 'window': 3600},   # 100 PATCH requests per hour
            'PUT': {'limit': 100, 'window': 3600},     # 100 PUT requests per hour
            'DELETE': {'limit': 50, 'window': 3600},   # 50 DELETE requests per hour
        }
        
        return default_configs.get(method, {'limit': 100, 'window': 3600})
    
    def get_exception_class(self):
        """Return endpoint-specific rate limit exception."""
        return EndpointRateLimitExceeded
    
    def is_endpoint_exempt(self, endpoint: str, request: HttpRequest) -> bool:
        """
        Check if endpoint should be exempt from rate limiting.
        
        Args:
            endpoint: Endpoint identifier
            request: Django HTTP request
            
        Returns:
            True if endpoint should be exempt
        """
        # Exempt health check endpoints
        health_check_patterns = [
            'health',
            'status',
            'ping',
            'ready',
            'live',
        ]
        
        for pattern in health_check_patterns:
            if pattern in endpoint.lower():
                return True
        
        # Exempt static file serving
        if 'static' in endpoint.lower() or 'media' in endpoint.lower():
            return True
        
        # Exempt superuser from endpoint limits in development
        if hasattr(request, 'user') and request.user.is_authenticated:
            if request.user.is_superuser and self._is_development_mode():
                return True
        
        return False
    
    def _is_development_mode(self) -> bool:
        """Check if application is in development mode."""
        try:
            from django.conf import settings
            return settings.DEBUG
        except:
            return False
    
    def is_allowed(self, request: HttpRequest, view: Any = None) -> tuple[bool, Dict[str, Any]]:
        """
        Check if endpoint request is allowed, with exemption support.
        
        Args:
            request: Django HTTP request
            view: Django view (optional)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        endpoint = self._get_endpoint_identifier(request, view)
        if not endpoint:
            logger.warning(f"Could not identify endpoint for rate limiting: {request.path}")
            return True, {'reason': 'no_endpoint'}
        
        # Check if endpoint is exempt
        if self.is_endpoint_exempt(endpoint, request):
            logger.debug(f"Endpoint {endpoint} exempt from rate limiting")
            return True, {'reason': 'exempt', 'endpoint': endpoint}
        
        # Perform normal rate limit check
        is_allowed, metadata = super().is_allowed(request, view)
        
        # Add endpoint-specific metadata
        metadata.update({
            'endpoint': endpoint,
            'method': request.method,
        })
        
        return is_allowed, metadata
    
    def get_rate_limit_headers(self, request: HttpRequest, metadata: Dict[str, Any]) -> Dict[str, str]:
        """
        Get HTTP headers for endpoint-based rate limit information.
        
        Args:
            request: Django HTTP request
            metadata: Rate limit metadata
            
        Returns:
            Dictionary of HTTP headers
        """
        headers = {}
        
        if 'remaining' in metadata:
            headers['X-RateLimit-Remaining'] = str(metadata['remaining'])
        
        if 'reset_time' in metadata:
            headers['X-RateLimit-Reset'] = str(metadata['reset_time'])
        
        # Add endpoint-specific headers
        if 'endpoint' in metadata:
            headers['X-RateLimit-Endpoint'] = metadata['endpoint']
        
        if 'method' in metadata:
            headers['X-RateLimit-Method'] = metadata['method']
        
        return headers
    
    def __str__(self):
        """String representation of endpoint rate limiter."""
        return f"EndpointRateLimiter(algorithm={self.algorithm})"