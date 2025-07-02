import os
import sys
import time
import django
from confluent_kafka import Consumer, Producer, KafkaError, KafkaException
import json
import logging
from typing import Dict, Any
from django.core.cache import cache
from kafka.errors import KafkaError as KafkaLibError

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrawl.settings')
django.setup()

from feed.services import FeedService

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(), logging.FileHandler('/app/logs/feed_consumer.log') if os.path.exists('/app/logs') else logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

DLQ_TOPIC = "feed_events_dlq"

class FeedEventProcessor:
    @staticmethod
    def process_post_event(event: Dict[str, Any]) -> bool:
        try:
            user_id = event.get('user_id')
            post_id = event.get('post_id')
            if not all([user_id, post_id]):
                logger.warning(f"Missing fields in post event: {event}")
                return False
            if event.get('event_type') == 'post.created':
                FeedService.invalidate_follower_feeds(user_id)
                logger.info(f"Invalidated follower feeds for new post {post_id} by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing post event {event}: {e}")
            return False

    @staticmethod
    def process_like_event(event: Dict[str, Any]) -> bool:
        try:
            user_id = event.get('user_id')
            post_id = event.get('post_id')
            if not all([user_id, post_id]):
                logger.warning(f"Missing fields in like event: {event}")
                return False
            if event.get('event_type') == 'like.created':
                FeedService.invalidate_user_feed(user_id)
                logger.info(f"Invalidated feed for user {user_id} after liking post {post_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing like event {event}: {e}")
            return False

    @staticmethod
    def process_follow_event(event: Dict[str, Any]) -> bool:
        try:
            follower_id = event.get('follower_id')
            followed_id = event.get('followed_id')
            if not all([follower_id, followed_id]):
                logger.warning(f"Missing fields in follow event: {event}")
                return False
            if event.get('event_type') == 'follow.created':
                FeedService.invalidate_user_feed(follower_id)
                logger.info(f"Invalidated feed for user {follower_id} after following {followed_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing follow event {event}: {e}")
            return False

    @staticmethod
    def process_post_updated_event(event: Dict[str, Any]) -> bool:
        try:
            user_id = event.get('user_id')
            if not user_id:
                logger.warning(f"Missing user_id in post.updated event: {event}")
                return False
            FeedService.invalidate_follower_feeds(user_id)
            logger.info(f"Invalidated follower feeds for updated post by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing post.updated event {event}: {e}")
            return False

    @staticmethod
    def process_post_deleted_event(event: Dict[str, Any]) -> bool:
        try:
            user_id = event.get('user_id')
            post_id = event.get('post_id')
            if not all([user_id, post_id]):
                logger.warning(f"Missing fields in post.deleted event: {event}")
                return False
            FeedService.invalidate_follower_feeds(user_id)
            logger.info(f"Invalidated feeds for deleted post {post_id} by user {user_id}")
            return True
        except Exception as e:
            logger.error(f"Error processing post.deleted event {event}: {e}")
            return False

    @staticmethod
    def process_follow_deleted_event(event: Dict[str, Any]) -> bool:
        try:
            follower_id = event.get('follower_id')
            if not follower_id:
                logger.warning(f"Missing follower_id in follow.deleted event: {event}")
                return False
            FeedService.invalidate_user_feed(follower_id)
            logger.info(f"Invalidated feed for user {follower_id} after unfollowing")
            return True
        except Exception as e:
            logger.error(f"Error processing follow.deleted event {event}: {e}")
            return False

def wait_for_kafka(bootstrap_servers: str, timeout: int = 60) -> bool:
    logger.info(f"Waiting for Kafka at {bootstrap_servers}")
    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            test_config = {'bootstrap.servers': bootstrap_servers, 'group.id': 'test-group', 'auto.offset.reset': 'latest'}
            consumer = Consumer(test_config)
            metadata = consumer.list_topics(timeout=5)
            consumer.close()
            if all(t in metadata.topics for t in ['post.events', 'like.events', 'follow.events']):
                return True
        except Exception as e:
            logger.warning(f"Kafka not ready yet: {e}")
        time.sleep(2)
    logger.error(f"Kafka not ready after {timeout} seconds")
    return False

def send_to_dlq(producer, msg):
    try:
        producer.produce(DLQ_TOPIC, value=msg.value())
        producer.flush()
        logger.info(f"Message sent to DLQ: {msg.offset()}")
    except Exception as e:
        logger.error(f"Failed to send to DLQ: {e}")

def start_feed_consumer():
    bootstrap_servers = os.environ.get('KAFKA_BROKER', 'drf_scrawl_kafka:9092')
    if not wait_for_kafka(bootstrap_servers):
        logger.error("Kafka not ready, exiting")
        return

    kafka_config = {
        'bootstrap.servers': bootstrap_servers,
        'group.id': 'feed-consumer-group',
        'auto.offset.reset': 'latest',
        'enable.auto.commit': True,
        'auto.commit.interval.ms': 5000,
        'session.timeout.ms': 10000,
        'heartbeat.interval.ms': 3000,
        'max.poll.interval.ms': 300000,
        'fetch.min.bytes': 1,
        'fetch.wait.max.ms': 500
    }

    consumer = Consumer(kafka_config)
    producer = Producer({'bootstrap.servers': bootstrap_servers})
    topics = ['post.events', 'like.events', 'follow.events']
    
    event_processors = {
        'post.created': FeedEventProcessor.process_post_event,
        'post.updated': FeedEventProcessor.process_post_updated_event,
        'post.deleted': FeedEventProcessor.process_post_deleted_event,
        'like.created': FeedEventProcessor.process_like_event,
        'follow.created': FeedEventProcessor.process_follow_event,
        'follow.deleted': FeedEventProcessor.process_follow_deleted_event
    }

    try:
        consumer.subscribe(topics)
        logger.info(f"Subscribing to topics: {topics}")
        message_count = 0
        last_log_time = time.time()

        while True:
            msg = consumer.poll(timeout=1.0)
            if msg is None:
                if time.time() - last_log_time > 30:
                    logger.info(f"Consumer alive, processed {message_count} messages")
                    last_log_time = time.time()
                continue
            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    logger.debug(f"End of partition reached {msg.topic()} [{msg.partition()}]")
                    continue
                logger.error(f"Consumer error: {msg.error()}")
                continue

            try:
                event = json.loads(msg.value().decode('utf-8'))
                event_type = event.get('event_type')
                processor = event_processors.get(event_type)
                if processor and processor(event):
                    message_count += 1
                    logger.debug(f"Processed {event_type} event: {event}")
                else:
                    logger.warning(f"Unprocessable event or no processor: {event}")
                    send_to_dlq(producer, msg)
            except json.JSONDecodeError as e:
                logger.error(f"JSON decode error: {e}, raw: {msg.value()}")
                send_to_dlq(producer, msg)
            except Exception as e:
                logger.error(f"Processing error: {e}")
                send_to_dlq(producer, msg)

    except KeyboardInterrupt:
        logger.info("Consumer interrupted by user")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
    finally:
        consumer.close()
        producer.close()

if __name__ == "__main__":
    start_feed_consumer()