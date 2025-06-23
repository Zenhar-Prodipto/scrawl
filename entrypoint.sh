#!/bin/sh

echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"
echo "REDIS_URL: $REDIS_URL"
echo "KAFKA_BROKER: $KAFKA_BROKER"

echo "Waiting for PostgreSQL to start..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "PostgreSQL started!"

# Wait until Redis is ready (parse REDIS_URL for host and port)
REDIS_HOST=$(echo $REDIS_URL | sed 's|redis://\(.*\):[0-9]*/[0-9]*|\1|')
REDIS_PORT=$(echo $REDIS_URL | sed 's|redis://[^:]*:\([0-9]*\)/[0-9]*|\1|')
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 1
done

echo "Redis started!"

echo "Waiting for Kafka to start..."
# Use KAFKA_BROKER from .env, fallback to service name
KAFKA_HOST=${KAFKA_BROKER%%:*}  # Extracts 'drf_scrawl_kafka' from 'drf_scrawl_kafka:9092'
KAFKA_PORT=${KAFKA_BROKER##*:}  # Extracts '9092' from 'drf_scrawl_kafka:9092'
while ! nc -z $KAFKA_HOST $KAFKA_PORT; do
  sleep 1
done
echo "Kafka started!"

# Execute the command passed to the container
exec "$@"