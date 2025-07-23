"""
Centralized event publishing for Scrawl application.
Replaces scattered producer.produce() calls with a clean, centralized interface.
"""
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from ..kafka.kafka_client import kafka_manager
from ..kafka.kafka_config import kafka_config

logger = logging.getLogger(__name__)

class EventPublisher:
    """Centralized event publisher for all Kafka events."""
    
    def __init__(self):
        self.producer = kafka_manager.producer
        self.kafka_config = kafka_config
    
    def _create_event_payload(self, event_type: str, data: Dict[str, Any], 
                             metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create standardized event payload.
        
        Args:
            event_type: Type of event (e.g., 'follow.created')
            data: Event-specific data
            metadata: Optional metadata
            
        Returns:
            Standardized event payload
        """
        payload = {
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'service': 'scrawl',
            'version': '1.0',
            'data': data
        }
        
        if metadata:
            payload['metadata'] = metadata
            
        return payload
    
    def _publish_to_topic(self, topic_name: str, payload: Dict[str, Any], 
                         key: Optional[str] = None, callback_type: str = 'default',
                         async_publish: bool = True) -> bool:
        """
        Publish event to specific Kafka topic.
        
        Args:
            topic_name: Kafka topic name
            payload: Event payload
            key: Optional message key for partitioning
            callback_type: Type of delivery callback ('default' or 'critical')
            async_publish: Whether to publish asynchronously
            
        Returns:
            bool: True if successfully queued, False otherwise
        """
        try:
            if not kafka_manager.is_connected():
                logger.error("Kafka not connected, cannot publish event")
                return False
            
            # Serialize payload
            message_value = json.dumps(payload).encode('utf-8')
            message_key = key.encode('utf-8') if key else None
            
            # Get appropriate callback
            callback = self.kafka_config.get_delivery_callback(callback_type)
            
            # Publish to Kafka
            self.producer.produce(
                topic=topic_name,
                value=message_value,
                key=message_key,
                callback=callback
            )
            
            # Handle synchronous vs asynchronous publishing
            if not async_publish:
                remaining = kafka_manager.flush_producer(timeout=10.0)
                if remaining > 0:
                    logger.warning(f"Failed to flush all messages, {remaining} pending")
                    return False
            
            logger.debug(f"Published {payload['event_type']} event to {topic_name}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to publish event to {topic_name}: {e}")
            return False
    
    def publish_follow_event(self, event_type_key: str, follower_id: int, followed_id: int,
                           is_super_follower: bool = False, async_publish: bool = True,
                           **extra_data) -> bool:
        """
        Publish follow-related events.
        
        Args:
            event_type_key: Event type key (e.g., 'follow_created')
            follower_id: ID of the follower
            followed_id: ID of the followed user
            is_super_follower: Whether this is a super follower relationship
            async_publish: Whether to publish asynchronously
            **extra_data: Additional event data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            event_type = self.kafka_config.get_event_type(event_type_key)
            topic_name = self.kafka_config.get_topic_name('follow_events')
            
            data = {
                'follower_id': follower_id,
                'followed_id': followed_id,
                'is_super_follower': is_super_follower,
                **extra_data
            }
            
            payload = self._create_event_payload(event_type, data)
            
            # Use follower_id as partition key for ordering
            return self._publish_to_topic(
                topic_name, payload, 
                key=str(follower_id),
                async_publish=async_publish
            )
            
        except Exception as e:
            logger.error(f"Failed to publish follow event {event_type_key}: {e}")
            return False
    
    def publish_post_event(self, event_type_key: str, post_id: int, user_id: int,
                          privacy: str = 'public', async_publish: bool = True,
                          **extra_data) -> bool:
        """
        Publish post-related events.
        
        Args:
            event_type_key: Event type key (e.g., 'post_created')
            post_id: ID of the post
            user_id: ID of the post owner
            privacy: Post privacy setting
            async_publish: Whether to publish asynchronously
            **extra_data: Additional event data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            event_type = self.kafka_config.get_event_type(event_type_key)
            topic_name = self.kafka_config.get_topic_name('post_events')
            
            data = {
                'post_id': post_id,
                'user_id': user_id,
                'privacy': privacy,
                **extra_data
            }
            
            payload = self._create_event_payload(event_type, data)
            
            # Use user_id as partition key for ordering
            return self._publish_to_topic(
                topic_name, payload,
                key=str(user_id),
                callback_type='critical',  # Posts are critical events
                async_publish=async_publish
            )
            
        except Exception as e:
            logger.error(f"Failed to publish post event {event_type_key}: {e}")
            return False
    
    def publish_like_event(self, event_type_key: str, user_id: int, post_id: int,
                          async_publish: bool = True, **extra_data) -> bool:
        """
        Publish like-related events.
        
        Args:
            event_type_key: Event type key (e.g., 'like_created')
            user_id: ID of the user who liked/unliked
            post_id: ID of the post
            async_publish: Whether to publish asynchronously
            **extra_data: Additional event data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            event_type = self.kafka_config.get_event_type(event_type_key)
            topic_name = self.kafka_config.get_topic_name('like_events')
            
            data = {
                'user_id': user_id,
                'post_id': post_id,
                **extra_data
            }
            
            payload = self._create_event_payload(event_type, data)
            
            # Use user_id as partition key
            return self._publish_to_topic(
                topic_name, payload,
                key=str(user_id),
                async_publish=async_publish
            )
            
        except Exception as e:
            logger.error(f"Failed to publish like event {event_type_key}: {e}")
            return False
    
    def publish_comment_event(self, event_type_key: str, user_id: int, post_id: int,
                             comment_id: int, async_publish: bool = True,
                             **extra_data) -> bool:
        """
        Publish comment-related events.
        
        Args:
            event_type_key: Event type key (e.g., 'comment_created')
            user_id: ID of the commenter
            post_id: ID of the post
            comment_id: ID of the comment
            async_publish: Whether to publish asynchronously
            **extra_data: Additional event data
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            event_type = self.kafka_config.get_event_type(event_type_key)
            topic_name = self.kafka_config.get_topic_name('comment_events')
            
            data = {
                'user_id': user_id,
                'post_id': post_id,
                'comment_id': comment_id,
                **extra_data
            }
            
            payload = self._create_event_payload(event_type, data)
            
            # Use user_id as partition key
            return self._publish_to_topic(
                topic_name, payload,
                key=str(user_id),
                async_publish=async_publish
            )
            
        except Exception as e:
            logger.error(f"Failed to publish comment event {event_type_key}: {e}")
            return False
    
    def publish_custom_event(self, topic_key: str, event_type_key: str, data: Dict[str, Any],
                           key: Optional[str] = None, callback_type: str = 'default',
                           async_publish: bool = True) -> bool:
        """
        Publish custom event to any topic.
        
        Args:
            topic_key: Topic key from kafka_config
            event_type_key: Event type key from kafka_config
            data: Event data
            key: Optional message key
            callback_type: Delivery callback type
            async_publish: Whether to publish asynchronously
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            topic_name = self.kafka_config.get_topic_name(topic_key)
            event_type = self.kafka_config.get_event_type(event_type_key)
            
            payload = self._create_event_payload(event_type, data)
            
            return self._publish_to_topic(
                topic_name, payload,
                key=key,
                callback_type=callback_type,
                async_publish=async_publish
            )
            
        except Exception as e:
            logger.error(f"Failed to publish custom event {event_type_key} to {topic_key}: {e}")
            return False
    
    def flush_all(self, timeout: float = 30.0) -> bool:
        """
        Flush all pending messages.
        
        Args:
            timeout: Maximum time to wait for flush
            
        Returns:
            bool: True if all messages flushed, False otherwise
        """
        try:
            remaining = kafka_manager.flush_producer(timeout)
            return remaining == 0
        except Exception as e:
            logger.error(f"Failed to flush producer: {e}")
            return False

# Global event publisher instance
event_publisher = EventPublisher()