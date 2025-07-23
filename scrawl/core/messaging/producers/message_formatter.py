"""
Message formatting utilities for Scrawl Kafka events.
Provides standardized message formats and validation for different event types.
"""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, Union
from django.core.serializers.json import DjangoJSONEncoder

logger = logging.getLogger(__name__)

class MessageFormatter:
    """Standardized message formatting for Kafka events."""
    
    # Message schema versions
    SCHEMA_VERSION = "1.0"
    
    # Required fields for different event types
    REQUIRED_FIELDS = {
        'follow.created': ['follower_id', 'followed_id'],
        'follow.deleted': ['follower_id', 'followed_id'],
        'follow.request.created': ['requester_id', 'target_id'],
        'follow.request.accepted': ['requester_id', 'target_id'],
        'follow.request.denied': ['requester_id', 'target_id'],
        
        'post.created': ['post_id', 'user_id', 'privacy'],
        'post.updated': ['post_id', 'user_id'],
        'post.deleted': ['post_id', 'user_id'],
        
        'like.created': ['user_id', 'post_id'],
        'like.deleted': ['user_id', 'post_id'],
        
        'comment.created': ['user_id', 'post_id', 'comment_id'],
        'comment.updated': ['user_id', 'post_id', 'comment_id'],
        'comment.deleted': ['user_id', 'post_id', 'comment_id'],
        
        'save.created': ['user_id', 'post_id'],
        'save.deleted': ['user_id', 'post_id'],
    }
    
    @classmethod
    def create_standard_message(cls, event_type: str, data: Dict[str, Any],
                              correlation_id: Optional[str] = None,
                              source: str = 'scrawl-api') -> Dict[str, Any]:
        """
        Create a standardized message format.
        
        Args:
            event_type: Type of event (e.g., 'post.created')
            data: Event payload data
            correlation_id: Optional correlation ID for tracking
            source: Source service name
            
        Returns:
            Standardized message dictionary
        """
        message = {
            'event_id': cls._generate_event_id(),
            'event_type': event_type,
            'timestamp': datetime.now().isoformat(),
            'schema_version': cls.SCHEMA_VERSION,
            'source': source,
            'data': cls._sanitize_data(data)
        }
        
        if correlation_id:
            message['correlation_id'] = correlation_id
            
        return message
    
    @classmethod
    def create_follow_message(cls, event_type: str, follower_id: int, followed_id: int,
                            is_super_follower: bool = False, created_at: Optional[str] = None,
                            **extra_fields) -> Dict[str, Any]:
        """Create standardized follow event message."""
        data = {
            'follower_id': follower_id,
            'followed_id': followed_id,
            'is_super_follower': is_super_follower,
        }
        
        if created_at:
            data['created_at'] = created_at
            
        data.update(extra_fields)
        
        return cls.create_standard_message(event_type, data)
    
    @classmethod
    def create_post_message(cls, event_type: str, post_id: int, user_id: int,
                          privacy: str = 'public', created_at: Optional[str] = None,
                          **extra_fields) -> Dict[str, Any]:
        """Create standardized post event message."""
        data = {
            'post_id': post_id,
            'user_id': user_id,
            'privacy': privacy,
        }
        
        if created_at:
            data['created_at'] = created_at
            
        data.update(extra_fields)
        
        return cls.create_standard_message(event_type, data)
    
    @classmethod
    def create_interaction_message(cls, event_type: str, user_id: int, post_id: int,
                                 interaction_id: Optional[int] = None,
                                 created_at: Optional[str] = None,
                                 **extra_fields) -> Dict[str, Any]:
        """Create standardized interaction event message (likes, comments, saves)."""
        data = {
            'user_id': user_id,
            'post_id': post_id,
        }
        
        if interaction_id:
            # eg: for comments, this would be comment_id
            if 'comment' in event_type:
                data['comment_id'] = interaction_id
            elif 'like' in event_type:
                data['like_id'] = interaction_id
            elif 'save' in event_type:
                data['save_id'] = interaction_id
        
        if created_at:
            data['created_at'] = created_at
            
        data.update(extra_fields)
        
        return cls.create_standard_message(event_type, data)
    
    @classmethod
    def create_follow_request_message(cls, event_type: str, requester_id: int, target_id: int,
                                    request_id: Optional[int] = None, status: str = 'pending',
                                    created_at: Optional[str] = None,
                                    **extra_fields) -> Dict[str, Any]:
        """Create standardized follow request event message."""
        data = {
            'requester_id': requester_id,
            'target_id': target_id,
            'status': status,
        }
        
        if request_id:
            data['request_id'] = request_id
            
        if created_at:
            data['created_at'] = created_at
            
        data.update(extra_fields)
        
        return cls.create_standard_message(event_type, data)
    
    @classmethod
    def validate_message(cls, message: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate message structure and required fields.
        
        Args:
            message: Message to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            # Check required top-level fields
            required_top_level = ['event_type', 'timestamp', 'data']
            for field in required_top_level:
                if field not in message:
                    return False, f"Missing required field: {field}"
            
            event_type = message['event_type']
            data = message['data']
            
            # Check event-specific required fields
            if event_type in cls.REQUIRED_FIELDS:
                required_data_fields = cls.REQUIRED_FIELDS[event_type]
                for field in required_data_fields:
                    if field not in data:
                        return False, f"Missing required data field for {event_type}: {field}"
            
            # Validate data types
            validation_errors = cls._validate_data_types(event_type, data)
            if validation_errors:
                return False, f"Data type validation errors: {', '.join(validation_errors)}"
            
            return True, None
            
        except Exception as e:
            return False, f"Validation error: {str(e)}"
    
    @classmethod
    def _validate_data_types(cls, event_type: str, data: Dict[str, Any]) -> list[str]:
        """Validate data types for specific event types."""
        errors = []
        
        # Common ID field validations
        id_fields = ['user_id', 'post_id', 'follower_id', 'followed_id', 
                    'requester_id', 'target_id', 'comment_id', 'like_id', 'save_id']
        
        for field in id_fields:
            if field in data and not isinstance(data[field], int):
                errors.append(f"{field} must be an integer")
        
        # String field validations
        string_fields = ['privacy', 'status', 'event_type']
        for field in string_fields:
            if field in data and not isinstance(data[field], str):
                errors.append(f"{field} must be a string")
        
        # Boolean field validations
        boolean_fields = ['is_super_follower']
        for field in boolean_fields:
            if field in data and not isinstance(data[field], bool):
                errors.append(f"{field} must be a boolean")
        
        return errors
    
    @classmethod
    def _sanitize_data(cls, data: Dict[str, Any]) -> Dict[str, Any]:
        """Sanitize data for JSON serialization."""
        try:
            # Use Django's JSON encoder to handle special types
            import json
            serialized = json.dumps(data, cls=DjangoJSONEncoder)
            return json.loads(serialized)
        except Exception as e:
            logger.warning(f"Data sanitization failed, using original data: {e}")
            return data
    
    @classmethod
    def _generate_event_id(cls) -> str:
        """Generate unique event ID."""
        import uuid
        return str(uuid.uuid4())
    
    @classmethod
    def add_metadata(cls, message: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
        """Add metadata to an existing message."""
        if 'metadata' not in message:
            message['metadata'] = {}
        
        message['metadata'].update(metadata)
        return message
    
    @classmethod
    def add_tracing_info(cls, message: Dict[str, Any], user_id: Optional[int] = None,
                        request_id: Optional[str] = None, 
                        session_id: Optional[str] = None) -> Dict[str, Any]:
        """Add tracing information for debugging and monitoring."""
        tracing_info = {}
        
        if user_id:
            tracing_info['user_id'] = user_id
        if request_id:
            tracing_info['request_id'] = request_id  
        if session_id:
            tracing_info['session_id'] = session_id
            
        if tracing_info:
            return cls.add_metadata(message, {'tracing': tracing_info})
        
        return message
    
    @classmethod
    def create_error_message(cls, original_message: Dict[str, Any], error: str,
                           retry_count: int = 0) -> Dict[str, Any]:
        """Create error message for DLQ."""
        error_message = {
            'error_type': 'processing_error',
            'error_message': error,
            'retry_count': retry_count,
            'failed_at': datetime.now().isoformat(),
            'original_message': original_message
        }
        
        return cls.create_standard_message('error.processing_failed', error_message)

# Create convenient instance
message_formatter = MessageFormatter()