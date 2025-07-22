"""
Main cache management system for Scrawl application.
Provides high-level caching operations with automatic key management and TTL handling.
"""
import json
import logging
from typing import Any, Optional, List, Dict, Union
from .redis_client import redis_manager

logger = logging.getLogger(__name__)

class CacheManager:
    """High-level cache management with predefined patterns and automatic key generation."""
    
    def __init__(self):
        self.redis_client = redis_manager.client
        
        # Cache key patterns - organized by domain
        self.key_patterns = {
            # User-related cache keys
            'user_profile': 'user:profile:{user_id}',
            'user_followers': 'user:followers:{user_id}',
            'user_following': 'user:following:{user_id}',
            'user_follower_count': 'user:follower_count:{user_id}',
            'user_following_count': 'user:following_count:{user_id}',
            
            # Follow-related cache keys
            'follow_status': 'follow:status:{user_id}:{target_id}',
            'follow_exists': 'follow:exists:{follower_id}:{followed_id}',
            'super_follower': 'follow:super:{follower_id}:{followed_id}',
            
            # Post-related cache keys
            'post_detail': 'post:detail:{post_id}',
            'post_list': 'post:list:{user_id}',
            'post_saved': 'post:saved:{user_id}',
            'post_user_posts': 'post:user:{user_id}',
            
            # Interaction cache keys
            'like_exists': 'interaction:like:{user_id}:{post_id}',
            'comment_exists': 'interaction:comment:{user_id}:{post_id}',
            'save_exists': 'interaction:save:{user_id}:{post_id}',
            
            # Feed cache keys
            'user_feed': 'feed:user:{user_id}',
            'feed_page': 'feed:page:{user_id}:{page}',
            
            # System cache keys
            'system_health': 'system:health',
            'user_session': 'session:user:{user_id}',
        }
        
        # Default TTL values (in seconds) by cache type
        self.default_ttl = {
            'user_profile': 300,        # 5 minutes
            'user_followers': 300,      # 5 minutes  
            'user_following': 300,      # 5 minutes
            'user_follower_count': 180, # 3 minutes
            'user_following_count': 180,# 3 minutes
            'follow_status': 60,        # 1 minute
            'follow_exists': 60,        # 1 minute
            'super_follower': 300,      # 5 minutes
            'post_detail': 300,         # 5 minutes
            'post_list': 300,           # 5 minutes
            'post_saved': 600,          # 10 minutes
            'post_user_posts': 300,     # 5 minutes
            'like_exists': 60,          # 1 minute
            'comment_exists': 60,       # 1 minute
            'save_exists': 60,          # 1 minute
            'user_feed': 600,           # 10 minutes
            'feed_page': 300,           # 5 minutes
            'system_health': 60,        # 1 minute
            'user_session': 3600,       # 1 hour
        }
    
    def _generate_key(self, key_type: str, **kwargs) -> str:
        """Generate cache key from pattern and parameters."""
        try:
            pattern = self.key_patterns.get(key_type)
            if not pattern:
                raise ValueError(f"Unknown cache key type: {key_type}")
            return pattern.format(**kwargs)
        except KeyError as e:
            logger.error(f"Missing parameter for cache key {key_type}: {e}")
            raise ValueError(f"Missing parameter {e} for cache key {key_type}")
    
    def _serialize_value(self, value: Any) -> str:
        """Serialize value for Redis storage."""
        if isinstance(value, str):
            return value
        try:
            return json.dumps(value, default=str)
        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize value {type(value)}: {e}")
            raise
    
    def _deserialize_value(self, value: str) -> Any:
        """Deserialize value from Redis."""
        if value is None:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            # Return as string if not valid JSON
            return value
    
    def set(self, key_type: str, value: Any, ttl: Optional[int] = None, **key_params) -> bool:
        """
        Set cache value with automatic key generation and TTL.
        
        Args:
            key_type: Type of cache key from predefined patterns
            value: Value to cache
            ttl: Time to live in seconds (uses default if not provided)
            **key_params: Parameters for key generation
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            if not redis_manager.is_connected():
                logger.warning("Redis not connected, skipping cache set")
                return False
            
            cache_key = self._generate_key(key_type, **key_params)
            ttl = ttl or self.default_ttl.get(key_type, 300)
            serialized_value = self._serialize_value(value)
            
            result = self.redis_client.setex(cache_key, ttl, serialized_value)
            
            if result:
                logger.debug(f"Cache SET: {cache_key} (TTL: {ttl}s)")
            else:
                logger.warning(f"Cache SET failed: {cache_key}")
            print(f"Cache SET: {cache_key} (TTL: {ttl}s)", flush=True)
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache SET error for {key_type}: {e}")
            return False
    
    def get(self, key_type: str, default: Any = None, **key_params) -> Any:
        """
        Get cache value with automatic key generation and deserialization.
        
        Args:
            key_type: Type of cache key from predefined patterns
            default: Default value to return if key not found
            **key_params: Parameters for key generation
            
        Returns:
            Cached value or default
        """
        try:
            if not redis_manager.is_connected():
                logger.warning("Redis not connected, returning default")
                return default
            
            cache_key = self._generate_key(key_type, **key_params)
            value = self.redis_client.get(cache_key)
            
            if value is None:
                logger.debug(f"Cache MISS: {cache_key}")
                return default
            
            logger.debug(f"Cache HIT: {cache_key}")
            return self._deserialize_value(value)
            
        except Exception as e:
            logger.error(f"Cache GET error for {key_type}: {e}")
            return default
    
    def delete(self, key_type: str, **key_params) -> bool:
        """
        Delete cache entry.
        
        Args:
            key_type: Type of cache key from predefined patterns
            **key_params: Parameters for key generation
            
        Returns:
            bool: True if deleted, False otherwise
        """
        try:
            if not redis_manager.is_connected():
                logger.warning("Redis not connected, skipping cache delete")
                return False
            
            cache_key = self._generate_key(key_type, **key_params)
            result = self.redis_client.delete(cache_key)
            
            if result:
                logger.debug(f"Cache DELETE: {cache_key}")
            
            return bool(result)
            
        except Exception as e:
            logger.error(f"Cache DELETE error for {key_type}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> int:
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Redis key pattern (supports wildcards)
            
        Returns:
            int: Number of keys deleted
        """
        try:
            if not redis_manager.is_connected():
                logger.warning("Redis not connected, skipping pattern delete")
                return 0
            
            keys = self.redis_client.keys(pattern)
            if not keys:
                return 0
            
            deleted_count = self.redis_client.delete(*keys)
            logger.debug(f"Cache DELETE PATTERN: {pattern} ({deleted_count} keys)")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Cache DELETE PATTERN error for {pattern}: {e}")
            return 0
    
    def exists(self, key_type: str, **key_params) -> bool:
        """Check if cache key exists."""
        try:
            if not redis_manager.is_connected():
                return False
            
            cache_key = self._generate_key(key_type, **key_params)
            return bool(self.redis_client.exists(cache_key))
            
        except Exception as e:
            logger.error(f"Cache EXISTS error for {key_type}: {e}")
            return False
    
    def get_ttl(self, key_type: str, **key_params) -> int:
        """Get remaining TTL for a cache key."""
        try:
            if not redis_manager.is_connected():
                return -1
            
            cache_key = self._generate_key(key_type, **key_params)
            return self.redis_client.ttl(cache_key)
            
        except Exception as e:
            logger.error(f"Cache TTL error for {key_type}: {e}")
            return -1

# Global cache manager instance
cache_manager = CacheManager()