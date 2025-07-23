"""
Event type definitions and schemas for Scrawl application.
Centralizes all event types, schemas, and validation rules.
"""
from enum import Enum
from dataclasses import dataclass, asdict
from typing import Dict, Any, Optional, List
from datetime import datetime

class EventType(str, Enum):
    """Enumeration of all event types in the system."""
    
    # Follow Events
    FOLLOW_CREATED = "follow.created"
    FOLLOW_DELETED = "follow.deleted"
    FOLLOW_REQUEST_CREATED = "follow.request.created"
    FOLLOW_REQUEST_ACCEPTED = "follow.request.accepted"
    FOLLOW_REQUEST_DENIED = "follow.request.denied"
    FOLLOW_REQUEST_CANCELLED = "follow.request.cancelled"
    
    # Post Events
    POST_CREATED = "post.created"
    POST_UPDATED = "post.updated"
    POST_DELETED = "post.deleted"
    POST_PRIVACY_CHANGED = "post.privacy.changed"
    
    # Like Events
    LIKE_CREATED = "like.created"
    LIKE_DELETED = "like.deleted"
    
    # Comment Events
    COMMENT_CREATED = "comment.created"
    COMMENT_UPDATED = "comment.updated"
    COMMENT_DELETED = "comment.deleted"
    
    # Save Events
    SAVE_CREATED = "save.created"
    SAVE_DELETED = "save.deleted"
    
    # User Events (for future use)
    USER_PROFILE_UPDATED = "user.profile.updated"
    USER_PRIVACY_CHANGED = "user.privacy.changed"
    
    # System Events
    ERROR_PROCESSING_FAILED = "error.processing.failed"

class TopicName(str, Enum):
    """Enumeration of all Kafka topics."""
    
    FOLLOW_EVENTS = "follow.events"
    POST_EVENTS = "post.events"
    LIKE_EVENTS = "like.events" 
    COMMENT_EVENTS = "comment.events"
    USER_EVENTS = "user.events"
    FEED_EVENTS_DLQ = "feed_events_dlq"

@dataclass
class BaseEvent:
    """Base class for all events."""
    event_type: str
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary."""
        return asdict(self)

@dataclass 
class FollowEvent:
    """Follow/Unfollow event schema."""
    event_type: str
    follower_id: int
    followed_id: int
    is_super_follower: bool = False
    created_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class FollowRequestEvent:
    """Follow request event schema."""
    event_type: str
    requester_id: int
    target_id: int
    request_id: Optional[int] = None
    status: str = "pending"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class PostEvent:
    """Post creation/update/deletion event schema."""
    event_type: str
    post_id: int
    user_id: int
    privacy: str = "public"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    tag_names: Optional[List[str]] = None
    image_count: Optional[int] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class LikeEvent:
    """Like/Unlike event schema."""
    event_type: str
    user_id: int
    post_id: int
    like_id: Optional[int] = None
    created_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class CommentEvent:
    """Comment creation/update/deletion event schema."""
    event_type: str
    user_id: int
    post_id: int
    comment_id: int
    parent_comment_id: Optional[int] = None
    text_length: Optional[int] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class SaveEvent:
    """Save/Unsave post event schema."""
    event_type: str
    user_id: int
    post_id: int
    save_id: Optional[int] = None
    created_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()

@dataclass
class UserEvent:
    """User profile/settings change event schema."""
    event_type: str
    user_id: int
    changed_fields: List[str]
    old_values: Optional[Dict[str, Any]] = None
    new_values: Optional[Dict[str, Any]] = None
    updated_at: Optional[str] = None
    timestamp: Optional[str] = None
    event_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now().isoformat()
        if self.event_id is None:
            import uuid
            self.event_id = str(uuid.uuid4())
        if self.updated_at is None:
            self.updated_at = datetime.now().isoformat()

class EventSchemaRegistry:
    """Registry for event schemas and validation."""
    
    # Mapping of event types to their schema classes
    EVENT_SCHEMAS = {
        EventType.FOLLOW_CREATED: FollowEvent,
        EventType.FOLLOW_DELETED: FollowEvent,
        EventType.FOLLOW_REQUEST_CREATED: FollowRequestEvent,
        EventType.FOLLOW_REQUEST_ACCEPTED: FollowRequestEvent,
        EventType.FOLLOW_REQUEST_DENIED: FollowRequestEvent,
        EventType.FOLLOW_REQUEST_CANCELLED: FollowRequestEvent,
        
        EventType.POST_CREATED: PostEvent,
        EventType.POST_UPDATED: PostEvent,
        EventType.POST_DELETED: PostEvent,
        EventType.POST_PRIVACY_CHANGED: PostEvent,
        
        EventType.LIKE_CREATED: LikeEvent,
        EventType.LIKE_DELETED: LikeEvent,
        
        EventType.COMMENT_CREATED: CommentEvent,
        EventType.COMMENT_UPDATED: CommentEvent,
        EventType.COMMENT_DELETED: CommentEvent,
        
        EventType.SAVE_CREATED: SaveEvent,
        EventType.SAVE_DELETED: SaveEvent,
        
        EventType.USER_PROFILE_UPDATED: UserEvent,
        EventType.USER_PRIVACY_CHANGED: UserEvent,
    }
    
    # Mapping of event types to their appropriate topics
    EVENT_TOPIC_MAPPING = {
        EventType.FOLLOW_CREATED: TopicName.FOLLOW_EVENTS,
        EventType.FOLLOW_DELETED: TopicName.FOLLOW_EVENTS,
        EventType.FOLLOW_REQUEST_CREATED: TopicName.FOLLOW_EVENTS,
        EventType.FOLLOW_REQUEST_ACCEPTED: TopicName.FOLLOW_EVENTS,
        EventType.FOLLOW_REQUEST_DENIED: TopicName.FOLLOW_EVENTS,
        EventType.FOLLOW_REQUEST_CANCELLED: TopicName.FOLLOW_EVENTS,
        
        EventType.POST_CREATED: TopicName.POST_EVENTS,
        EventType.POST_UPDATED: TopicName.POST_EVENTS,
        EventType.POST_DELETED: TopicName.POST_EVENTS,
        EventType.POST_PRIVACY_CHANGED: TopicName.POST_EVENTS,
        
        EventType.LIKE_CREATED: TopicName.LIKE_EVENTS,
        EventType.LIKE_DELETED: TopicName.LIKE_EVENTS,
        
        EventType.COMMENT_CREATED: TopicName.COMMENT_EVENTS,
        EventType.COMMENT_UPDATED: TopicName.COMMENT_EVENTS,
        EventType.COMMENT_DELETED: TopicName.COMMENT_EVENTS,
        
        EventType.SAVE_CREATED: TopicName.LIKE_EVENTS,  # Saves go to like events topic
        EventType.SAVE_DELETED: TopicName.LIKE_EVENTS,
        
        EventType.USER_PROFILE_UPDATED: TopicName.USER_EVENTS,
        EventType.USER_PRIVACY_CHANGED: TopicName.USER_EVENTS,
    }
    
    @classmethod
    def get_schema_class(cls, event_type: str):
        """Get schema class for event type."""
        if event_type not in cls.EVENT_SCHEMAS:
            raise ValueError(f"Unknown event type: {event_type}")
        return cls.EVENT_SCHEMAS[event_type]
    
    @classmethod
    def get_topic_for_event(cls, event_type: str) -> str:
        """Get appropriate topic for event type."""
        if event_type not in cls.EVENT_TOPIC_MAPPING:
            raise ValueError(f"No topic mapping for event type: {event_type}")
        return cls.EVENT_TOPIC_MAPPING[event_type].value
    
    @classmethod
    def create_event(cls, event_type: str, **kwargs) -> BaseEvent:
        """Create event instance from type and data."""
        schema_class = cls.get_schema_class(event_type)
        return schema_class(event_type=event_type, **kwargs)
    
    @classmethod
    def validate_event_data(cls, event_type: str, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate event data against schema."""
        try:
            schema_class = cls.get_schema_class(event_type)
            # Try to create event instance - this will validate required fields
            schema_class(event_type=event_type, **data)
            return True, None
        except TypeError as e:
            return False, f"Schema validation error: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @classmethod
    def get_all_event_types(cls) -> List[str]:
        """Get list of all supported event types."""
        return [event_type.value for event_type in EventType]
    
    @classmethod
    def get_all_topics(cls) -> List[str]:
        """Get list of all topics."""
        return [topic.value for topic in TopicName]
    
    @classmethod
    def get_events_for_topic(cls, topic_name: str) -> List[str]:
        """Get all event types that belong to a topic."""
        events = []
        for event_type, topic in cls.EVENT_TOPIC_MAPPING.items():
            if topic.value == topic_name:
                events.append(event_type.value)
        return events

# Create convenient access instance
event_registry = EventSchemaRegistry()