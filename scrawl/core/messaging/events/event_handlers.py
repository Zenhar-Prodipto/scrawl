"""
Event handlers for Scrawl application.
Centralizes all event processing logic with proper error handling and monitoring.
"""
import logging
from typing import Dict, Any, Optional, Callable
from django.db import DatabaseError

logger = logging.getLogger(__name__)

class EventHandlerRegistry:
    """
    Registry for all event handlers in the Scrawl application.
    Provides centralized event processing with error handling and metrics.
    """
    
    def __init__(self):
        """Initialize the event handler registry."""
        self.handler_stats = {}
        self.error_counts = {}
        
        # Import services here to avoid circular imports
        self._feed_service = None
        self._cache_invalidation = None
        
        logger.info("EventHandlerRegistry initialized")
    
    @property
    def feed_service(self):
        """Lazy load FeedService to avoid circular imports."""
        if self._feed_service is None:
            try:
                from feed.services import FeedService
                self._feed_service = FeedService
            except ImportError as e:
                logger.error(f"Failed to import FeedService: {e}")
                raise
        return self._feed_service
    
    @property
    def cache_invalidation(self):
        """Lazy load cache invalidation utilities."""
        if self._cache_invalidation is None:
            try:
                from scrawl.core.caching import invalidate
                self._cache_invalidation = invalidate
            except ImportError as e:
                logger.error(f"Failed to import cache invalidation: {e}")
                raise
        return self._cache_invalidation
    
    def _track_handler_call(self, handler_name: str, success: bool):
        """Track handler statistics."""
        if handler_name not in self.handler_stats:
            self.handler_stats[handler_name] = {'calls': 0, 'successes': 0, 'errors': 0}
        
        self.handler_stats[handler_name]['calls'] += 1
        if success:
            self.handler_stats[handler_name]['successes'] += 1
        else:
            self.handler_stats[handler_name]['errors'] += 1
            
            # Track specific error counts
            if handler_name not in self.error_counts:
                self.error_counts[handler_name] = 0
            self.error_counts[handler_name] += 1
    
    def _safe_execute(self, handler_name: str, handler_func: Callable, *args, **kwargs) -> bool:
        """
        Safely execute a handler function with error tracking.
        
        Args:
            handler_name: Name of the handler for tracking
            handler_func: Function to execute
            *args, **kwargs: Arguments to pass to the function
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            result = handler_func(*args, **kwargs)
            self._track_handler_call(handler_name, True)
            logger.debug(f"Handler {handler_name} executed successfully")
            return result if isinstance(result, bool) else True
            
        except DatabaseError as e:
            logger.error(f"Database error in {handler_name}: {e}")
            self._track_handler_call(handler_name, False)
            return False
            
        except Exception as e:
            logger.error(f"Error in {handler_name}: {e}")
            self._track_handler_call(handler_name, False)
            return False
    
    # Follow Event Handlers
    def handle_follow_created(self, follower_id: int, followed_id: int) -> bool:
        """
        Handle follow.created event - invalidate follower's feed cache.
        
        Args:
            follower_id: ID of the user who followed
            followed_id: ID of the user being followed
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the follower's feed since they now follow someone new
            self.feed_service.invalidate_user_feed(follower_id)
            
            # Also invalidate follow relationship cache
            self.cache_invalidation.invalidate_follow_relationship_cache(follower_id, followed_id)
            
            logger.info(f"Invalidated feed for user {follower_id} after following {followed_id}")
            return True
        
        return self._safe_execute('handle_follow_created', _execute)
    
    def handle_follow_deleted(self, follower_id: int, followed_id: int) -> bool:
        """
        Handle follow.deleted event - invalidate follower's feed cache.
        
        Args:
            follower_id: ID of the user who unfollowed
            followed_id: ID of the user being unfollowed
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the follower's feed since their following list changed
            self.feed_service.invalidate_user_feed(follower_id)
            
            # invalidate follow relationship cache
            self.cache_invalidation.invalidate_follow_relationship_cache(follower_id, followed_id)
            
            logger.info(f"Invalidated feed for user {follower_id} after unfollowing {followed_id}")
            return True
        
        return self._safe_execute('handle_follow_deleted', _execute)
    
    # Post Event Handlers
    def handle_post_created(self, user_id: int, post_id: int, privacy: str = 'public') -> bool:
        """
        Handle post.created event - invalidate followers' feeds.
        
        Args:
            user_id: ID of the user who created the post
            post_id: ID of the created post
            privacy: Privacy setting of the post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate feeds of all followers since there's new content
            self.feed_service.invalidate_follower_feeds(user_id)
            
            # Invalidate post-related caches
            self.cache_invalidation.invalidate_post_cache(post_id=post_id, user_id=user_id)
            
            logger.info(f"Invalidated follower feeds for new post {post_id} by user {user_id}")
            return True
        
        return self._safe_execute('handle_post_created', _execute)
    
    def handle_post_updated(self, user_id: int, post_id: int, privacy: str = 'public') -> bool:
        """
        Handle post.updated event - invalidate followers' feeds.
        
        Args:
            user_id: ID of the user who updated the post
            post_id: ID of the updated post
            privacy: Privacy setting of the post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate feeds of all followers since content changed
            self.feed_service.invalidate_follower_feeds(user_id)
            
            # Invalidate post-related caches
            self.cache_invalidation.invalidate_post_cache(post_id=post_id, user_id=user_id)
            
            logger.info(f"Invalidated follower feeds for updated post {post_id} by user {user_id}")
            return True
        
        return self._safe_execute('handle_post_updated', _execute)
    
    def handle_post_deleted(self, user_id: int, post_id: int) -> bool:
        """
        Handle post.deleted event - invalidate followers' feeds.
        
        Args:
            user_id: ID of the user who deleted the post
            post_id: ID of the deleted post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate feeds of all followers since content was removed
            self.feed_service.invalidate_follower_feeds(user_id)
            
            # Invalidate post-related caches
            self.cache_invalidation.invalidate_post_cache(post_id=post_id, user_id=user_id)
            
            logger.info(f"Invalidated follower feeds for deleted post {post_id} by user {user_id}")
            return True
        
        return self._safe_execute('handle_post_deleted', _execute)
    
    # Interaction Event Handlers
    def handle_like_created(self, user_id: int, post_id: int) -> bool:
        """
        Handle like.created event - invalidate user's feed for interaction tracking.
        
        Args:
            user_id: ID of the user who liked the post
            post_id: ID of the liked post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            # This affects the "interaction" tier of the feed algorithm
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='like'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after liking post {post_id}")
            return True
        
        return self._safe_execute('handle_like_created', _execute)
    
    def handle_like_deleted(self, user_id: int, post_id: int) -> bool:
        """
        Handle like.deleted event - invalidate user's feed.
        
        Args:
            user_id: ID of the user who unliked the post
            post_id: ID of the unliked post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='like'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after unliking post {post_id}")
            return True
        
        return self._safe_execute('handle_like_deleted', _execute)
    
    def handle_comment_created(self, user_id: int, post_id: int, comment_id: int) -> bool:
        """
        Handle comment.created event - invalidate user's feed for interaction tracking.
        
        Args:
            user_id: ID of the user who commented
            post_id: ID of the commented post
            comment_id: ID of the comment
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='comment'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after commenting on post {post_id}")
            return True
        
        return self._safe_execute('handle_comment_created', _execute)
    
    def handle_comment_updated(self, user_id: int, post_id: int, comment_id: int) -> bool:
        """
        Handle comment.updated event - minimal cache invalidation.
        
        Args:
            user_id: ID of the user who updated the comment
            post_id: ID of the post
            comment_id: ID of the comment
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Only invalidate interaction caches, no need to invalidate feed
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='comment'
            )
            
            logger.info(f"Invalidated comment cache for user {user_id} on post {post_id}")
            return True
        
        return self._safe_execute('handle_comment_updated', _execute)
    
    def handle_comment_deleted(self, user_id: int, post_id: int, comment_id: int) -> bool:
        """
        Handle comment.deleted event - invalidate user's feed.
        
        Args:
            user_id: ID of the user who deleted the comment
            post_id: ID of the post
            comment_id: ID of the deleted comment
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='comment'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after deleting comment on post {post_id}")
            return True
        
        return self._safe_execute('handle_comment_deleted', _execute)
    
    def handle_save_created(self, user_id: int, post_id: int) -> bool:
        """
        Handle save.created event - invalidate user's feed for interaction tracking.
        
        Args:
            user_id: ID of the user who saved the post
            post_id: ID of the saved post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='save'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after saving post {post_id}")
            return True
        
        return self._safe_execute('handle_save_created', _execute)
    
    def handle_save_deleted(self, user_id: int, post_id: int) -> bool:
        """
        Handle save.deleted event - invalidate user's feed.
        
        Args:
            user_id: ID of the user who unsaved the post
            post_id: ID of the unsaved post
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # Invalidate the user's feed since their interactions changed
            self.feed_service.invalidate_user_feed(user_id)
            
            # Invalidate interaction caches
            self.cache_invalidation.invalidate_interaction_cache(
                user_id=user_id, 
                post_id=post_id, 
                interaction_type='save'
            )
            
            logger.info(f"Invalidated feed for user {user_id} after unsaving post {post_id}")
            return True
        
        return self._safe_execute('handle_save_deleted', _execute)
    
    # System Event Handlers
    def handle_user_profile_updated(self, user_id: int, changed_fields: list) -> bool:
        """
        Handle user.profile.updated event - invalidate relevant caches.
        
        Args:
            user_id: ID of the user who updated their profile
            changed_fields: List of fields that were changed
            
        Returns:
            bool: True if handled successfully
        """
        def _execute():
            # If interests changed, invalidate feed
            if 'interests' in changed_fields:
                self.feed_service.invalidate_user_feed(user_id)
                logger.info(f"Invalidated feed for user {user_id} due to interest changes")
            
            # If profile_type changed, invalidate followers' feeds
            if 'profile_type' in changed_fields:
                self.feed_service.invalidate_follower_feeds(user_id)
                logger.info(f"Invalidated follower feeds for user {user_id} due to privacy changes")
            
            # Always invalidate user profile caches
            logger.info(f"Handled profile update for user {user_id}: {changed_fields}")
            return True
        
        return self._safe_execute('handle_user_profile_updated', _execute)
    
    # Utility Methods
    def get_handler_stats(self) -> Dict[str, Any]:
        """Get statistics for all event handlers."""
        return {
            'handler_statistics': self.handler_stats,
            'error_counts': self.error_counts,
            'total_handlers': len(self.handler_stats),
            'total_calls': sum(stats['calls'] for stats in self.handler_stats.values()),
            'total_errors': sum(stats['errors'] for stats in self.handler_stats.values()),
        }
    
    def reset_stats(self):
        """Reset handler statistics."""
        self.handler_stats.clear()
        self.error_counts.clear()
        logger.info("Handler statistics reset")
    
    def get_error_summary(self) -> Dict[str, Any]:
        """Get summary of errors by handler."""
        error_summary = {}
        for handler_name, stats in self.handler_stats.items():
            if stats['errors'] > 0:
                error_rate = stats['errors'] / stats['calls'] if stats['calls'] > 0 else 0
                error_summary[handler_name] = {
                    'total_errors': stats['errors'],
                    'total_calls': stats['calls'],
                    'error_rate': error_rate
                }
        return error_summary

# Global instance for easy access
event_handler_registry = EventHandlerRegistry()