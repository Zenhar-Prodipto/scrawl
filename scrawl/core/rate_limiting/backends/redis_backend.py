"""
Redis backend for rate limiting in Scrawl application.
Provides multiple rate limiting algorithms using existing Redis infrastructure.
"""
import time
import logging
from typing import Dict, Optional, Tuple
from scrawl.core.caching.managers.redis_client import redis_manager
from ..utils.exceptions import RateLimitBackendError

logger = logging.getLogger(__name__)


class RedisRateLimitBackend:
    """
    Redis-based rate limiting backend with multiple algorithms.
    Integrates with existing Scrawl Redis infrastructure.
    """
    
    def __init__(self):
        # Use existing Redis client from caching system
        self._redis = None
    
    @property
    def redis(self):
        """Get Redis client - lazy initialization."""
        if self._redis is None:
            self._redis = redis_manager.client
        return self._redis
    
    def is_connected(self) -> bool:
        """Check if Redis is available."""
        return redis_manager.is_connected()
    
    def sliding_window_check(self, key: str, limit: int, window: int) -> Tuple[bool, Dict[str, int]]:
        """
        Sliding window rate limiting algorithm.
        Most accurate but memory intensive - use for critical operations.
        
        Args:
            key: Rate limit key (e.g., 'user:123:posts')
            limit: Number of requests allowed
            window: Time window in seconds
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, allowing request")
                return True, {'remaining': limit, 'reset_time': int(time.time()) + window}
            
            current_time = time.time()
            window_start = current_time - window
            
            # Use Redis pipeline for atomic operations
            pipe = self.redis.pipeline()
            
            # Remove old entries outside the window
            pipe.zremrangebyscore(key, 0, window_start)
            
            # Count current requests in window
            pipe.zcard(key)
            
            # Add current request
            pipe.zadd(key, {str(current_time): current_time})
            
            # Set expiry for cleanup
            pipe.expire(key, window + 1)
            
            results = pipe.execute()
            current_count = results[1] + 1  # +1 for the request we just added
            
            is_allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            reset_time = int(current_time + window)
            
            if not is_allowed:
                # Remove the request we just added since it's not allowed
                self.redis.zrem(key, str(current_time))
            
            metadata = {
                'remaining': remaining,
                'reset_time': reset_time,
                'current_count': current_count,
                'algorithm': 'sliding_window'
            }
            
            logger.debug(f"Sliding window check for {key}: allowed={is_allowed}, count={current_count}/{limit}")
            return is_allowed, metadata
            
        except Exception as e:
            logger.error(f"Redis sliding window error for {key}: {e}")
            raise RateLimitBackendError(f"Sliding window check failed: {str(e)}")
    
    def token_bucket_check(self, key: str, limit: int, window: int, burst_size: Optional[int] = None) -> Tuple[bool, Dict[str, int]]:
        """
        Token bucket rate limiting algorithm.
        Allows bursts but maintains steady rate - perfect for social media.
        
        Args:
            key: Rate limit key
            limit: Tokens per window (steady rate)
            window: Refill window in seconds
            burst_size: Maximum burst size (defaults to limit)
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, allowing request")
                return True, {'remaining': limit, 'reset_time': int(time.time()) + window}
            
            # Ensure all values are proper types
            limit = int(limit)
            window = int(window)
            burst_size = int(burst_size or limit)
            current_time = float(time.time())
            
            # Get current bucket state - FIX: Handle None/string values properly
            bucket_data = self.redis.hmget(key, 'tokens', 'last_refill')

            # FIX: Proper handling of None/empty values from Redis
            try:
                tokens = float(bucket_data[0]) if bucket_data[0] is not None else float(burst_size)
            except (ValueError, TypeError):
                tokens = float(burst_size)

            try:
                last_refill = float(bucket_data[1]) if bucket_data[1] is not None else current_time
            except (ValueError, TypeError):
                last_refill = current_time
            
            # Calculate tokens to add based on time passed
            time_passed = current_time - last_refill
            tokens_to_add = (time_passed / float(window)) * float(limit)
            # Ensure tokens is float before math operations
            tokens = min(float(burst_size), float(tokens) + tokens_to_add)
            
            # Check if request is allowed, Ensure tokens is float
            is_allowed = float(tokens) >= 1.0
            
            if is_allowed:
                tokens = float(tokens) - 1.0
            
            # Update bucket state
            pipe = self.redis.pipeline()
            pipe.hset(key, mapping={
                'tokens': f"{tokens:.6f}",  # Store with precision
                'last_refill': f"{current_time:.6f}"
            })
            pipe.expire(key, int(window * 2))  # Keep bucket alive longer than window
            pipe.execute()
            
            metadata = {
                'remaining': int(tokens),
                'reset_time': int(current_time + window),
                'burst_available': int(tokens),
                'algorithm': 'token_bucket'
            }
            
            logger.debug(f"Token bucket check for {key}: allowed={is_allowed}, tokens={tokens:.2f}")
            return is_allowed, metadata
            
        except Exception as e:
            logger.error(f"Redis token bucket error for {key}: {e}")
            raise RateLimitBackendError(f"Token bucket check failed: {str(e)}")
    
    def fixed_window_check(self, key: str, limit: int, window: int) -> Tuple[bool, Dict[str, int]]:
        """
        Fixed window rate limiting algorithm.
        Simple and efficient - use for high-throughput endpoints.
        
        Args:
            key: Rate limit key
            limit: Requests allowed per window
            window: Window size in seconds
            
        Returns:
            Tuple of (is_allowed, metadata)
        """
        try:
            if not self.is_connected():
                logger.warning("Redis not connected, allowing request")
                return True, {'remaining': limit, 'reset_time': int(time.time()) + window}
            
            current_time = int(time.time())
            window_key = f"{key}:{current_time // window}"
            
            # Increment counter atomically
            pipe = self.redis.pipeline()
            pipe.incr(window_key)
            pipe.expire(window_key, window + 1)
            results = pipe.execute()
            
            current_count = results[0]
            is_allowed = current_count <= limit
            remaining = max(0, limit - current_count)
            reset_time = ((current_time // window) + 1) * window
            
            metadata = {
                'remaining': remaining,
                'reset_time': reset_time,
                'current_count': current_count,
                'algorithm': 'fixed_window'
            }
            
            logger.debug(f"Fixed window check for {key}: allowed={is_allowed}, count={current_count}/{limit}")
            return is_allowed, metadata
            
        except Exception as e:
            logger.error(f"Redis fixed window error for {key}: {e}")
            raise RateLimitBackendError(f"Fixed window check failed: {str(e)}")
    
    def get_current_usage(self, key: str, algorithm: str = 'fixed_window', window: int = 3600) -> Dict[str, int]:
        """
        Get current usage statistics for a rate limit key.
        
        Args:
            key: Rate limit key
            algorithm: Algorithm used ('sliding_window', 'token_bucket', 'fixed_window')
            window: Window size in seconds
            
        Returns:
            Dictionary with usage statistics
        """
        try:
            if not self.is_connected():
                return {'current_count': 0, 'algorithm': algorithm}
            
            if algorithm == 'sliding_window':
                current_time = time.time()
                window_start = current_time - window
                count = self.redis.zcount(key, window_start, current_time)
                return {'current_count': count, 'algorithm': algorithm}
            
            elif algorithm == 'token_bucket':
                bucket_data = self.redis.hmget(key, 'tokens')
                tokens = float(bucket_data[0] or 0)
                return {'remaining_tokens': int(tokens), 'algorithm': algorithm}
            
            elif algorithm == 'fixed_window':
                current_time = int(time.time())
                window_key = f"{key}:{current_time // window}"
                count = int(self.redis.get(window_key) or 0)
                return {'current_count': count, 'algorithm': algorithm}
            
            else:
                return {'error': f'Unknown algorithm: {algorithm}'}
                
        except Exception as e:
            logger.error(f"Redis usage check error for {key}: {e}")
            return {'error': str(e), 'algorithm': algorithm}
    
    def reset_limit(self, key: str, algorithm: str = 'fixed_window') -> bool:
        """
        Reset/clear a rate limit key.
        Useful for testing or administrative purposes.
        
        Args:
            key: Rate limit key to reset
            algorithm: Algorithm type for proper cleanup
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if not self.is_connected():
                return False
            
            if algorithm == 'fixed_window':
                # Delete all window keys for this limit
                pattern = f"{key}:*"
                keys = self.redis.keys(pattern)
                if keys:
                    self.redis.delete(*keys)
            else:
                # For sliding window and token bucket, just delete the key
                self.redis.delete(key)
            
            logger.info(f"Reset rate limit for key: {key} (algorithm: {algorithm})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to reset rate limit for {key}: {e}")
            return False


# Global backend instance
rate_limit_backend = RedisRateLimitBackend()