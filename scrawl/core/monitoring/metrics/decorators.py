"""
Monitoring decorators for easy performance tracking.
"""
import time
import logging
from functools import wraps
from typing import Callable, Any
from .collectors import api_request_duration, record_cache_operation

logger = logging.getLogger(__name__)

def track_performance(endpoint_name: str = None):
    """
    Decorator to track API endpoint performance.
    
    Args:
        endpoint_name: Optional endpoint name (auto-detected if not provided)
    
    Usage:
        @track_performance('user_login')
        def login_view(self, request):
            # Your view logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Auto-detect endpoint name if not provided
            if endpoint_name:
                name = endpoint_name
            else:
                # Try to get from view class and method
                if hasattr(func, '__name__'):
                    name = func.__name__
                else:
                    name = 'unknown'
            
            # Get HTTP method if available (from DRF views)
            method = 'unknown'
            if args and hasattr(args[0], 'request'):
                request = args[0].request
                method = request.method.upper()
            
            # Track timing
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Record the duration
                api_request_duration.labels(
                    method=method,
                    endpoint=name
                ).observe(duration)
                
                logger.debug(f"Performance tracked: {method} {name} took {duration:.3f}s")
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                api_request_duration.labels(
                    method=method,
                    endpoint=name
                ).observe(duration)
                logger.debug(f"Performance tracked (error): {method} {name} took {duration:.3f}s")
                raise
        
        return wrapper
    return decorator

def track_cache_usage(cache_type: str):
    """
    Decorator to track cache hit/miss ratios.
    
    Args:
        cache_type: Type of cache being used (e.g., 'user_posts', 'feed_cache')
    
    Usage:
        @track_cache_usage('user_posts')
        def get_user_posts(self, user_id):
            # Check cache first
            cached = cache_manager.get('post_list', user_id=user_id)
            if cached:
                return cached  # Cache hit tracked automatically
            # ... rest of logic
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                result = func(*args, **kwargs)
                
                # Simple heuristic: if result is from cache, it's typically faster
                # More sophisticated tracking would be done in the actual cache manager
                # This decorator is mainly for marking functions that use cache
                
                logger.debug(f"Cache usage tracked for {cache_type} in {func.__name__}")
                return result
                
            except Exception as e:
                logger.debug(f"Cache usage tracking error in {func.__name__}: {e}")
                raise
        
        return wrapper
    return decorator

def track_kafka_operation(topic: str, operation: str = 'publish'):
    """
    Decorator to track Kafka operations.
    
    Args:
        topic: Kafka topic name
        operation: Operation type ('publish' or 'consume')
    
    Usage:
        @track_kafka_operation('follow.events', 'publish')
        def publish_follow_event(self, data):
            # Your Kafka publish logic
            pass
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                # Import here to avoid circular imports
                from .collectors import kafka_publish_duration
                
                kafka_publish_duration.labels(
                    topic=topic,
                    event_type='unknown'  # Could be enhanced to detect event type
                ).observe(duration)
                
                logger.debug(f"Kafka {operation} tracked: {topic} took {duration:.3f}s")
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                logger.debug(f"Kafka {operation} tracking error: {topic} took {duration:.3f}s")
                raise
        
        return wrapper
    return decorator