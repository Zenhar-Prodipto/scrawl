#!/usr/bin/env python3
"""
Kafka Diagnostic Script
Run this to diagnose your Kafka setup issues.
"""

import os
import sys
import time
import json
from confluent_kafka import Producer, Consumer, KafkaError
from confluent_kafka.admin import AdminClient, NewTopic
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_kafka_connection(bootstrap_servers):
    """Test basic Kafka connection"""
    logger.info("=== Testing Kafka Connection ===")
    
    try:
        admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
        metadata = admin_client.list_topics(timeout=10)
        logger.info(f"✓ Successfully connected to Kafka at {bootstrap_servers}")
        logger.info(f"✓ Available topics: {list(metadata.topics.keys())}")
        return True
    except Exception as e:
        logger.error(f"✗ Failed to connect to Kafka: {e}")
        return False

def test_topic_creation(bootstrap_servers):
    """Test topic creation"""
    logger.info("=== Testing Topic Creation ===")
    
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    test_topic = "diagnostic.test"
    
    try:
        # Create test topic
        new_topic = NewTopic(test_topic, num_partitions=1, replication_factor=1)
        fs = admin_client.create_topics([new_topic])
        
        for topic, f in fs.items():
            try:
                f.result(timeout=10)
                logger.info(f"✓ Successfully created topic: {topic}")
            except Exception as e:
                if "already exists" in str(e).lower():
                    logger.info(f"✓ Topic {topic} already exists")
                else:
                    logger.error(f"✗ Failed to create topic {topic}: {e}")
                    return False
                    
        # Wait for topic to be available
        time.sleep(2)
        
        # Verify topic exists
        metadata = admin_client.list_topics(timeout=10)
        if test_topic in metadata.topics:
            logger.info(f"✓ Topic {test_topic} is available")
            return True
        else:
            logger.error(f"✗ Topic {test_topic} not found after creation")
            return False
            
    except Exception as e:
        logger.error(f"✗ Topic creation failed: {e}")
        return False

def test_producer(bootstrap_servers):
    """Test message production"""
    logger.info("=== Testing Producer ===")
    
    producer_config = {
        'bootstrap.servers': bootstrap_servers,
        'client.id': 'diagnostic-producer'
    }
    
    try:
        producer = Producer(producer_config)
        test_topic = "diagnostic.test"
        test_message = {"test": "message", "timestamp": time.time()}
        
        def delivery_callback(err, msg):
            if err:
                logger.error(f"✗ Message delivery failed: {err}")
            else:
                logger.info(f"✓ Message delivered to {msg.topic()} [{msg.partition()}] at offset {msg.offset()}")
        
        producer.produce(
            test_topic,
            value=json.dumps(test_message),
            callback=delivery_callback
        )
        
        producer.flush(timeout=10)
        logger.info("✓ Producer test completed")
        return True
        
    except Exception as e:
        logger.error(f"✗ Producer test failed: {e}")
        return False

def test_consumer(bootstrap_servers):
    """Test message consumption"""
    logger.info("=== Testing Consumer ===")
    
    consumer_config = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': 'diagnostic-group',
        'auto.offset.reset': 'earliest'
    }
    
    try:
        consumer = Consumer(consumer_config)
        test_topic = "diagnostic.test"
        consumer.subscribe([test_topic])
        
        logger.info(f"Subscribed to {test_topic}, polling for messages...")
        
        # Poll for messages for 10 seconds
        start_time = time.time()
        message_count = 0
        
        while time.time() - start_time < 10:
            msg = consumer.poll(timeout=1.0)
            
            if msg is None:
                continue
                
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                else:
                    logger.error(f"Consumer error: {msg.error()}")
                    return False
            
            message_count += 1
            logger.info(f"✓ Received message {message_count}: {msg.value().decode('utf-8')}")
        
        consumer.close()
        
        if message_count > 0:
            logger.info(f"✓ Consumer test completed - received {message_count} messages")
            return True
        else:
            logger.warning("⚠ Consumer test completed but no messages received")
            return False
            
    except Exception as e:
        logger.error(f"✗ Consumer test failed: {e}")
        return False

def test_your_topics(bootstrap_servers):
    """Test your specific topics"""
    logger.info("=== Testing Your Application Topics ===")
    
    topics = ['like.events', 'follow.events', 'post.events']
    admin_client = AdminClient({'bootstrap.servers': bootstrap_servers})
    
    try:
        # Check if topics exist
        metadata = admin_client.list_topics(timeout=10)
        existing_topics = list(metadata.topics.keys())
        
        for topic in topics:
            if topic in existing_topics:
                logger.info(f"✓ Topic {topic} exists")
                # Get topic details
                topic_metadata = metadata.topics[topic]
                partitions = len(topic_metadata.partitions)
                logger.info(f"  - Partitions: {partitions}")
            else:
                logger.warning(f"⚠ Topic {topic} not found")
        
        # Try to create missing topics
        missing_topics = [topic for topic in topics if topic not in existing_topics]
        if missing_topics:
            logger.info(f"Creating missing topics: {missing_topics}")
            new_topics = [NewTopic(topic, num_partitions=3, replication_factor=1) for topic in missing_topics]
            fs = admin_client.create_topics(new_topics)
            
            for topic, f in fs.items():
                try:
                    f.result(timeout=10)
                    logger.info(f"✓ Created topic: {topic}")
                except Exception as e:
                    logger.error(f"✗ Failed to create topic {topic}: {e}")
        
        return True
        
    except Exception as e:
        logger.error(f"✗ Failed to test application topics: {e}")
        return False

def main():
    bootstrap_servers = os.environ.get('KAFKA_BROKER', 'drf_scrawl_kafka:9092')
    logger.info(f"Starting Kafka diagnostics for: {bootstrap_servers}")
    
    tests = [
        ("Connection Test", lambda: test_kafka_connection(bootstrap_servers)),
        ("Topic Creation Test", lambda: test_topic_creation(bootstrap_servers)),
        ("Producer Test", lambda: test_producer(bootstrap_servers)),
        ("Consumer Test", lambda: test_consumer(bootstrap_servers)),
        ("Application Topics Test", lambda: test_your_topics(bootstrap_servers))
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n{'='*50}")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            logger.error(f"Test {test_name} crashed: {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info(f"\n{'='*50}")
    logger.info("DIAGNOSTIC SUMMARY")
    logger.info(f"{'='*50}")
    
    for test_name, result in results:
        status = "PASS" if result else "FAIL"
        logger.info(f"{test_name}: {status}")
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    logger.info(f"\nOverall: {passed}/{total} tests passed")
    
    if passed != total:
        logger.error("Some tests failed. Check the logs above for details.")
        return 1
    else:
        logger.info("All tests passed! Your Kafka setup looks good.")
        return 0

if __name__ == "__main__":
    sys.exit(main())
    
    
  