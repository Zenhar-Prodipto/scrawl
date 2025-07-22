"""
Cache invalidation strategies for Scrawl application.
Provides smart cache clearing patterns for different business operations.
"""
import logging
from typing import List, Dict, Any
from ..managers.cache_manager import cache_manager

logger = logging.getLogger(__name__)

class CacheInvalidationStrategy:
    """Smart cache invalidation patterns for different business operations."""
    
    @staticmethod
    def invalidate_user_profile_cache(user_id: int) -> None:
        """
        Invalidate all cache entries related to a user's profile changes.
        
        Called when: User updates profile, bio, privacy settings, etc.
        """
        try:
            patterns_to_clear = [
                f"user:profile:{user_id}",
                f"user:*:{user_id}",  # All user-related caches
            ]
            
            total_deleted = 0
            for pattern in patterns_to_clear:
                deleted = cache_manager.delete_pattern(pattern)
                total_deleted += deleted
            
            logger.info(f"Invalidated user profile cache for user {user_id}: {total_deleted} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate user profile cache for user {user_id}: {e}")
    
    @staticmethod
    def invalidate_follow_relationship_cache(follower_id: int, followed_id: int) -> None:
        """
        Invalidate cache entries when follow relationships change.
        
        Called when: User follows/unfollows, follow request accepted/denied.
        """
        try:
            # Specific keys to invalidate
            cache_keys = [
                ('follow_status', {'user_id': follower_id, 'target_id': followed_id}),
                ('follow_exists', {'follower_id': follower_id, 'followed_id': followed_id}),
                ('super_follower', {'follower_id': follower_id, 'followed_id': followed_id}),
                ('user_following', {'user_id': follower_id}),
                ('user_followers', {'user_id': followed_id}),
                ('user_following_count', {'user_id': follower_id}),
                ('user_follower_count', {'user_id': followed_id}),
            ]
            
            deleted_count = 0
            for key_type, params in cache_keys:
                if cache_manager.delete(key_type, **params):
                    deleted_count += 1
            
            # Pattern-based invalidation for related caches
            patterns = [
                f"follow:*:{follower_id}:*",
                f"follow:*:*:{followed_id}",
                f"feed:user:{follower_id}",  
                f"feed:page:{follower_id}:*",
            ]
            
            for pattern in patterns:
                deleted_count += cache_manager.delete_pattern(pattern)
            
            logger.info(f"Invalidated follow cache for {follower_id}->{followed_id}: {deleted_count} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate follow cache for {follower_id}->{followed_id}: {e}")
    
    @staticmethod
    def invalidate_post_cache(post_id: int, user_id: int) -> None:
        """
        Invalidate cache entries when posts are created, updated, or deleted.
        
        Called when: Post created/updated/deleted, post privacy changed.
        """
        try:
            # Specific post-related keys
            cache_keys = [
                ('post_detail', {'post_id': post_id}),
                ('post_list', {'user_id': user_id}),
                ('post_user_posts', {'user_id': user_id}),
            ]
            
            deleted_count = 0
            for key_type, params in cache_keys:
                if cache_manager.delete(key_type, **params):
                    deleted_count += 1
            
            # Pattern-based invalidation
            patterns = [
                f"interaction:*:*:{post_id}",  # All interactions with this post
                f"feed:*",  # Invalidate all feeds as post might affect many users
            ]
            
            for pattern in patterns:
                deleted_count += cache_manager.delete_pattern(pattern)
            
            logger.info(f"Invalidated post cache for post {post_id}: {deleted_count} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate post cache for post {post_id}: {e}")
    
    @staticmethod
    def invalidate_interaction_cache(user_id: int, post_id: int, interaction_type: str = None) -> None:
        """
        Invalidate cache entries when user interactions change.
        
        Called when: User likes/unlikes, comments, saves/unsaves posts.
        
        Args:
            user_id: ID of the user performing the interaction
            post_id: ID of the post being interacted with
            interaction_type: 'like', 'comment', 'save', or None for all
        """
        try:
            if interaction_type:
                # Invalidate specific interaction type
                cache_keys = [
                    (f'{interaction_type}_exists', {'user_id': user_id, 'post_id': post_id}),
                ]
            else:
                # Invalidate all interaction types
                cache_keys = [
                    ('like_exists', {'user_id': user_id, 'post_id': post_id}),
                    ('comment_exists', {'user_id': user_id, 'post_id': post_id}),
                    ('save_exists', {'user_id': user_id, 'post_id': post_id}),
                ]
            
            deleted_count = 0
            for key_type, params in cache_keys:
                if cache_manager.delete(key_type, **params):
                    deleted_count += 1
            
            # Also invalidate post details (interaction counts might have changed)
            cache_manager.delete('post_detail', post_id=post_id)
            deleted_count += 1
            
            # If it's a save interaction, invalidate saved posts list
            if interaction_type == 'save' or interaction_type is None:
                cache_manager.delete('post_saved', user_id=user_id)
                deleted_count += 1
            
            logger.info(f"Invalidated {interaction_type or 'all'} interaction cache for user {user_id}, post {post_id}: {deleted_count} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate interaction cache for user {user_id}, post {post_id}: {e}")
    
    @staticmethod
    def invalidate_feed_cache(user_id: int) -> None:
        """
        Invalidate user's feed cache.
        
        Called when: User's feed should be refreshed due to new posts, follows, etc.
        """
        try:
            patterns = [
                f"feed:user:{user_id}",
                f"feed:page:{user_id}:*",
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = cache_manager.delete_pattern(pattern)
                total_deleted += deleted
            
            logger.info(f"Invalidated feed cache for user {user_id}: {total_deleted} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate feed cache for user {user_id}: {e}")
    
    @staticmethod
    def invalidate_follower_feeds(user_id: int) -> None:
        """
        Invalidate feed caches for all followers of a user.
        
        Called when: User creates a new post that should appear in followers' feeds.
        """
        try:
            # Note: This is a heavy operation - in production you might want to:
            # 1. Use a background task
            # 2. Invalidate feeds lazily
            # 3. Use more specific cache patterns
            
            # For now, we'll invalidate all feeds (simple but not optimal)
            deleted = cache_manager.delete_pattern("feed:*")
            
            logger.info(f"Invalidated all follower feeds due to new post by user {user_id}: {deleted} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate follower feeds for user {user_id}: {e}")
    
    @staticmethod
    def invalidate_user_session_cache(user_id: int) -> None:
        """
        Invalidate user session-related cache.
        
        Called when: User logs out, password changes, account suspended.
        """
        try:
            patterns = [
                f"session:user:{user_id}",
                f"user:profile:{user_id}", 
            ]
            
            total_deleted = 0
            for pattern in patterns:
                deleted = cache_manager.delete_pattern(pattern)
                total_deleted += deleted
            
            logger.info(f"Invalidated session cache for user {user_id}: {total_deleted} keys deleted")
            
        except Exception as e:
            logger.error(f"Failed to invalidate session cache for user {user_id}: {e}")
    
    @staticmethod
    def bulk_invalidate(invalidation_requests: List[Dict[str, Any]]) -> None:
        """
        Perform bulk cache invalidation for multiple operations.
        
        Args:
            invalidation_requests: List of dicts with 'strategy' and 'params' keys
            
        Example:
            bulk_invalidate([
                {'strategy': 'user_profile', 'params': {'user_id': 1}},
                {'strategy': 'post', 'params': {'post_id': 123, 'user_id': 1}},
            ])
        """
        try:
            strategy_methods = {
                'user_profile': CacheInvalidationStrategy.invalidate_user_profile_cache,
                'follow_relationship': CacheInvalidationStrategy.invalidate_follow_relationship_cache,
                'post': CacheInvalidationStrategy.invalidate_post_cache,
                'interaction': CacheInvalidationStrategy.invalidate_interaction_cache,
                'feed': CacheInvalidationStrategy.invalidate_feed_cache,
                'follower_feeds': CacheInvalidationStrategy.invalidate_follower_feeds,
                'user_session': CacheInvalidationStrategy.invalidate_user_session_cache,
            }
            
            for request in invalidation_requests:
                strategy = request.get('strategy')
                params = request.get('params', {})
                
                if strategy in strategy_methods:
                    strategy_methods[strategy](**params)
                else:
                    logger.warning(f"Unknown invalidation strategy: {strategy}")
            
            logger.info(f"Completed bulk invalidation for {len(invalidation_requests)} operations")
            
        except Exception as e:
            logger.error(f"Failed bulk cache invalidation: {e}")

# Create convenient alias
invalidate = CacheInvalidationStrategy()