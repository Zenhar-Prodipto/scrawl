"""
Cache decorators for Scrawl application.
Provides function decorators for automatic caching and invalidation.
"""
import functools
import hashlib
import logging
from typing import Callable, Any, Optional, List, Dict
from ..managers.cache_manager import cache_manager
from ..invalidation.strategies import CacheInvalidationStrategy

logger = logging.getLogger(__name__)

def cache_result(key_type: str, ttl: Optional[int] = None, 
                key_params_func: Optional[Callable] = None):
    """
    Decorator to cache function results.
    
    Args:
        key_type: Cache key type from cache_manager patterns
        ttl: Time to live in seconds (uses default if not provided)
        key_params_func: Function to extract key parameters from function args
        
    Usage:
        @cache_result('user_profile', ttl=300, key_params_func=lambda *args, **kwargs: {'user_id': args[0]})
        def get_user_profile(user_id):
            return expensive_database_query(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Extract cache key parameters
                if key_params_func:
                    key_params = key_params_func(*args, **kwargs)
                else:
                    # Try to auto-extract common patterns
                    key_params = _auto_extract_key_params(func.__name__, *args, **kwargs)
                
                # Try to get from cache first
                cached_result = cache_manager.get(key_type, **key_params)
                if cached_result is not None:
                    logger.debug(f"Cache HIT for {func.__name__} with params {key_params}")
                    return cached_result
                
                # Execute function if not in cache
                logger.debug(f"Cache MISS for {func.__name__} with params {key_params}")
                result = func(*args, **kwargs)
                
                # Store result in cache
                if result is not None:
                    cache_manager.set(key_type, result, ttl=ttl, **key_params)
                
                return result
                
            except Exception as e:
                logger.error(f"Cache decorator error for {func.__name__}: {e}")
                # Return function result even if caching fails
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

def cache_key_from_args(*arg_names):
    """
    Helper decorator to create cache key parameters from function arguments.
    
    Usage:
        @cache_result('user_profile', ttl=300)
        @cache_key_from_args('user_id')
        def get_user_profile(user_id):
            return expensive_query(user_id)
    """
    def key_params_func(*args, **kwargs):
        params = {}
        # Map positional arguments
        for i, arg_name in enumerate(arg_names):
            if i < len(args):
                params[arg_name] = args[i]
        
        # Add keyword arguments that match our pattern
        for arg_name in arg_names:
            if arg_name in kwargs:
                params[arg_name] = kwargs[arg_name]
        
        return params
    
    def decorator(func: Callable) -> Callable:
        # Store the key params function on the decorated function
        func._cache_key_params_func = key_params_func
        return func
    
    return decorator

def invalidate_cache_on_change(invalidation_strategy: str, 
                              key_params_func: Optional[Callable] = None):
    """
    Decorator to invalidate cache when function is called.
    
    Args:
        invalidation_strategy: Strategy name from CacheInvalidationStrategy
        key_params_func: Function to extract parameters for invalidation
        
    Usage:
        @invalidate_cache_on_change('user_profile', lambda *args, **kwargs: {'user_id': args[0]})
        def update_user_profile(user_id, data):
            return update_database(user_id, data)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Execute the function first
            result = func(*args, **kwargs)
            
            try:
                # Extract parameters for cache invalidation
                if key_params_func:
                    params = key_params_func(*args, **kwargs)
                else:
                    params = _auto_extract_key_params(func.__name__, *args, **kwargs)
                
                # Perform cache invalidation
                strategy_method = getattr(CacheInvalidationStrategy, f'invalidate_{invalidation_strategy}_cache', None)
                if strategy_method:
                    strategy_method(**params)
                else:
                    logger.warning(f"Unknown invalidation strategy: {invalidation_strategy}")
                
            except Exception as e:
                logger.error(f"Cache invalidation error for {func.__name__}: {e}")
            
            return result
        
        return wrapper
    return decorator

def cache_multiple_keys(cache_configs: List[Dict[str, Any]]):
    """
    Decorator to cache function results with multiple cache keys.
    
    Args:
        cache_configs: List of cache configurations, each containing:
                      {'key_type': str, 'ttl': int, 'key_params_func': callable}
    
    Usage:
        @cache_multiple_keys([
            {'key_type': 'user_profile', 'key_params_func': lambda u, *a, **k: {'user_id': u.id}},
            {'key_type': 'user_session', 'key_params_func': lambda u, *a, **k: {'user_id': u.id}},
        ])
        def get_user_with_session(user):
            return expensive_query_with_joins(user)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Try to get from any cache first
            for config in cache_configs:
                try:
                    key_type = config['key_type']
                    key_params_func = config.get('key_params_func')
                    
                    if key_params_func:
                        key_params = key_params_func(*args, **kwargs)
                        cached_result = cache_manager.get(key_type, **key_params)
                        if cached_result is not None:
                            logger.debug(f"Multi-cache HIT for {func.__name__} on key {key_type}")
                            return cached_result
                except Exception as e:
                    logger.warning(f"Multi-cache check error for {key_type}: {e}")
                    continue
            
            # Execute function if not in any cache
            logger.debug(f"Multi-cache MISS for {func.__name__}")
            result = func(*args, **kwargs)
            
            # Store result in all caches
            if result is not None:
                for config in cache_configs:
                    try:
                        key_type = config['key_type']
                        ttl = config.get('ttl')
                        key_params_func = config.get('key_params_func')
                        
                        if key_params_func:
                            key_params = key_params_func(*args, **kwargs)
                            cache_manager.set(key_type, result, ttl=ttl, **key_params)
                    except Exception as e:
                        logger.error(f"Multi-cache store error for {key_type}: {e}")
            
            return result
        
        return wrapper
    return decorator

def cache_with_fallback(primary_key_type: str, fallback_func: Callable,
                       ttl: Optional[int] = None, key_params_func: Optional[Callable] = None):
    """
    Decorator to cache with fallback function if cache miss and main function fails.
    
    Usage:
        def get_user_from_cache_only(user_id):
            return cache_manager.get('user_profile', user_id=user_id)
            
        @cache_with_fallback('user_profile', get_user_from_cache_only)
        def get_user_profile(user_id):
            return expensive_database_query(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                # Extract cache key parameters
                if key_params_func:
                    key_params = key_params_func(*args, **kwargs)
                else:
                    key_params = _auto_extract_key_params(func.__name__, *args, **kwargs)
                
                # Try cache first
                cached_result = cache_manager.get(primary_key_type, **key_params)
                if cached_result is not None:
                    return cached_result
                
                # Try main function
                try:
                    result = func(*args, **kwargs)
                    if result is not None:
                        cache_manager.set(primary_key_type, result, ttl=ttl, **key_params)
                    return result
                except Exception as e:
                    logger.warning(f"Main function {func.__name__} failed: {e}, trying fallback")
                    return fallback_func(*args, **kwargs)
                
            except Exception as e:
                logger.error(f"Cache with fallback error for {func.__name__}: {e}")
                return func(*args, **kwargs)
        
        return wrapper
    return decorator

def _auto_extract_key_params(func_name: str, *args, **kwargs) -> Dict[str, Any]:
    """Auto-extract common cache key parameters from function arguments."""
    params = {}
    
    # Common parameter patterns
    param_patterns = {
        'user_id': ['user_id', 'id'],
        'post_id': ['post_id'],
        'target_id': ['target_id'],
        'follower_id': ['follower_id'],
        'followed_id': ['followed_id'],
    }
    
    # Extract from kwargs first
    for cache_param, possible_names in param_patterns.items():
        for name in possible_names:
            if name in kwargs:
                params[cache_param] = kwargs[name]
                break
    
    # Extract from positional args based on common function patterns
    if 'user' in func_name.lower() and len(args) > 0:
        if hasattr(args[0], 'id'):
            params['user_id'] = args[0].id
        elif isinstance(args[0], int):
            params['user_id'] = args[0]
    
    if 'post' in func_name.lower() and len(args) > 0:
        if hasattr(args[0], 'id'):
            params['post_id'] = args[0].id
        elif isinstance(args[0], int):
            params['post_id'] = args[0]
    
    return params

# Convenient aliases
cached = cache_result
invalidate_on_change = invalidate_cache_on_change