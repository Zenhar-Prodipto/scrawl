import os
import sys
import time
from confluent_kafka import Consumer, KafkaError, KafkaException
from confluent_kafka.admin import AdminClient, NewTopic
import json
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def wait_for_kafka(bootstrap_servers, timeout=60):
    """Wait for Kafka to be ready and topics to be available"""
    logger.info(f"Waiting for Kafka at {bootstrap_servers}")
    
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            metadata = admin_client.list_topics(timeout=5)
            topics = list(metadata.topics.keys())
            logger.info(f"Available topics: {topics}")
            
            required_topics = ['like.events', 'follow.events', 'post.events']
            missing_topics = [topic for topic in required_topics if topic not in topics]
            
            if not missing_topics:
                logger.info("All required topics are available")
                return True
            else:
                logger.info(f"Missing topics: {missing_topics}")
                
        except Exception as e:
            logger.warning(f"Kafka not ready yet: {e}")
        
        time.sleep(2)
    
    logger.error(f"Kafka not ready after {timeout} seconds")
    return False

def create_topics_if_needed(bootstrap_servers):
    """Create topics if they don't exist"""
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    topics_to_create = [
        NewTopic("like.events", num_partitions=3, replication_factor=1),
        NewTopic("follow.events", num_partitions=3, replication_factor=1),
        NewTopic("post.events", num_partitions=3, replication_factor=1)
    ]
    
    try:
        fs = admin_client.create_topics(topics_to_create)
        for topic, f in fs.items():
            try:
                f.result()  # The result itself is None
                logger.info(f"Topic {topic} created")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"Topic {topic} already exists")
                else:
                    logger.error(f"Failed to create topic {topic}: {e}")
    except Exception as e:
        logger.error(f"Error creating topics: {e}")

def main():
    bootstrap_servers = os.environ.get('KAFKA_BROKER', 'drf_scrawl_kafka:9092')
    logger.info(f"Starting consumer with broker: {bootstrap_servers}")
    
    if not wait_for_kafka(bootstrap_servers):
        logger.error("Kafka is not ready, exiting")
        sys.exit(1)
    
    create_topics_if_needed(bootstrap_servers)
    
    kafka_config = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': 'scrawl-group',
        'auto.offset.reset': 'earliest',
        'enable.auto.commit': True,
        'session.timeout.ms': 10000,
        'heartbeat.interval.ms': 3000,
        'max.poll.interval.ms': 300000,
        'fetch.wait.max.ms': 500,
        'fetch.min.bytes': 1
    }
    
    consumer = Consumer(kafka_config)
    topics = ['like.events', 'follow.events', 'post.events']
    
    try:
        logger.info(f"Subscribing to topics: {topics}")
        consumer.subscribe(topics)
        
        logger.info("Starting message polling...")
        consecutive_none_count = 0
        
        while True:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                consecutive_none_count += 1
                if consecutive_none_count % 30 == 0:  # Log every 30 seconds
                    logger.info(f"No messages received for {consecutive_none_count} seconds")
                continue
            
            consecutive_none_count = 0
            
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.info(f"End of partition reached {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
                    continue
                elif msg.error().code() == KafkaError.UNKNOWN_TOPIC_OR_PART:
                    logger.error(f"Unknown topic or partition: {msg.error()}")
                    time.sleep(5)
                    create_topics_if_needed(bootstrap_servers)
                    continue
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                    continue
            
            try:
                event = json.loads(msg.value().decode('utf-8'))
                logger.info(f"Received event from {msg.topic()} [{msg.partition()}] at offset {msg.offset()}: {event}")
            except json.JSONDecodeError as e:
                logger.error(f"Failed to decode JSON message: {e}, raw message: {msg.value()}")
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                
    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except KafkaException as e:
        logger.error(f"Kafka exception: {e}")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        logger.info("Closing consumer")
        consumer.close()

if __name__ == "__main__":
    main()