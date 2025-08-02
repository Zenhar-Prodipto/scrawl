"""
Health check functions for Scrawl system components.
"""
import logging
from typing import Dict, Any
from django.db import connection
from django.core.cache import cache

logger = logging.getLogger(__name__)

def check_database_health() -> Dict[str, Any]:
    """
    Check database connectivity and basic operations.
    
    Returns:
        Dict with health status and details
    """
    try:
        # Test database connection
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            result = cursor.fetchone()
        
        if result and result[0] == 1:
            return {
                'status': 'healthy',
                'component': 'database',
                'message': 'Database connection successful',
                'details': {
                    'vendor': connection.vendor,
                    'connection_name': connection.alias
                }
            }
        else:
            return {
                'status': 'unhealthy',
                'component': 'database',
                'message': 'Database query failed',
                'details': {}
            }
            
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        return {
            'status': 'unhealthy',
            'component': 'database',
            'message': f'Database error: {str(e)}',
            'details': {}
        }

def check_redis_health() -> Dict[str, Any]:
    """
    Check Redis connectivity and basic operations.
    
    Returns:
        Dict with health status and details
    """
    try:
        # Use Django's cache framework to test Redis
        test_key = 'health_check_test'
        test_value = 'healthy'
        
        # Set and get a test value
        cache.set(test_key, test_value, timeout=30)
        retrieved_value = cache.get(test_key)
        
        if retrieved_value == test_value:
            # Clean up test key
            cache.delete(test_key)
            
            return {
                'status': 'healthy',
                'component': 'redis',
                'message': 'Redis connection and operations successful',
                'details': {
                    'cache_backend': str(cache.__class__.__name__)
                }
            }
        else:
            return {
                'status': 'unhealthy',
                'component': 'redis',
                'message': 'Redis set/get operation failed',
                'details': {}
            }
            
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        return {
            'status': 'unhealthy',
            'component': 'redis',
            'message': f'Redis error: {str(e)}',
            'details': {}
        }

def check_kafka_health() -> Dict[str, Any]:
    """
    Check Kafka connectivity.
    
    Returns:
        Dict with health status and details
    """
    try:
        # Import Kafka manager
        from ...messaging.kafka.kafka_client import kafka_manager
        
        if kafka_manager.is_connected():
            return {
                'status': 'healthy',
                'component': 'kafka',
                'message': 'Kafka connection successful',
                'details': {}
            }
        else:
            return {
                'status': 'unhealthy',
                'component': 'kafka',
                'message': 'Kafka connection failed',
                'details': {}
            }
            
    except Exception as e:
        logger.error(f"Kafka health check failed: {e}")
        return {
            'status': 'unhealthy',
            'component': 'kafka',
            'message': f'Kafka error: {str(e)}',
            'details': {}
        }

def check_rate_limiting_health() -> Dict[str, Any]:
    """
    Check rate limiting system health.
    
    Returns:
        Dict with health status and details
    """
    try:
        from ...rate_limiting.backends.redis_backend import rate_limit_backend
        
        if rate_limit_backend.is_connected():
            return {
                'status': 'healthy',
                'component': 'rate_limiting',
                'message': 'Rate limiting system operational',
                'details': {
                    'backend': 'redis',
                    'algorithms': ['sliding_window', 'token_bucket', 'fixed_window']
                }
            }
        else:
            return {
                'status': 'unhealthy',
                'component': 'rate_limiting',
                'message': 'Rate limiting backend unavailable',
                'details': {}
            }
            
    except Exception as e:
        logger.error(f"Rate limiting health check failed: {e}")
        return {
            'status': 'unhealthy',
            'component': 'rate_limiting',
            'message': f'Rate limiting error: {str(e)}',
            'details': {}
        }

def get_system_health() -> Dict[str, Any]:
    """
    Get overall system health status.
    
    Returns:
        Dict with comprehensive health information
    """
    health_checks = {
        'database': check_database_health(),
        'redis': check_redis_health(),
        'kafka': check_kafka_health(),
        'rate_limiting': check_rate_limiting_health(),
    }
    
    # Count healthy vs unhealthy components
    healthy_count = sum(1 for check in health_checks.values() if check['status'] == 'healthy')
    total_count = len(health_checks)
    
    # Determine overall status
    if healthy_count == total_count:
        overall_status = 'healthy'
        overall_message = 'All systems operational'
    elif healthy_count > 0:
        overall_status = 'degraded'
        overall_message = f'{healthy_count}/{total_count} systems operational'
    else:
        overall_status = 'unhealthy'
        overall_message = 'Multiple system failures detected'
    
    # Update Prometheus metrics
    try:
        from ..metrics.collectors import update_system_health
        for component, check in health_checks.items():
            is_healthy = check['status'] == 'healthy'
            update_system_health(component, is_healthy)
    except Exception as e:
        logger.error(f"Failed to update health metrics: {e}")
    
    return {
        'status': overall_status,
        'message': overall_message,
        'timestamp': str(health_checks.get('database', {}).get('timestamp', 'unknown')),
        'components': health_checks,
        'summary': {
            'healthy': healthy_count,
            'total': total_count,
            'uptime_percentage': round((healthy_count / total_count) * 100, 1)
        }
    }