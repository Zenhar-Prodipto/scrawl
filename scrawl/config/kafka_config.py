import os
from confluent_kafka import Producer

kafka_config = {
    'bootstrap.servers': os.environ.get('KAFKA_BROKER', 'drf_scrawl_kafka:9092'),
    'client.id': 'follows-producer'
}

producer = Producer(kafka_config)

def delivery_report(err, msg):
    if err:
        print(f"Message delivery failed: {err}")
    else:
        print(f"Message delivered to {msg.topic()} [{msg.partition()}]")