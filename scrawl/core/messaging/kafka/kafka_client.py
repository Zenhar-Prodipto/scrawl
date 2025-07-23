"""
Kafka connection management for Scrawl application.
Provides singleton Kafka client with connection pooling and health monitoring.
"""
import logging
import os
from typing import Optional, Dict, Any
from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic


logger = logging.getLogger(__name__)

class KafkaConnectionManager:
    """Singleton Kafka connection manager with health monitoring and connection pooling."""
    
    _instance = None
    _producer = None
    _admin_client = None
    _initialized = False
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Don't initialize clients here to avoid accessing settings prematurely
        pass
    
    def _get_kafka_config(self) -> Dict[str, Any]:
        """Get Kafka configuration from Django settings - lazy loaded."""
        try:
            # Import Django settings only when needed
            from django.conf import settings
            return {
                'bootstrap.servers': settings.KAFKA['BOOTSTRAP_SERVERS'],
                'security.protocol': settings.KAFKA.get('SECURITY_PROTOCOL', 'PLAINTEXT'),
                'api.version.request': True,
                'broker.version.fallback': '2.3.0',
            }
        except Exception as e:
            # Fallback to environment variables if Django settings not available
            import os
            logger.warning(f"Failed to get Kafka config from Django settings: {e}, using environment")
            return {
                'bootstrap.servers': os.getenv('KAFKA_BROKER', 'drf_scrawl_kafka:9092'),
                'security.protocol': 'PLAINTEXT',
                'api.version.request': True,
                'broker.version.fallback': '2.3.0',
            }
        
    def _get_producer_config(self) -> Dict[str, Any]:
        """Get producer-specific configuration."""
        config = self._get_kafka_config()
        config.update({
            'client.id': 'scrawl-producer',
            'acks': 'all',
            'retries': 3,
            'retry.backoff.ms': 1000,
            'delivery.timeout.ms': 30000,
            'request.timeout.ms': 25000,
            'compression.type': 'snappy',
            'batch.size': 16384,
            'linger.ms': 10,
        })
        return config
    
    def _get_consumer_config(self, group_id: str, **kwargs) -> Dict[str, Any]:
        """Get consumer-specific configuration."""
        config = self._get_kafka_config()
        config.update({
            'group.id': group_id,
            'client.id': f'scrawl-consumer-{group_id}',
            'auto.offset.reset': 'latest',
            'enable.auto.commit': True,
            'auto.commit.interval.ms': 5000,
            'session.timeout.ms': 10000,
            'heartbeat.interval.ms': 3000,
            'max.poll.interval.ms': 300000,
            'fetch.min.bytes': 1,
            'fetch.wait.max.ms': 500,
        })
        config.update(kwargs)
        return config
    
    def _initialize_clients(self):
        """Initialize Kafka producer and admin client."""
        if self._initialized:
            return
            
        try:
            # Initialize producer
            producer_config = self._get_producer_config()
            self._producer = Producer(producer_config)
            logger.info("Kafka producer initialized successfully")
            
            # Initialize admin client
            admin_config = self._get_kafka_config()
            self._admin_client = AdminClient(admin_config)
            logger.info("Kafka admin client initialized successfully")
            
            # Test connectivity
            if self._test_connectivity():
                logger.info("Kafka connectivity test passed")
            else:
                logger.warning("Kafka connectivity test failed")
                
            self._initialized = True
            
        except Exception as e:
            logger.error(f"Failed to initialize Kafka clients: {e}")
            self._producer = None
            self._admin_client = None
            self._initialized = False
            raise
    
    def _test_connectivity(self) -> bool:
        """Test Kafka connectivity."""
        try:
            # Ensure admin client is initialized
            if self._admin_client is None:
                self._initialize_clients()
            
            metadata = self._admin_client.list_topics(timeout=5.0)
            topics = list(metadata.topics.keys())
            logger.debug(f"Available topics: {topics}")
            return True
        except Exception as e:
            logger.error(f"Kafka connectivity test failed: {e}")
            return False
    
    @property
    def producer(self) -> Optional[Producer]:
        """Get Kafka producer instance with lazy initialization."""
        if not self._initialized:
            self._initialize_clients()
        return self._producer
    
    @property
    def admin_client(self) -> Optional[AdminClient]:
        """Get Kafka admin client instance with lazy initialization."""
        if not self._initialized:
            self._initialize_clients()
        return self._admin_client
    
    def create_consumer(self, group_id: str, **kwargs) -> Consumer:
        """Create a new Kafka consumer with proper configuration."""
        try:
            consumer_config = self._get_consumer_config(group_id, **kwargs)
            consumer = Consumer(consumer_config)
            logger.info(f"Created Kafka consumer for group: {group_id}")
            return consumer
        except Exception as e:
            logger.error(f"Failed to create consumer for group {group_id}: {e}")
            raise
    
    def is_connected(self) -> bool:
        """Check if Kafka is connected and responsive."""
        return self._test_connectivity()
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get Kafka connection information and cluster metadata."""
        try:
            if not self.is_connected():
                return {"status": "disconnected", "error": "No connection to Kafka"}
            
            # Ensure admin client is initialized
            if self._admin_client is None:
                self._initialize_clients()
            
            metadata = self._admin_client.list_topics(timeout=5.0)
            
            broker_info = []
            for broker_id, broker_metadata in metadata.brokers.items():
                broker_info.append({
                    'id': broker_id,
                    'host': broker_metadata.host,
                    'port': broker_metadata.port
                })
            
            topic_info = []
            for topic_name, topic_metadata in metadata.topics.items():
                topic_info.append({
                    'name': topic_name,
                    'partitions': len(topic_metadata.partitions)
                })
            
            return {
                "status": "connected",
                "cluster_id": metadata.cluster_id,
                "brokers": broker_info,
                "topics": topic_info,
                "bootstrap_servers": self._get_kafka_config().get('bootstrap.servers')
            }
            
        except Exception as e:
            logger.error(f"Failed to get Kafka connection info: {e}")
            return {"status": "error", "error": str(e)}
    
    def ensure_topics_exist(self, topic_configs: list) -> bool:
        """Ensure required topics exist, create if they don't."""
        try:
            # Ensure admin client is initialized
            if self._admin_client is None:
                self._initialize_clients()
            
            metadata = self._admin_client.list_topics(timeout=10.0)
            existing_topics = set(metadata.topics.keys())
            
            topics_to_create = []
            for topic_config in topic_configs:
                topic_name = topic_config['name']
                if topic_name not in existing_topics:
                    topics_to_create.append(NewTopic(
                        topic_name,
                        num_partitions=topic_config.get('partitions', 3),
                        replication_factor=topic_config.get('replication_factor', 1)
                    ))
            
            if not topics_to_create:
                logger.info("All required topics already exist")
                return True
            
            futures = self._admin_client.create_topics(topics_to_create)
            
            for topic_name, future in futures.items():
                try:
                    future.result(timeout=10.0)
                    logger.info(f"Topic '{topic_name}' created successfully")
                except Exception as e:
                    if "already exists" in str(e).lower():
                        logger.info(f"Topic '{topic_name}' already exists")
                    else:
                        logger.error(f"Failed to create topic '{topic_name}': {e}")
                        return False
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to ensure topics exist: {e}")
            return False
    
    def flush_producer(self, timeout: float = 30.0) -> int:
        """Flush producer messages and return number of pending messages."""
        try:
            if self._producer is None:
                self._initialize_clients()
            
            remaining = self._producer.flush(timeout=timeout)
            if remaining == 0:
                logger.debug("All producer messages flushed successfully")
            else:
                logger.warning(f"{remaining} messages still pending after flush")
            return remaining
        except Exception as e:
            logger.error(f"Error flushing producer: {e}")
            return -1
    
    def close_connections(self):
        """Close all Kafka connections."""
        try:
            if self._producer:
                self._producer.flush(timeout=10.0)
                logger.info("Kafka producer closed successfully")
                self._producer = None
                
            if self._admin_client:
                logger.info("Kafka admin client closed")
                self._admin_client = None
                
            self._initialized = False
            logger.info("Kafka connections closed and reset")
                
        except Exception as e:
            logger.error(f"Error closing Kafka connections: {e}")

# Singleton instance
kafka_manager = KafkaConnectionManager()