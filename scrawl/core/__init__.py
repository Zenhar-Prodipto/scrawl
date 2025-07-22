"""
Scrawl Core Services Module

Provides centralized infrastructure services for the Scrawl application:
- Caching: Redis-based caching with smart invalidation
- Messaging: Kafka event publishing and consumption (TODO)
- Monitoring: Health checks and metrics (TODO)  
- Rate Limiting: API throttling and protection (TODO)

Usage:
    # Caching
    from scrawl.core.caching import cache_manager, cached, invalidate
    
    # Future imports (when implemented):
    # from scrawl.core.messaging import event_publisher
    # from scrawl.core.monitoring import health_checker
    # from scrawl.core.rate_limiting import throttle
"""

# Import caching functionality (implemented)
from .caching import (
    cache_manager,
    cached,
    invalidate,
    CacheInvalidationStrategy,
)

# Placeholder imports for future modules
# TODO: Implement these modules
# from .messaging import event_publisher
# from .monitoring import health_checker  
# from .rate_limiting import throttle

__all__ = [
    # Caching (available now)
    'cache_manager',
    'cached', 
    'invalidate',
    'CacheInvalidationStrategy',
    
    # Future exports (when implemented)
    # 'event_publisher',
    # 'health_checker', 
    # 'throttle',
]

__version__ = '1.0.0'