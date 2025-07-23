#!/usr/bin/env python3
"""
Kafka Diagnostic Script for Refactored Scrawl Architecture
Tests the new centralized messaging system with event publishers and consumers.
"""

import os
import sys
import time
import json
import django
from typing import Dict, Any, List

# Django setup
sys.path.append(os.path.abspath('.'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'scrawl.settings')
django.setup()

import logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def test_imports():
    """Test that all refactored imports work correctly."""
    logger.info("=== Testing Refactored Import System ===")
    
    try:
        # Test core messaging imports
        from scrawl.core.messaging import kafka_manager, event_publisher, EventType
        logger.info("✅ Core messaging imports successful")
        
        # Test consumer imports
        from scrawl.core.messaging.consumers.base_consumer import BaseConsumer
        from scrawl.core.messaging.consumers.feed_event_consumer import FeedEventConsumer
        from scrawl.core.messaging.consumers.general_event_consumer import GeneralEventConsumer
        logger.info("✅ Consumer imports successful")
        
        # Test event system imports
        from scrawl.core.messaging.events.event_types import event_registry
        from scrawl.core.messaging.events.event_handlers import event_handler_registry
        logger.info("✅ Event system imports successful")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Import test failed: {e}")
        return False

def test_kafka_connection():
    """Test Kafka connection with new architecture."""
    logger.info("=== Testing Kafka Connection (New Architecture) ===")
    
    try:
        from scrawl.core.messaging import kafka_manager
        
        # Test connection
        is_connected = kafka_manager.is_connected()
        logger.info(f"✅ Kafka connected: {is_connected}")
        
        if is_connected:
            # Get connection info
            info = kafka_manager.get_connection_info()
            logger.info(f"✅ Cluster ID: {info.get('cluster_id', 'N/A')}")
            logger.info(f"✅ Bootstrap servers: {info.get('bootstrap_servers', 'N/A')}")
            
            # List topics
            topics = [t['name'] for t in info.get('topics', [])]
            logger.info(f"✅ Available topics: {topics}")
            
            # Check required topics
            required_topics = ['follow.events', 'post.events', 'like.events', 'comment.events', 'feed_events_dlq']
            missing = set(required_topics) - set(topics)
            if missing:
                logger.warning(f"⚠️ Missing topics: {missing}")
            else:
                logger.info("✅ All required topics present")
        
        return is_connected
        
    except Exception as e:
        logger.error(f"❌ Kafka connection test failed: {e}")
        return False

def test_event_schema_system():
    """Test the new event schema and registry system."""
    logger.info("=== Testing Event Schema System ===")
    
    try:
        from scrawl.core.messaging.events.event_types import EventType, event_registry
        
        # Test event types enumeration
        event_types = event_registry.get_all_event_types()
        logger.info(f"✅ Total event types: {len(event_types)}")
        logger.info(f"   Sample types: {event_types[:5]}")
        
        # Test event creation
        test_event = event_registry.create_event(
            EventType.POST_CREATED,
            post_id=999,
            user_id=1,
            privacy='public'
        )
        logger.info(f"✅ Event creation successful: {test_event.event_type}")
        
        # Test event validation
        valid, error = event_registry.validate_event_data(
            EventType.FOLLOW_CREATED,
            {'follower_id': 1, 'followed_id': 2, 'is_super_follower': False}
        )
        logger.info(f"✅ Event validation: {valid}, error: {error}")
        
        # Test topic mapping
        topic = event_registry.get_topic_for_event(EventType.POST_CREATED)
        logger.info(f"✅ Topic mapping works: {EventType.POST_CREATED} -> {topic}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Event schema test failed: {e}")
        return False

def test_event_publisher():
    """Test the new centralized event publisher."""
    logger.info("=== Testing Event Publisher ===")
    
    try:
        from scrawl.core.messaging import event_publisher
        
        # Test different event types
        test_events = [
            ('post_created', lambda: event_publisher.publish_post_event(
                'post_created', post_id=999, user_id=1, privacy='public'
            )),
            ('follow_created', lambda: event_publisher.publish_follow_event(
                'follow_created', follower_id=1, followed_id=2, is_super_follower=False
            )),
            ('like_created', lambda: event_publisher.publish_like_event(
                'like_created', user_id=1, post_id=999
            )),
            ('comment_created', lambda: event_publisher.publish_comment_event(
                'comment_created', user_id=1, post_id=999, comment_id=1
            ))
        ]
        
        success_count = 0
        for event_name, publisher_func in test_events:
            try:
                success = publisher_func()
                if success:
                    logger.info(f"✅ {event_name} event published successfully")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ {event_name} event publishing returned False")
            except Exception as e:
                logger.error(f"❌ {event_name} event publishing failed: {e}")
        
        # Flush all events
        flushed = event_publisher.flush_all(timeout=10.0)
        logger.info(f"✅ Event flush completed: {flushed}")
        
        logger.info(f"📊 Publisher test summary: {success_count}/{len(test_events)} events successful")
        return success_count == len(test_events)
        
    except Exception as e:
        logger.error(f"❌ Event publisher test failed: {e}")
        return False

def test_event_handlers():
    """Test the event handler registry."""
    logger.info("=== Testing Event Handler Registry ===")
    
    try:
        from scrawl.core.messaging.events.event_handlers import event_handler_registry
        
        # Test different handlers
        test_handlers = [
            ('follow_created', lambda: event_handler_registry.handle_follow_created(1, 2)),
            ('post_created', lambda: event_handler_registry.handle_post_created(1, 999, 'public')),
            ('like_created', lambda: event_handler_registry.handle_like_created(1, 999)),
        ]
        
        success_count = 0
        for handler_name, handler_func in test_handlers:
            try:
                success = handler_func()
                if success:
                    logger.info(f"✅ {handler_name} handler executed successfully")
                    success_count += 1
                else:
                    logger.warning(f"⚠️ {handler_name} handler returned False")
            except Exception as e:
                logger.error(f"❌ {handler_name} handler failed: {e}")
        
        # Get handler statistics
        stats = event_handler_registry.get_handler_stats()
        logger.info(f"📊 Handler stats: {stats.get('total_calls', 0)} calls, {stats.get('total_errors', 0)} errors")
        
        logger.info(f"📊 Handler test summary: {success_count}/{len(test_handlers)} handlers successful")
        return success_count > 0
        
    except Exception as e:
        logger.error(f"❌ Event handler test failed: {e}")
        return False

def test_consumer_classes():
    """Test that consumer classes can be instantiated."""
    logger.info("=== Testing Consumer Classes ===")
    
    try:
        from scrawl.core.messaging.consumers.feed_event_consumer import FeedEventConsumer
        from scrawl.core.messaging.consumers.general_event_consumer import GeneralEventConsumer
        
        # Test feed consumer instantiation
        feed_consumer = FeedEventConsumer()
        logger.info("✅ FeedEventConsumer instantiated successfully")
        logger.info(f"   Topics: {feed_consumer.topics}")
        logger.info(f"   Group ID: {feed_consumer.group_id}")
        
        # Test general consumer instantiation  
        general_consumer = GeneralEventConsumer()
        logger.info("✅ GeneralEventConsumer instantiated successfully")
        logger.info(f"   Topics: {general_consumer.topics}")
        logger.info(f"   Group ID: {general_consumer.group_id}")
        
        # Test health check capability
        if hasattr(feed_consumer, 'perform_health_check'):
            health = feed_consumer.perform_health_check()
            logger.info(f"✅ Health check works: {health.get('status', 'unknown')}")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Consumer class test failed: {e}")
        return False

def test_cache_integration():
    """Test cache integration with new system."""
    logger.info("=== Testing Cache Integration ===")
    
    try:
        from scrawl.core.caching import cache_manager
        
        # Test basic cache operations using existing key patterns
        test_value = {'test': True, 'timestamp': time.time()}
        
        # Use existing key pattern instead of 'test_cache'
        cache_manager.set('user_profile', test_value, user_id=999)
        logger.info("✅ Cache set operation successful")
        
        # Get cache
        cached_value = cache_manager.get('user_profile', user_id=999)
        if cached_value:
            logger.info("✅ Cache get operation successful")
            logger.info(f"   Cached data: {cached_value}")
        else:
            logger.warning("⚠️ Cache get returned None")
        
        # Clean up test data
        cache_manager.delete('user_profile', user_id=999)
        
        return cached_value is not None
        
    except Exception as e:
        logger.error(f"❌ Cache integration test failed: {e}")
        return False

def test_end_to_end_flow():
    """Test complete end-to-end event flow."""
    logger.info("=== Testing End-to-End Event Flow ===")
    
    try:
        from scrawl.core.messaging import event_publisher
        from scrawl.core.messaging.events.event_handlers import event_handler_registry
        
        # Step 1: Publish an event
        logger.info("📤 Step 1: Publishing test event...")
        success = event_publisher.publish_post_event(
            'post_created', 
            post_id=99999, 
            user_id=999, 
            privacy='public',
            created_at=time.strftime('%Y-%m-%dT%H:%M:%S')
        )
        
        if not success:
            logger.error("❌ Event publishing failed")
            return False
        
        logger.info("✅ Event published successfully")
        
        # Step 2: Simulate event processing
        logger.info("⚙️ Step 2: Simulating event handler processing...")
        handler_success = event_handler_registry.handle_post_created(999, 99999, 'public')
        
        if handler_success:
            logger.info("✅ Event handler processed successfully")
        else:
            logger.warning("⚠️ Event handler returned False")
        
        # Step 3: Check handler statistics
        stats = event_handler_registry.get_handler_stats()
        logger.info(f"📊 Handler stats after test: {stats}")
        
        # Flush events to make sure they're sent
        event_publisher.flush_all(timeout=5.0)
        logger.info("✅ Events flushed successfully")
        
        return success and handler_success
        
    except Exception as e:
        logger.error(f"❌ End-to-end test failed: {e}")
        return False

def run_comprehensive_diagnostic():
    """Run all diagnostic tests."""
    logger.info("🚀 Starting Comprehensive Kafka Refactoring Diagnostic")
    logger.info("=" * 60)
    
    tests = [
        ("Import System", test_imports),
        ("Kafka Connection", test_kafka_connection),
        ("Event Schema System", test_event_schema_system),
        ("Event Publisher", test_event_publisher),
        ("Event Handlers", test_event_handlers),
        ("Consumer Classes", test_consumer_classes),
        ("Cache Integration", test_cache_integration),
        ("End-to-End Flow", test_end_to_end_flow),
    ]
    
    results = []
    for test_name, test_func in tests:
        logger.info(f"\n🔍 Running {test_name} test...")
        try:
            result = test_func()
            results.append((test_name, result))
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status}: {test_name}")
        except Exception as e:
            logger.error(f"💥 CRASH: {test_name} - {e}")
            results.append((test_name, False))
    
    # Summary
    logger.info("\n" + "=" * 60)
    logger.info("📋 DIAGNOSTIC SUMMARY")
    logger.info("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        logger.info(f"{status}: {test_name}")
    
    logger.info(f"\n📊 Overall Result: {passed}/{total} tests passed")
    
    if passed == total:
        logger.info("🎉 All tests passed! Your Kafka refactoring is working perfectly!")
        return 0
    else:
        logger.error(f"⚠️ {total - passed} tests failed. Check the logs above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(run_comprehensive_diagnostic())