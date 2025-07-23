"""
Scrawl Core Messaging Module

Provides centralized Kafka messaging functionality with event publishing,
standardized schemas, and consumer management.

Usage:
    from scrawl.core.messaging import event_publisher, EventType
    
    # Publish events
    event_publisher.publish_post_event('post_created', post_id=123, user_id=456)
    event_publisher.publish_follow_event('follow_created', follower_id=1, followed_id=2)
    
    # Use event types
    event_type = EventType.POST_CREATED
    
    # Access Kafka manager
    from scrawl.core.messaging import kafka_manager
    if kafka_manager.is_connected():
        # ... do something
"""

# LAZY LOADING - Don't import anything at module level
__all__ = [
    # Core managers and clients
    'kafka_manager',
    'kafka_config', 
    
    # Event publishing
    'event_publisher',
    'message_formatter',
    
    # Event types and schemas
    'EventType',
    'TopicName',
    'EventSchemaRegistry',
    'event_registry',
    
    # Event classes
    'BaseEvent',
    'FollowEvent',
    'FollowRequestEvent', 
    'PostEvent',
    'LikeEvent',
    'CommentEvent',
    'SaveEvent',
    'UserEvent',
]

# Version info
__version__ = '1.0.0'

def __getattr__(name):
    """Lazy load messaging components."""
    
    # Core managers
    if name == 'kafka_manager':
        from .kafka.kafka_client import kafka_manager
        return kafka_manager
    elif name == 'kafka_config':
        from .kafka.kafka_config import kafka_config
        return kafka_config
    
    # Publishers
    elif name == 'event_publisher':
        from .producers.event_publisher import event_publisher
        return event_publisher
    elif name == 'message_formatter':
        from .producers.message_formatter import message_formatter
        return message_formatter
    
    # Event types and schemas
    elif name == 'EventType':
        from .events.event_types import EventType
        return EventType
    elif name == 'TopicName':
        from .events.event_types import TopicName
        return TopicName
    elif name == 'EventSchemaRegistry':
        from .events.event_types import EventSchemaRegistry
        return EventSchemaRegistry
    elif name == 'event_registry':
        from .events.event_types import event_registry
        return event_registry
    
    # Event classes
    elif name == 'BaseEvent':
        from .events.event_types import BaseEvent
        return BaseEvent
    elif name == 'FollowEvent':
        from .events.event_types import FollowEvent
        return FollowEvent
    elif name == 'FollowRequestEvent':
        from .events.event_types import FollowRequestEvent
        return FollowRequestEvent
    elif name == 'PostEvent':
        from .events.event_types import PostEvent
        return PostEvent
    elif name == 'LikeEvent':
        from .events.event_types import LikeEvent
        return LikeEvent
    elif name == 'CommentEvent':
        from .events.event_types import CommentEvent
        return CommentEvent
    elif name == 'SaveEvent':
        from .events.event_types import SaveEvent
        return SaveEvent
    elif name == 'UserEvent':
        from .events.event_types import UserEvent
        return UserEvent
    
    raise AttributeError(f"module '{__name__}' has no attribute '{name}'")