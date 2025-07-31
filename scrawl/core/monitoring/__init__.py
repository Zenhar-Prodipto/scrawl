"""
Scrawl Core Monitoring Module

Provides Prometheus metrics collection, health checks, and performance tracking
for the Scrawl social media application.

Usage:
    # Basic metrics
    from scrawl.core.monitoring import track_performance, track_cache_usage
    
    # Health checks
    from scrawl.core.monitoring import get_system_health
    
    # Direct metric access
    from scrawl.core.monitoring import metrics
"""

# Import core monitoring components
from .metrics import (
    # Metric collectors
    rate_limit_violations,
    cache_operations,
    api_requests,
    kafka_messages_published,
    kafka_messages_consumed,
    
    # Decorators
    track_performance,
    track_cache_usage,
)

from .health import (
    get_system_health,
    check_redis_health,
    check_kafka_health,
    check_database_health,
)

# Import views for URL routing
from .views import MetricsView, HealthView
# from .middleware import APIMetricsMiddleware

__all__ = [
    # Metrics
    'rate_limit_violations',
    'cache_operations', 
    'api_requests',
    'kafka_messages_published',
    'kafka_messages_consumed',
    
    # Decorators
    'track_performance',
    'track_cache_usage',
    
    # Health checks
    'get_system_health',
    'check_redis_health',
    'check_kafka_health', 
    'check_database_health',
    
    # Views
    'MetricsView',
    'HealthView',
    
    # Middleware
    # 'APIMetricsMiddleware',
]

__version__ = '1.0.0'