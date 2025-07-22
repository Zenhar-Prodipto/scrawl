#!/bin/sh

set -e

echo "🚀 Starting Scrawl application..."
echo "Environment: ${ENVIRONMENT:-local}"

# Service connection details
echo "🔍 Checking services:"
echo "  DB_HOST: $DB_HOST"
echo "  DB_PORT: $DB_PORT" 
echo "  REDIS_URL: $REDIS_URL"
echo "  KAFKA_BROKER: $KAFKA_BROKER"

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL..."
while ! nc -z $DB_HOST $DB_PORT; do
  echo "   PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "✅ PostgreSQL started!"

# Wait for Redis
echo "⏳ Waiting for Redis..."
REDIS_HOST=$(echo $REDIS_URL | sed 's|redis://\(.*\):[0-9]*/[0-9]*|\1|')
REDIS_PORT=$(echo $REDIS_URL | sed 's|redis://[^:]*:\([0-9]*\)/[0-9]*|\1|')
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  echo "   Redis is unavailable - sleeping"
  sleep 1
done
echo "✅ Redis started!"

# Wait for Kafka
echo "⏳ Waiting for Kafka..."
KAFKA_HOST=${KAFKA_BROKER%%:*}
KAFKA_PORT=${KAFKA_BROKER##*:}
while ! nc -z $KAFKA_HOST $KAFKA_PORT; do
  echo "   Kafka is unavailable - sleeping"
  sleep 1
done
echo "✅ Kafka started!"

# Run Django commands if this is the web service
if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
    echo "🔧 Running Django setup..."
    
    # Apply migrations
    echo "   Running migrations..."
    python manage.py migrate --noinput
    
    echo "✅ Django setup completed!"
fi

echo "�� Starting: $@"

# Execute the command
exec "$@"
