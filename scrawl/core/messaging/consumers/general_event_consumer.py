"""
General event consumer for Scrawl application.
Processes all events for logging, monitoring, and general event handling.
"""
import json
import logging
import os
import sys
import django
from typing import Dict, Any, Optional
from confluent_kafka import Message

# Django setup for standalone consumer
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrawl.settings')
django.setup()

try:
    from .base_consumer import BaseConsumer, HealthMonitorMixin
except ImportError:
    # Fallback for direct execution
    from base_consumer import BaseConsumer, HealthMonitorMixin

logger = logging.getLogger(__name__)

class GeneralEventConsumer(HealthMonitorMixin, BaseConsumer):
    """
    General purpose consumer for processing all Kafka events.
    Handles logging, monitoring, and general event processing.
    """
    
    def __init__(self, group_id: str = 'scrawl-general-group', 
                 consumer_config: Optional[Dict[str, Any]] = None):
        """
        Initialize general event consumer.
        
        Args:
            group_id: Consumer group ID
            consumer_config: Optional consumer configuration overrides
        """
        # Topics this consumer processes (all events)
        topics = ['follow.events', 'post.events', 'like.events', 'comment.events']
        
        # Default consumer configuration for general processor
        default_config = {
            'auto.offset.reset': 'earliest',  # Process all messages from beginning
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
        
        # Performance metrics
        self.processed_by_type = {}
        self.processing_times = {}
        
        logger.info("GeneralEventConsumer initialized successfully")
    
    def process_message(self, message: Message) -> bool:
        """
        Process a single event message for general logging and monitoring.
        
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
            timestamp = payload.get('timestamp')
            
            if not event_type:
                logger.warning("Message missing event_type field")
                return False
            
            # Track processing metrics
            self._track_event_processing(event_type)
            
            # Log the event (main purpose of general consumer)
            logger.info(f"📨 Event received: {event_type} at {timestamp}")
            logger.debug(f"   Event data: {event_data}")
            logger.debug(f"   Message topic: {message.topic()}")
            logger.debug(f"   Message partition: {message.partition()}")
            logger.debug(f"   Message offset: {message.offset()}")
            
            # Process different event types for monitoring
            self._handle_event_monitoring(event_type, event_data, payload)
            
            return True
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode JSON message: {e}")
            return False
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return False
    
    def _handle_event_monitoring(self, event_type: str, event_data: Dict[str, Any], 
                                full_payload: Dict[str, Any]) -> bool:
        """
        Handle event-specific monitoring and alerting.
        
        Args:
            event_type: Type of event to monitor
            event_data: Event data payload
            full_payload: Full message payload for context
            
        Returns:
            bool: True if handled successfully
        """
        try:
            # Monitor for specific patterns or issues
            if event_type.startswith('post.'):
                user_id = event_data.get('user_id')
                post_id = event_data.get('post_id')
                logger.info(f"📝 Post event: {event_type} - User {user_id}, Post {post_id}")
                
            elif event_type.startswith('follow.'):
                follower_id = event_data.get('follower_id')
                followed_id = event_data.get('followed_id')
                logger.info(f"👥 Follow event: {event_type} - {follower_id} → {followed_id}")
                
            elif event_type.startswith('like.'):
                user_id = event_data.get('user_id')
                post_id = event_data.get('post_id')
                logger.info(f"❤️ Like event: {event_type} - User {user_id} on Post {post_id}")
                
            elif event_type.startswith('comment.'):
                user_id = event_data.get('user_id')
                post_id = event_data.get('post_id')
                comment_id = event_data.get('comment_id')
                logger.info(f"💬 Comment event: {event_type} - User {user_id} on Post {post_id}")
                
            # Check for potential issues
            self._check_for_alerts(event_type, event_data)
            
            return True
            
        except Exception as e:
            logger.error(f"Error in event monitoring: {e}")
            return False
    
    def _check_for_alerts(self, event_type: str, event_data: Dict[str, Any]):
        """Check for conditions that might need alerts."""
        try:
            # Example: Alert on high error rates
            if hasattr(self, 'error_count') and hasattr(self, 'message_count'):
                if self.message_count > 0:
                    error_rate = self.error_count / self.message_count
                    if error_rate > 0.1:  # 10% error rate
                        logger.warning(f"🚨 HIGH ERROR RATE: {error_rate:.2%} ({self.error_count}/{self.message_count})")
            
            # Example: Alert on missing critical fields
            critical_events = ['post.created', 'follow.created']
            if event_type in critical_events:
                required_fields = {
                    'post.created': ['user_id', 'post_id'],
                    'follow.created': ['follower_id', 'followed_id']
                }
                
                missing_fields = []
                for field in required_fields.get(event_type, []):
                    if field not in event_data or event_data[field] is None:
                        missing_fields.append(field)
                
                if missing_fields:
                    logger.warning(f"🚨 MISSING CRITICAL FIELDS in {event_type}: {missing_fields}")
            
        except Exception as e:
            logger.error(f"Error checking alerts: {e}")
    
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
        import time
        
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
            'consumer_type': 'GeneralEventConsumer'
        })
        
        return base_stats
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get a summary of consumer health for monitoring."""
        stats = self.get_processing_stats()
        health = self.perform_health_check()
        
        return {
            'consumer_name': 'GeneralEventConsumer',
            'status': health.get('status', 'unknown'),
            'total_messages': stats.get('message_count', 0),
            'total_errors': stats.get('error_count', 0),
            'error_rate': stats.get('error_rate', 0),
            'event_types_processed': len(self.processed_by_type),
            'kafka_connected': health.get('kafka_connected', False),
            'uptime_seconds': stats.get('uptime_seconds', 0)
        }

def main():
    """Main entry point for running the GeneralEventConsumer."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/app/logs/general_consumer.log') 
            if os.path.exists('/app/logs') else logging.StreamHandler()
        ]
    )
    
    logger.info("Starting Scrawl General Event Consumer")
    
    try:
        # Create and start the consumer
        consumer = GeneralEventConsumer()
        
        # Add custom shutdown handler for cleanup
        def cleanup_handler():
            logger.info("Performing general consumer cleanup...")
            # Add any custom cleanup logic here
            stats = consumer.get_processing_stats()
            logger.info(f"Final stats - Messages: {stats['message_count']}, Errors: {stats['error_count']}")
        
        consumer.add_shutdown_handler(cleanup_handler)
        
        # Start consuming messages
        consumer.start()
        
    except KeyboardInterrupt:
        logger.info("General consumer interrupted by user")
    except Exception as e:
        logger.error(f"General consumer failed: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()