#!/bin/sh

# Print the environment variables to verify if they are being set properly
echo "DB_HOST: $DB_HOST"
echo "DB_PORT: $DB_PORT"
echo "REDIS_URL: $REDIS_URL"

echo "Waiting for PostgreSQL to start..."

# Wait until PostgreSQL is ready
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

# Run migrations
python manage.py migrate

# Start the server
exec python manage.py runserver 0.0.0.0:8000