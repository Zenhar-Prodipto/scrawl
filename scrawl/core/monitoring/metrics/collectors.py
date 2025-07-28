"""
Prometheus metrics collectors for Scrawl application.
Defines all the metrics we'll track across the system.
"""
import logging
from prometheus_client import Counter, Histogram, Gauge, Info

logger = logging.getLogger(__name__)

# =============================================================================
# RATE LIMITING METRICS
# =============================================================================

rate_limit_violations = Counter(
    'scrawl_rate_limit_violations_total',
    'Total number of rate limit violations',
    ['limiter_type', 'user_tier', 'action', 'algorithm']
)

rate_limit_requests = Counter(
    'scrawl_rate_limit_requests_total',
    'Total number of rate limit checks',
    ['limiter_type', 'user_tier', 'action', 'result']
)

# =============================================================================
# CACHE METRICS
# =============================================================================

cache_operations = Counter(
    'scrawl_cache_operations_total',
    'Total cache operations',
    ['operation', 'cache_type', 'result']
)

cache_hit_ratio = Gauge(
    'scrawl_cache_hit_ratio',
    'Cache hit ratio by cache type',
    ['cache_type']
)

# =============================================================================
# API PERFORMANCE METRICS
# =============================================================================

api_requests = Counter(
    'scrawl_api_requests_total',
    'Total API requests',
    ['method', 'endpoint', 'status_code', 'user_tier']
)

api_request_duration = Histogram(
    'scrawl_api_request_duration_seconds',
    'API request duration in seconds',
    ['method', 'endpoint'],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.075, 0.1, 0.25, 0.5, 0.75, 1.0, 2.5, 5.0, 7.5, 10.0)
)

# =============================================================================
# KAFKA METRICS
# =============================================================================

kafka_messages_published = Counter(
    'scrawl_kafka_messages_published_total',
    'Total Kafka messages published',
    ['topic', 'event_type', 'status']
)

kafka_messages_consumed = Counter(
    'scrawl_kafka_messages_consumed_total',
    'Total Kafka messages consumed',
    ['topic', 'event_type', 'status']
)

kafka_publish_duration = Histogram(
    'scrawl_kafka_publish_duration_seconds',
    'Time taken to publish Kafka messages',
    ['topic', 'event_type'],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0)
)

# =============================================================================
# BUSINESS METRICS (Phase 2)
# =============================================================================

user_registrations = Counter(
    'scrawl_user_registrations_total',
    'Total user registrations',
    ['registration_type']
)

posts_created = Counter(
    'scrawl_posts_created_total',
    'Total posts created',
    ['privacy_type', 'user_tier']
)

follows_created = Counter(
    'scrawl_follows_created_total',
    'Total follow relationships created',
    ['follow_type', 'user_tier']
)

feed_requests = Counter(
    'scrawl_feed_requests_total',
    'Total feed requests',
    ['user_tier', 'cache_result']
)

authentication_events = Counter(
    'scrawl_authentication_events_total',
    'Authentication events',
    ['event_type', 'result']
)

# =============================================================================
# SYSTEM HEALTH METRICS
# =============================================================================

system_health = Gauge(
    'scrawl_system_health',
    'System health status (1=healthy, 0=unhealthy)',
    ['component']
)

redis_info = Info(
    'scrawl_redis_info',
    'Redis server information'
)

kafka_info = Info(
    'scrawl_kafka_info',
    'Kafka cluster information'
)

database_connections = Gauge(
    'scrawl_database_connections',
    'Database connection pool status',
    ['status']
)

# =============================================================================
# UTILITY FUNCTIONS
# =============================================================================

def record_rate_limit_violation(limiter_type: str, user_tier: str, action: str, algorithm: str):
    """Record a rate limit violation."""
    rate_limit_violations.labels(
        limiter_type=limiter_type,
        user_tier=user_tier,
        action=action,
        algorithm=algorithm
    ).inc()

def record_rate_limit_request(limiter_type: str, user_tier: str, action: str, allowed: bool):
    """Record a rate limit check."""
    result = 'allowed' if allowed else 'denied'
    rate_limit_requests.labels(
        limiter_type=limiter_type,
        user_tier=user_tier,
        action=action,
        result=result
    ).inc()

def record_cache_operation(operation: str, cache_type: str, hit: bool):
    """Record a cache operation."""
    result = 'hit' if hit else 'miss'
    cache_operations.labels(
        operation=operation,
        cache_type=cache_type,
        result=result
    ).inc()

def record_api_request(method: str, endpoint: str, status_code: int, user_tier: str = 'anonymous'):
    """Record an API request."""
    api_requests.labels(
        method=method,
        endpoint=endpoint,
        status_code=str(status_code),
        user_tier=user_tier
    ).inc()

def record_kafka_publish(topic: str, event_type: str, success: bool):
    """Record a Kafka message publish."""
    status = 'success' if success else 'failure'
    kafka_messages_published.labels(
        topic=topic,
        event_type=event_type,
        status=status
    ).inc()

def record_kafka_consume(topic: str, event_type: str, success: bool):
    """Record a Kafka message consumption."""
    status = 'success' if success else 'failure'
    kafka_messages_consumed.labels(
        topic=topic,
        event_type=event_type,
        status=status
    ).inc()

def update_system_health(component: str, healthy: bool):
    """Update system health status."""
    status = 1.0 if healthy else 0.0
    system_health.labels(component=component).set(status)

# =============================================================================
# BUSINESS METRIC HELPERS (Phase 2)
# =============================================================================

def record_user_registration(registration_type: str = 'standard'):
    """Record a user registration."""
    user_registrations.labels(registration_type=registration_type).inc()

def record_post_creation(privacy_type: str, user_tier: str = 'free'):
    """Record a post creation."""
    posts_created.labels(privacy_type=privacy_type, user_tier=user_tier).inc()

def record_follow_creation(follow_type: str = 'standard', user_tier: str = 'free'):
    """Record a follow relationship creation."""
    follows_created.labels(follow_type=follow_type, user_tier=user_tier).inc()

def record_feed_request(user_tier: str, cache_hit: bool):
    """Record a feed request."""
    cache_result = 'hit' if cache_hit else 'miss'
    feed_requests.labels(user_tier=user_tier, cache_result=cache_result).inc()

def record_authentication_event(event_type: str, success: bool):
    """Record an authentication event."""
    result = 'success' if success else 'failure'
    authentication_events.labels(event_type=event_type, result=result).inc()

logger.info("Scrawl metrics collectors initialized successfully")