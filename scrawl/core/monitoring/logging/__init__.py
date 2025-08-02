"""
ELK Stack logging utilities for Scrawl application.
Provides structured JSON logging that integrates with existing monitoring.
"""
import uuid
import json
import socket
import logging
from pythonjsonlogger import jsonlogger
from typing import Dict, Any, Optional

class ELKFormatter(jsonlogger.JsonFormatter):
    """
    Custom JSON formatter for ELK Stack.
    Adds standard fields and ensures consistent log structure.
    """
    
    def add_fields(self, log_record, record, message_dict):
        """Add standard fields to every log record."""
        super().add_fields(log_record, record, message_dict)
        
        # Add standard ELK fields
        log_record['service'] = 'scrawl'
        log_record['environment'] = getattr(record, 'environment', 'local')
        log_record['version'] = '1.0.0'
        
        # Ensure timestamp is properly formatted
        if not log_record.get('timestamp'):
            from datetime import datetime
            log_record['timestamp'] = datetime.utcnow().isoformat() + 'Z'
        
        # Add correlation ID if not present
        if not log_record.get('request_id'):
            log_record['request_id'] = getattr(record, 'request_id', self.generate_request_id())

    def generate_request_id(self) -> str:
        """Generate unique request ID for correlation."""
        return f"req_{uuid.uuid4().hex[:8]}"

class ELKTCPHandler(logging.Handler):
    """
    Custom TCP handler that sends JSON directly to Logstash.
    Avoids pickle serialization issues.
    """
    
    def __init__(self, host='drf_scrawl_logstash', port=5000):
        super().__init__()
        self.host = host
        self.port = port
        self.sock = None
        
    def _connect(self):
        """Establish connection to Logstash."""
        try:
            if self.sock:
                self.sock.close()
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)  # 5 second timeout
            self.sock.connect((self.host, self.port))
            return True
        except Exception as e:
            if self.sock:
                self.sock.close()
            self.sock = None
            return False
    
    def emit(self, record):
        """Send log record as JSON to Logstash."""
        try:
            # Format the record as JSON
            if self.formatter:
                json_str = self.formatter.format(record)
            else:
                json_str = json.dumps({
                    'message': record.getMessage(),
                    'level': record.levelname,
                    'timestamp': record.created
                })
            
            # Ensure we have a connection
            if not self.sock and not self._connect():
                return  # Connection failed, skip this log
            
            # Send JSON + newline
            message = json_str + '\n'
            self.sock.send(message.encode('utf-8'))
            
        except Exception as e:
            # Connection lost, try to reconnect next time
            if self.sock:
                self.sock.close()
            self.sock = None
            # Don't raise exception - just skip this log
    
    def close(self):
        """Close the socket connection."""
        if self.sock:
            self.sock.close()
            self.sock = None
        super().close()

def get_elk_logger(name: str = 'scrawl.elk') -> logging.Logger:
    """
    Get configured ELK logger instance.
    
    Args:
        name: Logger name
        
    Returns:
        Configured logger for ELK Stack
    """
    return logging.getLogger(name)

def create_log_context(request=None, user=None, **extra) -> Dict[str, Any]:
    """
    Create standard log context for ELK.
    
    Args:
        request: Django request object
        user: User object
        **extra: Additional context fields
        
    Returns:
        Dictionary with standard log context
    """
    context = {}
    
    # Request context
    if request:
        context.update({
            'ip_address': get_client_ip(request),
            'user_agent': request.META.get('HTTP_USER_AGENT', 'unknown'),
            'method': request.method,
            'path': request.path_info,
            'request_id': getattr(request, '_elk_request_id', f"req_{uuid.uuid4().hex[:8]}")
        })
    
    # User context
    if user and hasattr(user, 'id'):
        context.update({
            'user_id': user.id,
            'user_tier': 'admin' if getattr(user, 'is_superuser', False) else 'free',
            'username': getattr(user, 'username', 'unknown')
        })
    
    # Add extra context
    context.update(extra)
    
    return context

def get_client_ip(request) -> str:
    """Extract client IP from request."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR', 'unknown')
    return ip

# Standard event types
class EventTypes:
    """Standard event types for ELK logging."""
    API_REQUEST = 'api_request'
    API_ERROR = 'api_error'
    USER_AUTH = 'user_authentication'
    POST_INTERACTION = 'post_interaction'
    FOLLOW_INTERACTION = 'follow_interaction'
    CACHE_OPERATION = 'cache_operation'
    SYSTEM_ERROR = 'system_error'
    SECURITY_EVENT = 'security_event'

# Export commonly used items
__all__ = [
    'ELKFormatter',
    'ELKTCPHandler',
    'get_elk_logger', 
    'create_log_context',
    'get_client_ip',
    'EventTypes'
]