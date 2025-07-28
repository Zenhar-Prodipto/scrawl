"""
Scrawl Core Rate Limiting Module

Enterprise-grade rate limiting system for Django REST Framework applications.
Provides comprehensive protection against abuse, spam, and DDoS attacks with
multiple algorithms, tiered user limits, and production-ready monitoring.

Features:
- Multiple rate limiting algorithms (sliding window, token bucket, fixed window)
- User-based, IP-based, and endpoint-specific rate limiting
- Tiered user system (free, premium, admin)
- Django middleware for global protection
- Redis-based distributed rate limiting
- Comprehensive monitoring and analytics
- Flexible decorators and utilities

Usage:
    # Quick setup in settings.py
    MIDDLEWARE = [
        'scrawl.core.rate_limiting.middleware.RateLimitMiddleware',
        # ... other middleware
    ]
    
    
    # Decorator usage
    from scrawl.core.rate_limiting import rate_limit_user
    
    @rate_limit_user('post')
    def create_post(request, data):
        # Your logic here
        pass

For more information, see the documentation at:
https://github.com/yourorg/scrawl/docs/rate-limiting.md
"""

# Version information
__version__ = '1.0.0'
__author__ = 'Scrawl Development Team'


# Lazy loading for better Django compatibility
_backends_loaded = False
_limiters_loaded = False
_throttling_loaded = False
_middleware_loaded = False
_utils_loaded = False
_config_loaded = False

def _load_backends():
    """Lazy load backend components."""
    global _backends_loaded
    if not _backends_loaded:
        from .backends import RedisRateLimitBackend, rate_limit_backend
        globals().update({
            'RedisRateLimitBackend': RedisRateLimitBackend,
            'rate_limit_backend': rate_limit_backend,
        })
        _backends_loaded = True

def _load_limiters():
    """Lazy load limiter components."""
    global _limiters_loaded
    if not _limiters_loaded:
        from .limiters import (
            BaseRateLimiter,
            UserRateLimiter,
            IPRateLimiter,
            EndpointRateLimiter,
        )
        globals().update({
            'BaseRateLimiter': BaseRateLimiter,
            'UserRateLimiter': UserRateLimiter,
            'IPRateLimiter': IPRateLimiter,
            'EndpointRateLimiter': EndpointRateLimiter,
        })
        _limiters_loaded = True


def _load_middleware():
    """Lazy load middleware components."""
    global _middleware_loaded
    if not _middleware_loaded:
        from .middleware import RateLimitMiddleware, SmartRateLimitMiddleware
        globals().update({
            'RateLimitMiddleware': RateLimitMiddleware,
            'SmartRateLimitMiddleware': SmartRateLimitMiddleware,
        })
        _middleware_loaded = True

def _load_utils():
    """Lazy load utility components."""
    global _utils_loaded
    if not _utils_loaded:
        from .utils import (
            # Exceptions
            RateLimitExceeded,
            UserRateLimitExceeded,
            IPRateLimitExceeded,
            EndpointRateLimitExceeded,
            RateLimitConfigurationError,
            RateLimitBackendError,
            
            # Decorators
            rate_limit,
            rate_limit_user,
            rate_limit_ip,
            rate_limit_endpoint,
            rate_limit_view,
            
            # Service helpers
            check_rate_limit,
            get_rate_limit_status,
            reset_rate_limit,
            
            # Context manager
            RateLimitContext,
            
            # Analytics
            get_rate_limit_analytics,
            log_rate_limit_metrics,
            
            # Testing
            create_test_request,
            simulate_rate_limit_scenario,
        )
        globals().update({
            'RateLimitExceeded': RateLimitExceeded,
            'UserRateLimitExceeded': UserRateLimitExceeded,
            'IPRateLimitExceeded': IPRateLimitExceeded,
            'EndpointRateLimitExceeded': EndpointRateLimitExceeded,
            'RateLimitConfigurationError': RateLimitConfigurationError,
            'RateLimitBackendError': RateLimitBackendError,
            'rate_limit': rate_limit,
            'rate_limit_user': rate_limit_user,
            'rate_limit_ip': rate_limit_ip,
            'rate_limit_endpoint': rate_limit_endpoint,
            'rate_limit_view': rate_limit_view,
            'check_rate_limit': check_rate_limit,
            'get_rate_limit_status': get_rate_limit_status,
            'reset_rate_limit': reset_rate_limit,
            'RateLimitContext': RateLimitContext,
            'get_rate_limit_analytics': get_rate_limit_analytics,
            'log_rate_limit_metrics': log_rate_limit_metrics,
            'create_test_request': create_test_request,
            'simulate_rate_limit_scenario': simulate_rate_limit_scenario,
        })
        _utils_loaded = True

def _load_config():
    """Lazy load configuration components."""
    global _config_loaded
    if not _config_loaded:
        from .config import RateLimitConfig, rate_limit_config
        globals().update({
            'RateLimitConfig': RateLimitConfig,
            'rate_limit_config': rate_limit_config,
        })
        _config_loaded = True

# Module-level __getattr__ for lazy loading
def __getattr__(name):
    """Handle lazy loading of module attributes."""
    
    # Backend components
    if name in ['RedisRateLimitBackend', 'rate_limit_backend']:
        _load_backends()
        return globals().get(name)
    
    # Limiter components
    elif name in ['BaseRateLimiter', 'UserRateLimiter', 'IPRateLimiter', 'EndpointRateLimiter']:
        _load_limiters()
        return globals().get(name)
    
    
    # Middleware components
    elif name in ['RateLimitMiddleware', 'SmartRateLimitMiddleware']:
        _load_middleware()
        return globals().get(name)
    
    # Utility components
    elif name in [
        'RateLimitExceeded', 'UserRateLimitExceeded', 'IPRateLimitExceeded', 
        'EndpointRateLimitExceeded', 'RateLimitConfigurationError', 'RateLimitBackendError',
        'rate_limit', 'rate_limit_user', 'rate_limit_ip', 'rate_limit_endpoint', 'rate_limit_view',
        'check_rate_limit', 'get_rate_limit_status', 'reset_rate_limit', 'RateLimitContext',
        'get_rate_limit_analytics', 'log_rate_limit_metrics', 'create_test_request', 
        'simulate_rate_limit_scenario'
    ]:
        _load_utils()
        return globals().get(name)
    
    # Configuration components
    elif name in ['RateLimitConfig', 'rate_limit_config']:
        _load_config()
        return globals().get(name)
    
    # If nothing matches, raise AttributeError
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Public API - what users can import
__all__ = [
    # Backend
    'RedisRateLimitBackend',
    'rate_limit_backend',
    
    # Limiters
    'BaseRateLimiter',
    'UserRateLimiter',
    'IPRateLimiter',
    'EndpointRateLimiter',
    
    
    # Middleware
    'RateLimitMiddleware',
    'SmartRateLimitMiddleware',
    
    # Exceptions
    'RateLimitExceeded',
    'UserRateLimitExceeded',
    'IPRateLimitExceeded',
    'EndpointRateLimitExceeded',
    'RateLimitConfigurationError',
    'RateLimitBackendError',
    
    # Decorators (most commonly used)
    'rate_limit',
    'rate_limit_user',
    'rate_limit_ip',
    'rate_limit_endpoint',
    'rate_limit_view',
    
    # Service helpers
    'check_rate_limit',
    'get_rate_limit_status',
    'reset_rate_limit',
    
    # Context manager
    'RateLimitContext',
    
    # Configuration
    'RateLimitConfig',
    'rate_limit_config',
    
    # Analytics and monitoring  
    'get_rate_limit_analytics',
    'log_rate_limit_metrics',
    
    # Testing utilities
    'create_test_request',
    'simulate_rate_limit_scenario',
]


def setup_middleware():
    """
    Get middleware class path for Django settings.
    
    Returns:
        String path for MIDDLEWARE setting
        
    Usage:
        MIDDLEWARE = [
            setup_middleware(),
            # ... other middleware
        ]
    """
    return 'scrawl.core.rate_limiting.middleware.RateLimitMiddleware'

def setup_smart_middleware():
    """
    Get smart middleware class path for Django settings.
    
    Returns:
        String path for MIDDLEWARE setting with adaptive features
    """
    return 'scrawl.core.rate_limiting.middleware.SmartRateLimitMiddleware'

def get_version():
    """Get the current version of the rate limiting module."""
    return __version__

def get_health_status():
    """
    Get health status of the rate limiting system.
    
    Returns:
        Dictionary with system health information
    """
    try:
        _load_backends()
        _load_config()
        
        backend = globals().get('rate_limit_backend')
        config = globals().get('rate_limit_config')
        
        if not backend or not config:
            return {'status': 'error', 'message': 'Components not loaded'}
        
        # Check Redis connection
        redis_connected = backend.is_connected()
        
        # Check configuration
        config_valid = config.is_rate_limiting_enabled()
        
        status = 'healthy' if redis_connected and config_valid else 'degraded'
        
        return {
            'status': status,
            'version': __version__,
            'redis_connected': redis_connected,
            'rate_limiting_enabled': config_valid,
            'components': {
                'backends': _backends_loaded,
                'limiters': _limiters_loaded,
                'throttling': _throttling_loaded,
                'middleware': _middleware_loaded,
                'utils': _utils_loaded,
                'config': _config_loaded,
            }
        }
        
    except Exception as e:
        return {
            'status': 'error',
            'message': str(e),
            'version': __version__,
        }

# Module information for introspection
def get_module_info():
    """
    Get comprehensive information about the rate limiting module.
    
    Returns:
        Dictionary with module information
    """
    return {
        'name': 'Scrawl Rate Limiting',
        'version': __version__,
        'author': __author__,
        'email': __email__,
        'description': 'Enterprise-grade rate limiting for Django REST Framework',
        'features': [
            'Multiple rate limiting algorithms',
            'User-based, IP-based, and endpoint-specific limiting',
            'Tiered user system',
            'Django middleware integration',
            'Redis-based distributed limiting',
            'Comprehensive monitoring',
            'Flexible decorators and utilities',
        ],
        'algorithms': [
            'sliding_window',
            'token_bucket',
            'fixed_window',
        ],
        'components': {
            'backends': 1,
            'limiters': 3,
            'middleware': 2,
            'utilities': 15,
        }
    }