"""
Scrawl Core Caching Module

Provides centralized caching functionality with Redis backend,
smart invalidation strategies, and convenient decorators.

Usage:
    from scrawl.core.caching import cache_manager, invalidate, cached
    
    # Direct cache operations
    cache_manager.set('user_profile', user_data, user_id=123)
    user_data = cache_manager.get('user_profile', user_id=123)
    
    # Cache invalidation
    invalidate.invalidate_user_profile_cache(user_id=123)
    
    # Decorator usage
    @cached('user_profile', ttl=300)
    @cache_key_from_args('user_id')
    def get_user_profile(user_id):
        return expensive_database_query(user_id)
"""

from .managers.cache_manager import cache_manager
from .managers.redis_client import redis_manager
from .invalidation.strategies import CacheInvalidationStrategy, invalidate
from .decorators.cache_decorators import (
    cache_result,
    cached,
    cache_key_from_args,
    invalidate_cache_on_change,
    invalidate_on_change,
    cache_multiple_keys,
    cache_with_fallback,
)

# Main exports for easy importing
__all__ = [
    # Core managers
    'cache_manager',
    'redis_manager',
    
    # Invalidation strategies
    'CacheInvalidationStrategy',
    'invalidate',
    
    # Decorators
    'cache_result',
    'cached',  # Alias for cache_result
    'cache_key_from_args',
    'invalidate_cache_on_change',
    'invalidate_on_change',  # Alias
    'cache_multiple_keys',
    'cache_with_fallback',
]

# Version info
__version__ = '1.0.0'