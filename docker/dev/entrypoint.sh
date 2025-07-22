#!/bin/sh

set -e

echo "🏗️ Starting Scrawl - DEVELOPMENT Environment"
echo "Environment: ${ENVIRONMENT:-development}"
echo "Debug mode: ${DEBUG:-False}"

# Service connection details
echo "🔍 Development service configuration:"
echo "  DB_HOST: $DB_HOST"
echo "  DB_PORT: $DB_PORT"
echo "  REDIS_URL: $REDIS_URL"
echo "  KAFKA_BROKER: $KAFKA_BROKER"

# Wait for PostgreSQL
echo "⏳ Waiting for PostgreSQL (Dev)..."
while ! nc -z $DB_HOST $DB_PORT; do
  echo "   PostgreSQL is unavailable - sleeping"
  sleep 1
done
echo "✅ PostgreSQL connected!"

# Wait for Redis
echo "⏳ Waiting for Redis (Dev)..."
REDIS_HOST=$(echo $REDIS_URL | sed 's|redis://\(.*\):[0-9]*/[0-9]*|\1|')
REDIS_PORT=$(echo $REDIS_URL | sed 's|redis://[^:]*:\([0-9]*\)/[0-9]*|\1|')
while ! nc -z $REDIS_HOST $REDIS_PORT; do
  echo "   Redis is unavailable - sleeping"
  sleep 1
done
echo "✅ Redis connected!"

# Wait for Kafka
echo "⏳ Waiting for Kafka (Dev)..."
KAFKA_HOST=${KAFKA_BROKER%%:*}
KAFKA_PORT=${KAFKA_BROKER##*:}
while ! nc -z $KAFKA_HOST $KAFKA_PORT; do
  echo "   Kafka is unavailable - sleeping"
  sleep 1
done
echo "✅ Kafka connected!"

# Development-specific setup
if [ "$1" = "python" ] && [ "$2" = "manage.py" ] && [ "$3" = "runserver" ]; then
    echo "🔧 Running Django development setup..."
    
    # Apply migrations
    echo "   Running migrations..."
    python manage.py migrate --noinput
    
    # Create superuser if it doesn't exist (dev convenience)
    echo "   Checking for superuser..."
    python -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print('   Superuser created: admin/admin123')
else:
    print('   Superuser already exists')
" || echo "   Superuser creation skipped"
    
    echo "✅ Development setup completed!"
fi

echo "🎉 Starting development service: $@"

# Execute the command
exec "$@"