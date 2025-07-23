"""
Centralized Kafka configuration for Scrawl application.
Defines topic schemas, configurations, and delivery callbacks.
"""
import logging
from typing import Dict, Any, List, Callable
from confluent_kafka import Message

logger = logging.getLogger(__name__)

class KafkaConfig:
    """Centralized Kafka configuration and topic management."""
    
    # Topic configurations
    TOPICS = {
        'follow_events': {
            'name': 'follow.events',
            'partitions': 3,
            'replication_factor': 1,
            'description': 'Follow and unfollow events'
        },
        'post_events': {
            'name': 'post.events', 
            'partitions': 3,
            'replication_factor': 1,
            'description': 'Post creation, update, and deletion events'
        },
        'like_events': {
            'name': 'like.events',
            'partitions': 3,
            'replication_factor': 1,
            'description': 'Like and unlike events'
        },
        'comment_events': {
            'name': 'comment.events',
            'partitions': 3,
            'replication_factor': 1,
            'description': 'Comment creation, update, and deletion events'
        },
        'feed_events_dlq': {
            'name': 'feed_events_dlq',
            'partitions': 1,
            'replication_factor': 1,
            'description': 'Dead letter queue for failed feed events'
        }
    }
    
    # Consumer group configurations
    CONSUMER_GROUPS = {
        'feed_processor': {
            'group_id': 'feed-consumer-group',
            'topics': ['follow.events', 'post.events', 'like.events'],
            'description': 'Processes events for feed cache invalidation'
        },
        'general_processor': {
            'group_id': 'scrawl-group', 
            'topics': ['follow.events', 'post.events', 'like.events'],
            'description': 'General event processing and logging'
        }
    }
    
    # Event type mappings
    EVENT_TYPES = {
        # Follow events
        'follow_created': 'follow.created',
        'follow_deleted': 'follow.deleted', 
        'follow_request_created': 'follow.request.created',
        'follow_request_accepted': 'follow.request.accepted',
        'follow_request_denied': 'follow.request.denied',
        
        # Post events
        'post_created': 'post.created',
        'post_updated': 'post.updated',
        'post_deleted': 'post.deleted',
        
        # Like events
        'like_created': 'like.created',
        'like_deleted': 'like.deleted',
        
        # Comment events  
        'comment_created': 'comment.created',
        'comment_updated': 'comment.updated',
        'comment_deleted': 'comment.deleted',
        
        # Save events
        'save_created': 'save.created',
        'save_deleted': 'save.deleted',
    }
    
    @classmethod
    def get_topic_name(cls, topic_key: str) -> str:
        """Get topic name by key."""
        topic_config = cls.TOPICS.get(topic_key)
        if not topic_config:
            raise ValueError(f"Unknown topic key: {topic_key}")
        return topic_config['name']
    
    @classmethod
    def get_topic_config(cls, topic_key: str) -> Dict[str, Any]:
        """Get full topic configuration."""
        if topic_key not in cls.TOPICS:
            raise ValueError(f"Unknown topic key: {topic_key}")
        return cls.TOPICS[topic_key]
    
    @classmethod
    def get_all_topic_configs(cls) -> List[Dict[str, Any]]:
        """Get all topic configurations for creation."""
        return list(cls.TOPICS.values())
    
    @classmethod
    def get_consumer_config(cls, group_key: str) -> Dict[str, Any]:
        """Get consumer group configuration."""
        if group_key not in cls.CONSUMER_GROUPS:
            raise ValueError(f"Unknown consumer group key: {group_key}")
        return cls.CONSUMER_GROUPS[group_key]
    
    @classmethod
    def get_event_type(cls, event_key: str) -> str:
        """Get event type string by key."""
        if event_key not in cls.EVENT_TYPES:
            raise ValueError(f"Unknown event type key: {event_key}")
        return cls.EVENT_TYPES[event_key]
    
    @staticmethod
    def delivery_callback(err: Exception, msg: Message) -> None:
        """
        Default delivery callback for Kafka producer.
        
        Args:
            err: Error if message delivery failed
            msg: Message that was delivered (or failed)
        """
        if err:
            logger.error(f"Message delivery failed: {err}")
        else:
            logger.debug(f"Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
    
    @staticmethod
    def critical_delivery_callback(err: Exception, msg: Message) -> None:
        """
        Critical delivery callback for important messages.
        Logs errors at higher severity and could trigger alerts.
        """
        if err:
            logger.critical(f"CRITICAL: Failed to deliver important message: {err}")
            # In production:
            # - Immediate alert to monitoring
            # - Retry mechanism
            # - Store in persistent queue
        else:
            logger.info(f"Critical message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
    
    @classmethod
    def get_delivery_callback(cls, callback_type: str = 'default') -> Callable:
        """Get appropriate delivery callback based on message importance."""
        callbacks = {
            'default': cls.delivery_callback,
            'critical': cls.critical_delivery_callback,
        }
        
        if callback_type not in callbacks:
            logger.warning(f"Unknown callback type: {callback_type}, using default")
            callback_type = 'default'
            
        return callbacks[callback_type]

# Create convenient access instance
kafka_config = KafkaConfig()