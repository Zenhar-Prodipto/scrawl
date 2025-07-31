"""
Feed event consumer for Scrawl application.
Processes events related to feed cache invalidation and user feed updates.
"""
import json
import logging
import os
import sys
import django
from typing import Dict, Any, Optional
from confluent_kafka import Message
from ...monitoring.metrics.collectors import record_kafka_consume


# Django setup for standalone consumer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrawl.settings')
django.setup()


try:
    from .base_consumer import BaseConsumer, HealthMonitorMixin
    from ..events.event_handlers import EventHandlerRegistry
except ImportError:
    # Fallback for direct execution
    from base_consumer import BaseConsumer, HealthMonitorMixin
    from scrawl.core.messaging.events.event_handlers import EventHandlerRegistry

logger = logging.getLogger(__name__)


class FeedEventConsumer(HealthMonitorMixin, BaseConsumer):
    """
    Specialized consumer for processing feed-related events.
    Handles cache invalidation and feed updates based on user actions.
    """
    
    def __init__(self, group_id: str = 'feed-consumer-group', 
                 consumer_config: Optional[Dict[str, Any]] = None):
        """
        Initialize feed event consumer.
        
        Args:
            group_id: Consumer group ID
            consumer_config: Optional consumer configuration overrides
        """
        # Topics this consumer processes
        topics = ['follow.events', 'post.events', 'like.events', 'comment.events']
        
        # Default consumer configuration for feed processor
        default_config = {
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,
            'session.timeout.ms': 10000,
            'max.poll.interval.ms': 300000,
            'fetch.min.bytes': 1,
            'fetch.wait.max.ms': 500,
        }
        
        if consumer_config:
            default_config.update(consumer_config)
        
        super().__init__(group_id, topics, default_config)
        
        # Initialize event handler registry
        self.event_handlers = EventHandlerRegistry()
        
        # Performance metrics
        self.processed_by_type = {}
        self.processing_times = {}
        
        logger.info("FeedEventConsumer initialized successfully")
    
    def process_message(self, message: Message) -> bool:
        """
        Process a single feed-related event message.
        
        Args:
            message: Kafka message containing event data
            
        Returns:
            bool: True if processing successful, False otherwise
        """
        try:
            # Parse message payload
            payload = json.loads(message.value().decode('utf-8'))
            event_type = payload.get('event_type')
            event_data = payload.get('data', {})
            
            if not event_type:
                logger.warning("Message missing event_type field")
                return False
            
            # Track processing metrics
            self._track_event_processing(event_type)
            
            logger.debug(f"Processing {event_type} event: {event_data}")
            
            # Route to appropriate handler
            success = self._route_event_to_handler(event_type, event_data, payload)
            
            if success:
                logger.debug(f"Successfully processed {event_type} event")
                record_kafka_consume(message.topic(), event_type, True)
            else:
                logger.warning(f"Failed to process {event_type} event")
                record_kafka_consume(message.topic(), event_type, False)
            
            return success
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False
    
    def _route_event_to_handler(self, event_type: str, event_data: Dict[str, Any], 
                               full_payload: Dict[str, Any]) -> bool:
        """
        Route event to appropriate handler based on event type.
        
        Args:
            event_type: Type of event to process
            event_data: Event data payload
            full_payload: Full message payload for context
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            # Map event types to handler methods
            handler_map = {
                # Follow events
                'follow.created': self._handle_follow_created,
                'follow.deleted': self._handle_follow_deleted,
                'follow.request.accepted': self._handle_follow_request_accepted,
                
                # Post events
                'post.created': self._handle_post_created,
                'post.updated': self._handle_post_updated,
                'post.deleted': self._handle_post_deleted,
                
                # Like events  
                'like.created': self._handle_like_created,
                'like.deleted': self._handle_like_deleted,
                
                # Comment events
                'comment.created': self._handle_comment_created,
                'comment.updated': self._handle_comment_updated,
                'comment.deleted': self._handle_comment_deleted,
                
                # Save events
                'save.created': self._handle_save_created,
                'save.deleted': self._handle_save_deleted,
            }
            
            handler = handler_map.get(event_type)
            if not handler:
                logger.warning(f"No handler found for event type: {event_type}")
                return True  # Return True to acknowledge unknown events
            
            return handler(event_data, full_payload)
            
        except Exception as e:
            logger.error(f"Error routing event {event_type}: {e}")
            return False
    
    def _handle_follow_created(self, event_data: Dict[str, Any], 
                              full_payload: Dict[str, Any]) -> bool:
        """Handle follow.created event - invalidate follower's feed."""
        try:
            follower_id = event_data.get('follower_id')
            followed_id = event_data.get('followed_id')
            
            if not all([follower_id, followed_id]):
                logger.warning(f"Missing required fields in follow.created event: {event_data}")
                return False
            
            # Use event handler registry
            return self.event_handlers.handle_follow_created(follower_id, followed_id)
            
        except Exception as e:
            logger.error(f"Error handling follow.created event: {e}")
            return False
    
    def _handle_follow_deleted(self, event_data: Dict[str, Any], 
                              full_payload: Dict[str, Any]) -> bool:
        """Handle follow.deleted event - invalidate follower's feed."""
        try:
            follower_id = event_data.get('follower_id')
            followed_id = event_data.get('followed_id')
            
            if not all([follower_id, followed_id]):
                logger.warning(f"Missing required fields in follow.deleted event: {event_data}")
                return False
            
            return self.event_handlers.handle_follow_deleted(follower_id, followed_id)
            
        except Exception as e:
            logger.error(f"Error handling follow.deleted event: {e}")
            return False
    
    def _handle_follow_request_accepted(self, event_data: Dict[str, Any], 
                                       full_payload: Dict[str, Any]) -> bool:
        """Handle follow.request.accepted event - same as follow created."""
        try:
            requester_id = event_data.get('requester_id')
            target_id = event_data.get('target_id')
            
            if not all([requester_id, target_id]):
                logger.warning(f"Missing required fields in follow.request.accepted event: {event_data}")
                return False
            
            # Treat accepted request same as follow created
            return self.event_handlers.handle_follow_created(requester_id, target_id)
            
        except Exception as e:
            logger.error(f"Error handling follow.request.accepted event: {e}")
            return False
    
    def _handle_post_created(self, event_data: Dict[str, Any], 
                            full_payload: Dict[str, Any]) -> bool:
        """Handle post.created event - invalidate followers' feeds."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            privacy = event_data.get('privacy', 'public')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in post.created event: {event_data}")
                return False
            
            return self.event_handlers.handle_post_created(user_id, post_id, privacy)
            
        except Exception as e:
            logger.error(f"Error handling post.created event: {e}")
            return False
    
    def _handle_post_updated(self, event_data: Dict[str, Any], 
                            full_payload: Dict[str, Any]) -> bool:
        """Handle post.updated event - invalidate followers' feeds."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            privacy = event_data.get('privacy', 'public')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in post.updated event: {event_data}")
                return False
            
            return self.event_handlers.handle_post_updated(user_id, post_id, privacy)
            
        except Exception as e:
            logger.error(f"Error handling post.updated event: {e}")
            return False
    
    def _handle_post_deleted(self, event_data: Dict[str, Any], 
                            full_payload: Dict[str, Any]) -> bool:
        """Handle post.deleted event - invalidate followers' feeds."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in post.deleted event: {event_data}")
                return False
            
            return self.event_handlers.handle_post_deleted(user_id, post_id)
            
        except Exception as e:
            logger.error(f"Error handling post.deleted event: {e}")
            return False
    
    def _handle_like_created(self, event_data: Dict[str, Any], 
                           full_payload: Dict[str, Any]) -> bool:
        """Handle like.created event - invalidate user's feed for interaction tracking."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in like.created event: {event_data}")
                return False
            
            return self.event_handlers.handle_like_created(user_id, post_id)
            
        except Exception as e:
            logger.error(f"Error handling like.created event: {e}")
            return False
    
    def _handle_like_deleted(self, event_data: Dict[str, Any], 
                           full_payload: Dict[str, Any]) -> bool:
        """Handle like.deleted event - invalidate user's feed."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in like.deleted event: {event_data}")
                return False
            
            return self.event_handlers.handle_like_deleted(user_id, post_id)
            
        except Exception as e:
            logger.error(f"Error handling like.deleted event: {e}")
            return False
    
    def _handle_comment_created(self, event_data: Dict[str, Any], 
                               full_payload: Dict[str, Any]) -> bool:
        """Handle comment.created event - invalidate user's feed for interaction tracking."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            comment_id = event_data.get('comment_id')
            
            if not all([user_id, post_id, comment_id]):
                logger.warning(f"Missing required fields in comment.created event: {event_data}")
                return False
            
            return self.event_handlers.handle_comment_created(user_id, post_id, comment_id)
            
        except Exception as e:
            logger.error(f"Error handling comment.created event: {e}")
            return False
    
    def _handle_comment_updated(self, event_data: Dict[str, Any], 
                               full_payload: Dict[str, Any]) -> bool:
        """Handle comment.updated event."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            comment_id = event_data.get('comment_id')
            
            if not all([user_id, post_id, comment_id]):
                logger.warning(f"Missing required fields in comment.updated event: {event_data}")
                return False
            
            return self.event_handlers.handle_comment_updated(user_id, post_id, comment_id)
            
        except Exception as e:
            logger.error(f"Error handling comment.updated event: {e}")
            return False
    
    def _handle_comment_deleted(self, event_data: Dict[str, Any], 
                               full_payload: Dict[str, Any]) -> bool:
        """Handle comment.deleted event."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            comment_id = event_data.get('comment_id')
            
            if not all([user_id, post_id, comment_id]):
                logger.warning(f"Missing required fields in comment.deleted event: {event_data}")
                return False
            
            return self.event_handlers.handle_comment_deleted(user_id, post_id, comment_id)
            
        except Exception as e:
            logger.error(f"Error handling comment.deleted event: {e}")
            return False
    
    def _handle_save_created(self, event_data: Dict[str, Any], 
                            full_payload: Dict[str, Any]) -> bool:
        """Handle save.created event - invalidate user's feed for interaction tracking."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in save.created event: {event_data}")
                return False
            
            return self.event_handlers.handle_save_created(user_id, post_id)
            
        except Exception as e:
            logger.error(f"Error handling save.created event: {e}")
            return False
    
    def _handle_save_deleted(self, event_data: Dict[str, Any], 
                            full_payload: Dict[str, Any]) -> bool:
        """Handle save.deleted event - invalidate user's feed."""
        try:
            user_id = event_data.get('user_id')
            post_id = event_data.get('post_id')
            
            if not all([user_id, post_id]):
                logger.warning(f"Missing required fields in save.deleted event: {event_data}")
                return False
            
            return self.event_handlers.handle_save_deleted(user_id, post_id)
            
        except Exception as e:
            logger.error(f"Error handling save.deleted event: {e}")
            return False
    
    def _track_event_processing(self, event_type: str):
        """Track event processing metrics."""
        import time
        
        if event_type not in self.processed_by_type:
            self.processed_by_type[event_type] = 0
            self.processing_times[event_type] = []
        
        self.processed_by_type[event_type] += 1
        self.processing_times[event_type].append(time.time())
        
        # Keep only last 100 timestamps for memory efficiency
        if len(self.processing_times[event_type]) > 100:
            self.processing_times[event_type] = self.processing_times[event_type][-100:]
    
    def get_processing_stats(self) -> Dict[str, Any]:
        """Get detailed processing statistics."""
        base_stats = self.get_stats()
        
        # Add event-specific statistics
        event_stats = {}
        for event_type, count in self.processed_by_type.items():
            recent_times = self.processing_times.get(event_type, [])
            if recent_times:
                current_time = time.time()
                recent_count = len([t for t in recent_times if current_time - t < 300])  # Last 5 minutes
                rate_per_minute = recent_count / 5 if recent_count > 0 else 0
            else:
                rate_per_minute = 0
            
            event_stats[event_type] = {
                'total_processed': count,
                'rate_per_minute': rate_per_minute
            }
        
        base_stats.update({
            'event_statistics': event_stats,
            'total_event_types': len(self.processed_by_type),
            'consumer_type': 'FeedEventConsumer'
        })
        
        return base_stats

def main():
    """Main entry point for running the FeedEventConsumer."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/app/logs/feed_consumer.log') 
            if os.path.exists('/app/logs') else logging.StreamHandler()
        ]
    )
    
    logger.info("Starting Scrawl Feed Event Consumer")
    
    try:
        # Create and start the consumer
        consumer = FeedEventConsumer()
        
        # Add custom shutdown handler for cleanup
        def cleanup_handler():
            logger.info("Performing feed consumer cleanup...")
            # Add any custom cleanup logic here
        
        consumer.add_shutdown_handler(cleanup_handler)
        
        # Start consuming messages
        consumer.start()
        
    except KeyboardInterrupt:
        logger.info("Feed consumer interrupted by user")
    except Exception as e:
        logger.error(f"Feed consumer failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    import os
    import django
    
    # Django setup
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrawl.settings')
    django.setup()
    
    main()