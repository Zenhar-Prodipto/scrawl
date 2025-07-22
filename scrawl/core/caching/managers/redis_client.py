"""
Redis connection management for Scrawl application.
Provides singleton Redis client with connection pooling and error handling.
"""
import logging
import redis
from typing import Optional
from django.conf import settings

logger = logging.getLogger(__name__)

class RedisConnectionManager:
    """Singleton Redis connection manager with health monitoring."""
    
    _instance = None
    _client = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        if self._client is None:
            self._initialize_client()
    
    def _initialize_client(self):
        """Initialize Redis client with connection pooling."""
        try:
            # Connection pool configuration
            pool = redis.ConnectionPool.from_url(
                settings.REDIS_URL,
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
            logger.info("Redis connection established successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize Redis client: {e}")
            self._client = None
            raise
    
    @property
    def client(self) -> Optional[redis.Redis]:
        """Get Redis client instance."""
        if self._client is None:
            self._initialize_client()
        return self._client
    
    def is_connected(self) -> bool:
        """Check if Redis is connected and responsive."""
        try:
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

# Singleton instance
redis_manager = RedisConnectionManager()