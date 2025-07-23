"""
Base consumer class for Scrawl application Kafka consumers.
Provides common functionality, error handling, and monitoring for all consumers.
"""
import json
import logging
import time
import signal
import sys
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from confluent_kafka import Consumer, KafkaError, KafkaException, Message
from django.conf import settings

from ..kafka.kafka_client import kafka_manager
from ..kafka.kafka_config import kafka_config
from ..producers.event_publisher import event_publisher

logger = logging.getLogger(__name__)

class BaseConsumer(ABC):
    """
    Base class for all Kafka consumers in Scrawl application.
    Provides common functionality like connection management, error handling,
    health monitoring, and graceful shutdown.
    """
    
    def __init__(self, group_id: str, topics: List[str], 
                 consumer_config: Optional[Dict[str, Any]] = None):
        """
        Initialize base consumer.
        
        Args:
            group_id: Kafka consumer group ID
            topics: List of topics to subscribe to
            consumer_config: Optional consumer configuration overrides
        """
        self.group_id = group_id
        self.topics = topics
        self.consumer = None
        self.running = False
        self.message_count = 0
        self.error_count = 0
        self.last_heartbeat = time.time()
        
        # Consumer configuration
        self.consumer_config = consumer_config or {}
        
        # Shutdown handling
        self.shutdown_handlers = []
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initialized {self.__class__.__name__} for group {group_id}")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        logger.info(f"Received signal {signum}, initiating graceful shutdown")
        self.shutdown()
    
    def _create_consumer(self) -> Consumer:
        """Create and configure Kafka consumer."""
        try:
            consumer = kafka_manager.create_consumer(
                self.group_id, 
                **self.consumer_config
            )
            logger.info(f"Created consumer for group {self.group_id}")
            return consumer
        except Exception as e:
            logger.error(f"Failed to create consumer: {e}")
            raise
    
    def _subscribe_to_topics(self):
        """Subscribe consumer to configured topics."""
        try:
            self.consumer.subscribe(self.topics)
            logger.info(f"Subscribed to topics: {self.topics}")
        except Exception as e:
            logger.error(f"Failed to subscribe to topics: {e}")
            raise
    
    def _wait_for_kafka_ready(self, timeout: int = 60) -> bool:
        """Wait for Kafka to be ready and topics to be available."""
        logger.info("Waiting for Kafka to be ready...")
        
        start_time = time.time()
        while time.time() - start_time < timeout:
            try:
                if kafka_manager.is_connected():
                    # Check if all required topics exist
                    connection_info = kafka_manager.get_connection_info()
                    available_topics = [t['name'] for t in connection_info.get('topics', [])]
                    missing_topics = set(self.topics) - set(available_topics)
                    
                    if not missing_topics:
                        logger.info("All required topics are available")
                        return True
                    else:
                        logger.info(f"Missing topics: {missing_topics}")
                
            except Exception as e:
                logger.warning(f"Kafka readiness check failed: {e}")
            
            time.sleep(2)
        
        logger.error(f"Kafka not ready after {timeout} seconds")
        return False
    
    @abstractmethod
    def process_message(self, message: Message) -> bool:
        """
        Process a single Kafka message.
        Must be implemented by subclasses.
        
        Args:
            message: Kafka message to process
            
        Returns:
            bool: True if processing successful, False otherwise
        """
        pass
    
    def _handle_message(self, message: Message) -> bool:
        """
        Handle a single message with error handling and metrics.
        
        Args:
            message: Kafka message to handle
            
        Returns:
            bool: True if handled successfully, False otherwise
        """
        try:
            # Update heartbeat
            self.last_heartbeat = time.time()
            
            # Validate message
            if not self._validate_message(message):
                logger.warning(f"Invalid message format: {message.value()}")
                self._send_to_dlq(message, "Invalid message format")
                return False
            
            # Process message
            success = self.process_message(message)
            
            if success:
                self.message_count += 1
                logger.debug(f"Processed message from {message.topic()} [{message.partition()}] at offset {message.offset()}")
            else:
                self.error_count += 1
                logger.warning(f"Failed to process message from {message.topic()}")
                self._send_to_dlq(message, "Processing failed")
            
            return success
            
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            self.error_count += 1
            self._send_to_dlq(message, f"Exception during processing: {str(e)}")
            return False
    
    def _validate_message(self, message: Message) -> bool:
        """
        Validate message format and structure.
        
        Args:
            message: Kafka message to validate
            
        Returns:
            bool: True if valid, False otherwise
        """
        try:
            # Try to decode as JSON
            payload = json.loads(message.value().decode('utf-8'))
            
            # Check required fields
            required_fields = ['event_type', 'timestamp', 'data']
            for field in required_fields:
                if field not in payload:
                    logger.warning(f"Missing required field: {field}")
                    return False
            
            return True
            
        except json.JSONDecodeError:
            logger.warning("Message is not valid JSON")
            return False
        except Exception as e:
            logger.warning(f"Message validation error: {e}")
            return False
    
    def _send_to_dlq(self, message: Message, error_reason: str):
        """
        Send failed message to Dead Letter Queue.
        
        Args:
            message: Original failed message
            error_reason: Reason for failure
        """
        try:
            dlq_payload = {
                'original_topic': message.topic(),
                'original_partition': message.partition(),
                'original_offset': message.offset(),
                'original_timestamp': message.timestamp()[1] if message.timestamp()[0] else None,
                'error_reason': error_reason,
                'failed_at': time.time(),
                'consumer_group': self.group_id,
                'original_message': message.value().decode('utf-8') if message.value() else None
            }
            
            # Use event publisher to send to DLQ
            event_publisher.publish_custom_event(
                'feed_events_dlq',
                'error_processing_failed', 
                dlq_payload,
                key=message.key().decode('utf-8') if message.key() else None,
                async_publish=True
            )
            
            logger.info(f"Sent message to DLQ: {error_reason}")
            
        except Exception as e:
            logger.error(f"Failed to send message to DLQ: {e}")
    
    def _log_health_status(self):
        """Log consumer health status."""
        uptime = time.time() - self.last_heartbeat
        logger.info(
            f"Consumer health - Messages: {self.message_count}, "
            f"Errors: {self.error_count}, Uptime: {uptime:.1f}s"
        )
    
    def start(self):
        """
        Start the consumer and begin processing messages.
        This is the main consumer loop.
        """
        logger.info(f"Starting {self.__class__.__name__} consumer")
        
        try:
            # Wait for Kafka to be ready
            if not self._wait_for_kafka_ready():
                logger.error("Kafka not ready, cannot start consumer")
                return
            
            # Create and configure consumer
            self.consumer = self._create_consumer()
            self._subscribe_to_topics()
            
            self.running = True
            consecutive_none_count = 0
            last_health_log = time.time()
            
            logger.info("Consumer started, beginning message polling...")
            
            while self.running:
                try:
                    # Poll for messages
                    message = self.consumer.poll(timeout=1.0)
                    
                    if message is None:
                        consecutive_none_count += 1
                        
                        # Log health status periodically
                        if time.time() - last_health_log > 30:
                            self._log_health_status()
                            last_health_log = time.time()
                        
                        continue
                    
                    consecutive_none_count = 0
                    
                    # Handle Kafka errors
                    if message.error():
                        if message.error().code() == KafkaError._PARTITION_EOF:
                            logger.debug(f"Reached end of partition {message.topic()} [{message.partition()}]")
                            continue
                        else:
                            logger.error(f"Kafka error: {message.error()}")
                            continue
                    
                    # Process the message
                    self._handle_message(message)
                    
                except KafkaException as e:
                    logger.error(f"Kafka exception: {e}")
                    time.sleep(5)  # Wait before retrying
                    
                except Exception as e:
                    logger.error(f"Unexpected error in consumer loop: {e}")
                    time.sleep(1)
            
        except Exception as e:
            logger.error(f"Consumer startup failed: {e}")
            raise
        finally:
            self._cleanup()
    
    def shutdown(self):
        """Gracefully shutdown the consumer."""
        logger.info("Shutting down consumer...")
        self.running = False
        
        # Execute shutdown handlers
        for handler in self.shutdown_handlers:
            try:
                handler()
            except Exception as e:
                logger.error(f"Error in shutdown handler: {e}")
    
    def _cleanup(self):
        """Clean up resources."""
        logger.info("Cleaning up consumer resources...")
        
        try:
            if self.consumer:
                self.consumer.close()
                logger.info("Consumer closed successfully")
        except Exception as e:
            logger.error(f"Error closing consumer: {e}")
        
        # Log final statistics
        logger.info(
            f"Consumer stopped - Total messages: {self.message_count}, "
            f"Total errors: {self.error_count}"
        )
    
    def add_shutdown_handler(self, handler: Callable):
        """
        Add a custom shutdown handler.
        
        Args:
            handler: Function to call during shutdown
        """
        self.shutdown_handlers.append(handler)
    
    def get_stats(self) -> Dict[str, Any]:
        """
        Get consumer statistics.
        
        Returns:
            Dict with consumer statistics
        """
        uptime = time.time() - self.last_heartbeat if self.running else 0
        
        return {
            'group_id': self.group_id,
            'topics': self.topics,
            'running': self.running,
            'message_count': self.message_count,
            'error_count': self.error_count,
            'uptime_seconds': uptime,
            'error_rate': self.error_count / max(self.message_count, 1),
            'last_heartbeat': self.last_heartbeat
        }

class HealthMonitorMixin:
    """Mixin to add health monitoring capabilities to consumers."""
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.health_check_interval = 30
        self.last_health_check = time.time()
    
    def perform_health_check(self) -> Dict[str, Any]:
        """Perform health check and return status."""
        now = time.time()
        
        if now - self.last_health_check < self.health_check_interval:
            return {'status': 'healthy', 'last_check': self.last_health_check}
        
        try:
            # Check Kafka connectivity
            is_connected = kafka_manager.is_connected()
            
            # Check consumer lag (simplified)
            error_rate = self.error_count / max(self.message_count, 1)
            
            status = 'healthy' if is_connected and error_rate < 0.1 else 'unhealthy'
            
            health_info = {
                'status': status,
                'kafka_connected': is_connected,
                'error_rate': error_rate,
                'message_count': self.message_count,
                'error_count': self.error_count,
                'last_check': now
            }
            
            self.last_health_check = now
            return health_info
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {'status': 'unhealthy', 'error': str(e), 'last_check': now}