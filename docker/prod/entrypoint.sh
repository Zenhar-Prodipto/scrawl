#!/bin/sh

set -e

echo "🚀 Starting Scrawl - PRODUCTION Environment"
echo "Environment: ${ENVIRONMENT:-production}"

# Production service connection details (minimal logging for security)
echo "🔍 Checking production services..."

# Wait for PostgreSQL (production)
echo "⏳ Waiting for database..."
while ! nc -z $DB_HOST $DB_PORT; do
  sleep 1
done
echo "✅ Database connected"

# Wait for Redis (production)
echo "⏳ Waiting for cache..."
REDIS_HOST=$(echo $REDIS_URL | sed 's|redis://\(.*\):[0-9]*/[0-9]*|\1|')
REDIS_PORT=$(echo $REDIS_URL | sed 's|redis://[^:]*:\([0-9]*\)/[0-9]*|\1|')
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  sleep 1
done
echo "✅ Cache connected"

# Wait for Kafka (production)
echo "⏳ Waiting for message queue..."
KAFKA_HOST=${KAFKA_BROKER%%:*}
KAFKA_PORT=${KAFKA_BROKER##*:}
while ! nc -z $KAFKA_HOST $KAFKA_PORT; do
  sleep 1
done
echo "✅ Message queue connected"

# Production-specific setup
if [ "$1" = "gunicorn" ] || ([ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]); then
    echo "🔧 Production application setup..."
    
    # Apply migrations (production)
    echo "   Applying database migrations..."
    python manage.py migrate --noinput
    
    # Collect static files (production)
    echo "   Collecting static files..."
    python manage.py collectstatic --noinput --clear
    
    # Validate deployment
    echo "   Validating deployment..."
    python manage.py check --deploy --fail-level WARNING
    
    echo "✅ Production setup completed"
fi

echo "🎉 Starting production service"

# Execute the command
exec "$@"