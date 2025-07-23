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

# Version info
__version__ = '1.0.0'

# Lazy loading globals - will be initialized when first accessed
_cache_manager = None
_redis_manager = None
_invalidate = None
_decorators_loaded = False

def _get_cache_manager():
    """Lazy load cache manager."""
    global _cache_manager
    if _cache_manager is None:
        from .managers.cache_manager import cache_manager as cm
        _cache_manager = cm
    return _cache_manager

def _get_redis_manager():
    """Lazy load redis manager."""
    global _redis_manager
    if _redis_manager is None:
        from .managers.redis_client import redis_manager as rm
        _redis_manager = rm
    return _redis_manager

def _get_invalidate():
    """Lazy load invalidation strategies."""
    global _invalidate
    if _invalidate is None:
        from .invalidation.strategies import CacheInvalidationStrategy, invalidate as inv
        _invalidate = inv
    return _invalidate

def _load_decorators():
    """Lazy load decorators."""
    global _decorators_loaded
    if not _decorators_loaded:
        # Import all decorators and make them available at module level
        from .decorators.cache_decorators import (
            cache_result,
            cached,
            cache_key_from_args,
            invalidate_cache_on_change,
            invalidate_on_change,
            cache_multiple_keys,
            cache_with_fallback,
        )
        
        # Add them to globals so they can be imported
        globals().update({
            'cache_result': cache_result,
            'cached': cached,
            'cache_key_from_args': cache_key_from_args,
            'invalidate_cache_on_change': invalidate_cache_on_change,
            'invalidate_on_change': invalidate_on_change,
            'cache_multiple_keys': cache_multiple_keys,
            'cache_with_fallback': cache_with_fallback,
        })
        _decorators_loaded = True

# Module-level getattr to handle imports
def __getattr__(name):
    """Handle lazy loading of module attributes."""
    
    # Core managers
    if name == 'cache_manager':
        return _get_cache_manager()
    elif name == 'redis_manager':
        return _get_redis_manager()
    elif name == 'invalidate':
        return _get_invalidate()
    elif name == 'CacheInvalidationStrategy':
        from .invalidation.strategies import CacheInvalidationStrategy
        return CacheInvalidationStrategy
    
    # Decorators - load them if not already loaded
    elif name in ['cache_result', 'cached', 'cache_key_from_args', 
                  'invalidate_cache_on_change', 'invalidate_on_change',
                  'cache_multiple_keys', 'cache_with_fallback']:
        _load_decorators()
        return globals().get(name)
    
    # If nothing matches, raise AttributeError
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")

# Main exports for IDE auto-completion (but won't be imported immediately)
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