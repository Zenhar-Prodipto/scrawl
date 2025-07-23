"""
Redis connection management for Scrawl application.
Provides singleton Redis client with connection pooling and error handling.
"""
import logging
import redis
from typing import Optional

logger = logging.getLogger(__name__)

class RedisConnectionManager:
    """Singleton Redis connection manager with health monitoring."""
    
    _instance = None
    _client = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Don't initialize client in __init__ - do it lazily when first accessed
        pass
    
    def _get_redis_url(self):
        """Get Redis URL from Django settings - lazy loaded."""
        try:
            from django.conf import settings
            return settings.REDIS_URL
        except Exception as e:
            logger.error(f"Failed to get Redis URL from settings: {e}")
            # Fallback to environment variable
            import os
            redis_url = os.getenv('REDIS_URL', 'redis://redis:6379/1')
            logger.info(f"Using Redis URL from environment: {redis_url}")
            return redis_url
    
    def _initialize_client(self):
        """Initialize Redis client with connection pooling - only when needed."""
        if self._initialized:
            return
            
        try:
            # Get Redis URL lazily (Django settings should be ready by now)
            redis_url = self._get_redis_url()
            
            # Connection pool configuration
            pool = redis.ConnectionPool.from_url(
                redis_url,
                max_connections=20,
                retry_on_timeout=True,
                socket_connect_timeout=5,
                socket_timeout=5,
                health_check_interval=30
            )
            
            self._client = redis.Redis(
                connection_pool=pool,
                decode_responses=True
            )
            
            # Test connection
            self._client.ping()
            self._initialized = True
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self._client = None
            self._initialized = False
            raise
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client instance - lazy initialization."""
        if not self._initialized:
            self._initialize_client()
        return self._client
    
    def is_connected(self) -> bool:
        """Check if Redis is connected and responsive."""
        try:
            # Only initialize if someone actually tries to check connection
            if not self._initialized:
                self._initialize_client()
            
            if self._client is None:
                return False
                
            self._client.ping()
            return True
        except Exception as e:
            logger.warning(f"Redis connection check failed: {e}")
            return False
    
    def get_connection_info(self) -> dict:
        """Get Redis connection information."""
        try:
            if not self.is_connected():
                return {"status": "disconnected", "error": "No connection"}
            
            info = self._client.info()
            return {
                "status": "connected",
                "redis_url": self._get_redis_url(),
                "redis_version": info.get("redis_version", "unknown"),
                "connected_clients": info.get("connected_clients", 0),
                "used_memory_human": info.get("used_memory_human", "unknown"),
                "total_commands_processed": info.get("total_commands_processed", 0),
            }
        except Exception as e:
            logger.error(f"Failed to get Redis info: {e}")
            return {"status": "error", "error": str(e)}
    
    def close_connection(self):
        """Close Redis connection."""
        try:
            if self._client:
                self._client.close()
                logger.info("Redis connection closed")
        except Exception as e:
            logger.error(f"Error closing Redis connection: {e}")
        finally:
            self._client = None
            self._initialized = False

# Singleton instance - but no immediate initialization
redis_manager = RedisConnectionManager()