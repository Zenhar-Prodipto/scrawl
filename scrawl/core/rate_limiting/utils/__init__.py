# scrawl/core/rate_limiting/utils/__init__.py
"""Rate limiting utilities and exceptions."""

from .exceptions import (
    RateLimitExceeded,
    UserRateLimitExceeded,
    IPRateLimitExceeded,
    EndpointRateLimitExceeded,
    RateLimitConfigurationError,
    RateLimitBackendError,
)

from .helpers import (
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

__all__ = [
    # Exceptions
    'RateLimitExceeded',
    'UserRateLimitExceeded', 
    'IPRateLimitExceeded',
    'EndpointRateLimitExceeded',
    'RateLimitConfigurationError',
    'RateLimitBackendError',
    
    # Decorators
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
    
    # Analytics
    'get_rate_limit_analytics',
    'log_rate_limit_metrics',
    
    # Testing
    'create_test_request',
    'simulate_rate_limit_scenario',
]