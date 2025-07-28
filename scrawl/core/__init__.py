# """
# Scrawl Core Services Module

# Provides centralized infrastructure services for the Scrawl application:
# - Caching: Redis-based caching with smart invalidation
# - Messaging: Kafka event publishing and consumption (TODO)
# - Monitoring: Health checks and metrics (TODO)  
# - Rate Limiting: API throttling and protection (TODO)

# Usage:
#     # Caching
#     from scrawl.core.caching import cache_manager, cached, invalidate
    
#     # Future imports (when implemented):
#     # from scrawl.core.messaging import event_publisher
#     # from scrawl.core.monitoring import health_checker
#     # from scrawl.core.rate_limiting import throttle
# """

# # Import caching functionality (implemented)
# from .caching import (
#     cache_manager,
#     cached,
#     invalidate,
#     CacheInvalidationStrategy,
# )

# # Placeholder imports for future modules
# # TODO: Implement these modules
# # from .messaging import event_publisher
# # from .monitoring import health_checker  
# # from .rate_limiting import throttle

# __all__ = [
#     # Caching (available now)
#     'cache_manager',
#     'cached', 
#     'invalidate',
#     'CacheInvalidationStrategy',
    
#     # Future exports (when implemented)
#     # 'event_publisher',
#     # 'health_checker', 
#     # 'throttle',
# ]

# __version__ = '1.0.0'


"""
Scrawl Core Services Module

Provides centralized infrastructure services for the Scrawl application:
- Caching: Redis-based caching with smart invalidation ✅
- Messaging: Kafka event publishing and consumption ✅
- Rate Limiting: Enterprise-grade API protection with multiple algorithms ✅
- Monitoring: Health checks and metrics (TODO)

Usage:
    # Caching
    from scrawl.core.caching import cache_manager, cached, invalidate
    
    # Messaging  
    from scrawl.core.messaging import event_publisher
    
    # Rate Limiting
    from scrawl.core.rate_limiting import (
        rate_limit_user, rate_limit_ip, rate_limit_endpoint,
        UserRateLimiter, IPRateLimiter, EndpointRateLimiter
    )
    
    # Future imports:
    # from scrawl.core.monitoring import health_checker
"""

# Import caching functionality
from .caching import (
    cache_manager,
    cached,
    invalidate,
    CacheInvalidationStrategy,
)

# Import messaging functionality
from .messaging import event_publisher

# Import rate limiting functionality
from .rate_limiting import (
    # Decorators (most commonly used)
    rate_limit_user,
    rate_limit_ip, 
    rate_limit_endpoint,
    
    # Limiter classes
    UserRateLimiter,
    IPRateLimiter,
    EndpointRateLimiter,
    
    # Exceptions
    RateLimitExceeded,
    UserRateLimitExceeded,
    IPRateLimitExceeded,
    
    # Utilities
    check_rate_limit,
    get_rate_limit_status,
)

__all__ = [
    # Caching
    'cache_manager',
    'cached', 
    'invalidate',
    'CacheInvalidationStrategy',
    
    # Messaging
    'event_publisher',
    
    # Rate Limiting - Decorators
    'rate_limit_user',
    'rate_limit_ip',
    'rate_limit_endpoint',
    
    # Rate Limiting - Classes
    'UserRateLimiter',
    'IPRateLimiter', 
    'EndpointRateLimiter',
    
    # Rate Limiting - Exceptions
    'RateLimitExceeded',
    'UserRateLimitExceeded',
    'IPRateLimitExceeded',
    
    # Rate Limiting - Utilities
    'check_rate_limit',
    'get_rate_limit_status',
]

__version__ = '2.0.0'  # Major version bump - you added 2 major systems!